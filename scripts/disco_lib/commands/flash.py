"""Flash programming commands."""

import os
import re
import tempfile

import click

from ..ocd_provider import get_ocd
from .. import flash as flash_backend
from .. import cpu as cpu_backend
from .flash_fingerprint import fingerprint


@click.group()
def flash():
    """Flash programming commands.

    Program and erase the STM32F469 internal flash via JTAG/OpenOCD.
    The flash is 2MB organized as dual-bank with mixed sector sizes.

    \b
    Flash Layout (STM32F469, 2MB dual-bank):
      Bank 1 (0x08000000 - 0x080FFFFF):
        Sectors 0-3:   16KB each  (0x08000000 - 0x0800FFFF)
        Sector 4:      64KB       (0x08010000 - 0x0801FFFF)
        Sectors 5-11: 128KB each  (0x08020000 - 0x080FFFFF)

      Bank 2 (0x08100000 - 0x081FFFFF):
        Same layout as Bank 1

    \b
    Filesystem Preservation:
      MicroPython firmware files typically have zeros between code regions
      to preserve the internal filesystem during updates. Zero regions
      won't overwrite existing flash data when programmed.
      Use 'disco flash analyze <file>' to see the firmware layout.

    \b
    Programming Addresses:
      0x08000000  Full image (bootloader + firmware, preserves filesystem)
      0x08020000  Main firmware only (default for 'program' command)

    \b
    Examples:
      disco flash analyze firmware.bin             # Show firmware layout
      disco flash program firmware.bin             # Flash to 0x08020000
      disco flash program full.bin --addr 0x08000000
      disco flash erase                            # Requires confirmation

    \b
    Safety:
      - 'program' verifies after writing by default (--no-verify to skip)
      - 'program' resets the board after flashing (--no-reset to skip)
      - 'erase' requires explicit confirmation
    """
    pass


@flash.command("info")
def flash_info():
    """Show flash bank info."""
    with get_ocd().ensure_running():
        click.secho("=== Flash Bank Info ===", fg="blue")
        click.echo(flash_backend.read_info(get_ocd()))


@flash.command("identify")
@click.argument("file", type=click.Path(exists=True), required=False)
def flash_identify(file: str):
    """Identify firmware build type (debug vs production).

    Searches for version tag in firmware. Can check a file or read from flash.

    \b
    Version tags:
      0100900099 = production build (USB disabled at boot)
      0100900001 = debug build (USB enabled by default)

    \b
    Examples:
      disco flash identify                    # Check currently flashed firmware
      disco flash identify firmware.bin       # Check a firmware file
    """
    version_pattern = rb'<version:tag10>([^<]*)</version:tag10>'

    if file:
        filepath = os.path.abspath(file)
        click.secho("=== Identifying Firmware ===", fg="blue")
        click.echo(f"File: {filepath}")

        with open(filepath, "rb") as f:
            data = f.read()
    else:
        with get_ocd().ensure_running():
            click.secho("=== Identifying Flashed Firmware ===", fg="blue")
            click.echo("Reading from flash...")

            with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as tmp:
                tmp_path = tmp.name

            with cpu_backend.halted(get_ocd()):
                flash_backend.dump_image(get_ocd(), tmp_path, 0x08000000, 0x180000, timeout=60)

                with open(tmp_path, "rb") as f:
                    data = f.read()
                os.unlink(tmp_path)

    match = re.search(version_pattern, data)
    click.echo()

    if match:
        version = match.group(1).decode("utf-8", errors="replace")
        click.echo(f"Version tag: {version}")

        if version == "0100900099":
            click.secho("Build type: PRODUCTION", fg="yellow")
            click.echo("  - USB/REPL disabled at boot")
            click.echo("  - Enabled after PIN entry")
        elif version == "0100900001":
            click.secho("Build type: DEBUG", fg="green")
            click.echo("  - USB/REPL enabled by default")
            click.echo("  - Runs hardwaretest.py")
        else:
            click.secho("Build type: UNKNOWN", fg="cyan")
            click.echo(f"  - Version: {version}")
    else:
        click.secho("No version tag found", fg="red")


