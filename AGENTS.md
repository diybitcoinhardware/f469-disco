# f469-disco

MicroPython firmware for STM32F469-Discovery board with Bitcoin/crypto focus.

**Includes:** secp256k1 bindings, embit bitcoin library, LVGL GUI

**Use case:** DIY Bitcoin hardware wallet development

## Setup

```
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Build

```
make disco   # firmware → bin/upy-f469disco.bin
make unix    # simulator → bin/micropython_unix
make test    # run tests
```

## Board Interaction

For ANY interaction with the physical board, run:
```
./scripts/disco quickstart
```

This gives you the full command reference for:
- OpenOCD/JTAG debugging
- Flash programming
- MicroPython REPL
- Diagnostics

## Beads Workflow

Use `bd` for issue tracking. See `bd quickstart` for commands.

When discovering useful board interactions or debug techniques:
```
bd create "disco: <brief description>"
# ... work ...
bd close
```
