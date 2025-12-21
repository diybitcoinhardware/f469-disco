"""Memory inspection commands."""

import os
import re

import click

from ..ocd_provider import get_ocd
from .. import cpu as cpu_backend
from .. import memory


@click.group()
def mem():
    """Memory inspection commands.

    Read memory from the STM32F469 via JTAG/OpenOCD. The CPU is halted
    during memory reads to ensure consistent data.

    \b
    STM32F469 Memory Map:
      0x08000000  Flash (2MB) - Bootloader starts here
      0x08020000  Firmware area (when using USE_DBOOT bootloader)
      0x20000000  SRAM (320KB)
      0x40000000  Peripherals
      0xE0000000  Cortex-M4 internal (SysTick, NVIC, etc.)

    \b
    Vector Table Format (first 8 words):
      [0] Initial SP      - Stack pointer after reset
      [1] Reset handler   - Entry point after reset
      [2] NMI handler     - Non-maskable interrupt
      [3] HardFault       - All fault types if not configured
      [4] MemManage       - Memory protection fault
      [5] BusFault        - Bus error
      [6] UsageFault      - Undefined instruction, etc.
      [7] Reserved

    \b
    Examples:
      disco mem read 0x20000000 16    # Read 16 words from SRAM
      disco mem vectors               # Show bootloader vectors
      disco mem vectors --fw          # Show firmware vectors
    """
    pass


@mem.command("read")
@click.argument("addr", default="0x08000000")
@click.argument("count", default=8, type=int)
def mem_read(addr: str, count: int):
    """Read memory words from address."""
    get_ocd().require_running()

    # Parse address
    if addr.startswith("0x"):
        addr_int = int(addr, 16)
    else:
        addr_int = int(addr)

    click.secho(f"=== Memory @ 0x{addr_int:08x} ({count} words) ===", fg="blue")
    with cpu_backend.halted(get_ocd()):
        click.echo(memory.read_words(get_ocd(), addr_int, count))


@mem.command("vectors")
@click.option("--fw", is_flag=True, help="Show firmware vectors at 0x08020000 instead")
def mem_vectors(fw: bool):
    """Show vector table (bootloader or firmware)."""
    get_ocd().require_running()
    with cpu_backend.halted(get_ocd()):
        if fw:
            click.secho("=== Vector Table @ 0x08020000 (Firmware) ===", fg="blue")
            click.echo(memory.read_words(get_ocd(), 0x08020000, 8))
        else:
            click.secho("=== Vector Table @ 0x08000000 (Bootloader) ===", fg="blue")
            vectors = memory.read_vectors(get_ocd(), 0x08000000)
            click.echo(vectors["raw"])
            click.echo()

            labels = [
                "Initial SP", "Reset", "NMI", "HardFault",
                "MemManage", "BusFault", "UsageFault", "Reserved",
            ]
            keys = [
                "initial_sp", "reset", "nmi", "hardfault",
                "memmanage", "busfault", "usagefault", "reserved",
            ]
            for label, key in zip(labels, keys):
                val = vectors.get(key)
                if val is not None:
                    click.echo(f"  {label}: 0x{val:08x}")


@mem.command("dump")
@click.argument("count", default=32, type=int)
def mem_dump(count: int):
    """Dump first N words from flash (default 32)."""
    get_ocd().require_running()
    click.secho(f"=== Flash @ 0x08000000 ({count} words) ===", fg="blue")
    with cpu_backend.halted(get_ocd()):
        click.echo(memory.read_words(get_ocd(), 0x08000000, count))


@mem.command("save")
@click.argument("file", type=click.Path())
@click.argument("addr")
@click.argument("size")
def mem_save(file: str, addr: str, size: str):
    """Save memory region to binary file.

    \b
    Arguments:
      FILE  Output filename
      ADDR  Start address (hex, e.g., 0x08000000)
      SIZE  Number of bytes (hex or decimal, e.g., 0x20000 or 131072)

    \b
    Examples:
      disco mem save flash.bin 0x08000000 0x200000    # Dump all flash (2MB)
      disco mem save firmware.bin 0x08020000 0x100000 # Dump firmware area
      disco mem save ram.bin 0x20000000 0x50000       # Dump SRAM
    """
    get_ocd().require_running()

    # Parse address
    if addr.startswith("0x"):
        addr_int = int(addr, 16)
    else:
        addr_int = int(addr)

    # Parse size (support hex or decimal)
    if size.startswith("0x"):
        byte_count = int(size, 16)
    else:
        byte_count = int(size)

    file = os.path.abspath(file)
    click.secho(f"=== Saving Memory to File ===", fg="blue")
    click.echo(f"Address: 0x{addr_int:08x}")
    click.echo(f"Size: {byte_count:,} bytes ({byte_count // 1024} KB)")
    click.echo(f"File: {file}")

    with cpu_backend.halted(get_ocd()):
        # Use memory module for dump
        success = memory.dump_to_file(get_ocd(), file, addr_int, byte_count, timeout=60)

        if success and os.path.exists(file):
            actual_size = os.path.getsize(file)
            click.secho(f"Saved {actual_size:,} bytes to {file}", fg="green")
        else:
            click.secho("Failed to create file", fg="red")