@flash.command("analyze")
@click.argument("file", type=click.Path(exists=True))
def flash_analyze(file: str):
    """Analyze firmware file layout.

    Shows code regions vs zero-padded areas. Useful for understanding
    what will be written to flash and whether filesystem is preserved.

    \b
    Examples:
      disco flash analyze firmware.bin
      disco flash analyze upy-f469disco.bin
    """
    file = os.path.abspath(file)
    size = os.path.getsize(file)

    click.secho("=== Firmware Analysis ===", fg="blue")
    click.echo(f"File: {file}")
    click.echo(f"Size: {size:,} bytes ({size/1024:.1f} KB)")
    click.echo()

    regions = flash_backend.analyze_firmware(file)
    internal_zeros = flash_backend.has_internal_zeros(regions)

    code_bytes = flash_backend.calculate_code_bytes(regions)
    zero_bytes = sum(end - start for start, end, has_data in regions if not has_data)

    click.secho("Regions:", fg="cyan")
    code_seen = False
    for start, end, has_data in regions:
        region_size = end - start
        if has_data:
            code_seen = True
            click.echo(f"  0x{start:08x} - 0x{end:08x}: {region_size:>8,} bytes  [CODE]")
        else:
            idx = regions.index((start, end, has_data))
            more_code_after = any(hd for _, _, hd in regions[idx + 1:])
            if code_seen and more_code_after:
                click.secho(
                    f"  0x{start:08x} - 0x{end:08x}: {region_size:>8,} bytes  [ZEROS - preserved area]",
                    fg="yellow"
                )
            else:
                click.echo(f"  0x{start:08x} - 0x{end:08x}: {region_size:>8,} bytes  [ZEROS]")

    click.echo()
    click.echo(f"Code:  {code_bytes:,} bytes ({code_bytes/1024:.1f} KB)")
    click.echo(f"Zeros: {zero_bytes:,} bytes ({zero_bytes/1024:.1f} KB)")

    if internal_zeros:
        click.echo()
        click.secho("Warning: Data preservation detected:", fg="yellow")
        click.echo("  This firmware has zeros between code regions.")
        click.echo("  Existing flash data in zero regions will NOT be overwritten.")
        click.echo("  (Typically used to preserve filesystem during updates)")
        click.echo()
        click.echo("  OpenOCD verify will report 'mismatch' for these regions.")
        click.echo("  Use 'disco flash verify --smart' after programming.")


@flash.command("read")
@click.argument("file", type=click.Path())
@click.option("--addr", default="0x08000000", help="Start address (default: 0x08000000)")
@click.option("--size", default="0x200000", help="Size in bytes (default: 0x200000 = 2MB)")
def flash_read(file: str, addr: str, size: str):
    """Read flash contents to file.

    \b
    Examples:
      disco flash read backup.bin                        # Full 2MB flash
      disco flash read firmware.bin --addr 0x08020000 --size 0x100000
    """
    file = os.path.abspath(file)

    # Parse address
    if addr.startswith("0x"):
        addr_int = int(addr, 16)
    else:
        addr_int = int(addr)

    if size.startswith("0x"):
        byte_count = int(size, 16)
    else:
        byte_count = int(size)

    timeout = max(60, int(byte_count / (50 * 1024)) + 30)

    click.secho("=== Reading Flash ===", fg="blue")
    click.echo(f"Address: 0x{addr_int:08x}")
    click.echo(f"Size: {byte_count:,} bytes ({byte_count/1024:.1f} KB)")
    click.echo(f"File: {file}")
    click.echo(f"Timeout: {timeout}s")
    click.echo()

    with get_ocd().ensure_running():
        with cpu_backend.halted(get_ocd()):
            click.secho("Reading flash (this may take a while)...", fg="yellow")
            result = flash_backend.dump_image(get_ocd(), file, addr_int, byte_count, timeout=timeout)

            if result:
                click.echo(result)

            if os.path.exists(file):
                actual_size = os.path.getsize(file)
                if actual_size == byte_count:
                    click.secho(f"Read {actual_size:,} bytes to {file}", fg="green")
                else:
                    click.secho(f"Warning: Read {actual_size:,} bytes (expected {byte_count:,})", fg="yellow")
            else:
                click.secho("Failed to create output file", fg="red")


