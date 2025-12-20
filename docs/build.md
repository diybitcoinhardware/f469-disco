# Build Guide

## Development Environment

### Nix Flake + direnv (Recommended)

Requires Nix >=2.7 with flakes enabled and direnv.

```bash
cd f469-disco
direnv allow
```

Environment activates automatically on entering the directory.

### nix-shell

```bash
nix develop
# or for legacy nix:
nix-shell
```

### Manual Setup

**Linux (Debian/Ubuntu):**
```bash
sudo apt-get install gcc-arm-none-eabi binutils-arm-none-eabi python3 libsdl2-dev
```

**macOS:**
```bash
brew tap ArmMbed/homebrew-formulae
brew install arm-none-eabi-gcc python3 sdl2
```

## Submodules

Initialize submodules (done automatically by make):
```bash
git submodule update --init --recursive
```

## Build Commands

```bash
make mpy-cross   # build cross-compiler (required first)
make disco       # firmware with frozen bitcoin lib → bin/upy-f469disco.bin
make empty       # minimal firmware → bin/upy-f469disco-empty.bin
make unix        # simulator → bin/micropython_unix
make test        # run tests
make simulate    # run simulator
make clean       # clean build artifacts
make all         # build everything
```

## Output Files

All binaries output to `bin/`:
- `upy-f469disco.bin` - full firmware
- `upy-f469disco-empty.bin` - minimal firmware
- `micropython_unix` - simulator binary
