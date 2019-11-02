// Include required definitions first.
#include "py/obj.h"
#include "py/runtime.h"
#include "py/builtin.h"
#include "lvgl.h"
#include "lv_stm_hal.h"

STATIC mp_obj_t display_init(){
    lv_init();
    tft_init();
    touchpad_init();
    return mp_const_none;
}
STATIC MP_DEFINE_CONST_FUN_OBJ_0(display_init_obj, display_init);

STATIC mp_obj_t display_update(mp_obj_t dt_obj){
    uint32_t dt = mp_obj_get_int(dt_obj);
    lv_tick_inc(dt);
    lv_task_handler();
    return mp_const_none;
}
STATIC MP_DEFINE_CONST_FUN_OBJ_1(display_update_obj, display_update);

/****************************** MODULE ******************************/

STATIC const mp_rom_map_elem_t display_module_globals_table[] = {
    { MP_ROM_QSTR(MP_QSTR___name__), MP_ROM_QSTR(MP_QSTR_display) },
    { MP_ROM_QSTR(MP_QSTR_init), MP_ROM_PTR(&display_init_obj) },
    { MP_ROM_QSTR(MP_QSTR_update), MP_ROM_PTR(&display_update_obj) },
};
STATIC MP_DEFINE_CONST_DICT(display_module_globals, display_module_globals_table);

// Define module object.
const mp_obj_module_t display_user_cmodule = {
    .base = { &mp_type_module },
    .globals = (mp_obj_dict_t*)&display_module_globals,
};

// #include "lvgl_mpy.c"
#include "lv_mpy_example.c"

// Register the module to make it available in Python
MP_REGISTER_MODULE(MP_QSTR_display, display_user_cmodule, MODULE_DISPLAY_ENABLED);
MP_REGISTER_MODULE(MP_QSTR_lvgl, mp_module_lvgl, MODULE_DISPLAY_ENABLED);
