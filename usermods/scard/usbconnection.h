/**
 * @file       usbreader.h
 * @brief      MicroPython uscard usb module: UsbReader class
 * @author     Rostislav Gurin <rgurin@embedity.dev>
 * @copyright  Copyright 2021 Crypto Advance GmbH. All rights reserved.
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

/// Size of receive buffer in bytes inside wait loops
#define WAIT_LOOP_RX_BUF_SIZE           (32U)
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
/// Number of sequential cycles that presence pin should keep the same state to
/// change presence of smart card
#define CARD_PRESENCE_CYCLES            (5U)
/* Features from dwFeatures */
#define CCID_CLASS_AUTO_CONF_ATR     0x00000002
#define CCID_CLASS_AUTO_ACTIVATION   0x00000004
#define CCID_CLASS_AUTO_VOLTAGE      0x00000008
#define CCID_CLASS_AUTO_BAUD         0x00000020
#define CCID_CLASS_AUTO_PPS_PROP     0x00000040
#define CCID_CLASS_AUTO_PPS_CUR      0x00000080
#define CCID_CLASS_AUTO_IFSD         0x00000400
#define CCID_CLASS_CHARACTER         0x00000000
#define CCID_CLASS_TPDU              0x00010000
#define CCID_CLASS_SHORT_APDU        0x00020000
#define CCID_CLASS_EXTENDED_APDU     0x00040000
#define CCID_CLASS_EXCHANGE_MASK     0x00070000
/// Length of ICC header
#define CCID_ICC_HEADER_LENGTH    (10U)
/// CCID maximum data message length
#define CCID_MAX_DATA_LENGTH      (261U)
/// CCID maximum data length
#define CCID_MAX_RESP_LENGTH      (254U)
/// Connection state
typedef enum state_ {
  state_closed       = MP_QSTR_closed,       ///< Connection is closed
  state_disconnected = MP_QSTR_disconnected, ///< Card is disconnected
  state_connecting   = MP_QSTR_connecting,   ///< Connection in progress
  state_connected    = MP_QSTR_connected,    ///< Card is connected
  state_error        = MP_QSTR_error         ///< Card error
} state_t;

/// Connection state
typedef enum process_state_ {
  process_state_closed, ///< USB Host prosecc is not running
  process_state_init,   ///< USB Host process initialization state
  process_state_ready   ///< USB Host process ready to connect
} process_state_t;

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

/// Types of Bulk-In pipe messages
typedef enum bulk_in_message_type_
{
  RDR_to_PC_DataBlock = 0x80, ///< Data block message
  RDR_to_PC_SlotStatus,       ///< Slot status message
  RDR_to_PC_Parameters,       ///< Usb transfer parameters message
  RDR_to_PC_Escape,           ///< Escape message
  RDR_to_PC_DataRateAndClockFrequency = 0x84 ///< Data rate and clock frequency message
} bulk_in_message_type_t;

/// Format of PC_to_RDR_XfrBlock command
typedef enum {
  ccid_xfrblock_cmd_code = 0,        ///< Command code
  ccid_xfrblock_apdu_len,            ///< APDU length
  ccid_xfrblock_cmd_slot = ccid_xfrblock_apdu_len + 4, ///< CCID slot
  ccid_xfrblock_cmd_pbseq,           ///< pbSeq number
  ccid_xfrblock_cmd_bwi,                 ///< Block waiting time
  ccid_xfrblock_cmd_wlevelparam_0,       ///< Expected length, in character mode only
  ccid_xfrblock_cmd_wlevelparam_1,       ///< Expected length, in character mode only
  ccid_xfrblock_cmd_cmd_hdr_len          ///<< Command length
} ccid_xfrblock_cmd_t;

/// Format of PC_To_RDR_SetParameters command
typedef enum {
  ccid_setparam_cmd_code = 0,        ///< Command code
  ccid_setparam_apdu_len,            ///< APDU length
  ccid_setparam_cmd_slot = ccid_setparam_apdu_len + 4, ///< CCID slot
  ccid_setparam_cmd_pbseq,           ///< pbSeq number
  ccid_setparam_protocol_num,        ///< Protocol number
  ccid_setparam_cmd_rfu_0,  ///<< Bytes reserved for future use
  ccid_setparam_cmd_rfu_1, ///<< Bytes reserved for future use
  ccid_setparam_cmd_hdr_len          ///<< Command length
} ccid_setparam_cmd_t;

