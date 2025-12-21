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

## Landing the Plane (Session Completion)

**When ending a work session**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** - Create issues for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **PUSH TO REMOTE** - This is MANDATORY:
   ```bash
   git pull --rebase
   bd sync
   git push
   git status  # MUST show "up to date with origin"
   ```
5. **Clean up** - Clear stashes, prune remote branches
6. **Verify** - All changes committed AND pushed
7. **Hand off** - Provide context for next session

**CRITICAL RULES:**
- Work is NOT complete until `git push` succeeds
- NEVER stop before pushing - that leaves work stranded locally
- NEVER say "ready to push when you are" - YOU must push
- If push fails, resolve and retry until it succeeds
