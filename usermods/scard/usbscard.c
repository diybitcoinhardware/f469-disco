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
STATIC const mp_rom_map_elem_t usb_scard_module_globals_table[] = {
  { MP_ROM_QSTR(MP_QSTR___name__),                MP_ROM_QSTR(MP_QSTR_usbscard)                },
  { MP_ROM_QSTR(MP_QSTR_UsbReader),               MP_ROM_PTR(&scard_UsbReader_type)            },
  { MP_ROM_QSTR(MP_QSTR_CardConnection),          MP_ROM_PTR(&scard_UsbCardConnection_type)       },
};
STATIC MP_DEFINE_CONST_DICT(usb_scard_module_globals, usb_scard_module_globals_table);

// Define module object
const mp_obj_module_t usb_scard_user_cmodule = {
  .base = { &mp_type_module },
  .globals = (mp_obj_dict_t*)&usb_scard_module_globals,
};

// Register the module to make it available in Python
MP_REGISTER_MODULE(MP_QSTR_usbscard, usb_scard_user_cmodule, MODULE_USBSCARD_ENABLED);