@flash.command("verify")
@click.argument("file", type=click.Path(exists=True))
@click.option("--addr", default="0x08020000", help="Flash address (default: 0x08020000)")
@click.option("--smart/--full", default=True, help="Smart verify skips internal zeros (default: smart)")
def flash_verify(file: str, addr: str, smart: bool):
    """Verify flash contents against file.

    By default uses smart verification that skips zero-padded regions
    between code sections. Use --full for strict byte-by-byte verification.

    \b
    Examples:
      disco flash verify firmware.bin
      disco flash verify firmware.bin --full    # Strict verify
      disco flash verify bootloader.bin --addr 0x08000000
    """
    file = os.path.abspath(file)
    size = os.path.getsize(file)

    # Parse address
    if addr.startswith("0x"):
        addr_int = int(addr, 16)
    else:
        addr_int = int(addr)

    regions = flash_backend.analyze_firmware(file)
    internal_zeros = flash_backend.has_internal_zeros(regions)

    click.secho("=== Verifying Flash ===", fg="blue")
    click.echo(f"File: {file}")
    click.echo(f"Size: {size:,} bytes ({size/1024:.1f} KB)")
    click.echo(f"Address: 0x{addr_int:08x}")
    click.echo(f"Mode: {'smart (code regions only)' if smart else 'full (strict)'}")

    if internal_zeros and smart:
        click.secho("Note: File has zeros between code - will verify code regions only", fg="yellow")
    click.echo()

    with get_ocd().ensure_running():
        # Use business layer verify_firmware which handles halt/resume internally
        success = flash_backend.verify_firmware(get_ocd(), file, addr_int, smart)

    if success:
        click.secho("Verification PASSED!", fg="green")
    else:
        click.secho("Verification FAILED!", fg="red")
        if internal_zeros and not smart:
            click.echo()
            click.secho("Hint: File has zeros between code regions.", fg="yellow")
            click.echo("Use 'disco flash verify --smart' to skip these areas.")


@flash.command("erase")
def flash_erase():
    """Mass erase flash (DANGEROUS)."""
    click.secho("WARNING: This will erase all flash memory!", fg="red")
    if not click.confirm("Type 'y' to confirm"):
        click.echo("Aborted")
        return

    with get_ocd().ensure_running():
        with cpu_backend.halted(get_ocd()):
            click.echo(flash_backend.erase_all(get_ocd()))
            click.secho("Flash erased", fg="green")


@flash.command("rdp")
def flash_rdp():
    """Show current read protection (RDP) level.

    \b
    RDP Levels:
      0 = No protection (default)
      1 = Flash protected, debug restricted (recoverable via mass erase)
      2 = PERMANENT - debug disabled forever (device bricked for debugging)
    """
    with get_ocd().ensure_running():
        click.secho("=== Read Protection Status ===", fg="blue")
        output = flash_backend.read_option_bytes(get_ocd())
        level = flash_backend.parse_rdp_level(output)

    if level is None:
        click.echo(f"Raw output: {output}")
        click.secho("Could not parse RDP level", fg="red")
        return

    if level == 0:
        click.secho("RDP Level 0 - No protection", fg="green")
        click.echo("  Flash readable via debug interface")
    elif level == 1:
        click.secho("RDP Level 1 - Protected", fg="yellow")
        click.echo("  Flash protected from debug read")
        click.echo("  Use 'disco flash unlock' to remove (causes mass erase)")
    elif level == 2:
        click.secho("RDP Level 2 - PERMANENTLY LOCKED", fg="red")
        click.echo("  Debug interface permanently disabled")
        click.echo("  CANNOT be unlocked - device is bricked for debugging")


