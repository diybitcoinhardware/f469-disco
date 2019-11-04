#include "lv_stm_hal.h"
#include "lv_conf.h"
#include "lvgl/src/lv_hal/lv_hal.h"
#include "stm32469i_discovery_lcd.h"
#include "stm32469i_discovery_ts.h"

static lv_disp_drv_t disp_drv;
static lv_disp_t * disp;

/*These 3 functions are needed by LittlevGL*/
static void tft_flush(lv_disp_drv_t * drv, const lv_area_t * area, lv_color_t * color_p);
static void gpu_mem_blend(lv_disp_drv_t * drv, lv_color_t * dest, const lv_color_t * src, uint32_t length, lv_opa_t opa);
static void gpu_mem_fill(lv_disp_drv_t * disp_drv, lv_color_t * dest_buf, lv_coord_t dest_width,
        const lv_area_t * fill_area, lv_color_t color);

void tft_init(){
    BSP_LCD_Init();
    BSP_LCD_InitEx(LCD_ORIENTATION_PORTRAIT);
    BSP_LCD_LayerDefaultInit(LTDC_ACTIVE_LAYER_BACKGROUND, LCD_FB_START_ADDRESS);
    BSP_LCD_SelectLayer(LTDC_ACTIVE_LAYER_BACKGROUND);
    BSP_LCD_Clear(0xFFFFFFFF);
    BSP_LCD_SetBackColor(0xFFFFFFFF);

	// FIXME: try two full-screen buffers in SRAM
	static lv_color_t disp_buf1[LV_HOR_RES_MAX * 30];
	static lv_disp_buf_t buf;
	lv_disp_buf_init(&buf, disp_buf1, NULL, LV_HOR_RES_MAX * 30);
	lv_disp_drv_init(&disp_drv);


	disp_drv.buffer = &buf;
	disp_drv.flush_cb = tft_flush;
// #if TFT_USE_GPU != 0
  // DMA2D_Config();
  // disp_drv.gpu_blend_cb = gpu_mem_blend;
  // disp_drv.gpu_fill_cb = gpu_mem_fill;
// #endif
	disp = lv_disp_drv_register(&disp_drv);

}

static void tft_flush(lv_disp_drv_t * drv, const lv_area_t * area, lv_color_t * color_p){

#if LV_COLOR_DEPTH == 32
    /* Copy pixed data line by line using DMA */
    uint8_t result = LCD_ERROR;

    if(area->x2 >= area->x1 && area->y2 >= area->y1 && color_p) {
      result = BSP_LCD_DrawBitmapRaw( area->x1, area->y1, 
                                      area->x2 - area->x1 + 1, 
                                      area->y2 - area->y1 + 1,
                                      LV_COLOR_DEPTH, color_p );
    }
    if(result != LCD_OK) return;
#else
    /*The most simple case (but also the slowest) to put all pixels to the screen one-by-one*/
    uint16_t x, y;
    for(y = area->y1; y <= area->y2; y++) {
        for(x = area->x1; x <= area->x2; x++) {
        	uint32_t color = lv_color_to32(color_p[0]);
            BSP_LCD_DrawPixel(x, y, color);
            color_p++;
        }
    }
#endif    

    /* IMPORTANT!!!
     * Inform the graphics library that you are ready with the flushing*/
    lv_disp_flush_ready(&disp_drv);
}

static void gpu_mem_blend(lv_disp_drv_t * drv, lv_color_t * dest, const lv_color_t * src, uint32_t length, lv_opa_t opa){

}

static void gpu_mem_fill(lv_disp_drv_t * disp_drv, lv_color_t * dest_buf, lv_coord_t dest_width,
        const lv_area_t * fill_area, lv_color_t color){

}


/**************** touchpad ****************/

static bool touchpad_read(lv_indev_drv_t * drv, lv_indev_data_t *data);
static TS_StateTypeDef  TS_State;

void touchpad_init(){
  BSP_TS_Init(LV_HOR_RES_MAX, LV_VER_RES_MAX);

  lv_indev_drv_t indev_drv;
  lv_indev_drv_init(&indev_drv);
  indev_drv.read_cb = touchpad_read;
  indev_drv.type = LV_INDEV_TYPE_POINTER;
  lv_indev_drv_register(&indev_drv);
}

static bool touchpad_read(lv_indev_drv_t * drv, lv_indev_data_t *data)
{
	static int16_t last_x = 0;
	static int16_t last_y = 0;

	BSP_TS_GetState(&TS_State);
	if(TS_State.touchDetected != 0) {
		data->point.x = TS_State.touchX[0];
		data->point.y = TS_State.touchY[0];
		last_x = data->point.x;
		last_y = data->point.y;
		data->state = LV_INDEV_STATE_PR;
	} else {
		data->point.x = last_x;
		data->point.y = last_y;
		data->state = LV_INDEV_STATE_REL;
	}

	return false;
}