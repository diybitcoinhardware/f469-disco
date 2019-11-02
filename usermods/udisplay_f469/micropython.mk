DISPLAY_MOD_DIR := $(USERMOD_DIR)

# The module itself
SRC_USERMOD += $(DISPLAY_MOD_DIR)/display.c

# LCD display support
SRC_USERMOD += $(DISPLAY_MOD_DIR)/BSP_DISCO_F469NI/Utilities/Fonts/font12.c
SRC_USERMOD += $(DISPLAY_MOD_DIR)/BSP_DISCO_F469NI/Utilities/Fonts/font16.c
SRC_USERMOD += $(DISPLAY_MOD_DIR)/BSP_DISCO_F469NI/Utilities/Fonts/font20.c
SRC_USERMOD += $(DISPLAY_MOD_DIR)/BSP_DISCO_F469NI/Utilities/Fonts/font24.c
SRC_USERMOD += $(DISPLAY_MOD_DIR)/BSP_DISCO_F469NI/Utilities/Fonts/font8.c
SRC_USERMOD += $(DISPLAY_MOD_DIR)/BSP_DISCO_F469NI/Drivers/BSP/STM32469I-Discovery/stm32469i_discovery.c
SRC_USERMOD += $(DISPLAY_MOD_DIR)/BSP_DISCO_F469NI/Drivers/BSP/STM32469I-Discovery/stm32469i_discovery_lcd.c
SRC_USERMOD += $(DISPLAY_MOD_DIR)/BSP_DISCO_F469NI/Drivers/BSP/STM32469I-Discovery/stm32469i_discovery_sdram.c
SRC_USERMOD += $(DISPLAY_MOD_DIR)/BSP_DISCO_F469NI/Drivers/BSP/Components/otm8009a/otm8009a.c

# Touchscreen support
SRC_USERMOD += $(DISPLAY_MOD_DIR)/BSP_DISCO_F469NI/Drivers/BSP/STM32469I-Discovery/stm32469i_discovery_ts.c
SRC_USERMOD += $(DISPLAY_MOD_DIR)/BSP_DISCO_F469NI/Drivers/BSP/Components/ft6x06/ft6x06.c

# Sample extra functions
SRC_USERMOD += $(DISPLAY_MOD_DIR)/nanogui/logo.c

# FIXME: this should be included automatically 
# as these files are in micropython repo as well
# Probably changes in mpboardconfigport.mk or some #defines can help
SRC_USERMOD += $(DISPLAY_MOD_DIR)/STM32F4xx_HAL_Driver/stm32f4xx_hal_dsi.c
SRC_USERMOD += $(DISPLAY_MOD_DIR)/STM32F4xx_HAL_Driver/stm32f4xx_hal_ltdc.c
SRC_USERMOD += $(DISPLAY_MOD_DIR)/STM32F4xx_HAL_Driver/stm32f4xx_hal_ltdc_ex.c
SRC_USERMOD += $(DISPLAY_MOD_DIR)/STM32F4xx_HAL_Driver/stm32f4xx_hal_dma2d.c

# Dirs with header files
CFLAGS_USERMOD += -I$(DISPLAY_MOD_DIR)/BSP_DISCO_F469NI
CFLAGS_USERMOD += -I$(DISPLAY_MOD_DIR)/BSP_DISCO_F469NI/Drivers/BSP/STM32469I-Discovery
CFLAGS_USERMOD += -I$(DISPLAY_MOD_DIR)/nanogui
