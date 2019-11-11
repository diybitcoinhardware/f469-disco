# (WIP) DIY Bitcoin Hardware Wallet with Touchscreen & QR Scanner in Micropython

## Compile

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

