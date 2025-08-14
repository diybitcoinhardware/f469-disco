#include "lv_stm_hal.h"
#include "lv_conf.h"
#include "lvgl/src/display/lv_display.h"
#include "lvgl/src/indev/lv_indev.h"
#include "stm32469i_discovery_lcd.h"
#include "stm32469i_discovery_ts.h"

static void tft_flush(lv_display_t * disp, const lv_area_t * area, uint8_t * px_map);

void tft_init(void) {
    BSP_LCD_Init();
    BSP_LCD_LayerDefaultInit(LTDC_ACTIVE_LAYER_BACKGROUND, LCD_FB_START_ADDRESS);
    BSP_LCD_SelectLayer(LTDC_ACTIVE_LAYER_BACKGROUND);
    BSP_LCD_Clear(0xFFFFFFFF);
    BSP_LCD_SetBackColor(0xFFFFFFFF);

	// FIXME: try two full-screen buffers in SRAM
	static lv_color_t buf1[LV_HOR_RES_MAX * 30];
    lv_display_t *disp = lv_display_create(LV_HOR_RES_MAX, LV_VER_RES_MAX);
    lv_display_set_flush_cb(disp, tft_flush);
    lv_display_set_buffers(disp, buf1, NULL, sizeof(buf1), LV_DISPLAY_RENDER_MODE_PARTIAL);
}

static void tft_flush(lv_display_t * disp, const lv_area_t * area, uint8_t * px_map) {

#if LV_COLOR_DEPTH == 32
    /* Copy pixel data line by line using DMA */
    uint8_t result = LCD_ERROR;

    if(area->x2 >= area->x1 && area->y2 >= area->y1 && px_map) {
      result = BSP_LCD_DrawBitmapRaw( area->x1, area->y1,
                                      area->x2 - area->x1 + 1,
                                      area->y2 - area->y1 + 1,
                                      LV_COLOR_DEPTH, px_map );
    }
    if(result != LCD_OK) return;
#else
#   error "Unsupported LV_COLOR_DEPTH"
#endif

    /* Inform the graphics library that you are ready with the flushing */
    lv_display_flush_ready(disp);
}

/**************** touchpad ****************/

static bool touchpad_read(lv_indev_t *indev, lv_indev_data_t *data);
static TS_StateTypeDef  TS_State;

void touchpad_init(void) {
    BSP_TS_Init(LV_HOR_RES_MAX, LV_VER_RES_MAX);

    lv_indev_t *indev = lv_indev_create();
    lv_indev_set_type(indev, LV_INDEV_TYPE_POINTER);
    lv_indev_set_read_cb(indev, touchpad_read);
}

static bool touchpad_read(lv_indev_t *indev, lv_indev_data_t *data) {
	static int16_t last_x = 0;
	static int16_t last_y = 0;

	BSP_TS_GetState(&TS_State);
	if(TS_State.touchDetected != 0) {
		data->point.x = TS_State.touchX[0];
		data->point.y = TS_State.touchY[0];
		last_x = data->point.x;
		last_y = data->point.y;
		data->state = LV_INDEV_STATE_PRESSED;
	} else {
		data->point.x = last_x;
		data->point.y = last_y;
		data->state = LV_INDEV_STATE_RELEASED;
	}

	return false;
}