# Firmware Test Box

Collection of firmware images for testing the disco tool and board behavior.

## Structure

Each firmware is in its own directory with:
- `*.bin` - firmware binary
- `fingerprint.yaml` - auto-generated metadata (use `disco flash fingerprint`)
- `*.hex` - optional Intel HEX format

## Firmware Summary

| Directory | Build | Size | Version Tag | Notes |
|-----------|-------|------|-------------|-------|
| `upy-current/` | unknown | 1.3MB | - | Vanilla MicroPython |
| `tadeu-autobuild/` | production | 1.5MB | 0100900099 | Specter DIY autobuild |
| `old/main/` | production | 1.5MB | 0100900099 | Older Specter DIY main |
| `old/debug/` | debug | 1.5MB | 0100900001 | Older Specter DIY debug |
| `new/main/` | production | 1.8MB | 0100900099 | Newer Specter DIY main |
| `new/debug/` | debug | 1.8MB | 0100900001 | Newer Specter DIY debug |
| `spflashbug/` | debug | 1.8MB | 0100900001 | Debug build for flash bug testing |

## Official Specter DIY Releases

Downloaded from https://github.com/cryptoadvance/specter-diy/releases

| Version | Type | Size | Notes |
|---------|------|------|-------|
| v1.0.0 - v1.3.0 | single | 1.0-1.2MB | Single `specter-diy.bin` file |
| v1.4.0 - v1.9.0 | initial/upgrade | 1.9MB/1.1-1.4MB | Separate initial and upgrade firmware |

Structure for v1.4.0+:
- `specter_releases/v1.X.0/initial/` - initial firmware (includes bootloader)
- `specter_releases/v1.X.0/upgrade/` - upgrade firmware (app only)

## Build Types

- **production** (tag `0100900099`): USB/REPL disabled at boot, enabled after PIN
- **debug** (tag `0100900001`): USB/REPL enabled by default, runs hardwaretest.py
- **unknown**: No version tag found (likely vanilla MicroPython)

## Usage

Generate fingerprint for a firmware:
```bash
disco flash fingerprint path/to/firmware.bin
```

Flash and test:
```bash
disco flash program path/to/firmware.bin
disco check
disco repl info  # if miniUSB connected
```

## Fingerprint Spec

The `fingerprint.yaml` format:

```yaml
name: string              # directory name (auto)
filename: string          # binary filename (auto)
static:                   # from binary analysis (auto)
  size_bytes: int
  sha256: string          # hex digest
  regions: list           # memory layout
    - start: hex          # e.g. "0x00000000"
      end: hex
      size: int
      type: code|zeros
      label: bootloader|main|preserved
  version_tag: string|null    # from <version:tag10>...</version:tag10>
  build_type: production|debug|unknown
  filesystem_preservation: bool   # has zero gap for LittleFS
runtime:                  # from hardware testing
  jtag_works: bool|null   # can read PC via JTAG
  cpu_runs: bool|null     # PC in firmware area and changing
  usb_cdc: bool|null      # USB OTG serial appears
  repl_responsive: bool|null  # MicroPython REPL responds
notes: string             # freeform notes
```

### Fingerprint Commands

```bash
# Create new fingerprint (fails if exists)
disco flash fingerprint create firmware.bin

# Update existing fingerprint (creates if missing)
disco flash fingerprint update firmware.bin

# Test against existing fingerprint
disco flash fingerprint test fingerprint.yaml
# Returns non-zero if differs, creates fingerprint_diff_<timestamp>.yaml
```

All commands run both static analysis and runtime hardware tests.
