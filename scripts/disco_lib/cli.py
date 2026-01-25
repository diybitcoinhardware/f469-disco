"""Main CLI entry point for disco."""

import click

from .commands import (
    ocd, cpu, mem, flash, serial, repl,
    doctor, quickstart, cables, check, power,
)


@click.group()
def cli():
    """STM32F469 Discovery board debugging utility.

    Commands are organized into groups:

    \b
      ocd     - OpenOCD server management
      cpu     - CPU control (halt, resume, reset, step)
      mem     - Memory inspection
      flash   - Flash programming
      serial  - Serial device detection
      repl    - MicroPython REPL interaction
      power   - USB power control via YKUSH hub

    Top-level commands:

    \b
      doctor  - Automated diagnostics with logging
      check   - Run full board diagnostics
      cables  - Detect connected USB cables
    """
    pass


# Register command groups
cli.add_command(ocd)
cli.add_command(cpu)
cli.add_command(mem)
cli.add_command(flash)
cli.add_command(serial)
cli.add_command(repl)
cli.add_command(power)

# Register top-level commands
cli.add_command(doctor)
cli.add_command(quickstart)
cli.add_command(cables)
cli.add_command(check)
