# f469-disco

MicroPython firmware for STM32F469-Discovery board with Bitcoin/crypto focus.

**Includes:** secp256k1 bindings, embit bitcoin library, LVGL GUI

**Use case:** DIY Bitcoin hardware wallet development

## Setup

**Nix (recommended):** The project has a `flake.nix` providing all build tools:
```bash
nix develop   # enters shell with arm-gcc, openocd, gdb, python, SDL2
```

**Python venv** (for disco tool only):
```bash
python3 -m venv .venv
.venv/bin/pip install -r scripts/requirements.txt
```

## Build

Requires Nix or manual install of arm-none-eabi-gcc toolchain.

```bash
nix develop -c make disco   # firmware → bin/upy-f469disco.bin
nix develop -c make unix    # simulator → bin/micropython_unix
nix develop -c make test    # run tests
```

Or inside `nix develop` shell:
```bash
make disco && make unix && make test
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

## Useful Resources

Before diving in, skim the docs that fit what you're doing:

**Board & debugging**
- [docs/debugging.md](docs/debugging.md) — JTAG/SWD via ST-LINK, OpenOCD, GDB, LED patterns, known issues (QSPI shadow dirs, SPI flash hang)
- [docs/architecture/firmware_layouts.md](docs/architecture/firmware_layouts.md) — memory map, initial vs upgrade vs dev firmwares, RDP/PCROP hazards (v1.4.0+ initial firmware locks the device)
- [tests/fwbox/README.md](tests/fwbox/README.md) — catalog of test firmwares (debug/main/vanilla) with fingerprints
- `./scripts/disco quickstart` — full disco-tool command reference

**Build & release**
- [docs/build.md](docs/build.md) — build commands and toolchain notes
- [docs/release.md](docs/release.md) — release process

**API**
- [docs/readme.md](docs/readme.md) — entry point to tutorial + API docs
- [docs/api/](docs/api/) — `bitcoin`, `secp256k1`, `hashlib`, `display` modules
- [docs/tutorial/](docs/tutorial/) — step-by-step hardware-wallet tutorial

## Landing the Plane (Session Completion)

**When ending a work session**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **Run quality gates** (if code changed) - Tests, linters, builds
2. **PUSH TO REMOTE** - This is MANDATORY:
   ```bash
   git pull --rebase
   git push
   git status  # MUST show "up to date with origin"
   ```
3. **Clean up** - Clear stashes, prune remote branches
4. **Verify** - All changes committed AND pushed
5. **Hand off** - Provide context for next session

**CRITICAL RULES:**
- Work is NOT complete until `git push` succeeds
- NEVER stop before pushing - that leaves work stranded locally
- NEVER say "ready to push when you are" - YOU must push
- If push fails, resolve and retry until it succeeds
