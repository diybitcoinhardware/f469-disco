#!/bin/bash
# mpy cross-compiler
pushd micropython/mpy-cross
make clean
popd
# f469 board
pushd micropython/ports/stm32
make BOARD=STM32F469DISC USER_C_MODULES=../../../usermods clean
# not sure if it does something
make BOARD=STM32F469DISC USER_C_MODULES=../../../usermods FROZEN_MANIFEST=../../../manifest_f469.py clean
popd

pushd micropython/ports/unix
make USER_C_MODULES=../../../usermods FROZEN_MANIFEST=../../../manifest_unixport.py clean
popd

rm micropython_unix
rm upy-f469disco-empty.bin
rm upy-f469disco.bin