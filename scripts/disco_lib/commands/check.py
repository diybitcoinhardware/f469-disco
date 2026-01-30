"""Board check command."""

import click

from ..ocd_provider import get_ocd
from .. import cpu as cpu_backend
from .. import memory
from .. import flash as flash_backend
from ..diagnostics import is_rdp_enabled


@click.command()
@click.option("--no-resume", is_flag=True, help="Keep CPU halted after check (disconnects USB)")
def check(no_resume: bool):
    """Run full board diagnostics.

    By default, resumes CPU after check to keep USB CDC working.
    Use --no-resume to keep halted for further debugging.
    """
    with get_ocd().ensure_running():
        click.secho("=== Board Diagnostic Check ===", fg="blue")

        cpu_backend.halt(get_ocd())
        try:
            click.secho("\n1. CPU State", fg="yellow")
            click.echo(cpu_backend.read_reg(get_ocd(), "pc"))
            click.echo(cpu_backend.read_reg(get_ocd(), "sp"))
            click.echo(cpu_backend.read_reg(get_ocd(), "lr"))

            click.secho("\n2. Vector Table (0x08000000)", fg="yellow")
            click.echo(memory.read_words(get_ocd(), 0x08000000, 4))

            click.secho("\n3. Firmware Area (0x08020000)", fg="yellow")
            click.echo(memory.read_words(get_ocd(), 0x08020000, 4))

            click.secho("\n4. RAM Check (0x20000000)", fg="yellow")
            click.echo(memory.read_words(get_ocd(), 0x20000000, 4))

            click.secho("\n5. Flash Info", fg="yellow")
            flash_info = flash_backend.read_info(get_ocd())
            if is_rdp_enabled(flash_info):
                click.secho("RDP: enabled (flash locked)", fg="yellow")
            else:
                click.secho("RDP: disabled", fg="green")
            click.echo(flash_info)
        finally:
            if no_resume:
                click.secho("\nCPU left halted (--no-resume). USB CDC disconnected.", fg="yellow")
            else:
                cpu_backend.resume(get_ocd())
                click.secho("\nCPU resumed. USB CDC should reconnect.", fg="green")