@flash.command("unlock")
def flash_unlock():
    """Remove flash read protection (RDP Level 1 -> 0).

    WARNING: This causes a MASS ERASE of all flash memory!

    Use this to recover a device with RDP Level 1 enabled.
    After unlocking, you must power cycle the board.

    \b
    RDP Level 2 cannot be unlocked - it is permanent.
    """
    with get_ocd().ensure_running():
        click.secho("=== Flash Unlock (Remove RDP) ===", fg="blue")

        # Check current RDP level
        output = flash_backend.read_option_bytes(get_ocd())
        level = flash_backend.parse_rdp_level(output)

        if level is None:
            click.echo(f"Raw output: {output}")
            raise click.ClickException("Could not determine current RDP level")

        if level == 0:
            click.secho("Device is already unlocked (RDP Level 0)", fg="green")
            return

        if level == 2:
            click.secho("RDP Level 2 - PERMANENTLY LOCKED", fg="red")
            raise click.ClickException(
                "Cannot unlock RDP Level 2 - device is permanently locked.\n"
                "Debug interface is disabled forever."
            )

        # Level 1 - can unlock but requires mass erase
        click.secho("Current: RDP Level 1 (protected)", fg="yellow")
        click.echo()
        click.secho("WARNING: Unlocking will cause MASS ERASE!", fg="red", bold=True)
        click.echo("  - All flash memory will be erased")
        click.echo("  - Bootloader, firmware, filesystem - ALL GONE")
        click.echo("  - You will need to reflash everything")
        click.echo()

        if not click.confirm("Proceed with unlock and mass erase?"):
            click.echo("Aborted")
            return

        click.secho("Unlocking...", fg="yellow")
        result = flash_backend.unlock_rdp(get_ocd())
        click.echo(result)

    click.echo()
    click.secho("Unlock command sent.", fg="green")
    click.secho("IMPORTANT: Power cycle the board now!", fg="yellow", bold=True)
    click.echo("  Unplug USB and power, then reconnect.")


@flash.command("lock")
def flash_lock():
    """Enable flash read protection (RDP Level 0 -> 1).

    WARNING: After locking, flash cannot be read via debug interface.
    Unlocking requires mass erase (all data lost).

    Use this for production devices to protect firmware.
    After locking, you must power cycle the board.

    \b
    Note: This sets RDP Level 1, NOT Level 2.
    Level 2 (permanent lock) is intentionally not supported.
    """
    with get_ocd().ensure_running():
        click.secho("=== Flash Lock (Enable RDP) ===", fg="blue")

        # Check current RDP level
        output = flash_backend.read_option_bytes(get_ocd())
        level = flash_backend.parse_rdp_level(output)

        if level is None:
            click.echo(f"Raw output: {output}")
            raise click.ClickException("Could not determine current RDP level")

        if level == 1:
            click.secho("Device is already locked (RDP Level 1)", fg="yellow")
            return

        if level == 2:
            click.secho("Device is permanently locked (RDP Level 2)", fg="red")
            return

        # Level 0 - can lock
        click.secho("Current: RDP Level 0 (no protection)", fg="green")
        click.echo()
        click.secho("WARNING: After locking:", fg="yellow")
        click.echo("  - Flash cannot be read via debug interface")
        click.echo("  - Unlocking requires MASS ERASE (all data lost)")
        click.echo("  - This sets RDP Level 1 (recoverable)")
        click.echo()

        if not click.confirm("Proceed with locking?"):
            click.echo("Aborted")
            return

        click.secho("Locking...", fg="yellow")
        result = flash_backend.lock_rdp(get_ocd())
        click.echo(result)

    click.echo()
    click.secho("Lock command sent.", fg="green")
    click.secho("IMPORTANT: Power cycle the board now!", fg="yellow", bold=True)
    click.echo("  Unplug USB and power, then reconnect.")


