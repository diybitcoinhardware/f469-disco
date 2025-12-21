"""Board check command."""

import click

from ..openocd import OpenOCD

_ocd = OpenOCD()


@click.command()
@click.option("--no-resume", is_flag=True, help="Keep CPU halted after check (disconnects USB)")
def check(no_resume: bool):
    """Run full board diagnostics.

    By default, resumes CPU after check to keep USB CDC working.
    Use --no-resume to keep halted for further debugging.
    """
    _ocd.require_running()
    click.secho("=== Board Diagnostic Check ===", fg="blue")
    _ocd.send("halt")

    click.secho("\n1. CPU State", fg="yellow")
    click.echo(_ocd.send("reg pc"))
    click.echo(_ocd.send("reg sp"))
    click.echo(_ocd.send("reg lr"))

    click.secho("\n2. Vector Table (0x08000000)", fg="yellow")
    click.echo(_ocd.send("mdw 0x08000000 4"))

    click.secho("\n3. Firmware Area (0x08020000)", fg="yellow")
    click.echo(_ocd.send("mdw 0x08020000 4"))

    click.secho("\n4. RAM Check (0x20000000)", fg="yellow")
    click.echo(_ocd.send("mdw 0x20000000 4"))

    click.secho("\n5. Flash Info", fg="yellow")
    click.echo(_ocd.send("flash info 0"))

    if no_resume:
        click.secho("\nCPU left halted (--no-resume). USB CDC disconnected.", fg="yellow")
    else:
        _ocd.send("resume")
        click.secho("\nCPU resumed. USB CDC should reconnect.", fg="green")
