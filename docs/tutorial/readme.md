# Tutorial

This is a step-by-step tutorial that will guide you through the process of setting up the board, working with hardware peripherals, display and bitcoin library.

We will start with an [online simulator](https://diybitcoinhardware.com/f469-disco/simulator/index.html) so at first there is no need in real hardware, then we will continue with the real board and unix emulator.

Every step of the tutorial contains a final `main.py` script that you can upload to the board and see how it works. There are also jupyter notebooks that explain what is happening and allow you to communicate with the board interactively.

We recommend to start with online emulator, then proceed to jupyter notebooks and look at the final `main.py` files.

# Jupyter notebook setup

Setup jupyter notebook MicroPython kernel ([instructions](https://github.com/goatchurchprime/jupyter_micropython_kernel)).

# Table of contents

- [1_blinky](./1_blinky) - board setup and blinking with LEDs
- [2_gui](./2_gui) - how to work with a display and [littlevgl](https://littlevgl.com/) library
- [3_bitcoin](./3_bitcoin) - generating a recovery phrase, deriving keys from HD wallet and printing addresses
- [4_addresses](./4_addresses) - a small app that displays addresses, navigates through them and stores the last shown address
- [5_psbt](./5_psbt) - parding, displaying and signing psbt transactions
