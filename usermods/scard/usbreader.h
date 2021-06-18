/**
 * @file       usbreader.h
 * @brief      MicroPython uscard usb module: UsbReader class
 * @author     Rostislav Gurin <rgurin@embedity.dev>
 * @copyright  Copyright 2020 Crypto Advance GmbH. All rights reserved.
 */


#ifndef USBREADER_H_INCLUDED
/// Avoids multiple inclusion of this file
#define USBREADER_H_INCLUDED

#include "py/obj.h"
#include "usbh_core.h"
#include "usbh_ccid.h"
#include "usb_host.h"
#include "usbh_def.h"
#include "led.h"

extern USBH_HandleTypeDef hUsbHostFS;
extern const mp_obj_type_t scard_UsbReader_type;

#endif