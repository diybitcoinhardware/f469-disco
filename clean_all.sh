#!/bin/bash
# mpy cross-compiler
make -C micropython/mpy-cross clean
# f469 board
make -C micropython/ports/stm32 BOARD=STM32F469DISC USER_C_MODULES=../../../usermods clean
# not sure if it does something
make -C micropython/ports/stm32 BOARD=STM32F469DISC USER_C_MODULES=../../../usermods FROZEN_MANIFEST=../../../manifest_f469.py clean
# unixport
make -C micropython/ports/unix USER_C_MODULES=../../../usermods FROZEN_MANIFEST=../../../manifest_unixport.py clean

rm micropython_unix
rm upy-f469disco-empty.bin
rm upy-f469disco.bin