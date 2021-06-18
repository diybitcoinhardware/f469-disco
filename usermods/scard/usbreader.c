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
typedef struct reader_obj_ {
  /// Pointer to type of base class
  mp_obj_base_t base;
  /// Reader name
  mp_obj_t name;
  /// Active connection
  mp_obj_t connection;
} reader_obj_t;

STATIC mp_obj_t usb_reader_make_new()
{
    // Create new object
    reader_obj_t* self = m_new0(reader_obj_t, 1U);
    self->base.type = &scard_UsbReader_type;
    self->name = "USB Smart Card Reader";
    self->connection = MP_OBJ_NULL;
    led_state(1, 1);
    led_state(2, 1);
    USBH_Init(&hUsbHostFS, USBH_UserProcess, HOST_FS);
    USBH_RegisterClass(&hUsbHostFS, USBH_CCID_CLASS);
    USBH_Start(&hUsbHostFS);
    return MP_OBJ_FROM_PTR(self);
}

STATIC mp_obj_t usbreader_createConnection(mp_obj_t self_in) {
  reader_obj_t* self = (reader_obj_t*)self_in;

  // Create a new connection
  mp_obj_t args[] =  {
    // Positional arguments
    MP_OBJ_FROM_PTR(self),               // reader
  };
  self->connection = scard_UsbCardConnection_type.make_new(
    &scard_UsbCardConnection_type, 2U, 0U, args);

  return MP_OBJ_FROM_PTR(self->connection);
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