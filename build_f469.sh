#!/bin/bash
# mpy cross-compiler
pushd micropython/mpy-cross
make
popd
# f469 board
pushd micropython/ports/stm32
make BOARD=STM32F469DISC USER_C_MODULES=../../../usermods FROZEN_MANIFEST=../../../manifest_f469.py
arm-none-eabi-objcopy -O binary build-STM32F469DISC/firmware.elf ../../../upy-f469disco.bin
popd
