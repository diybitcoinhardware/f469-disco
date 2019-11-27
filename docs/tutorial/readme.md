# Tutorial

This is a step-by-step tutorial that will guide you through the process of setting up the board, working with hardware peripherals, display and bitcoin library.

We will start with an [online simulator](https://diybitcoinhardware.com/f469-disco/simulator/) so at first there is no need in real hardware, then we will continue with the real board and unix emulator.

Every step of the tutorial contains a final `main.py` script that you can upload to the board and see how it works. There are also jupyter notebooks that explain what is happening and allow you to communicate with the board interactively.

We recommend to start with online emulator, then proceed to jupyter notebooks and look at the final `main.py` files.

# Jupyter notebook setup

Setup jupyter notebook MicroPython kernel ([instructions](https://github.com/goatchurchprime/jupyter_micropython_kernel)).

# Table of contents

- [1. Bitcoin](./1_bitcoin) - getting started with `bitcoin` module [(try online)](https://diybitcoinhardware.com/f469-disco/simulator/?script=https://raw.githubusercontent.com/diybitcoinhardware/f469-disco/master/docs/tutorial/1_bitcoin/main.py)
- [2. Addresses](./2_addresses_gui) - create a simple screen that navigates between addresses derived from bip32 recovery phrase [(try online)](https://diybitcoinhardware.com/f469-disco/simulator/?script=https://raw.githubusercontent.com/diybitcoinhardware/f469-disco/master/docs/tutorial/2_addresses_gui/main.py)
- [3. PSBT](./3_psbt) - parse PSBT transaction, print it and sign [(try online)](https://diybitcoinhardware.com/f469-disco/simulator/?script=https://raw.githubusercontent.com/diybitcoinhardware/f469-disco/master/docs/tutorial/3_psbt/main.py)
- [4. Mini wallet](./4_miniwallet) - create a minimal hardware wallet that can sign transactions, show addresses and master public key [(try online)](https://diybitcoinhardware.com/f469-disco/simulator/?script=https://raw.githubusercontent.com/diybitcoinhardware/f469-disco/master/docs/tutorial/4_miniwallet/main.py)
