"""CPU control business logic.

Provides high-level functions for CPU operations via OpenOCD.
Commands should use these functions instead of calling ocd.send() directly.
"""

import re
from contextlib import contextmanager
from typing import Generator

from .ocd_provider import OCDProtocol


@contextmanager
def halted(ocd: OCDProtocol) -> Generator[None, None, None]:
    """Context manager for safe halt/resume.

    Halts CPU, yields control, then resumes even if exception occurs.

    Usage:
        with cpu.halted(ocd):
            # CPU is halted here
            data = memory.read_words(ocd, 0x08000000, 8)
        # CPU is resumed here
    """
    ocd.send("halt")
    try:
        yield
    finally:
        ocd.send("resume")


def halt(ocd: OCDProtocol) -> str:
    """Halt the CPU."""
    return ocd.send("halt")


def resume(ocd: OCDProtocol) -> str:
    """Resume CPU execution."""
    return ocd.send("resume")


def reset_halt(ocd: OCDProtocol) -> str:
    """Reset CPU and halt at reset vector."""
    return ocd.send("reset halt")


def reset_run(ocd: OCDProtocol) -> str:
    """Reset CPU and let it run."""
    return ocd.send("reset run")


def step(ocd: OCDProtocol) -> str:
    """Single-step the CPU."""
    return ocd.send("step")


def read_regs(ocd: OCDProtocol) -> str:
    """Read all CPU registers."""
    return ocd.send("reg")


def read_reg(ocd: OCDProtocol, name: str) -> str:
    """Read a specific register (pc, sp, lr, etc)."""
    return ocd.send(f"reg {name}")


def read_pc(ocd: OCDProtocol) -> int | None:
    """Read program counter value.

    Returns PC as integer or None if parse fails.
    """
    result = ocd.send("reg pc")
    match = re.search(r"0x([0-9a-fA-F]+)", result)
    if match:
        return int(match.group(1), 16)
    return None


def read_sp(ocd: OCDProtocol) -> int | None:
    """Read stack pointer value.

    Returns SP as integer or None if parse fails.
    """
    result = ocd.send("reg sp")
    match = re.search(r"0x([0-9a-fA-F]+)", result)
    if match:
        return int(match.group(1), 16)
    return None


def read_pc_sp(ocd: OCDProtocol) -> str:
    """Read PC and SP registers together."""
    return ocd.send("reg pc sp")
