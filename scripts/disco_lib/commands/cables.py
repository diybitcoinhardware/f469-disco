"""Cable detection command."""

import re
import subprocess
import sys

import click

from ..openocd import OpenOCD
from ..serial import SerialDevice

_ocd = OpenOCD()
_ser = SerialDevice()

# USB Vendor/Product IDs
STLINK_VENDOR_ID = "0x0483"
MICROPYTHON_VENDOR_ID = "0xf055"


def _check_usb_devices():
    """Check raw USB devices via system command.

    Returns dict with 'stlink' and 'micropython' booleans.
    """
    result = {"stlink": False, "micropython": False}

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
        except Exception:
            pass
    elif sys.platform == "linux":
        try:
            out = subprocess.run(
                ["lsusb"], capture_output=True, text=True, timeout=5
            )
            if "0483:" in out.stdout:
                result["stlink"] = True
            if "f055:" in out.stdout:
                result["micropython"] = True
        except Exception:
            pass

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
        match = re.search(r'usbmodem(\w+)', path)
        if match:
            port_id = match.group(1)
            if len(port_id) <= 6:
                stlink_serial = True
            else:
                usb_otg_serial = True

    jtag_ok = False
    ocd_running = _ocd.is_running()
    if ocd_running:
        _ocd.send("halt")
        result = _ocd.send("reg pc")
        _ocd.send("resume")
        jtag_ok = "0x" in result

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
        click.secho("  JTAG: OpenOCD not running (use 'disco ocd connect')", fg="yellow")
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
        click.secho("  USB: detected but no CDC - firmware issue?", fg="yellow")

    click.echo()
    if not usb["stlink"] and not usb["micropython"]:
        click.secho("No USB devices detected - check both cables!", fg="red")
    elif not usb["stlink"]:
        click.secho("Tip: ST-LINK cable not connected or bad cable", fg="yellow")
    elif not usb_otg_serial:
        click.secho("Tip: Connect miniUSB cable for REPL access", fg="yellow")
