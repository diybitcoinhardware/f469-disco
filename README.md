# MicroPython Bitcoin bundle for microcontrollers

Focusing on F469-Discovery board from STMicroelectronics, planning to add other boards later as well.

Build includes: [secp256k1](https://github.com/bitcoin-core/secp256k1) bindings, bitcoin python library, [LittlevGL](https://littlevgl.com/) GUI library

## Quick start

Check out the [documentation](./docs) folder for a tutorial and API of crypto modules.

Some examples are located in the [examples](./examples) folder.

To get micropython running on the board:
- Download the latest `upy-f469disco.bin` file from [releases](https://github.com/diybitcoinhardware/f469-disco/releases)
- Make sure your power jumper on the board is set to STLK position
- Connect the board to your computer with miniUSB cable
- Copy the `upy-f469disco.bin` file to mounted `F469NI_DISCO` volume
- Wait until it unmounts
- Connect the board with microUSB cable (on the other side of the board)
- Use `screen` or `miniterm` or whatever you like to connect to a virtual serial port that appears on your system
- Have fun with MicroPython on the board! Type `help('modules')` there to get information about installed modules.

## Build

Clone this repo recursively - we have many submodules. If you forgot - makefile will do it for you, but be patient, submodules are pretty large.

### Prerequisities: Board

To compile the firmware for the board you will need `arm-none-eabi-gcc` compiler.

On **MacOS** install it using brew: 
```sh
brew install arm-none-eabi-gcc
```

On **Linux**: 
```sh
sudo apt-get install gcc-arm-none-eabi binutils-arm-none-eabi gdb-multiarch openocd
```

On **Windows**: Install linux subsystem and follow Linux instructions.

### Prerequisities: Simulator

You may need to install SDL2 library to simulate the screen of the device.

**Linux**: 
```sh
sudo apt install libsdl2-dev
```

**MacOS**: 
```sh
brew install sdl2
```

**Windows**: 
- `sudo apt install libsdl2-dev` on Linux side 
- install and launch [Xming](https://sourceforge.net/projects/xming/) on Windows side
- set `export DISPLAY=:0` on linux part

### Compilation

We use makefiles. All resulting binaries will end up in the `bin` folder.

- `make disco` - firmware for the board with frozen bitcoin library `bin/upy-f469disco.bin`
- `make empty` - firmware for the board without frozen library - `bin/upy-f469disco-empty.bin`
- `make unix` - compiles a simulator for mac/unix - `bin/micropython_unix`

To launch a simulator either run `bin/micropython_unix` or simly run `make simulate`.

If something is not working you can clean up with `make clean`

## Run Unittests

Currently unittests work only on linuxport, and there are... not many... Contributions are very welcome!

```
make test
```

## IDE Configuration

[Visual Studio Code configuration](/debug/vscode.md)
