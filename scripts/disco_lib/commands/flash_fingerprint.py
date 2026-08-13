"""Flash fingerprint commands."""

import os

import click

from .. import flash as flash_backend


@click.group("fingerprint")
def fingerprint():
    """Firmware fingerprint commands.

    Fingerprints capture firmware identity (hash, regions, version tag)
    and runtime behavior (JTAG works, CPU runs, USB/REPL responsive).
    Used for regression testing, CI validation, and firmware verification.

    \b
    Workflow:
      1. `create` - Generate fingerprint for new firmware
      2. `test` - Verify firmware matches expected fingerprint
      3. `update` - Regenerate fingerprint after intentional changes
    """
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
