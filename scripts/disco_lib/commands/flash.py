"""Flash programming commands."""

import os
import re
import tempfile

import click

from ..ocd_provider import get_ocd
from .. import flash as flash_backend
from .. import cpu as cpu_backend


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
    get_ocd().require_running()
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
        get_ocd().require_running()
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
    get_ocd().require_running()

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
    get_ocd().require_running()

    file = os.path.abspath(file)
    size = os.path.getsize(file)

    # Parse address
    if addr.startswith("0x"):
        addr_int = int(addr, 16)
    else:
        addr_int = int(addr)

    regions = flash_backend.analyze_firmware(file)
    code_regions = flash_backend.get_code_regions(regions)
    internal_zeros = flash_backend.has_internal_zeros(regions)

    click.secho("=== Verifying Flash ===", fg="blue")
    click.echo(f"File: {file}")
    click.echo(f"Size: {size:,} bytes ({size/1024:.1f} KB)")
    click.echo(f"Address: 0x{addr_int:08x}")
    click.echo(f"Mode: {'smart (code regions only)' if smart else 'full (strict)'}")

    if internal_zeros and smart:
        click.secho("Note: File has zeros between code - will verify code regions only", fg="yellow")
    click.echo()

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
    get_ocd().require_running()
    click.secho("WARNING: This will erase all flash memory!", fg="red")
    if click.confirm("Type 'y' to confirm"):
        with cpu_backend.halted(get_ocd()):
            click.echo(flash_backend.erase_all(get_ocd()))
            click.secho("Flash erased", fg="green")
    else:
        click.echo("Aborted")


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
    get_ocd().require_running()

    file = os.path.abspath(file)
    size = os.path.getsize(file)

    regions = flash_backend.analyze_firmware(file)
    code_regions = flash_backend.get_code_regions(regions)
    internal_zeros = flash_backend.has_internal_zeros(regions)
    code_bytes = flash_backend.calculate_code_bytes(regions)

    # Auto-detect flash address
    detected_addr = flash_backend.detect_flash_address(regions, internal_zeros)

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

    success = flash_backend.program_firmware(get_ocd(), file, addr_int, verify, reset, timeout)

    if success:
        click.secho("Programming complete!", fg="green")
        if verify and internal_zeros:
            click.echo()
            click.secho("OpenOCD verify may have failed on zero regions.", fg="yellow")
            click.echo("Run 'disco flash verify --smart' to verify code regions only.")
    else:
        click.secho("Programming status unclear - check output above", fg="yellow")


@flash.group("fingerprint")
def fingerprint():
    """Firmware fingerprint commands."""
    pass


def _write_fingerprint(fingerprint: dict, output: str):
    """Write fingerprint to YAML file."""
    import yaml
    yaml_str = yaml.dump(fingerprint, default_flow_style=False, sort_keys=False, allow_unicode=True)
    with open(output, "w") as f:
        f.write("# Firmware fingerprint - auto-generated\n")
        f.write(yaml_str)


def _flash_and_verify(ocd, filepath: str, addr: int) -> bool:
    """Flash firmware and verify. Returns True on success."""
    import time

    click.echo("Flashing firmware...")
    if not flash_backend.program_firmware(ocd, filepath, addr):
        click.secho("Flash failed", fg="red")
        return False

    # Wait for target to stabilize after reset - OpenOCD needs time to
    # re-establish connection after reset, otherwise we get "Connection reset"
    time.sleep(2.0)

    click.echo("Verifying flash...")
    if not flash_backend.verify_firmware(ocd, filepath, addr):
        click.secho("Flash verification failed", fg="red")
        return False

    click.secho("Flash verified OK", fg="green")
    return True


