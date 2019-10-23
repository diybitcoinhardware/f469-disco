# DIY Bitcoin Hardware Wallet with Touchscreen & QR Scanner in Micropython

## Run Unittests

```
# Build unix firmware
./make_unix.sh

# Run unittests in unix firmware
./run_tests.sh
```

## TODO

- Python 
    - Bitcoin
        - ECC
            - Use bytes internally, not integers
        - PSBT
            - Only support segwit
            - Unoptimized first version, then decrease memory footprint
        - HD wallets
    - Device
        - Serial driver
        - QR driver
        - Display driver (most work is on the C side)
    - Libwally?
        - We have a `gen_mpy` branch that attempted to auto-generate micropython bindings for libwally using [this approach](https://github.com/littlevgl/lv_binding_micropython/blob/master/gen/gen_mpy.py). It seemed very complex so we decided to postpone for now, but it should be attempted again in the future.
