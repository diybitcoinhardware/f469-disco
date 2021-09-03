/**
 * @file       protocols.h
 * @brief      MicroPython uscard module: protocol wrappers
 * @author     Mike Tolkachev <contact@miketolkachev.dev>
 * @copyright  Copyright 2020 Crypto Advance GmbH. All rights reserved.
 */

#ifndef PROTOCOLS_H_INCLUDED
/// Avoids multiple inclusion of this file
#define PROTOCOLS_H_INCLUDED

#include "py/obj.h"
#include "t1_protocol.h"

/// Protocol identifier
typedef enum protocol_ {
  /// T=0 protocol identifier
  T0_protocol = 0x00000001L,
  /// T=1 protocol identifier
  T1_protocol = 0x00000002L,
  /// Any available protocol
  protocol_any = (int)T0_protocol | (int)T1_protocol,
  /// No protocol selected
  protocol_na = 0
} protocol_t;

/// Special values accepted for some parameters
typedef enum proto_prm_special_ {
  proto_prm_default   = -1, ///< Parameter is set to default
  proto_prm_unchanged = -2  ///< Parameter is unchanged
} proto_prm_special_t;

/// Protocol events
///
/// If parameter is not specified it equals to NULL.
typedef enum proto_ev_code_ {
  proto_ev_none = 0,          ///< Not an event
  proto_ev_atr_received,      ///< ATR is received; parameter: proto_atr_t*
  proto_ev_connect,           ///< Connection established
  proto_ev_apdu_received,     ///< APDU is received; parameter: proto_apdu_t*
  proto_ev_pps_exchange_done,  ///< PPS exchange done
  proto_ev_error              ///< Error; parameter: const char string
} proto_ev_code_t;

/// Parameter of proto_ev_atr_received
typedef struct proto_atr_ {
  const uint8_t* atr;  ///< Raw ATR message
  size_t len;          ///< Length of raw ATR in bytes
} proto_atr_t;

/// Parameter of proto_ev_apdu_received
typedef struct proto_apdu_ {
  const uint8_t *apdu; ///< Pointer to buffer containing APDU
  size_t len;          ///< Length of APDU in bytes
} proto_apdu_t;

typedef union proto_ev_prm_ {
  void* none;                        ///< Parameter of proto_ev_none
  const proto_atr_t* atr_received;   ///< Parameter of proto_ev_atr_received
  void* connect;                     ///< Parameter of proto_ev_connect (n/a)
  const proto_apdu_t* apdu_received; ///< Parameter of proto_ev_apdu_received
  const char* error;                 ///< Parameter of proto_ev_error
} proto_ev_prm_t;

/**
 * Callback function that outputs bytes to serial port
 *
 * @param self  instance of user class
 * @param buf   buffer containing data to transmit
 * @param len   length of data block in bytes
 */
typedef bool (*proto_cb_serial_out_t)(mp_obj_t self, const uint8_t* buf,
                                      size_t len);

/**
 * Callback function that handles protocol events
 *
 * This protocol implementation guarantees that event handler is always called
 * just before termination of any external API function. It allows to call
 * safely any other API function(s) within user handler code.
 *
 * @param self     instance of user class
 * @param ev_code  event code
 * @param ev_prm   event parameter depending on event code, typically NULL
 */
typedef void (*proto_cb_handle_event_t)(mp_obj_t self, proto_ev_code_t ev_code,
                                        proto_ev_prm_t ev_prm);

/// Pointer to protocol context
typedef struct proto_ctx_ {
  void* any;     ///< Abstract handle to any protocol
  t1_inst_t* t1; ///< Pointer to instance of T=1 protocol
} proto_ctx_t;

