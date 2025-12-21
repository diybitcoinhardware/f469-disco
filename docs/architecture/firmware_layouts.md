# Firmware Layouts

Documentation of STM32F469 firmware memory layouts for Specter DIY.

## Types of Firmware

### 1. Initial Firmware (`initial_firmware.bin`)

Complete firmware for fresh device programming. Contains:
- **Startup code** (0x0000-0x2000): Vector table and early init
- **Bootloader** (0x3000-0x4000): Secure bootloader with integrity checks
- **Flash storage area** (0x4000-0x20000): Reserved for LittleFS filesystem
- **Main firmware** (0x20000+): Specter DIY application

Built by: `specter-diy/build_firmware.sh assemble`
Tool: `bootloader/tools/make-initial-firmware.py`

### 2. Upgrade Firmware (`specter_upgrade.bin`)

Signed firmware for OTA updates. Only contains main firmware (no bootloader).
Requires existing bootloader to verify signature and flash.

Built by: `specter-diy/build_firmware.sh assemble`
Tool: `bootloader/tools/upgrade-generator.py`

### 3. Development Firmware (`specter-diy.bin`)

Main firmware without bootloader for development. Can be flashed directly
via JTAG without signature verification.

Built by: `specter-diy/build_firmware.sh nobootloader`

### 4. Vanilla MicroPython

Standard MicroPython without Specter DIY application. Has similar
bootloader/main structure but no version tag.

## Memory Map (STM32F469)

```
0x08000000  +------------------+
            | Startup/Vectors  | 8KB   (0x0000-0x2000)
0x08002000  +------------------+
            | Reserved         | 4KB   (0x2000-0x3000)
0x08003000  +------------------+
            | Bootloader       | 4KB   (0x3000-0x4000)
0x08004000  +------------------+
            | Flash Storage    | 112KB (0x4000-0x20000)
            | (LittleFS)       |       preserved during updates
0x08020000  +------------------+
            | Main Firmware    | ~1.3MB
            | (Specter DIY)    |
0x0816C000  +------------------+
            | Filesystem Area  | ~340KB (zeros/preserved)
0x081C0000  +------------------+
            | Additional Code  | ~100KB (modules/apps)
0x081E0000  +------------------+
            | Metadata/ICR     | integrity check records
0x08200000  +------------------+ (2MB Flash End)
```

## Build System

### Scripts

- `specter-diy/build_firmware.sh` - Main build orchestrator
  - `main` - Build main firmware with bootloader support
  - `bootloader` - Build secure bootloader
  - `assemble` - Combine into initial/upgrade binaries
  - `nobootloader` - Build development firmware
  - `sign` - Add vendor signatures

### Key Tools

- `bootloader/tools/make-initial-firmware.py` - Combines startup + bootloader + firmware
- `bootloader/tools/upgrade-generator.py` - Creates signed upgrade packages

## Version Tags

Specter DIY embeds version info as: `<version:tag10>XXXXXXXXXX</version:tag10>`

| Tag | Build Type |
|-----|------------|
| `0100900099` | Production (USB/REPL disabled at boot) |
| `0100900001` | Debug (USB/REPL enabled, runs hardwaretest.py) |
| `0000000001` | Development/unsigned |
| (none) | Vanilla MicroPython |

## Filesystem Preservation

Firmware with zero regions between code sections preserves existing flash data:
- Initial firmware: zeros at 0x4000-0x20000 preserve LittleFS
- Upgrade firmware: only overwrites main code area

## Fingerprint Analysis

The `disco flash fingerprint` command analyzes:
- **Static**: size, SHA256, regions, version tag, build type
- **Runtime**: JTAG, CPU state, USB CDC, REPL response

Note: Release firmware (production builds) do not have REPL enabled - `repl_responsive` will be False. Only debug/development builds expose the MicroPython REPL.

Region detection treats both 0x00 and 0xFF as blank (erased flash).

Labels:
- `bootloader` - Code in 0x0-0x20000 area (< 64KB)
- `main` - Largest code region (main firmware)
- `flash_storage` - Blank area at 0x4000-0x20000
- `preserved` - Other blank areas
- `metadata` - Small code regions (< 64KB, likely integrity records)
- `code` - Other code regions (additional modules)
