# Tutorial

This is a step-by-step tutorial that will guide you through the process of setting up the board, working with hardware peripherals, display and bitcoin library.

We will start with an [online simulator](https://diybitcoinhardware.com/f469-disco/simulator/index.html) so at first there is no need in real hardware, then we will continue with the real board and unix emulator.

Every step of the tutorial contains a final `main.py` script that you can upload to the board and see how it works. There are also jupyter notebooks that explain what is happening and allow you to communicate with the board interactively.

We recommend to start with online emulator, then proceed to jupyter notebooks and look at the final `main.py` files.

# Jupyter notebook setup

Setup jupyter notebook MicroPython kernel ([instructions](https://github.com/goatchurchprime/jupyter_micropython_kernel)).

# Table of contents

- [1_bitcoin](./1_bitcoin) - getting started with `bitcoin` module [(try online)](https://diybitcoinhardware.com/f469-disco/simulator/index.html?script=https://raw.githubusercontent.com/diybitcoinhardware/f469-disco/master/docs/tutorial/1_bitcoin/main.py)
- [2_addresses](./2_addresses_gui) - create a simple screen that navigates between addresses derived from bip32 recovery phrase [(try online)](https://diybitcoinhardware.com/f469-disco/simulator/index.html?script=https://raw.githubusercontent.com/diybitcoinhardware/f469-disco/master/examples/gui/address_navigator.py)
- [3_blinky](./3_blinky) - blink with LEDs on the board (hardware only, jupyter notebook)
- [4_gui on hardware](./4_gui) - work with a display and a GUI library
- [5_psbt](./5_psbt) - parsing, displaying and signing psbt transactions