def _print_fingerprint_summary(fingerprint: dict, runtime_results: dict = None):
    """Print fingerprint summary."""
    click.echo(f"Name: {fingerprint['name']}")
    click.echo(f"Size: {fingerprint['static']['size_bytes']:,} bytes")
    click.echo(f"SHA256: {fingerprint['static']['sha256'][:16]}...")
    click.echo(f"Build: {fingerprint['static']['build_type']}")
    click.echo(f"Regions: {len(fingerprint['static']['regions'])}")
    if runtime_results:
        click.echo()
        click.echo("Runtime:")
        for key, val in runtime_results.items():
            icon = click.style("OK", fg="green") if val else click.style("FAIL", fg="red")
            click.echo(f"  {icon} {key}: {val}")


@fingerprint.command("create")
@click.argument("file", type=click.Path(exists=True))
@click.option("--output", "-o", type=click.Path(), help="Output YAML file (default: fingerprint.yaml in same dir)")
def fingerprint_create(file: str, output: str):
    """Create new fingerprint for firmware file.

    Runs static analysis and runtime hardware tests.
    Fails if fingerprint.yaml already exists.

    \b
    Examples:
      disco flash fingerprint create firmware.bin
    """
    import time
    from ..ocd_provider import with_ocd
    from ..serial import SerialDevice

    if output is None:
        output = os.path.join(os.path.dirname(os.path.abspath(file)), "fingerprint.yaml")

    if os.path.exists(output):
        click.secho(f"Error: {output} already exists. Use 'update' instead.", fg="red")
        raise SystemExit(1)

    click.echo("Analyzing firmware...")
    fp = flash_backend.generate_fingerprint(file)

    # Get flash address from fingerprint
    flash_addr_str = fp.get("static", {}).get("flash_address", "0x08020000")
    flash_addr = int(flash_addr_str, 16)
    click.echo(f"Flash address: {flash_addr_str} (auto-detected)")

    with with_ocd() as ocd:
        if not _flash_and_verify(ocd, file, flash_addr):
            raise SystemExit(1)

        click.echo("Waiting for device to boot...")
        time.sleep(5.0)  # Wait for boot + USB re-enumeration

        click.echo("Running runtime tests...")
        ser = SerialDevice()
        runtime = flash_backend.test_runtime(ocd, ser)
        fp["runtime"] = runtime

    _write_fingerprint(fp, output)
    click.secho(f"\nFingerprint created: {output}", fg="green")
    click.echo()
    _print_fingerprint_summary(fp, runtime)


@fingerprint.command("update")
@click.argument("file", type=click.Path(exists=True))
@click.option("--output", "-o", type=click.Path(), help="Output YAML file (default: fingerprint.yaml in same dir)")
def fingerprint_update(file: str, output: str):
    """Update fingerprint for firmware file.

    Runs static analysis and runtime hardware tests.
    Creates new file if doesn't exist.

    \b
    Examples:
      disco flash fingerprint update firmware.bin
    """
    import time
    from ..ocd_provider import with_ocd
    from ..serial import SerialDevice

    if output is None:
        output = os.path.join(os.path.dirname(os.path.abspath(file)), "fingerprint.yaml")

    click.echo("Analyzing firmware...")
    fp = flash_backend.generate_fingerprint(file)

    # Get flash address from fingerprint
    flash_addr_str = fp.get("static", {}).get("flash_address", "0x08020000")
    flash_addr = int(flash_addr_str, 16)
    click.echo(f"Flash address: {flash_addr_str} (auto-detected)")

    with with_ocd() as ocd:
        if not _flash_and_verify(ocd, file, flash_addr):
            raise SystemExit(1)

        click.echo("Waiting for device to boot...")
        time.sleep(5.0)  # Wait for boot + USB re-enumeration

        click.echo("Running runtime tests...")
        ser = SerialDevice()
        runtime = flash_backend.test_runtime(ocd, ser)
        fp["runtime"] = runtime

    action = "updated" if os.path.exists(output) else "created"
    _write_fingerprint(fp, output)
    click.secho(f"\nFingerprint {action}: {output}", fg="green")
    click.echo()
    _print_fingerprint_summary(fp, runtime)


