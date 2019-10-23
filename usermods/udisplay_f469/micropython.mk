EXAMPLE_MOD_DIR := $(USERMOD_DIR)

# Add all C files to SRC_USERMOD.
SRC_USERMOD += $(EXAMPLE_MOD_DIR)/BSP_DISCO_F469NI/Utilities/Fonts/font12.c
SRC_USERMOD += $(EXAMPLE_MOD_DIR)/BSP_DISCO_F469NI/Utilities/Fonts/font16.c
SRC_USERMOD += $(EXAMPLE_MOD_DIR)/BSP_DISCO_F469NI/Utilities/Fonts/font20.c
SRC_USERMOD += $(EXAMPLE_MOD_DIR)/BSP_DISCO_F469NI/Utilities/Fonts/font24.c
SRC_USERMOD += $(EXAMPLE_MOD_DIR)/BSP_DISCO_F469NI/Utilities/Fonts/font8.c
SRC_USERMOD += $(EXAMPLE_MOD_DIR)/BSP_DISCO_F469NI/Drivers/BSP/STM32469I-Discovery/stm32469i_discovery.c
SRC_USERMOD += $(EXAMPLE_MOD_DIR)/BSP_DISCO_F469NI/Drivers/BSP/STM32469I-Discovery/stm32469i_discovery_lcd.c
SRC_USERMOD += $(EXAMPLE_MOD_DIR)/BSP_DISCO_F469NI/Drivers/BSP/STM32469I-Discovery/stm32469i_discovery_sdram.c
SRC_USERMOD += $(EXAMPLE_MOD_DIR)/BSP_DISCO_F469NI/Drivers/BSP/Components/otm8009a/otm8009a.c
SRC_USERMOD += $(EXAMPLE_MOD_DIR)/display.c
SRC_USERMOD += $(EXAMPLE_MOD_DIR)/STM32F4xx_HAL_Driver/stm32f4xx_hal_dsi.c
SRC_USERMOD += $(EXAMPLE_MOD_DIR)/STM32F4xx_HAL_Driver/stm32f4xx_hal_ltdc.c
SRC_USERMOD += $(EXAMPLE_MOD_DIR)/STM32F4xx_HAL_Driver/stm32f4xx_hal_ltdc_ex.c
SRC_USERMOD += $(EXAMPLE_MOD_DIR)/STM32F4xx_HAL_Driver/stm32f4xx_hal_dma2d.c

# We can add our module folder to include paths if needed
# This is not actually needed in this example.
CFLAGS_USERMOD += -I$(EXAMPLE_MOD_DIR)/BSP_DISCO_F469NI
CFLAGS_USERMOD += -I$(EXAMPLE_MOD_DIR)/BSP_DISCO_F469NI/Drivers/BSP/STM32469I-Discovery
