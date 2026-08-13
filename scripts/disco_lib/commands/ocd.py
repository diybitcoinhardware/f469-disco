"""OpenOCD server management commands."""

import click

from .. import GDB_PORT, OPENOCD_PORT
from ..ocd_provider import get_ocd


@click.group()
def ocd():
    """OpenOCD server management.

    OpenOCD (Open On-Chip Debugger) provides JTAG/SWD access to the
    STM32F469 via the ST-LINK interface on the MicroUSB connector.

    \b
    Most commands auto-connect to OpenOCD when needed. If OpenOCD wasn't
    running, it will be stopped after the command completes.

    \b
    Use 'disco ocd start' to keep OpenOCD running persistently:
      - Faster repeated commands (no startup delay)
      - Required for GDB debugging sessions
      - Use 'disco ocd stop' when done

    \b
    Connection details:
      - Telnet port: 4444 (for manual commands)
      - GDB port: 3333 (for GDB debugging)
      - Config: board/stm32f469discovery.cfg
      - Log file: /tmp/openocd.log

    \b
    Troubleshooting:
      - Check MicroUSB cable is connected to ST-LINK port
      - Run 'disco cables' to verify JTAG connection
      - Check /tmp/openocd.log for errors
    """
    pass


@ocd.command("start")
def ocd_start():
    """Start OpenOCD server (background)."""
    get_ocd().start()


@ocd.command("stop")
def ocd_stop():
    """Stop OpenOCD server."""
    get_ocd().stop()


@ocd.command("status")
def ocd_status():
    """Check if OpenOCD is running and board connected."""
    if get_ocd().is_running():
        click.secho("OpenOCD: running", fg="green")
        click.echo(f"Ports: telnet={OPENOCD_PORT}, gdb={GDB_PORT}")
        click.echo(get_ocd().send("reg pc sp"))
    else:
        click.secho("OpenOCD: not running", fg="red")


@ocd.command("cmd")
@click.argument("command", nargs=-1, required=True)
def ocd_cmd(command):
    """Send raw OpenOCD command.

    \b
    Examples:
      disco ocd cmd halt
      disco ocd cmd "mdw 0x08000000 4"
      disco ocd cmd flash probe 0
      disco ocd cmd targets
    """
    cmd_str = " ".join(command)
    with get_ocd().ensure_running():
        click.secho(f"> {cmd_str}", fg="cyan")
        result = get_ocd().send(cmd_str)
        if result:
            click.echo(result)
        else:
            click.secho("(no output)", fg="yellow")
