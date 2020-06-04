/**
 * @file       scard.c
 * @brief      MicroPython uscard module
 * @author     Mike Tolkachev <contact@miketolkachev.dev>
 * @copyright  Copyright 2020 Crypto Advance GmbH. All rights reserved.
 */

#include "py/obj.h"
#include "py/objexcept.h"
#include "scard.h"
#include "connection.h"
#include "reader.h"

#if !defined(NDEBUG)
  bool scard_module_debug = false;
  bool scard_module_debug_ansi = true;
#endif

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
STATIC mp_obj_t scard_enableDebug(size_t n_args, const mp_obj_t *pos_args,
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
STATIC MP_DEFINE_CONST_FUN_OBJ_KW(scard_enableDebug_obj, 0, scard_enableDebug);

MP_DEFINE_EXCEPTION(SmartcardException, Exception)
MP_DEFINE_EXCEPTION(CardConnectionException, SmartcardException)
MP_DEFINE_EXCEPTION(NoCardException, SmartcardException)

STATIC const mp_rom_map_elem_t scard_module_globals_table[] = {
  { MP_ROM_QSTR(MP_QSTR___name__),                MP_ROM_QSTR(MP_QSTR_uscard)                  },
  //Functions
  { MP_ROM_QSTR(MP_QSTR_enableDebug),             MP_ROM_PTR(&scard_enableDebug_obj)           },
  // Classes
  { MP_ROM_QSTR(MP_QSTR_Reader),                  MP_ROM_PTR(&scard_Reader_type)               },
  { MP_ROM_QSTR(MP_QSTR_CardConnection),          MP_ROM_PTR(&scard_CardConnection_type)       },
  // Exceptions
  { MP_ROM_QSTR(MP_QSTR_SmartcardException),      MP_ROM_PTR(&mp_type_SmartcardException)      },
  { MP_ROM_QSTR(MP_QSTR_CardConnectionException), MP_ROM_PTR(&mp_type_CardConnectionException) },
  { MP_ROM_QSTR(MP_QSTR_NoCardException),         MP_ROM_PTR(&mp_type_NoCardException)         },
};
STATIC MP_DEFINE_CONST_DICT(scard_module_globals, scard_module_globals_table);

// Define module object
const mp_obj_module_t scard_user_cmodule = {
  .base = { &mp_type_module },
  .globals = (mp_obj_dict_t*)&scard_module_globals,
};

// Register the module to make it available in Python
MP_REGISTER_MODULE(MP_QSTR_uscard, scard_user_cmodule, MODULE_SCARD_ENABLED);
