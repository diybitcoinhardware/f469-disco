TARGET_DIR = bin
BOARD ?= STM32F469DISC
USER_C_MODULES ?= ../../../usermods
MPY_DIR ?= micropython
EMBIT_INIT ?= libs/common/embit/src/embit/__init__.py
FROZEN_MANIFEST_EMPTY ?= ../../../manifests/empty.py
FROZEN_MANIFEST_FULL ?= ../../../manifests/disco.py
FROZEN_MANIFEST_UNIX ?= ../../../manifests/unix.py
DEBUG ?= 0

$(TARGET_DIR):
	mkdir -p $(TARGET_DIR)

# check submodules
$(MPY_DIR)/mpy-cross/Makefile:
	git submodule update --init --recursive

$(EMBIT_INIT): | $(MPY_DIR)/mpy-cross/Makefile
	git submodule update --init --recursive

# cross-compiler
mpy-cross: $(TARGET_DIR) $(MPY_DIR)/mpy-cross/Makefile $(EMBIT_INIT)
	@echo Building cross-compiler
	make -C $(MPY_DIR)/mpy-cross \
	DEBUG=$(DEBUG) && \
	cp $(MPY_DIR)/mpy-cross/mpy-cross $(TARGET_DIR)

# disco board without bitcoin frozen library
empty: $(TARGET_DIR) mpy-cross $(MPY_DIR)/ports/stm32
	@echo Building binary without frozen files
	make -C $(MPY_DIR)/ports/stm32 \
		BOARD=$(BOARD) \
		USER_C_MODULES=$(USER_C_MODULES) \
		FROZEN_MANIFEST=$(FROZEN_MANIFEST_EMPTY) \
		DEBUG=$(DEBUG) && \
	arm-none-eabi-objcopy -O binary \
		$(MPY_DIR)/ports/stm32/build-STM32F469DISC/firmware.elf \
		$(TARGET_DIR)/upy-f469disco-empty.bin

# disco board with bitcoin library
disco: $(TARGET_DIR) mpy-cross $(MPY_DIR)/ports/stm32
	@echo Building binary with frozen files
	make -C $(MPY_DIR)/ports/stm32 \
		BOARD=$(BOARD) \
		USER_C_MODULES=$(USER_C_MODULES) \
		FROZEN_MANIFEST=$(FROZEN_MANIFEST_FULL) \
		DEBUG=$(DEBUG) && \
	arm-none-eabi-objcopy -O binary \
		$(MPY_DIR)/ports/stm32/build-STM32F469DISC/firmware.elf \
		$(TARGET_DIR)/upy-f469disco.bin

# unixport (simulator)
unix: $(TARGET_DIR) mpy-cross $(MPY_DIR)/ports/unix
	@echo Building binary with frozen files
	make -C $(MPY_DIR)/ports/unix \
		USER_C_MODULES=$(USER_C_MODULES) \
		FROZEN_MANIFEST=$(FROZEN_MANIFEST_UNIX) && \
	cp $(MPY_DIR)/ports/unix/micropython $(TARGET_DIR)/micropython_unix

simulate: unix
	$(TARGET_DIR)/micropython_unix

frozen-import-smoke: unix
	cd /tmp && $(abspath $(TARGET_DIR)/micropython_unix) -c 'import asyncio; import asyncio.core; import microur.encoder; import microur.decoder; import microur.util.bytewords; import embit.bip39; import embit.bip85; import embit.compact; import embit.ec; import embit.hashes; import embit.networks; import embit.psbt; import embit.psbtview; import embit.script; import embit.transaction; import embit.descriptor; import embit.descriptor.arguments; import embit.descriptor.checksum; import embit.liquid; import embit.liquid.addresses; import embit.liquid.descriptor; import embit.liquid.networks; import embit.liquid.pset; import embit.liquid.psetview; import embit.liquid.slip77; import embit.liquid.transaction'

test: unix frozen-import-smoke
	$(TARGET_DIR)/micropython_unix tests/run_tests.py

all: mpy-cross empty disco unix

clean:
	rm -rf $(TARGET_DIR)
	make -C $(MPY_DIR)/mpy-cross clean
	make -C $(MPY_DIR)/ports/unix \
		USER_C_MODULES=$(USER_C_MODULES) \
		FROZEN_MANIFEST=$(FROZEN_MANIFEST_UNIX) clean
	make -C $(MPY_DIR)/ports/stm32 \
		BOARD=$(BOARD) \
		USER_C_MODULES=$(USER_C_MODULES) clean

.PHONY: all clean frozen-import-smoke
