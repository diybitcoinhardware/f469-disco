/**
 * @file       usbreader.h
 * @brief      MicroPython uscard usb module: UsbReader class
 * @author     Rostislav Gurin <rgurin@embedity.dev>
 * @copyright  Copyright 2020 Crypto Advance GmbH. All rights reserved.
 */


#ifndef USBCONNECTION_H_INCLUDED
/// Avoids multiple inclusion of this file
#define USBCONNECTION_H_INCLUDED
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "py/obj.h"
#include "py/runtime.h"
#include "py/builtin.h"
#include "py/mperrno.h"
#include "py/mphal.h"
#include "py/smallint.h"
#include "modmachine.h"
#include "protocols.h"
#include "usbreader.h"
#include "scard.h"
/// Timer period in milliseconds
#define TIMER_PERIOD_MS                 (10U)
/// Smart card reset duration in ms, 5ms (at least 400 clock cycles)
#define RESET_TIME_MS                   (5U)
/// Debounce time in milliseconds
#define DEBOUNCE_TIME_MS                (5U)
/// Maximal number of keyward arguments of an event
#define EVENT_MAX_KW                    (1U)
/// Number of positional arguments of an event, 2: connection and type
#define EVENT_POS_ARGS                  (2U)
/// Maximal number of events in queue
#define MAX_EVENTS                      (4U)
/// Size of receive buffer in bytes inside wait loops
#define WAIT_LOOP_RX_BUF_SIZE           (32U)
/// Number of sequential cycles that presence pin should keep the same state to
/// change presence of smart card
#define CARD_PRESENCE_CYCLES            (5U)

#define CCID_CLASS_AUTO_ACTIVATION	    0x00000004

#define CCID_CLASS_AUTO_VOLTAGE		      0x00000008

#define CCID_ICC_POWER_ON_CMD_LENGTH    (10U)
/// Connection state
typedef enum state_ {
  state_closed       = MP_QSTR_closed,       ///< Connection is closed
  state_disconnected = MP_QSTR_disconnected, ///< Card is disconnected
  state_connecting   = MP_QSTR_connecting,   ///< Connection in progress
  state_connected    = MP_QSTR_connected,    ///< Card is connected
  state_error        = MP_QSTR_error         ///< Card error
} state_t;

/// Types of connection events
typedef enum event_type_ {
  event_connect    = MP_QSTR_connect,    ///< Connected to smart card
  event_disconnect = MP_QSTR_disconnect, ///< Disconnected from smart card
  event_command    = MP_QSTR_command,    ///< Command transmitted
  event_response   = MP_QSTR_response,   ///< Response received
  event_insertion  = MP_QSTR_insertion,  ///< Card insertion
  event_removal    = MP_QSTR_removal,    ///< Card removal
  event_error      = MP_QSTR_error       ///< Error
} event_type_t;

/// Event as a set of arguments of observer
typedef struct event_ {
  /// Buffer with arguments of observer
  mp_obj_t args[EVENT_POS_ARGS + 2U * EVENT_MAX_KW];
  /// Number of keyword arguments
  size_t n_kw;
} event_t;

typedef struct usb_connection_obj_ {
  mp_obj_base_t base;            ///< Pointer to type of base class
  mp_obj_t reader;               ///< Reader to which connection is bound
  state_t state;                 ///< Connection state
  mp_obj_t timer;                ///< Timer object
  mp_obj_t atr;                  ///< ATR as bytes object
  mp_uint_t prev_ticks_ms;       ///< Previous value of millisecond ticks
  uint8_t pbSeq;
  uint8_t IccPowerOnCmd[10];
} usb_connection_obj_t;

typedef struct usb_process_obj_ {
  __IO HOST_StateTypeDef     gProcessState;
  bool scardConnected;
} usb_process_obj_t;

STATIC void usb_timer_init(usb_connection_obj_t* self); 
static void timer_task(usb_connection_obj_t* self);
/// Connection class type
extern const mp_obj_type_t scard_UsbCardConnection_type;
usb_process_obj_t usbProcess_type;
#endif