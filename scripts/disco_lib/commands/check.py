"""Board check command."""

import click

from ..ocd_provider import get_ocd


@click.command()
@click.option("--no-resume", is_flag=True, help="Keep CPU halted after check (disconnects USB)")
def check(no_resume: bool):
    """Run full board diagnostics.

    By default, resumes CPU after check to keep USB CDC working.
    Use --no-resume to keep halted for further debugging.
    """
    get_ocd().require_running()
    click.secho("=== Board Diagnostic Check ===", fg="blue")
    get_ocd().send("halt")
    try:
        click.secho("\n1. CPU State", fg="yellow")
        click.echo(get_ocd().send("reg pc"))
        click.echo(get_ocd().send("reg sp"))
        click.echo(get_ocd().send("reg lr"))

        click.secho("\n2. Vector Table (0x08000000)", fg="yellow")
        click.echo(get_ocd().send("mdw 0x08000000 4"))

        click.secho("\n3. Firmware Area (0x08020000)", fg="yellow")
        click.echo(get_ocd().send("mdw 0x08020000 4"))

        click.secho("\n4. RAM Check (0x20000000)", fg="yellow")
        click.echo(get_ocd().send("mdw 0x20000000 4"))

        click.secho("\n5. Flash Info", fg="yellow")
        click.echo(get_ocd().send("flash info 0"))
    finally:
        if no_resume:
            click.secho("\nCPU left halted (--no-resume). USB CDC disconnected.", fg="yellow")
        else:
            get_ocd().send("resume")
            click.secho("\nCPU resumed. USB CDC should reconnect.", fg="green")