/// Format of PC_To_RDR_GetParameters command
typedef enum {
  ccid_getparam_cmd_code = 0,    ///< Command code
  ccid_getparam_cmd_dwlength_0,  ///< Message specific data length
  ccid_getparam_cmd_dwlength_1,  ///< Message specific data length
  ccid_getparam_cmd_dwlength_2,  ///< Message specific data length
  ccid_getparam_cmd_dwlength_3,  ///< Message specific data length
  ccid_getparam_cmd_slot,        ///< CCID slot
  ccid_getparam_cmd_pbseq,       ///< pbSeq number
  ccid_getparam_cmd_rfu_1,       ///<< Bytes reserved for future use
  ccid_getparam_cmd_rfu_2,       ///<< Bytes reserved for future use
  ccid_getparam_cmd_rfu_3,       ///<< Bytes reserved for future use
  ccid_getparam_cmd_hdr_len      ///<< Command length
} ccid_getparam_cmd_t;

/// Event as a set of arguments of observer
typedef struct event_ {
  /// Buffer with arguments of observer
  mp_obj_t args[EVENT_POS_ARGS + 2U * EVENT_MAX_KW];
  /// Number of keyword arguments
  size_t n_kw;
} event_t;

typedef struct usb_ccid_apdu_ {
  const uint8_t *apdu;  ///< Pointer to buffer containing APDU
  size_t len;           ///< Length of APDU in bytes
} usb_ccid_apdu_t;

typedef struct usb_ccid_atr_ {
  const uint8_t *atr;  ///< Pointer to buffer containing ATR
  size_t len;          ///< Length of ATR in bytes
} usb_ccid_atr_t;
typedef struct usb_connection_obj_ {
  mp_obj_base_t base;               ///< Pointer to type of base class
  mp_obj_t reader;                  ///< Reader to which connection is bound
  state_t state;                    ///< Connection state
  process_state_t process_state;    ///<  USB host process state
  mp_obj_t timer;                   ///< Timer object
  mp_obj_t atr;                     ///< ATR as bytes object
  mp_obj_t apdu;                    ///< APDU as bytes object
  mp_uint_t prev_ticks_ms;          ///< Previous value of millisecond ticks
  mp_obj_t observers;               ///< List of observers
  event_t event_buf[MAX_EVENTS];    ///< Event buffer
  size_t event_idx;                 ///< Event index within event_buf[]
  int32_t atr_timeout_ms;           ///< ATR timeout in ms
  int32_t rsp_timeout_ms;           ///< Response timeout in ms
  int32_t max_timeout_ms;           ///< Maximal response timeout in ms
  CCID_HandleTypeDef *CCID_Handle;  ///< Structure for CCID process
  uint8_t pbSeq;                    ///< Sequence number for command.
  uint8_t IccCmd[10];               ///< CCID command
  usb_ccid_apdu_t apdu_recived;     ///< Received APDU
  usb_ccid_atr_t atr_received;      ///< Received ATR
  mp_obj_t response;                ///< Card response, a list [data, sw1, sw2]
  mp_int_t next_protocol;           ///< ID of the protocol for the next op.
  uint16_t presence_cycles;      ///< Counter of card presence cycles (debounce)
  bool presence_state;           ///< Card presence state
  const proto_impl_t *protocol;  ///< Protocol used to communicate with card
  proto_handle_t proto_handle;   ///< Protocol handle
  bool blocking;                 ///< If true, all operations are blocking
  bool raise_on_error;           ///< Forces exception for non-blocking mode
  uint32_t processTimer;         ///< Timer for USB Host process
  uint32_t dwFeatures;           ///< Card reader features field
  uint8_t TA_1;                  ///< Fi/Di value required by cardreader
  USBH_ChipCardDescTypeDef chipCardDesc;  ///< Smart Card descriptor
} usb_connection_obj_t;
// Initializing usb timer
STATIC void usb_timer_init(usb_connection_obj_t *self);
// Usb timer task
static void timer_task(usb_connection_obj_t *self);
/// Connection class type
extern const mp_obj_type_t scard_UsbCardConnection_type;
#endif