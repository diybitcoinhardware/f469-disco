TARGET_DIR = bin
BOARD ?= STM32F469DISC
USER_C_MODULES ?= ../../../usermods
FROZEN_MANIFEST_EMPTY ?= ../../../manifests/empty.py
FROZEN_MANIFEST_FULL ?= ../../../manifests/disco.py
FROZEN_MANIFEST_UNIX ?= ../../../manifests/unix.py

$(TARGET_DIR):
	mkdir -p $(TARGET_DIR)

# check submodules
micropython/mpy-cross/Makefile:
	git submodule update --init --recursive

# cross-compiler
mpy-cross: $(TARGET_DIR) micropython/mpy-cross/Makefile
	@echo Building cross-compiler
	make -C micropython/mpy-cross && \
	cp micropython/mpy-cross/mpy-cross $(TARGET_DIR)

# disco board without bitcoin frozen library
empty: $(TARGET_DIR) mpy-cross micropython/ports/stm32
	@echo Building binary without frozen files
	make -C micropython/ports/stm32 \
		BOARD=$(BOARD) \
		USER_C_MODULES=$(USER_C_MODULES) \
		FROZEN_MANIFEST=$(FROZEN_MANIFEST) && \
	arm-none-eabi-objcopy -O binary \
		micropython/ports/stm32/build-STM32F469DISC/firmware.elf \
		$(TARGET_DIR)/upy-f469disco-empty.bin

# disco board with bitcoin library
disco: $(TARGET_DIR) mpy-cross micropython/ports/stm32
	@echo Building binary with frozen files
	make -C micropython/ports/stm32 \
		BOARD=$(BOARD) \
		USER_C_MODULES=$(USER_C_MODULES) \
		FROZEN_MANIFEST=$(FROZEN_MANIFEST_FULL) && \
	arm-none-eabi-objcopy -O binary \
		micropython/ports/stm32/build-STM32F469DISC/firmware.elf \
		$(TARGET_DIR)/upy-f469disco.bin

# unixport (simulator)
unix: $(TARGET_DIR) mpy-cross micropython/ports/unix
	@echo Building binary with frozen files
	make -C micropython/ports/unix \
		USER_C_MODULES=$(USER_C_MODULES) \
		FROZEN_MANIFEST=$(FROZEN_MANIFEST_UNIX) && \
	cp micropython/ports/unix/micropython $(TARGET_DIR)/micropython_unix

simulate: unix
	$(TARGET_DIR)/micropython_unix

test: unix
	$(TARGET_DIR)/micropython_unix tests/run_tests.py

all: mpy-cross empty disco unix

clean:
	rm -rf $(TARGET_DIR)
	make -C micropython/mpy-cross clean
	make -C micropython/ports/unix \
		USER_C_MODULES=$(USER_C_MODULES) \
		FROZEN_MANIFEST=$(FROZEN_MANIFEST_UNIX) clean
	make -C micropython/ports/stm32 \
		BOARD=$(BOARD) \
		USER_C_MODULES=$(USER_C_MODULES) clean

.PHONY: all clean
