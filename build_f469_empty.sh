#!/bin/bash
# mpy cross-compiler
make -C micropython/mpy-cross
# f469 board
make -C micropython/ports/stm32 BOARD=STM32F469DISC USER_C_MODULES=../../../usermods FROZEN_MANIFEST=../../../manifest_f469_empty.py
arm-none-eabi-objcopy -O binary micropython/ports/stm32/build-STM32F469DISC/firmware.elf upy-f469disco-empty.bin
