// Include required definitions first.
#include "py/obj.h"
#include "py/runtime.h"
#include "py/builtin.h"
#include "stm32469i_discovery_lcd.h"
#include "stm32469i_discovery_ts.h"
#include "logo.h"

static TS_StateTypeDef  TS_State;

STATIC mp_obj_t display_init(mp_obj_t orientation){
    uint8_t or = mp_obj_get_int(orientation);
 	BSP_LCD_Init();
    if(or){
        BSP_LCD_InitEx(LCD_ORIENTATION_PORTRAIT);
        BSP_TS_Init(480, 800);
    }else{
        BSP_LCD_InitEx(LCD_ORIENTATION_LANDSCAPE);
        BSP_TS_Init(800, 480);
    }
    BSP_LCD_LayerDefaultInit(0, LCD_FB_START_ADDRESS);
    BSP_LCD_Clear(0xFFFFFFFF);

    return mp_const_none;
}
STATIC MP_DEFINE_CONST_FUN_OBJ_1(display_init_obj, display_init);


STATIC mp_obj_t display_clear(mp_obj_t color){
    uint32_t c = 0xFF000000 | (mp_obj_get_int(color) & 0xFFFFFF);
    BSP_LCD_Clear(c);

    return mp_const_none;
}
STATIC MP_DEFINE_CONST_FUN_OBJ_1(display_clear_obj, display_clear);


STATIC mp_obj_t display_print(mp_obj_t arg, mp_obj_t x_obj, mp_obj_t y_obj){

    mp_buffer_info_t bufinfo;
    mp_get_buffer_raise(arg, &bufinfo, MP_BUFFER_READ);

    int x = mp_obj_get_int(x_obj);
    int y = mp_obj_get_int(y_obj);

    BSP_LCD_DisplayStringAt(x, y, (uint8_t *)bufinfo.buf, LEFT_MODE);

    return mp_const_none;
}
STATIC MP_DEFINE_CONST_FUN_OBJ_3(display_print_obj, display_print);


STATIC mp_obj_t display_draw_logo(mp_obj_t x_obj, mp_obj_t y_obj, mp_obj_t scale_obj){

    uint16_t x = mp_obj_get_int(x_obj);
    uint16_t y = mp_obj_get_int(y_obj);
    uint16_t scale = mp_obj_get_int(scale_obj);

    draw_logo(x, y, scale);

    return mp_const_none;
}
STATIC MP_DEFINE_CONST_FUN_OBJ_3(display_draw_logo_obj, display_draw_logo);


/****************************** MODULE ******************************/

STATIC const mp_rom_map_elem_t display_module_globals_table[] = {
    { MP_ROM_QSTR(MP_QSTR___name__), MP_ROM_QSTR(MP_QSTR_display) },
    { MP_ROM_QSTR(MP_QSTR_init), MP_ROM_PTR(&display_init_obj) },
    { MP_ROM_QSTR(MP_QSTR_PORTRAIT), MP_ROM_INT(1) },
    { MP_ROM_QSTR(MP_QSTR_LANDSCAPE), MP_ROM_INT(0) },
    { MP_ROM_QSTR(MP_QSTR_clear), MP_ROM_PTR(&display_clear_obj) },
    { MP_ROM_QSTR(MP_QSTR_print), MP_ROM_PTR(&display_print_obj) },
    { MP_ROM_QSTR(MP_QSTR_draw_logo), MP_ROM_PTR(&display_draw_logo_obj) },
};
STATIC MP_DEFINE_CONST_DICT(display_module_globals, display_module_globals_table);

// Define module object.
const mp_obj_module_t display_user_cmodule = {
    .base = { &mp_type_module },
    .globals = (mp_obj_dict_t*)&display_module_globals,
};

// Register the module to make it available in Python
MP_REGISTER_MODULE(MP_QSTR_display, display_user_cmodule, MODULE_DISPLAY_ENABLED);