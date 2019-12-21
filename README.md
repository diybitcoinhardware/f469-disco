# (WIP) DIY Bitcoin Hardware Wallet with Touchscreen & QR Scanner in Micropython

## Quick start

Check out the [documentation](./docs) folder for a tutorial and API of crypto modules.

Some examples are located in the [examples](./examples) folder.

## Compile

To compile the firmware you will need `arm-none-eabi-gcc` compiler.

On MacOS install it using brew: `brew install arm-none-eabi-gcc`

On Linux: `sudo apt-get install gcc-arm-none-eabi binutils-arm-none-eabi gdb-arm-none-eabi openocd`

Run `./build_f469.sh` script, if everything goes well you will get a `upy-f469disco.bin` file in the root folder.

Run `./build_unixport.sh` to get unix version of micropython. You may need to install SDL2 library to work with the GUI (`sudo apt install libsdl2-dev` or `brew install sdl2`).

### STM32F469-Discovery board:

```
cd micropython/ports/stm32
make BOARD=STM32F469DISC USER_C_MODULES=../../../usermods
arm-none-eabi-objcopy -O binary build-STM32F469DISC/firmware.elf upy-f469disco.bin
```

Copy `upy-f469disco.bin` to the board (volume `DIS_469NI`, mini-usb port).

Micropython is now available over MiniUSB port (another one).

Recommended to work with SD card inserted. Micropython loads files from SD card first, so if you screwed up with the `main.py` file you can just remove SD card and fix it on your computer.

### Unix/Mac (requires SDL2 library):

```
cd micropython/ports/unix
make USER_C_MODULES=../../../usermods FROZEN_MANIFEST=../../../usermods/udisplay_f469/manifest.py
```

Now you can run `./micropython`

## Run Unittests

```
# Build unix firmware
./make_unix.sh

# Run unittests in unix firmware
./run_tests.sh
```
## IDE Configuration

[Visual Studio Code configuration](/debug/vscode.md)