# Register fingerprint subgroup
flash.add_command(fingerprint)


@flash.command("program")
@click.argument("file", type=click.Path(exists=True))
@click.option("--addr", default=None, help="Flash address (auto-detected if not specified)")
@click.option("--force", is_flag=True, help="Force --addr even if it conflicts with auto-detected")
@click.option("--verify/--no-verify", default=True, help="Verify after programming")
@click.option("--reset/--no-reset", default=True, help="Reset after programming")
@click.option("--timeout", "-t", default=0, type=int, help="Timeout in seconds (0=auto based on size)")
def flash_program(file: str, addr: str | None, force: bool, verify: bool, reset: bool, timeout: int):
    """Program firmware to flash.

    Analyzes firmware layout before programming. Zero regions between code
    sections won't overwrite existing flash data (preserves filesystem).

    Flash address is auto-detected based on firmware layout:
      - Initial/full images (with bootloader) -> 0x08000000
      - Upgrade images (main firmware only) -> 0x08020000

    Use --addr to override, requires --force if it conflicts with auto-detect.

    \b
    Note on verification:
      OpenOCD's built-in verify compares byte-by-byte, which may fail on
      files with zeros between code. After programming, use
      'disco flash verify --smart' for accurate verification.
    """
    file = os.path.abspath(file)
    size = os.path.getsize(file)

    regions = flash_backend.analyze_firmware(file)
    code_regions = flash_backend.get_code_regions(regions)
    internal_zeros = flash_backend.has_internal_zeros(regions)
    code_bytes = flash_backend.calculate_code_bytes(regions)

    # Auto-detect flash address
    detected_addr = flash_backend.detect_flash_address(
        regions, internal_zeros, flash_backend.read_reset_vector(file)
    )

    # Handle user-provided address
    if addr is not None:
        addr_int = int(addr, 16) if addr.startswith("0x") else int(addr)
        if addr_int != detected_addr and not force:
            raise click.ClickException(
                f"Address mismatch: --addr=0x{addr_int:08x} but detected 0x{detected_addr:08x}\n"
                f"Use --force to override auto-detection"
            )
    else:
        addr_int = detected_addr

    click.secho("=== Programming Firmware ===", fg="blue")
    click.echo(f"File: {file}")
    click.echo(f"Size: {size:,} bytes ({size/1024:.1f} KB)")
    click.echo(f"Code: {code_bytes:,} bytes in {len(code_regions)} region(s)")
    addr_source = "auto-detected" if addr is None else ("forced" if force else "user")
    click.echo(f"Address: 0x{addr_int:08x} ({addr_source})")
    click.echo(f"Timeout: {timeout}s" if timeout else "Timeout: auto")

    if internal_zeros:
        click.echo()
        click.secho("Data preservation: YES", fg="yellow")
        click.echo("  Zeros between code regions - existing data preserved.")
        if verify:
            click.secho("  Note: OpenOCD verify may report mismatch (expected).", fg="yellow")
    click.echo()

    click.secho("Programming in progress (this may take a while)...", fg="yellow")

    with get_ocd().ensure_running():
        success = flash_backend.program_firmware(get_ocd(), file, addr_int, verify, reset, timeout)

    if success:
        click.secho("Programming complete!", fg="green")
        if verify and internal_zeros:
            click.echo()
            click.secho("OpenOCD verify may have failed on zero regions.", fg="yellow")
            click.echo("Run 'disco flash verify --smart' to verify code regions only.")
    else:
        click.secho("Programming status unclear - check output above", fg="yellow")
