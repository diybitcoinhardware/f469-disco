"""Cable detection command."""

import re

import click

from ..openocd import OpenOCD
from ..serial import SerialDevice

_ocd = OpenOCD()
_ser = SerialDevice()


@click.command()
def cables():
    """Detect connected USB cables."""
    click.secho("=== Cable Detection ===", fg="blue")

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
    if jtag_ok:
        click.secho("  JTAG: connected", fg="green")
    elif ocd_running:
        click.secho("  JTAG: OpenOCD running but target not responding", fg="yellow")
    else:
        click.secho("  JTAG: OpenOCD not running (use 'disco ocd connect')", fg="red")
    if stlink_serial:
        click.secho("  Serial (VCP): available", fg="green")
    else:
        click.secho("  Serial (VCP): not detected", fg="yellow")

    click.echo()
    click.echo("MiniUSB (USB OTG connector):")
    if usb_otg_serial:
        click.secho("  Serial (CDC): available - REPL should work", fg="green")
    else:
        click.secho("  Serial (CDC): not connected - REPL unavailable", fg="red")

    click.echo()
    if not usb_otg_serial:
        click.secho("Tip: Connect miniUSB cable for REPL access", fg="yellow")