@fingerprint.command("test")
@click.argument("fingerprint_file", type=click.Path(exists=True))
@click.option("--static-only", is_flag=True, help="Only compare file fingerprint (no flash, no hardware)")
def fingerprint_test(fingerprint_file: str, static_only: bool):
    """Test current state against existing fingerprint.

    Flashes firmware, runs tests and compares to expected values.
    Returns non-zero if differs, creates fingerprint_diff_<timestamp>.yaml.

    With --static-only, only compares file fingerprint without hardware.

    \b
    Examples:
      disco flash fingerprint test fingerprint.yaml
      disco flash fingerprint test fingerprint.yaml --static-only
    """
    import time
    import yaml
    from datetime import datetime

    # Validate file type
    if not fingerprint_file.endswith(('.yaml', '.yml')):
        raise click.ClickException(
            f"Expected a fingerprint YAML file, got: {os.path.basename(fingerprint_file)}\n"
            f"Usage: disco flash fingerprint test fingerprint.yaml"
        )

    # Load existing fingerprint
    with open(fingerprint_file) as f:
        expected = yaml.safe_load(f)

    firmware_file = os.path.join(os.path.dirname(fingerprint_file), expected.get("filename", ""))

    click.echo(f"Testing against: {fingerprint_file}")
    click.echo(f"Firmware: {expected.get('filename')}")
    if static_only:
        click.echo("Mode: static only (no flash, no hardware)")

    if not os.path.exists(firmware_file):
        raise click.ClickException(f"Firmware file not found: {firmware_file}")

    click.echo("Analyzing firmware...")
    current = flash_backend.generate_fingerprint(firmware_file)

    runtime = None
    if not static_only:
        from ..ocd_provider import with_ocd
        from ..serial import SerialDevice

        # Get flash address from fingerprint or auto-detect
        flash_addr_str = expected.get("static", {}).get("flash_address")
        if flash_addr_str:
            flash_addr = int(flash_addr_str, 16)
            click.echo(f"Flash address: {flash_addr_str} (from fingerprint)")
        else:
            flash_addr_str = current.get("static", {}).get("flash_address", "0x08020000")
            flash_addr = int(flash_addr_str, 16)
            click.echo(f"Flash address: {flash_addr_str} (auto-detected)")

        with with_ocd() as ocd:
            if not _flash_and_verify(ocd, firmware_file, flash_addr):
                raise click.ClickException("Flash/verify failed")

            click.echo("Waiting for device to boot...")
            time.sleep(5.0)  # Wait for boot + USB re-enumeration

            click.echo("Running runtime tests...")
            ser = SerialDevice()
            runtime = flash_backend.test_runtime(ocd, ser)
            current["runtime"] = runtime

    # Compare
    diffs = flash_backend.compare_fingerprints(expected, current, static_only=static_only)

    if not diffs:
        msg = "static fingerprint matches" if static_only else "fingerprint matches"
        click.secho(f"\nAll tests passed - {msg}", fg="green")
        raise SystemExit(0)

    # Show differences
    click.secho(f"\n{len(diffs)} difference(s) found:", fg="red")
    for key, diff in diffs.items():
        click.echo(f"  {key}: expected={diff['expected']}, actual={diff['actual']}")

    # Write diff file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    diff_file = fingerprint_file.replace(".yaml", f"_diff_{timestamp}.yaml")
    diff_data = {
        "expected_file": fingerprint_file,
        "timestamp": timestamp,
        "differences": diffs,
    }
    if runtime:
        diff_data["current_runtime"] = runtime
    with open(diff_file, "w") as f:
        yaml.dump(diff_data, f, default_flow_style=False, sort_keys=False)

    click.secho(f"\nDiff written to: {diff_file}", fg="yellow")
    raise SystemExit(1)
