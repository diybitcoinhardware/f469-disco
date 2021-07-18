/**
 * @file       usbscard.c
 * @brief      MicroPython uscard usb module: UsbReader class
 * @author     Rostislav Gurin <rgurin@embedity.dev>
 * @copyright  Copyright 2020 Crypto Advance GmbH. All rights reserved.
 */

#include "py/obj.h"
#include "py/objexcept.h"
#include "connection.h"
#include "usbreader.h"
#include "usbconnection.h"

/**
 * @brief Enables/disables debug output of uscard module
 *
 * .. function:: uscard.enableDebug(enable=True, ansi=True)
 *
 *   Enables/disables debug output of uscard module. Arguments:
 *
 *     - *enable* if true enables debug output
 *     - *ansi* if true enables ANSI support for debug output
 *
 * @param n_args    number of positional arguments
 * @param pos_args  positional arguments
 * @param kw_args   keyword arguments
 * @return          None
 */
STATIC mp_obj_t usbscard_enableDebug(size_t n_args, const mp_obj_t *pos_args,
                                  mp_map_t *kw_args) {
#if !defined(NDEBUG)
  enum { ARG_enable, ARG_ansi };
  static const mp_arg_t allowed_args[] = {
      { MP_QSTR_enable, MP_ARG_OBJ, {.u_obj = mp_const_true} },
      { MP_QSTR_ansi,  MP_ARG_OBJ, {.u_obj = mp_const_true} },
  };

  mp_arg_val_t args[MP_ARRAY_SIZE(allowed_args)];
  mp_arg_parse_all(n_args, pos_args, kw_args, MP_ARRAY_SIZE(allowed_args),
                   allowed_args, args);

  scard_module_debug = mp_obj_is_true(args[ARG_enable].u_obj);
  scard_module_debug_ansi = mp_obj_is_true(args[ARG_ansi].u_obj);
#endif // !defined(NDEBUG)

  return mp_const_none;
}
STATIC MP_DEFINE_CONST_FUN_OBJ_KW(usbscard_enableDebug_obj, 0, usbscard_enableDebug);

STATIC const mp_rom_map_elem_t usb_scard_module_globals_table[] = {
  { MP_ROM_QSTR(MP_QSTR___name__),                MP_ROM_QSTR(MP_QSTR_usbscard)                },
  //Functions
  { MP_ROM_QSTR(MP_QSTR_enableDebug),             MP_ROM_PTR(&usbscard_enableDebug_obj)        },
  //Classes
  { MP_ROM_QSTR(MP_QSTR_UsbReader),               MP_ROM_PTR(&scard_UsbReader_type)            },
  { MP_ROM_QSTR(MP_QSTR_CardConnection),          MP_ROM_PTR(&scard_UsbCardConnection_type)    },
};
STATIC MP_DEFINE_CONST_DICT(usb_scard_module_globals, usb_scard_module_globals_table);

// Define module object
const mp_obj_module_t usb_scard_user_cmodule = {
  .base = { &mp_type_module },
  .globals = (mp_obj_dict_t*)&usb_scard_module_globals,
};

// Register the module to make it available in Python
MP_REGISTER_MODULE(MP_QSTR_usbscard, usb_scard_user_cmodule, MODULE_USBSCARD_ENABLED);