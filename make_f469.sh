pushd micropython/ports/stm32
make BOARD=STM32F469DISC USER_C_MODULES=../../../usermods
arm-none-eabi-objcopy -O binary build-STM32F469DISC/firmware.elf ../../../upy-f469disco.bin
popd
