# MicroPython + Bitcoin documentation

Check out our step-by-step [tutorial](./tutorial) that will guide you through the process of setting up the board, working with hardware peripherals, display and bitcoin library:

- [1_blinky](./tutorial/1_blinky) - board setup and blinking with LEDs
- [2_gui](./tutorial/2_gui) - how to work with a display and [littlevgl](https://littlevgl.com/) library
- [3_bitcoin](./tutorial/3_bitcoin) - generating a recovery phrase, deriving keys from HD wallet and printing addresses
- [4_addresses](./tutorial/4_addresses) - a small app that displays addresses, navigates through them and stores the last shown address
- [5_psbt](./tutorial/5_psbt) - parding, displaying and signing psbt transactions

[API](./api) folder contains documentation on different modules included in the distribution:

- [bitcoin](./api/bitcoin) module written in pure Python with support of private/public keys, HD wallets, PSBT transactions, scripts, addresses etc.
- [hashlib](./api/hashlib) module with binding to C for necessary hash functions
- [secp256k1](./api/secp256k1) module with bindings to [secp256k1 library from Bitcoin Core](https://github.com/bitcoin-core/secp256k1)
