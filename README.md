# (WIP) MicroPython Bitcoin bundle for microcontrollers

Focusing on F469-Discovery board from STMicroelectronics, possibly other boards later as well.

Build includes: secp256k1 bindings, bitcoin library, LittlevGL GUI library

## Quick start

Check out the [documentation](./docs) folder for a tutorial and API of crypto modules.

Some examples are located in the [examples](./examples) folder.

## Compile

To compile the firmware you will need `arm-none-eabi-gcc` compiler.

On MacOS install it using brew: `brew install arm-none-eabi-gcc`

On Linux: `sudo apt-get install gcc-arm-none-eabi binutils-arm-none-eabi gdb-arm-none-eabi openocd`

We have a set of small shell scripts that compile micropython for discovery board or unix/mac. Feel free to check out content of these scripts and tune it if you want:

### `./build_f469.sh` 

It will compile micropython with frozen bitcoin library. `secp256k1` and `lvgl` are still there though. You should see a `upy-f469disco.bin` file in the root folder when the script is done.

Freezing python files saves a lot of RAM, but then they can't be edited without rebuilding the firmware.

### `./build_f469_empty.sh`

This script does roughly the same as previous but doesn't freeze python bitcoin files - you can copy content of the `libs` folder to your board later and edit them without reflashing the board every time you change the library.

### `./build_unixport.sh`

Compiles unix version of micropython. You may need to install SDL2 library to work with the GUI (`sudo apt install libsdl2-dev` or `brew install sdl2`).

### `./clean_all.sh`

If you are having problems with the build try running this script - it will to `make clean` in all folders used in `build_...` scripts.

## Run Unittests

```
# Run unittests in unix firmware
./run_tests.sh
```

## IDE Configuration

[Visual Studio Code configuration](/debug/vscode.md)

## TODO:

refactor build scripts with Makefiles
