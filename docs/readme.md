# MicroPython + Bitcoin documentation

Check out our step-by-step [tutorial](./tutorial) that will guide you through the process of setting up the board, working with hardware peripherals, display and bitcoin library:

## Simulator

You can also try out this micropython build in [online simulator](https://diybitcoinhardware.com/f469-disco/simulator/index.html). You can also load the scripts to the emulator by providing a `script` parameter, for example: [https://diybitcoinhardware.com/f469-disco/simulator/index.html?script=https://raw.githubusercontent.com/diybitcoinhardware/f469-disco/master/examples/gui/address_navigator.py](https://diybitcoinhardware.com/f469-disco/simulator/index.html?script=https://raw.githubusercontent.com/diybitcoinhardware/f469-disco/master/examples/gui/address_navigator.py).

## API documentation

[API](./api) folder contains documentation on different modules included in the distribution:

- [bitcoin](./api/bitcoin) module written in pure Python with support of private/public keys, HD wallets, PSBT transactions, scripts, addresses etc.
- [hashlib](./api/hashlib) module with binding to C for necessary hash functions
- [secp256k1](./api/secp256k1) module with bindings to [secp256k1 library from Bitcoin Core](https://github.com/bitcoin-core/secp256k1)
- [display](./api/display) module that helps you to work with the display and [LittlevGL](https://littlevgl.com/) library