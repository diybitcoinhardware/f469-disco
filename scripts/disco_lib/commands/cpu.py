"""CPU control commands."""

import click

from ..ocd_provider import get_ocd
from .. import cpu as cpu_backend
from .. import memory


@click.group()
def cpu():
    """CPU control commands.

    Control the ARM Cortex-M4 CPU via JTAG/SWD through OpenOCD.
    These commands require OpenOCD to be running (disco ocd connect).

    \b
    WARNING: Halting the CPU disconnects USB CDC (REPL).
    Use 'disco cpu resume' or 'disco ocd cmd reset run' to restore.

    \b
    Typical debug workflow:
      1. disco ocd connect     # Start OpenOCD
      2. disco cpu halt        # Stop execution (USB disconnects!)
      3. disco cpu pc          # See where we are
      4. disco cpu regs        # Check register state
      5. disco cpu step        # Single-step through code
      6. disco cpu resume      # Continue running (USB reconnects)
    """
    pass


@cpu.command("halt")
def cpu_halt():
    """Halt the CPU.

    WARNING: This disconnects USB CDC - REPL will be unavailable until resumed.
    """
    get_ocd().require_running()
    cpu_backend.halt(get_ocd())
    click.secho("CPU halted", fg="green")
    click.secho("Note: USB CDC (REPL) disconnected while halted", fg="yellow")
    click.echo(cpu_backend.read_pc_sp(get_ocd()))


@cpu.command("resume")
def cpu_resume():
    """Resume execution."""
    get_ocd().require_running()
    cpu_backend.resume(get_ocd())
    click.secho("CPU resumed", fg="green")


@cpu.command("reset")
def cpu_reset():
    """Reset and halt."""
    get_ocd().require_running()
    cpu_backend.reset_halt(get_ocd())
    click.secho("CPU reset and halted", fg="green")
    click.echo(cpu_backend.read_pc_sp(get_ocd()))


@cpu.command("step")
def cpu_step():
    """Single step."""
    get_ocd().require_running()
    cpu_backend.step(get_ocd())
    click.echo(cpu_backend.read_reg(get_ocd(), "pc"))


@cpu.command("regs")
def cpu_regs():
    """Show all CPU registers."""
    get_ocd().require_running()
    click.secho("=== CPU Registers ===", fg="blue")
    with cpu_backend.halted(get_ocd()):
        click.echo(cpu_backend.read_regs(get_ocd()))


@cpu.command("pc")
def cpu_pc():
    """Show current PC and memory around it."""
    get_ocd().require_running()
    click.secho("=== Current PC ===", fg="blue")
    with cpu_backend.halted(get_ocd()):
        pc_val = cpu_backend.read_pc(get_ocd())
        if pc_val is not None:
            click.echo(f"PC: 0x{pc_val:08x}")
            click.echo()
            click.echo("Memory around PC:")
            pc_aligned = (pc_val & ~0xF) - 0x10
            click.echo(memory.read_words(get_ocd(), pc_aligned, 16))
        else:
            click.echo(cpu_backend.read_reg(get_ocd(), "pc"))


@cpu.command("stack")
@click.argument("count", default=16, type=int)
def cpu_stack(count: int):
    """Show stack (N words, default 16)."""
    get_ocd().require_running()
    click.secho(f"=== Stack ({count} words) ===", fg="blue")
    with cpu_backend.halted(get_ocd()):
        sp_val = cpu_backend.read_sp(get_ocd())
        if sp_val is not None:
            click.echo(f"SP: 0x{sp_val:08x}")
            click.echo(memory.read_words(get_ocd(), sp_val, count))
        else:
            click.echo(cpu_backend.read_reg(get_ocd(), "sp"))


@cpu.command("gdb")
@click.argument("elf", type=click.Path(exists=True), required=False)
@click.option("--run", is_flag=True, help="Actually launch GDB (default: just print command)")
def cpu_gdb(elf: str, run: bool):
    """Show or launch GDB command for debugging.

    \b
    With no arguments, prints the GDB command to connect to target.
    With --run, actually launches GDB.

    \b
    Examples:
      disco cpu gdb                           # Print GDB command
      disco cpu gdb firmware.elf              # Print command with ELF
      disco cpu gdb firmware.elf --run        # Launch GDB with ELF
      disco cpu gdb --run                     # Launch GDB without ELF

    \b
    GDB Commands Cheat Sheet:
      target remote :3333    # Connect to OpenOCD (done automatically)
      monitor halt           # Halt CPU via OpenOCD
      monitor reset halt     # Reset and halt
      load                   # Load ELF to target (if ELF provided)
      break main             # Set breakpoint
      continue               # Run
      step / next            # Step into / over
      info registers         # Show registers
      x/10x $sp              # Examine memory at SP
    """
    import os
    import shutil

    get_ocd().require_running()

    # Find GDB
    gdb_names = ["arm-none-eabi-gdb", "gdb-multiarch", "gdb"]
    gdb_path = None
    for name in gdb_names:
        if shutil.which(name):
            gdb_path = name
            break

    if not gdb_path:
        click.secho("Error: No ARM GDB found. Install arm-none-eabi-gdb", fg="red")
        return

    # Build command
    cmd_parts = [gdb_path]
    if elf:
        cmd_parts.append(os.path.abspath(elf))
    cmd_parts.extend(["-ex", "target remote :3333"])

    cmd_str = " ".join(f'"{p}"' if " " in p else p for p in cmd_parts)

    if run:
        click.secho(f"Launching: {cmd_str}", fg="green")
        os.execvp(gdb_path, cmd_parts)
    else:
        click.secho("=== GDB Command ===", fg="blue")
        click.echo(cmd_str)
        click.echo()
        click.secho("Run with --run flag to launch, or copy/paste the command", fg="yellow")
