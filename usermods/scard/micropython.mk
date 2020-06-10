SCARD_IO_MOD_DIR := $(USERMOD_DIR)

# disable for simulator
ifeq ($(UNAME_S),)

# Reduce FIFO size for T=1 protocol
CFLAGS_USERMOD += -DT1_TX_FIFO_SIZE=600

# Only STM32 series is currently supported
ifeq ($(MCU_SERIES),$(filter $(MCU_SERIES),f0 f4 f7 l0 l4 wb))

# Reproduce environment variables from main makefile (not defined at the moment)
SCARD_MPY_DIR = $(USERMOD_DIR)/../../micropython
SCARD_MCU_SERIES_UPPER = $(shell echo $(MCU_SERIES) | tr '[:lower:]' '[:upper:]')
SCARD_HAL_DIR = $(SCARD_MPY_DIR)/lib/stm32lib/STM32$(SCARD_MCU_SERIES_UPPER)xx_HAL_Driver

# Add all C files to SRC_USERMOD.
SRC_USERMOD += $(SCARD_IO_MOD_DIR)/scard.c
SRC_USERMOD += $(SCARD_IO_MOD_DIR)/reader.c
SRC_USERMOD += $(SCARD_IO_MOD_DIR)/connection.c
SRC_USERMOD += $(SCARD_IO_MOD_DIR)/protocols.c
SRC_USERMOD += $(SCARD_IO_MOD_DIR)/t1_protocol/t1_protocol.c
SRC_USERMOD += $(SCARD_IO_MOD_DIR)/ports/stm32/scard_io.c

# We can add our module folder to include paths if needed
CFLAGS_USERMOD += -I$(SCARD_IO_MOD_DIR)
CFLAGS_USERMOD += -I$(SCARD_IO_MOD_DIR)/t1_protocol
CFLAGS_USERMOD += -I$(SCARD_IO_MOD_DIR)/ports/stm32

else # MCU_SERIES == [f0, f4, f7, l0, l4, wb]

$(error Unsupported platform)

endif # MCU_SERIES == [f0, f4, f7, l0, l4, wb]

endif