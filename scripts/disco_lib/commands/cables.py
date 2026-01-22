"""Cable detection command."""

import re
import subprocess
import sys

import click

from ..ocd_provider import get_ocd
from ..serial import SerialDevice
from .. import cpu as cpu_backend

_ser = SerialDevice()

# USB Vendor/Product IDs
STLINK_VENDOR_ID = "0x0483"
MICROPYTHON_VENDOR_ID = "0xf055"


def _check_usb_devices():
    """Check raw USB devices via system command.

    Returns dict with 'stlink' and 'micropython' booleans,
    plus 'error' (str or None) and 'platform' for diagnostics.
    """
    result = {
        "stlink": False,
        "micropython": False,
        "error": None,
        "platform": sys.platform,
    }

    if sys.platform == "darwin":
        try:
            out = subprocess.run(
                ["system_profiler", "SPUSBDataType"],
                capture_output=True, text=True, timeout=10
            )
            if STLINK_VENDOR_ID in out.stdout:
                result["stlink"] = True
            if MICROPYTHON_VENDOR_ID in out.stdout:
                result["micropython"] = True
        except FileNotFoundError as e:
            result["error"] = f"Command not found: {e.filename}"
        except subprocess.TimeoutExpired:
            result["error"] = "USB enumeration timed out"
    elif sys.platform == "linux":
        try:
            out = subprocess.run(
                ["lsusb"], capture_output=True, text=True, timeout=5
            )
            if "0483:" in out.stdout:
                result["stlink"] = True
            if "f055:" in out.stdout:
                result["micropython"] = True
        except FileNotFoundError as e:
            result["error"] = f"Command not found: {e.filename}"
        except subprocess.TimeoutExpired:
            result["error"] = "USB enumeration timed out"
    else:
        result["error"] = f"Unsupported platform: {sys.platform}"

    return result


@click.command()
def cables():
    """Detect connected USB cables."""
    click.secho("=== Cable Detection ===", fg="blue")

    # Check raw USB hardware
    usb = _check_usb_devices()

    stlink_serial = False
    usb_otg_serial = False

    devices = _ser.list_devices()
    for path, blacklisted in devices:
        if blacklisted:
            continue
        # MacOS check
        match = re.search(r'usbmodem(\w+)', path)
        if match:
            port_id = match.group(1)
            if len(port_id) <= 6:
                stlink_serial = True
            else:
                usb_otg_serial = True

        # Linux check
        match = re.search(r'serial/by-id/(.+)', path)
        if match:
            dev_name = match.group(1).lower()
            if "STLink".lower() in dev_name:
                stlink_serial = True
            elif "MicroPython".lower() in dev_name:
                usb_otg_serial = True

    jtag_ok = False
    ocd_running = get_ocd().is_running()
    if ocd_running:
        with cpu_backend.halted(get_ocd()):
            pc_val = cpu_backend.read_pc(get_ocd())
            jtag_ok = pc_val is not None

    click.echo()
    if usb["error"]:
        click.secho(f"USB detection error: {usb['error']}", fg="yellow")
        click.echo()

    click.echo("MicroUSB (ST-LINK connector):")
    if not usb["stlink"]:
        click.secho("  USB: NOT DETECTED - check cable!", fg="red")
    elif jtag_ok:
        click.secho("  JTAG: connected", fg="green")
    elif ocd_running:
        click.secho("  JTAG: OpenOCD running but target not responding", fg="yellow")
    else:
        click.secho("  USB: detected", fg="green")
        click.secho("  JTAG: OpenOCD not running (use 'disco ocd start')", fg="yellow")
    if stlink_serial:
        click.secho("  Serial (VCP): available", fg="green")
    elif usb["stlink"]:
        click.secho("  Serial (VCP): not detected", fg="yellow")

    click.echo()
    click.echo("MiniUSB (USB OTG connector):")
    if not usb["micropython"]:
        click.secho("  USB: NOT DETECTED - check cable!", fg="red")
    elif usb_otg_serial:
        click.secho("  Serial (CDC): available - REPL should work", fg="green")
    else:
        click.secho("  USB: detected, but CDC interface is missing. This may indicate a firmware issue or incorrect USB detection logic", fg="yellow")

    click.echo()
    if not usb["stlink"] and not usb["micropython"]:
        click.secho("No USB devices detected - check both cables!", fg="red")
    elif not usb["stlink"]:
        click.secho("Tip: ST-LINK cable not connected or bad cable", fg="yellow")
    elif not usb_otg_serial:
        click.secho("Tip: Connect miniUSB cable for REPL access", fg="yellow")
