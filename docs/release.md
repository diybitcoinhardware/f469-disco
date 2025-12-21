# Release Procedure

Releases are automated via GitHub Actions. Pushing a version tag triggers a build and creates a GitHub release.

## Creating a Release

```bash
git tag v1.4.0
git push origin v1.4.0
```

## What Happens

1. GitHub Actions checks out code with submodules
2. Builds `mpy-cross`, `disco`, `empty`, and `unix` targets
3. Runs tests
4. Creates release with:
   - `upy-f469disco.bin` - firmware with frozen bitcoin library
   - `upy-f469disco-empty.bin` - minimal firmware
   - Auto-generated release notes from commits

## Version Format

Tags must match `vX.Y.Z` pattern (e.g., `v1.4.0`, `v2.0.0-beta`).

## Manual Build

To build locally:

```bash
make mpy-cross
make disco      # bin/upy-f469disco.bin
make empty      # bin/upy-f469disco-empty.bin
```

## Requirements

- ARM toolchain (`arm-none-eabi-gcc`)
- Python 3
- SDL2 (for tests/simulator)
