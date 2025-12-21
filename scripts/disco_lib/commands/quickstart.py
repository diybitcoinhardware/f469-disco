"""Quickstart command - AI agent context for disco tool."""

import click

QUICKSTART_TEXT = """\
# disco - STM32F469 Discovery Board Tool

Use `disco` for ALL interactions with the STM32F469-Discovery board.
Handles OpenOCD, JTAG debugging, flash programming, and MicroPython REPL.

## Command Tree

```
disco
├── cables          # Detect connected USB cables
├── check           # Run full board diagnostics
├── doctor          # Automated diagnostics with logging
│
├── ocd             # OpenOCD server management
│   ├── connect     # Start OpenOCD (background)
│   ├── disconnect  # Stop OpenOCD
│   ├── status      # Check if running
│   └── cmd         # Send raw OpenOCD command
│
├── cpu             # CPU control (requires ocd connect)
│   ├── halt        # Halt CPU
│   ├── resume      # Resume execution
│   ├── reset       # Reset and halt
│   ├── step        # Single step
│   ├── pc          # Show program counter
│   ├── regs        # Show all registers
│   ├── stack       # Show stack (N words)
│   └── gdb         # Show/launch GDB
│
├── mem             # Memory inspection
│   ├── read        # Read memory words
│   ├── vectors     # Show vector table
│   ├── dump        # Dump N words from flash
│   └── save        # Save region to file
│
├── flash           # Flash programming
│   ├── program     # Program firmware
│   ├── erase       # Mass erase (dangerous!)
│   ├── verify      # Verify against file
│   ├── read        # Read flash to file
│   ├── info        # Show flash bank info
│   ├── analyze     # Analyze firmware layout
│   └── identify    # Identify build type
│
├── serial          # Serial/REPL communication
│   ├── list        # List serial devices
│   ├── repl        # Test REPL connection
│   ├── console     # Interactive console (screen)
│   ├── test        # Quick serial test
│   └── boot        # Reset and capture boot output
│
└── repl            # MicroPython REPL interaction
    ├── exec        # Execute Python code
    ├── info        # Show board info
    ├── modules     # List available modules
    ├── help        # Show MicroPython help
    ├── hello       # Display message on screen
    ├── import      # Import module, show output
    ├── reset       # Soft-reset (Ctrl-D)
    ├── ls          # List files
    ├── cat         # Print file contents
    ├── cp          # Copy file to/from board
    └── rm          # Remove file
```

## Quick Start

1. Connect: microUSB (ST-LINK) + miniUSB (USB OTG)
2. `disco ocd connect` - Start OpenOCD
3. `disco cables` - Verify connections
4. `disco doctor` - Run full diagnostics

## Common Workflows

**First thing when board misbehaves:**
```
disco ocd connect
disco doctor          # Automated fault analysis with logging
```
Doctor checks: OpenOCD, JTAG, fault registers, FPU, vectors, USB/REPL.
Logs saved to `/tmp/disco_log/`.

**Debug crash manually:**
```
disco cpu regs        # Check registers
disco mem vectors     # Verify vector table
disco cpu stack 16    # Inspect stack
```

**Flash firmware:**
```
disco flash program firmware.bin --address 0x08000000
disco flash verify firmware.bin && disco cpu reset
```

**MicroPython interaction:**
```
disco repl exec "print('hello')"
disco repl ls / && disco repl cat /main.py
disco repl cp local.py :/main.py
```

## Memory Map

| Region      | Address    | Size  |
|-------------|------------|-------|
| Bootloader  | 0x08000000 | 128K  |
| Firmware    | 0x08020000 | 1.75M |
| RAM         | 0x20000000 | 320K  |
| SDRAM       | 0xC0000000 | 16M   |

## Beads Workflow

When you discover useful board interactions or debug techniques:
```
bd create "disco: <brief discovery description>"
# ... document commands and output ...
bd close
```

Examples worth capturing:
- New debug techniques for specific fault types
- Workarounds for hardware quirks
- Useful memory inspection patterns
- Firmware identification methods

This builds institutional knowledge about the board.
"""


@click.command()
@click.option("--raw", is_flag=True, help="Output without formatting")
def quickstart(raw: bool):
    """Output AI agent context for disco tool.

    Prints command reference and workflows for AI agents.
    Use in Claude Code hooks (SessionStart, PreCompact).
    """
    click.echo(QUICKSTART_TEXT)
