"""REPL communication backend."""

import time
from contextlib import contextmanager

import serial as pyserial

from . import BAUD_RATE


@contextmanager
def mpremote_transport(dev: str, baud: int = BAUD_RATE, soft_reset: bool = True):
    """Context manager for mpremote SerialTransport."""
    from mpremote.transport_serial import SerialTransport
    transport = SerialTransport(dev, baud)
    transport.enter_raw_repl(soft_reset=soft_reset)
    try:
        yield transport
    finally:
        transport.exit_raw_repl()
        transport.close()


def filter_repl_output(text: str, code: str) -> str:
    """Filter REPL output to extract just the result.

    Removes:
      - Command echo (the code we sent)
      - REPL prompts (>>>, ...)
      - Empty lines
      - Carriage returns
    """
    lines = text.split("\n")
    output_lines = []
    for line in lines:
        line = line.rstrip("\r")
        # Skip command echo
        if line.strip() == code.strip():
            continue
        # Skip empty prompts
        if line.strip() in (">>>", "...", ""):
            continue
        # Remove leading >>> if present
        if line.startswith(">>> "):
            line = line[4:]
        elif line.startswith("... "):
            line = line[4:]
        output_lines.append(line)

    return "\n".join(output_lines).strip()


def exec_raw(dev: str, code: str, baud: int = BAUD_RATE, timeout: float = 5.0) -> str:
    """Execute multi-line Python via mpremote raw REPL.

    Unlike exec_code() which uses the friendly REPL (single-line only),
    this uses mpremote's raw REPL protocol to send multi-line scripts.
    """
    with mpremote_transport(dev, baud, soft_reset=False) as transport:
        transport.exec_raw_no_follow(code)
        stdout, stderr = transport.follow(timeout=timeout)
        stdout = stdout.decode("utf-8", errors="replace") if isinstance(stdout, bytes) else stdout
        stderr = stderr.decode("utf-8", errors="replace") if isinstance(stderr, bytes) else stderr
        if stderr:
            raise RuntimeError(f"MicroPython error:\n{stderr}")
        return stdout.strip()


def exec_code(dev: str, code: str, baud: int = BAUD_RATE, timeout: float = 3.0) -> str:
    """Execute Python code on REPL and return output."""
    with pyserial.Serial(dev, baud, timeout=timeout) as ser:
        # Interrupt any running code
        ser.write(b"\x03")
        time.sleep(0.1)
        # Clear buffer
        ser.read(4096)

        # Send code
        ser.write(code.encode() + b"\r\n")
        time.sleep(0.5)

        # Read response
        data = ser.read(8192)
        text = data.decode("utf-8", errors="replace")

        return filter_repl_output(text, code)


def soft_reset(dev: str, baud: int = BAUD_RATE, timeout: float = 3.0) -> str:
    """Send soft reset (Ctrl-D) and return output."""
    with pyserial.Serial(dev, baud, timeout=timeout) as ser:
        ser.write(b"\x03")  # Ctrl-C first
        time.sleep(0.1)
        ser.write(b"\x04")  # Ctrl-D
        time.sleep(1)
        data = ser.read(4096)
        return data.decode("utf-8", errors="replace")
