// Include required definitions first.
#include "py/obj.h"
#include "py/runtime.h"
#include "py/builtin.h"
#include "stm32469i_discovery_lcd.h"

STATIC mp_obj_t display_clear();

STATIC mp_obj_t display_init(){

 	BSP_LCD_Init();
    BSP_LCD_LayerDefaultInit(0, LCD_FB_START_ADDRESS);
    display_clear();

    return mp_const_none;
}
STATIC MP_DEFINE_CONST_FUN_OBJ_0(display_init_obj, display_init);


STATIC mp_obj_t display_clear(){

    BSP_LCD_Clear(LCD_COLOR_WHITE);

    return mp_const_none;
}
STATIC MP_DEFINE_CONST_FUN_OBJ_0(display_clear_obj, display_clear);


STATIC mp_obj_t display_print(mp_obj_t arg, mp_obj_t x_obj, mp_obj_t y_obj){

    mp_buffer_info_t bufinfo;
    mp_get_buffer_raise(arg, &bufinfo, MP_BUFFER_READ);

    int x = mp_obj_get_int(x_obj);
    int y = mp_obj_get_int(y_obj);

    BSP_LCD_DisplayStringAt(x, y, (uint8_t *)bufinfo.buf, LEFT_MODE);

    return mp_const_none;
}
STATIC MP_DEFINE_CONST_FUN_OBJ_3(display_print_obj, display_print);

/****************************** MODULE ******************************/

STATIC const mp_rom_map_elem_t display_module_globals_table[] = {
    { MP_ROM_QSTR(MP_QSTR___name__), MP_ROM_QSTR(MP_QSTR_display) },
    { MP_ROM_QSTR(MP_QSTR_init), MP_ROM_PTR(&display_init_obj) },
    { MP_ROM_QSTR(MP_QSTR_clear), MP_ROM_PTR(&display_clear_obj) },
    { MP_ROM_QSTR(MP_QSTR_print), MP_ROM_PTR(&display_print_obj) },
};
STATIC MP_DEFINE_CONST_DICT(display_module_globals, display_module_globals_table);

// Define module object.
const mp_obj_module_t display_user_cmodule = {
    .base = { &mp_type_module },
    .globals = (mp_obj_dict_t*)&display_module_globals,
};

// Register the module to make it available in Python
MP_REGISTER_MODULE(MP_QSTR_display, display_user_cmodule, MODULE_DISPLAY_ENABLED);