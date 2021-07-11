/**
 * @file       usbreader.c
 * @brief      MicroPython uscard usb module: UsbReader class
 * @author     Rostislav Gurin <rgurin@embedity.dev>
 * @copyright  Copyright 2020 Crypto Advance GmbH. All rights reserved.
 */

#include <stdio.h>
#include "py/obj.h"
#include "py/runtime.h"
#include "py/mphal.h"
#include "usbconnection.h"
#include "usbreader.h"
/// Reader class type
extern const mp_obj_type_t scard_UsbReader_type;
typedef struct usb_reader_obj_ {
  /// Pointer to type of base class
  mp_obj_base_t base;
  /// Reader name
  mp_obj_t name;
  /// Active connection
  mp_obj_t connection;
} usb_reader_obj_t;

STATIC mp_obj_t usb_reader_make_new(const mp_obj_type_t* type, size_t n_args,
                                size_t n_kw, const mp_obj_t* all_args)
{
    enum 
    { 
      ARG_name, 
      ARG_timerId
    };
    static const mp_arg_t allowed_args[] = {
      { MP_QSTR_name,     MP_ARG_KW_ONLY  | MP_ARG_OBJ, {.u_obj = mp_const_none}},
      { MP_QSTR_timerId,  MP_ARG_KW_ONLY  | MP_ARG_OBJ,
      {.u_obj = MP_OBJ_NEW_SMALL_INT(-1)} }
    };
    mp_arg_val_t args[MP_ARRAY_SIZE(allowed_args)];
    mp_arg_parse_all_kw_array(n_args, n_kw, all_args, MP_ARRAY_SIZE(allowed_args),
                              allowed_args, args);
    // Check name
    if( !mp_obj_is_type(args[ARG_name].u_obj, &mp_type_NoneType) &&
        !mp_obj_is_str(args[ARG_name].u_obj) ) {
      mp_raise_ValueError("name must be string or None");
    }
    // Create new object
    usb_reader_obj_t* self = m_new0(usb_reader_obj_t, 1U);
    self->base.type = &scard_UsbReader_type;
    self->name = args[ARG_name].u_obj;
    self->connection = MP_OBJ_NULL;
    led_state(1, 1);
    led_state(2, 1);
    USBH_Init(&hUsbHostFS, USBH_UserProcess, HOST_FS);
    USBH_RegisterClass(&hUsbHostFS, USBH_CCID_CLASS);
    USBH_Start(&hUsbHostFS);
    return MP_OBJ_FROM_PTR(self);
}

STATIC mp_obj_t usbreader_createConnection(mp_obj_t self_in) {
  usb_reader_obj_t* self = (usb_reader_obj_t*)self_in;

  // Create a new connection
  mp_obj_t args[] =  {
    // Positional arguments
    MP_OBJ_FROM_PTR(self),
  };
  self->connection = scard_UsbCardConnection_type.make_new(
    &scard_UsbCardConnection_type, 1U, 0U, args);

  return MP_OBJ_FROM_PTR(self->connection);
}

void usbreader_deleteConnection(mp_obj_t* self_in, mp_obj_t* connection) {
  usb_reader_obj_t* self = (usb_reader_obj_t*)self_in;

  if(mp_obj_is_type(self, &scard_UsbReader_type)) {
    if(connection && self->connection == connection) {
      // Remove the reference to let the GC collecting this connection object
      self->connection = MP_OBJ_NULL;
    }
  }
}

STATIC MP_DEFINE_CONST_FUN_OBJ_1(usbreader_createConnection_obj, usbreader_createConnection);

STATIC const mp_rom_map_elem_t usbreader_locals_dict_table[] = {
  // Instance methods
  { MP_ROM_QSTR(MP_QSTR_createConnection), MP_ROM_PTR(&usbreader_createConnection_obj) },
};
STATIC MP_DEFINE_CONST_DICT(usbreader_locals_dict, usbreader_locals_dict_table);

const mp_obj_type_t scard_UsbReader_type = {
  { &mp_type_type },
  .name = MP_QSTR_UsbReader,
  .make_new = usb_reader_make_new,
  .locals_dict = (void*)&usbreader_locals_dict,
};