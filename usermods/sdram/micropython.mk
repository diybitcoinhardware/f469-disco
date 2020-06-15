# Add all C files to SRC_USERMOD.
ifeq ($(CMSIS_MCU),STM32F469xx)

SRC_USERMOD += $(USERMOD_DIR)/sdram.c

endif