/// Instance and handle of a protocol
typedef struct proto_inst_ {
  proto_ctx_t ctx;                          ///< Protocol context
  proto_cb_serial_out_t cb_serial_out;      ///< Serial out callback
  proto_cb_handle_event_t cb_handle_event;  ///< Callback handling events
  mp_obj_t cb_self;                         ///< Self parameter for callback
  uint8_t tx_errors;                        ///< Counter of transmit errors
  proto_ev_code_t user_event;
} proto_inst_t, *proto_handle_t;

/**
 * Initializes protocol implementation
 *
 * @param cb_serial_out    callback function outputting bytes to serial port
 * @param cb_handle_event  callback function handling protocol events
 * @param cb_self          self parameter for callback
 * @return                 protocol handle or NULL if failed
 */
typedef proto_handle_t (*proto_init_t)(proto_cb_serial_out_t cb_serial_out,
                                       proto_cb_handle_event_t cb_handle_event,
                                       mp_obj_t cb_self);

/**
 * Releases protocol context
 *
 * @param handle  protocol handle
 */
typedef void (*proto_deinit_t)(proto_handle_t handle);

/**
 * Re-initializes protocol instance cleaning receive and transmit buffers
 *
 * @param handle    protocol handle
 * @param wait_atr  if true sets protocol instance into "waiting for ATR" state
 */
typedef void (*proto_reset_t)(proto_handle_t handle, bool wait_atr);

/**
 * Timer task, called by host periodically to implement timeouts
 *
 * This function must be called periodically by host application at least once
 * in 50ms.
 *
 * @param handle      protocol handle
 * @param elapsed_ms  time in milliseconds passed since previous call
 */
typedef void (*proto_timer_task_t)(proto_handle_t handle, uint32_t elapsed_ms);

/**
 * Handles received bytes from serial port
 *
 * @param handle  protocol handle
 * @param buf    buffer holding received bytes
 * @param len    number of bytes received
 */
typedef void (*proto_serial_in_t)(proto_handle_t handle, const uint8_t* buf,
                                  size_t len);

/**
 * Transmits APDU
 *
 * @param handle  protocol handle
 * @param apdu    buffer containing APDU
 * @param len     length of APDU in bytes
 */
typedef void (*proto_transmit_apdu_t)(proto_handle_t handle,
                                      const uint8_t* apdu, size_t len);

/**
 * Configures protocol timeouts
 *
 * This function accept special values for timeout parameters:
 * proto_prm_unchanged, proto_prm_default.
 *
 * @param handle          protocol handle
 * @param atr_timeout_ms  ATR timeout in ms
 * @param rsp_timeout_ms  response timeout in ms
 * @param max_timeout_ms  maximal response timeout in ms
 */
typedef void (*proto_set_timeouts_t)(proto_handle_t handle,
                                     int32_t atr_timeout_ms,
                                     int32_t rsp_timeout_ms,
                                     int32_t max_timeout_ms);

typedef void (*proto_set_usb_features_t)(proto_handle_t handle,
                                     uint32_t dwFeatures, uint8_t maxIFSD);

/// Abstract implementation of a protocol
typedef struct proto_implementation_ {
  protocol_t                id;               ///< Protocol identifier
  const char*               name;             ///< Protocol name
  proto_init_t              init;             ///< Initialization function
  proto_deinit_t            deinit;           ///< Deinitialization function
  proto_reset_t             reset;            ///< Reset function
  proto_timer_task_t        timer_task;       ///< Timer task function
  proto_serial_in_t         serial_in;        ///< Serial input function
  proto_transmit_apdu_t     transmit_apdu;    ///< APDU transmission function
  proto_set_timeouts_t      set_timeouts;     ///< Timeout configuration function
  proto_set_usb_features_t  set_usb_features; ///< Set additional parameters for USB connection
} proto_impl_t;

/**
 * Searches for implementation of a protocol with a given identifier
 *
 * @param protocol  requested protocol, a bit mask
 * @return          pointer to implementation structure or NULL if not found
 */
const proto_impl_t* proto_get_implementation(mp_int_t protocol);

#endif // PROTOCOLS_H_INCLUDED
