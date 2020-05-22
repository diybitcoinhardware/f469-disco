/**
 * @file       reader.h
 * @brief      MicroPython uscard module: Reader class
 * @author     Mike Tolkachev <contact@miketolkachev.dev>
 * @copyright  Copyright 2020 Crypto Advance GmbH. All rights reserved.
 */

#include <stdio.h>
#include "py/obj.h"
#include "py/runtime.h"
#include "py/mphal.h"
#include "scard.h"
#include "connection.h"
#include "reader.h"

/// Object of Reader class
typedef struct reader_obj_ {
  /// Pointer to type of base class
  mp_obj_base_t base;
  /// Reader name
  mp_obj_t name;
  /// Connection parameters
  scard_conn_params_t conn_params;
  /// Active connection
  mp_obj_t connection;
} reader_obj_t;

/**
 * @brief Constructor of Reader
 *
 * Constructor
 * .. class:: Reader( ifaceId, ioPin, clkPin, rstPin, presPin, pwrPin,
 *                    name=None, rstPol=0, presPol=1, pwrPol=0, timerId=-1 )
 *
 *  Constructs a Reader object with given parameters:
 *
 *    - *ifaceId* is an interface identifier, like 3 for USART3
 *    - *ioPin* specifies the bidirectional IO pin to use
 *    - *clkPin* specifies the CLK output pin to use
 *    - *rstPin* specifies the RST output pin to use
 *    - *presPin* specifies the card presence detect pin to use
 *    - *pwrPin* specifies the pin controling power to the card
 *
 *  Optional keyword parameters:
 *
 *    - *name* name of smart card reader
 *    - *rstPol* RST polarity, active low by default
 *    - *presPol* polarity of card presence detect pin, active low by default
 *    - *pwrPol* polarity of power control pin, active low by default
 *    - *timerId* id of the timer to be used use for background tasks
 *
 * Argument *timerId* can also be None, denying creation of a separate timer
 * for a CardConnection object. In this case, CardConnection() must be called by
 * user code periodically at least once in 50ms to run background tasks.
 *
 * @param type      pointer to type structure
 * @param n_args    number of arguments
 * @param n_kw      number of keyword arguments
 * @param all_args  array containing arguments
 * @return          a new instance of CardConnection class
 */
STATIC mp_obj_t reader_make_new(const mp_obj_type_t* type, size_t n_args,
                                size_t n_kw, const mp_obj_t* all_args) {
  enum {
    ARG_ifaceId = 0, ARG_ioPin, ARG_clkPin, ARG_rstPin, ARG_presPin,
    ARG_pwrPin, ARG_name, ARG_rstPol, ARG_presPol, ARG_pwrPol, ARG_timerId
  };
  const mp_obj_t def_timer_id = MP_OBJ_NEW_SMALL_INT(-1);
  static const mp_arg_t allowed_args[] = {
    { MP_QSTR_ifaceId,  MP_ARG_REQUIRED | MP_ARG_OBJ, {.u_obj = MP_OBJ_NULL}  },
    { MP_QSTR_ioPin,    MP_ARG_REQUIRED | MP_ARG_OBJ, {.u_obj = MP_OBJ_NULL}  },
    { MP_QSTR_clkPin,   MP_ARG_REQUIRED | MP_ARG_OBJ, {.u_obj = MP_OBJ_NULL}  },
    { MP_QSTR_rstPin,   MP_ARG_REQUIRED | MP_ARG_OBJ, {.u_obj = MP_OBJ_NULL}  },
    { MP_QSTR_presPin,  MP_ARG_REQUIRED | MP_ARG_OBJ, {.u_obj = MP_OBJ_NULL}  },
    { MP_QSTR_pwrPin,   MP_ARG_REQUIRED | MP_ARG_OBJ, {.u_obj = MP_OBJ_NULL}  },
    { MP_QSTR_name,     MP_ARG_KW_ONLY  | MP_ARG_OBJ, {.u_obj = mp_const_none}},
    { MP_QSTR_rstPol,   MP_ARG_KW_ONLY  | MP_ARG_INT, {.u_int = 0}            },
    { MP_QSTR_presPol,  MP_ARG_KW_ONLY  | MP_ARG_INT, {.u_int = 1}            },
    { MP_QSTR_pwrPol,   MP_ARG_KW_ONLY  | MP_ARG_INT, {.u_int = 0}            },
    { MP_QSTR_timerId,  MP_ARG_KW_ONLY  | MP_ARG_OBJ, {.u_obj = def_timer_id} }
  };
  mp_arg_val_t args[MP_ARRAY_SIZE(allowed_args)];
  mp_arg_parse_all_kw_array(n_args, n_kw, all_args, MP_ARRAY_SIZE(allowed_args),
                            allowed_args, args);

  // Check if given interface exists
  if(!scard_interface_exists(args[ARG_ifaceId].u_obj)) {
    mp_raise_ValueError("interface does not exists");
  }

  // Check name
  if( !mp_obj_is_type(args[ARG_name].u_obj, &mp_type_NoneType) &&
      !mp_obj_is_str(args[ARG_name].u_obj) ) {
    mp_raise_ValueError("name must be string or None");
  }

  // Create new object
  reader_obj_t* self = m_new0(reader_obj_t, 1U);
  self->base.type = &scard_Reader_type;
  self->conn_params.base.type = &scard_conn_params_type;
  self->name = args[ARG_name].u_obj;
  self->connection = MP_OBJ_NULL;

  // Save connection parameters
  self->conn_params.iface_id = args[ARG_ifaceId].u_obj;
  self->conn_params.io_pin   = args[ARG_ioPin].u_obj;
  self->conn_params.clk_pin  = args[ARG_clkPin].u_obj;
  self->conn_params.rst_pin  = args[ARG_rstPin].u_obj;
  self->conn_params.pres_pin = args[ARG_presPin].u_obj;
  self->conn_params.pwr_pin  = args[ARG_pwrPin].u_obj;
  self->conn_params.rst_pol  = args[ARG_rstPol].u_int;
  self->conn_params.pres_pol = args[ARG_presPol].u_int;
  self->conn_params.pwr_pol  = args[ARG_pwrPol].u_int;
  self->conn_params.timer_id = args[ARG_timerId].u_obj;

  if(scard_module_debug) {
    printf("\r\nNew smart card reader created");
  }

  return MP_OBJ_FROM_PTR(self);
}

