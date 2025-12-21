"""Memory operations business logic.

Provides high-level functions for memory operations via OpenOCD.
Commands should use these functions instead of calling ocd.send() directly.
"""

import os
import re
from typing import Any

from .ocd_provider import OCDProtocol


def read_words(ocd: OCDProtocol, addr: int, count: int) -> str:
    """Read memory words (32-bit) from address.

    Args:
        ocd: OpenOCD instance
        addr: Start address
        count: Number of 32-bit words to read

    Returns:
        Raw OpenOCD mdw output string
    """
    return ocd.send(f"mdw 0x{addr:08x} {count}")


def read_vectors(ocd: OCDProtocol, addr: int = 0x08000000) -> dict[str, Any]:
    """Read ARM Cortex-M vector table.

    Args:
        ocd: OpenOCD instance
        addr: Vector table address (default: 0x08000000)

    Returns:
        Dict with vector names and values, plus raw output
    """
    result = ocd.send(f"mdw 0x{addr:08x} 8")

    vectors = {
        "raw": result,
        "initial_sp": None,
        "reset": None,
        "nmi": None,
        "hardfault": None,
        "memmanage": None,
        "busfault": None,
        "usagefault": None,
        "reserved": None,
    }

    # Parse: "0x08000000: 2004fff8 08050e59 08046dfb ..."
    match = re.search(r":\s*(.+)", result)
    if match:
        words = match.group(1).split()
        names = list(vectors.keys())[1:]  # Skip 'raw'
        for name, word in zip(names, words[:8]):
            try:
                vectors[name] = int(word, 16)
            except ValueError:
                pass

    return vectors


def dump_to_file(
    ocd: OCDProtocol,
    filepath: str,
    addr: int,
    size: int,
    timeout: float = 60.0,
) -> bool:
    """Dump memory region to binary file.

    Args:
        ocd: OpenOCD instance
        filepath: Output file path
        addr: Start address
        size: Number of bytes to dump
        timeout: Command timeout in seconds

    Returns:
        True if file was created successfully
    """
    filepath = os.path.abspath(filepath)
    ocd.send(f"dump_image {filepath} 0x{addr:08x} {size}", timeout=timeout)
    return os.path.exists(filepath)
