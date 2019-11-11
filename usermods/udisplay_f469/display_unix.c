// // Include required definitions first.
// #include "py/obj.h"
// #include "py/runtime.h"
// #include "py/builtin.h"

// #include "lvgl_mpy.c"
#include "lv_mpy_example.c"
// Register the module to make it available in Python
// MP_REGISTER_MODULE(MP_QSTR_display, display_user_cmodule, MODULE_DISPLAY_ENABLED);
MP_REGISTER_MODULE(MP_QSTR_lvgl, mp_module_lvgl, MODULE_DISPLAY_ENABLED);

