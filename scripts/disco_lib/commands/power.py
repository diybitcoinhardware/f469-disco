"""Power control commands using YKUSH USB hub."""

import os

import click

from ..ykush import (
    Ykush,
    YkushError,
    YkushInvalidPortError,
    YkushNoDevicesError,
    YkushNotFoundError,
)
from ..ykush_provider import get_ykush


def _get_ykush_instance(serial: str | None) -> Ykush:
    """Get YKUSH instance with optional serial selection."""
    return get_ykush(serial=serial)


def _parse_port(port_str: str | None) -> int | str:
    """Parse port argument to int or 'all'.

    Args:
        port_str: Port string from CLI (None, '1', '2', '3', 'all', 'a').

    Returns:
        Port number (1, 2, 3) or 'all'.

    Raises:
        click.BadParameter: If port is invalid.
    """
    if port_str is None or port_str.lower() in ("all", "a"):
        return "all"
    try:
        port = int(port_str)
        if port not in (1, 2, 3):
            raise click.BadParameter("Port must be 1, 2, 3, or 'all'")
        return port
    except ValueError:
        raise click.BadParameter("Port must be 1, 2, 3, or 'all'")


def _print_ykush_unavailable():
    """Print helpful message when YKUSH is not available."""
    click.secho("YKUSH not available.", fg="red")
    click.echo()
    click.echo("To power cycle the board manually:")
    click.echo("  1. Unplug the USB cables from the board")
    click.echo("  2. Wait 2-3 seconds")
    click.echo("  3. Reconnect the cables")
    click.echo()
    click.echo("For automated power control, install a YKUSH USB hub:")
    click.echo("  https://www.yepkit.com/")


def _print_no_devices():
    """Print message when no YKUSH devices found."""
    click.secho("No YKUSH devices found.", fg="yellow")
    click.echo()
    click.echo("Check that:")
    click.echo("  - YKUSH hub is connected via USB")
    click.echo("  - USB cable is working")
    click.echo("  - ykushcmd can see the device: ykushcmd -l")


@click.group()
@click.option(
    "--serial",
    "-s",
    envvar="YKUSH_SERIAL",
    help="YKUSH device serial number (or set YKUSH_SERIAL env var)",
)
@click.pass_context
def power(ctx, serial):
    """USB power control via YKUSH hub.

    Control power to USB devices connected through a YKUSH USB hub.
    Useful for power cycling the STM32F469 Discovery board to recover
    from hangs or reset USB enumeration.

    \b
    Examples:
      disco power status              # Show all devices and port states
      disco power cycle               # Power cycle all ports (default)
      disco power off 1               # Power down port 1 only
      disco power on                  # Power up all ports
      disco power --serial YK123 off  # Target specific device
    """
    ctx.ensure_object(dict)
    ctx.obj["serial"] = serial


@power.command("status")
@click.pass_context
def power_status(ctx):
    """Show YKUSH devices and port states."""
    serial = ctx.obj.get("serial")

    try:
        ykush = _get_ykush_instance(serial)

        # First list all devices
        devices = ykush.list_devices()
        if not devices:
            _print_no_devices()
            return

        click.secho("=== YKUSH Status ===", fg="blue")
        click.echo(f"Devices found: {len(devices)}")
        click.echo()

        for dev_serial in devices:
            click.echo(f"Device: {dev_serial}")
            # Get status for each port
            for port in (1, 2, 3):
                try:
                    # Create instance for this specific device to get port status
                    dev_ykush = get_ykush(serial=dev_serial)
                    is_on = dev_ykush.get_port_status(port)
                    status_icon = click.style("ON", fg="green") if is_on else click.style("OFF", fg="red")
                    click.echo(f"  Port {port}: {status_icon}")
                except YkushError:
                    click.echo(f"  Port {port}: " + click.style("?", fg="yellow"))
            click.echo()

    except YkushNotFoundError:
        _print_ykush_unavailable()
    except YkushNoDevicesError:
        _print_no_devices()
    except YkushError as e:
        raise click.ClickException(str(e))


@power.command("on")
@click.argument("port", required=False, default=None)
@click.pass_context
def power_on(ctx, port):
    """Power up port(s).

    PORT can be 1, 2, 3, or 'all' (default: all).
    """
    serial = ctx.obj.get("serial")
    port_val = _parse_port(port)

    try:
        ykush = _get_ykush_instance(serial)
        ykush.select_device()  # Validate device exists

        port_desc = "all ports" if port_val == "all" else f"port {port_val}"
        click.echo(f"Powering on {port_desc}...")
        result = ykush.power_up(port_val)
        if result:
            click.echo(result)
        click.secho(f"Power ON: {port_desc}", fg="green")

    except YkushNotFoundError:
        _print_ykush_unavailable()
    except YkushNoDevicesError:
        _print_no_devices()
    except YkushInvalidPortError as e:
        raise click.BadParameter(str(e))
    except YkushError as e:
        raise click.ClickException(str(e))


@power.command("off")
@click.argument("port", required=False, default=None)
@click.pass_context
def power_off(ctx, port):
    """Power down port(s).

    PORT can be 1, 2, 3, or 'all' (default: all).
    """
    serial = ctx.obj.get("serial")
    port_val = _parse_port(port)

    try:
        ykush = _get_ykush_instance(serial)
        ykush.select_device()  # Validate device exists

        port_desc = "all ports" if port_val == "all" else f"port {port_val}"
        click.echo(f"Powering off {port_desc}...")
        result = ykush.power_down(port_val)
        if result:
            click.echo(result)
        click.secho(f"Power OFF: {port_desc}", fg="yellow")

    except YkushNotFoundError:
        _print_ykush_unavailable()
    except YkushNoDevicesError:
        _print_no_devices()
    except YkushInvalidPortError as e:
        raise click.BadParameter(str(e))
    except YkushError as e:
        raise click.ClickException(str(e))


@power.command("cycle")
@click.argument("port", required=False, default=None)
@click.option("--delay", "-d", default=2.0, type=float, help="Delay in seconds between off/on (default: 2.0)")
@click.pass_context
def power_cycle(ctx, port, delay):
    """Power cycle port(s) with delay.

    PORT can be 1, 2, 3, or 'all' (default: all).

    \b
    Example workflow:
      disco power cycle && sleep 3 && disco ocd start
    """
    serial = ctx.obj.get("serial")
    port_val = _parse_port(port)

    try:
        ykush = _get_ykush_instance(serial)
        ykush.select_device()  # Validate device exists

        port_desc = "all ports" if port_val == "all" else f"port {port_val}"
        click.echo(f"Power cycling {port_desc} (delay: {delay}s)...")
        click.echo("  Power OFF...")
        ykush.power_down(port_val)
        click.echo(f"  Waiting {delay}s...")
        # Note: actual sleep happens in power_cycle, but we call power_down/up
        # separately to show progress
        import time

        time.sleep(delay)
        click.echo("  Power ON...")
        ykush.power_up(port_val)
        click.secho(f"Power cycle complete: {port_desc}", fg="green")

    except YkushNotFoundError:
        _print_ykush_unavailable()
    except YkushNoDevicesError:
        _print_no_devices()
    except YkushInvalidPortError as e:
        raise click.BadParameter(str(e))
    except YkushError as e:
        raise click.ClickException(str(e))