/**
 * @brief Returns a smart card connection through a reader
 *
 * .. method:: Reader.createConnection()
 *
 *  Returns a smart card connection through a reader
 *
 * @param self_in  instance of Reader class
 * @return         a new smart card connection
 */
STATIC mp_obj_t reader_createConnection(mp_obj_t self_in) {
  reader_obj_t* self = (reader_obj_t*)self_in;

  // Only single connection is allowed (exclusive mode)
  if(self->connection) {
    raise_SmartcardException("too many connections");
  }

  // Create a new connection
  mp_obj_t args[] =  {
    // Positional arguments
    MP_OBJ_FROM_PTR(self),               // reader
    MP_OBJ_FROM_PTR(&self->conn_params), // conn_params
  };
  self->connection = scard_CardConnection_type.make_new(
    &scard_CardConnection_type, 2U, 0U, args);

  return MP_OBJ_FROM_PTR(self->connection);
}

/**
 * @brief Returns reader name
 *
 * .. method:: Reader.getName()
 *
 *  Returns the name of smart card reader
 *
 * @param self_in  instance of Reader class
 * @return         name of smart card reader
 */
STATIC mp_obj_t reader_getName(mp_obj_t self_in) {
  reader_obj_t* self = (reader_obj_t*)self_in;
  return self->name;
}

void reader_deleteConnection(mp_obj_t* self_in, mp_obj_t* connection) {
  reader_obj_t* self = (reader_obj_t*)self_in;

  if(mp_obj_is_type(self, &scard_Reader_type)) {
    if(connection && self->connection == connection) {
      // Remove the reference to let the GC collecting this connection object
      self->connection = MP_OBJ_NULL;
    }
  }
}

/**
 * Prints Reader object
 *
 * @param print    output stream
 * @param self_in  instance of Reader class
 * @param kind     print kind
 */
STATIC void reader_print(const mp_print_t *print, mp_obj_t self_in,
                         mp_print_kind_t kind) {
  reader_obj_t* self = (reader_obj_t*)self_in;

  if(!mp_obj_is_type(self->name, &mp_type_NoneType)) {
    mp_printf(print, "<Reader '%s' at '", mp_obj_str_get_str(self->name));
  } else {
    mp_printf(print, "<Reader at '");
  }
  scard_interface_print_by_id(print, self->conn_params.iface_id);
  mp_printf(print, "' connections=%u>", self->connection ? 1U : 0U);
}

STATIC MP_DEFINE_CONST_FUN_OBJ_1(reader_createConnection_obj, reader_createConnection);
STATIC MP_DEFINE_CONST_FUN_OBJ_1(reader_getName_obj, reader_getName);

STATIC const mp_rom_map_elem_t reader_locals_dict_table[] = {
  // Instance methods
  { MP_ROM_QSTR(MP_QSTR_createConnection), MP_ROM_PTR(&reader_createConnection_obj) },
  { MP_ROM_QSTR(MP_QSTR_getName),          MP_ROM_PTR(&reader_getName_obj)          }
};
STATIC MP_DEFINE_CONST_DICT(reader_locals_dict, reader_locals_dict_table);

const mp_obj_type_t scard_Reader_type = {
  { &mp_type_type },
  .name = MP_QSTR_Reader,
  .print = reader_print,
  .make_new = reader_make_new,
  .locals_dict = (void*)&reader_locals_dict,
};
