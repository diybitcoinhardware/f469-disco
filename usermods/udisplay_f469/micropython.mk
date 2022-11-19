DISPLAY_MOD_DIR := $(USERMOD_DIR)

# custom font
SRC_USERMOD += $(DISPLAY_MOD_DIR)/fonts/custom_symbols_16.c

# stm32f469
ifeq ($(CMSIS_MCU),STM32F469xx)
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
SRC_USERMOD += $(DISPLAY_MOD_DIR)/BSP_DISCO_F469NI/Drivers/BSP/Components/nt35510/nt35510.c

# Touchscreen support
SRC_USERMOD += $(DISPLAY_MOD_DIR)/BSP_DISCO_F469NI/Drivers/BSP/STM32469I-Discovery/stm32469i_discovery_ts.c
SRC_USERMOD += $(DISPLAY_MOD_DIR)/BSP_DISCO_F469NI/Drivers/BSP/Components/ft6x06/ft6x06.c

# FIXME: this should be included automatically 
# as these files are in micropython repo as well
# Probably changes in mpboardconfigport.mk or some #defines can help
SRC_USERMOD += $(DISPLAY_MOD_DIR)/STM32F4xx_HAL_Driver/stm32f4xx_hal_dsi.c
SRC_USERMOD += $(DISPLAY_MOD_DIR)/STM32F4xx_HAL_Driver/stm32f4xx_hal_ltdc.c
SRC_USERMOD += $(DISPLAY_MOD_DIR)/STM32F4xx_HAL_Driver/stm32f4xx_hal_ltdc_ex.c
SRC_USERMOD += $(DISPLAY_MOD_DIR)/STM32F4xx_HAL_Driver/stm32f4xx_hal_dma2d.c

# lvgl support
LVGL_DIR := $(DISPLAY_MOD_DIR)
include $(LVGL_DIR)/lvgl/lvgl.mk
SRC_USERMOD += $(CSRCS)
CFLAGS_USERMOD += $(CFLAGS)

# display driver
SRC_USERMOD += $(DISPLAY_MOD_DIR)/lv_stm_hal/lv_stm_hal.c
# square font
SRC_USERMOD += $(DISPLAY_MOD_DIR)/fonts/square.c
# roboto mono font
SRC_USERMOD += $(DISPLAY_MOD_DIR)/fonts/font_roboto_mono_28.c
SRC_USERMOD += $(DISPLAY_MOD_DIR)/fonts/font_roboto_mono_22.c
SRC_USERMOD += $(DISPLAY_MOD_DIR)/fonts/font_roboto_mono_16.c
SRC_USERMOD += $(DISPLAY_MOD_DIR)/fonts/font_roboto_mono_12.c
# px_img class
SRC_USERMOD += $(DISPLAY_MOD_DIR)/pixelart/px_img.c

# Dirs with header files
CFLAGS_USERMOD += -I$(DISPLAY_MOD_DIR)
CFLAGS_USERMOD += -I$(DISPLAY_MOD_DIR)/lvgl
CFLAGS_USERMOD += -I$(DISPLAY_MOD_DIR)/lv_stm_hal
CFLAGS_USERMOD += -I$(DISPLAY_MOD_DIR)/pixelart
CFLAGS_USERMOD += -I$(DISPLAY_MOD_DIR)/BSP_DISCO_F469NI
CFLAGS_USERMOD += -I$(DISPLAY_MOD_DIR)/BSP_DISCO_F469NI/Drivers/BSP/STM32469I-Discovery

endif

ifneq ($(UNAME_S),)
# unixport (mac / linux)

# The module itself
SRC_USERMOD += $(DISPLAY_MOD_DIR)/display_unix.c
SRC_USERMOD += $(DISPLAY_MOD_DIR)/display_unix_sdl.c
SRC_USERMOD += $(DISPLAY_MOD_DIR)/lv_sdl_hal/SDL/SDL_monitor.c
SRC_USERMOD += $(DISPLAY_MOD_DIR)/lv_sdl_hal/SDL/SDL_mouse.c

# lvgl support
LVGL_DIR := $(DISPLAY_MOD_DIR)
include $(LVGL_DIR)/lvgl/lvgl.mk
SRC_USERMOD += $(CSRCS)
CFLAGS_USERMOD += $(CFLAGS)

# square font
SRC_USERMOD += $(DISPLAY_MOD_DIR)/fonts/square.c
# roboto mono font
SRC_USERMOD += $(DISPLAY_MOD_DIR)/fonts/font_roboto_mono_28.c
SRC_USERMOD += $(DISPLAY_MOD_DIR)/fonts/font_roboto_mono_22.c
SRC_USERMOD += $(DISPLAY_MOD_DIR)/fonts/font_roboto_mono_16.c
SRC_USERMOD += $(DISPLAY_MOD_DIR)/fonts/font_roboto_mono_12.c
# px_img class
SRC_USERMOD += $(DISPLAY_MOD_DIR)/pixelart/px_img.c

# Dirs with header files
CFLAGS_USERMOD += -I$(DISPLAY_MOD_DIR)
CFLAGS_USERMOD += -I$(DISPLAY_MOD_DIR)/lvgl
CFLAGS_USERMOD += -I$(DISPLAY_MOD_DIR)/pixelart
CFLAGS_USERMOD += -I$(DISPLAY_MOD_DIR)/lv_sdl_hal/SDL

LDFLAGS_MOD += -lSDL2

endif
