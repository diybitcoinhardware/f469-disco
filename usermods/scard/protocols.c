/**
 * @file       protocols.c
 * @brief      MicroPython uscard module: protocol wrappers
 * @author     Mike Tolkachev <contact@miketolkachev.dev>
 * @copyright  Copyright 2020 Crypto Advance GmbH. All rights reserved.
 */

#include <stdio.h>
#include "scard.h"
#include "protocols.h"
#include "py/obj.h"

/// Maximal number sequential of TX errors for T=1 protocol
#define MAX_TX_ERRORS_T1                (2U)

/// Error descriptor
typedef struct error_dsc_ {
  int32_t id;        ///< Identifier
  const char* text;  ///< Error text
} error_dsc_t;

/// T=1 protocol errors
static const error_dsc_t errors_t1[] = {
  { t1_ev_err_internal,       "internal error"                       },
  { t1_ev_err_serial_out,     "serial output error"                  },
  { t1_ev_err_comm_failure,   "smart card connection failed"         },
  { t1_ev_err_atr_timeout,    "ATR timeout"                          },
  { t1_ev_err_bad_atr,        "incorrect ATR format"                 },
  { t1_ev_err_incompatible,   "incompatible card"                    },
  { t1_ev_err_oversized_apdu, "received APDU does not fit in buffer" },
  { t1_ev_err_sc_abort,       "operation aborted by smart card"      },
  { t1_ev_pps_failed,         "PPS exchange failed"                  },
  { .text = NULL } // Terminating record
};

/// Unknown error
const char* unknown_error = "unknown error";

/**
 * Searches for error text
 *
 * @param error_table  error table
 * @param id           error identifier
 * @return             error text string
 */
static const char* error_text(const error_dsc_t* error_table, int32_t id) {
  const error_dsc_t* p_dsc = error_table;
  while(p_dsc->text) {
    if(p_dsc->id == id) {
      return p_dsc->text;
    }
    ++p_dsc;
  }
  return unknown_error;
}

/**
 * Calls error handler
 *
 * @param handle  protocol handle
 * @param text    error text
 */
static inline void emit_error(proto_handle_t handle, const char* text) {
  proto_ev_prm_t prm = { .error = text };
  handle->cb_handle_event(handle->cb_self, proto_ev_error, prm);
}

/**
 * T=1 protocol: callback function that outputs bytes to serial port
 *
 * @param buf         buffer containing data to transmit
 * @param len         length of data block in bytes
 * @param p_user_prm  user defined parameter
 */
static bool t1_cb_serial_out(const uint8_t* buf, size_t len, void* p_user_prm) {
  if(scard_module_debug) {
    scard_ansi_color(SCARD_ANSI_RED);
    for(size_t i = 0; i < len; ++i) {
      printf(scard_module_debug_ansi ? " %02X" : " t%02X", buf[i]);
    }
    scard_ansi_reset();
  }

  proto_handle_t handle = (proto_handle_t)p_user_prm;
  bool status = handle->cb_serial_out(handle->cb_self, buf, len);

  // For T=1 we can skip some TX errors hoping that the block will be
  // retransmitted
  if(status) {
    handle->tx_errors = 0U;
  } else if(handle->tx_errors >= MAX_TX_ERRORS_T1) {
    return false;
  } else {
    ++handle->tx_errors;
  }
  return true;
}

/**
 * T=1 protocol: callback function that handles protocol events
 *
 * @param ev_code     event code
 * @param ev_prm      event parameter depending on event code, typically NULL
 * @param p_user_prm  user defined parameter
 */
static void t1_cb_handle_event(t1_ev_code_t ev_code, const void* ev_prm,
                               void* p_user_prm) {
  proto_handle_t handle = (proto_handle_t)p_user_prm;

  if(t1_is_error_event(ev_code) && t1_ev_err_incompatible != ev_code) {
    emit_error(handle, error_text(errors_t1, ev_code));
  } else {
    switch(ev_code) {
      case t1_ev_atr_received:
      case t1_ev_err_incompatible: {
          // Forward ATR data
          t1_atr_decoded_t* p_atr = (t1_atr_decoded_t*)ev_prm;
          proto_atr_t atr = { .atr = p_atr->atr, .len = p_atr->atr_len };
          proto_ev_prm_t prm = { .atr_received = &atr };
          handle->cb_handle_event(handle->cb_self, proto_ev_atr_received, prm);

          // Emit error if the card is incompatible
          if(t1_ev_err_incompatible == ev_code) {
            emit_error(handle, error_text(errors_t1, ev_code));
          }
        }
        break;

      case t1_ev_connect: {
          proto_ev_prm_t prm = { .connect = NULL };
          handle->cb_handle_event(handle->cb_self, proto_ev_connect, prm);
        }
        break;

      case t1_ev_apdu_received: {
          t1_apdu_t* p_apdu = (t1_apdu_t*)ev_prm;
          proto_apdu_t apdu = { .apdu = p_apdu->apdu, .len = p_apdu->len };
          proto_ev_prm_t prm = { .apdu_received = &apdu };
          handle->cb_handle_event(handle->cb_self, proto_ev_apdu_received, prm);
        }
      case t1_ev_pps_exchange_done: {
          proto_ev_prm_t prm = { .connect = NULL };
          handle->cb_handle_event(handle->cb_self, proto_ev_pps_exchange_done, prm);
        }
        break;
      default:
        break; // Ignore unknown event
    }
  }
}

/**
 * T=1: releases protocol context
 *
 * @param handle  protocol handle
 */
static void deinit_t1(proto_handle_t handle) {
  if(handle) {
    if(handle->ctx.t1) {
      m_del(t1_inst_t, handle->ctx.t1, 1);
      handle->ctx.t1 = NULL;
    }
    m_del(proto_inst_t, handle, 1);
  }
}

/**
 * T=1: initializes protocol implementation
 *
 * @param cb_serial_out    callback function outputting bytes to serial port
 * @param cb_handle_event  callback function handling protocol events
 * @param cb_self          self parameter for callback
 * @return                 protocol handle or NULL if failed
 */
static proto_handle_t init_t1(proto_cb_serial_out_t cb_serial_out,
                              proto_cb_handle_event_t cb_handle_event,
                              mp_obj_t cb_self) {

  // Allocate instance of wrap and of a protocol, save parameters
  proto_handle_t handle = m_new0(proto_inst_t, 1);
  handle->ctx.t1 = m_new0(t1_inst_t, 1);
  handle->cb_serial_out = cb_serial_out;
  handle->cb_handle_event = cb_handle_event;
  handle->cb_self = cb_self;
  handle->tx_errors = 0U;

  if(!t1_init(handle->ctx.t1, t1_cb_serial_out, t1_cb_handle_event, handle)) {
    deinit_t1(handle);
    return NULL;
  }

  return handle;
}

/**
 * T=1: re-initializes protocol instance cleaning receive and transmit buffers
 *
 * @param handle  protocol handle
 * @param wait_atr  if true sets protocol instance into "waiting for ATR" state
 */
static void reset_t1(proto_handle_t handle, bool wait_atr) {
  if(handle) {
    t1_reset(handle->ctx.t1, wait_atr);
  }
}

/**
 * T=1: timer task, called by host periodically to implement timeouts
 *
 * @param handle      protocol handle
 * @param elapsed_ms  time in milliseconds passed since previous call
 */
static void timer_task_t1(proto_handle_t handle, uint32_t elapsed_ms) {
  if(handle) {
    t1_timer_task(handle->ctx.t1, elapsed_ms);
  }
}

/**
 * T=1: handles received bytes from serial port
 *
 * @param handle  protocol handle
 * @param buf    buffer holding received bytes
 * @param len    number of bytes received
 */
static void serial_in_t1(proto_handle_t handle, const uint8_t* buf,
                         size_t len) {
  if(scard_module_debug) {
    scard_ansi_color(SCARD_ANSI_GREEN);
    for(size_t i = 0; i < len; ++i) {
      printf(scard_module_debug_ansi ? " %02X" : " r%02X", buf[i]);
    }
    scard_ansi_reset();
  }

  if(handle) {
    t1_serial_in(handle->ctx.t1, buf, len);
  }
}

/**
 * T=1: transmits APDU
 *
 * @param handle  protocol handle
 * @param apdu    buffer containing APDU
 * @param len     length of APDU in bytes
 * @return        true - OK, false - error
 */
static void transmit_apdu_t1(proto_handle_t handle, const uint8_t* apdu,
                             size_t len) {
  if(handle) {
    if(!t1_transmit_apdu(handle->ctx.t1, apdu, len)) {
      emit_error(handle, "error transmitting APDU");
    }
  }
}

/**
 * Sets T=1 protocol parameter
 *
 * @param handle  protocol handle
 * @param prm_id  parameter identifier of T=1 protocol
 * @param value   parameter value, accepts proto_prm_unchanged and
 *                proto_prm_default
 * @return        true if successful
 */
static bool set_t1_config(proto_handle_t handle, t1_config_prm_id_t prm_id,
                          int32_t value) {
  if(proto_prm_default == value) {
    return t1_set_default_config(handle->ctx.t1, prm_id);
  } else if(proto_prm_unchanged != value) {
    return t1_set_config(handle->ctx.t1, prm_id, value);
  }
  return true;
}

/**
 * T=1: Configures protocol timeouts
 *
 * This function accept special values for timeout parameters:
 * proto_prm_unchanged, proto_prm_default.
 *
 * @param handle          protocol handle
 * @param atr_timeout_ms  ATR timeout in ms
 * @param rsp_timeout_ms  response timeout in ms
 * @param max_timeout_ms  maximal response timeout in ms
 * @return                true - OK, false - error
 */
static void set_timeouts_t1(proto_handle_t handle, int32_t atr_timeout_ms,
                            int32_t rsp_timeout_ms, int32_t max_timeout_ms) {
  if(handle) {
    bool ok = set_t1_config(handle, t1_cfg_tm_atr, atr_timeout_ms);
    ok = ok && set_t1_config(handle, t1_cfg_tm_response, rsp_timeout_ms);
    ok = ok && set_t1_config(handle, t1_cfg_tm_response_max, max_timeout_ms);
    if(!ok) {
      emit_error(handle, "error configuring timeouts");
    }
  }
}

/**
 * T=1: Configures parameters of USB transfer
 *
 * This function accept special values for timeout parameters:
 * proto_prm_unchanged, proto_prm_default.
 *
 * @param handle          protocol handle
 * @param maxIFSD         IFSD value for USB transfer
 */
static void set_usb_features_t1(proto_handle_t handle, uint32_t dwFeatures, uint8_t maxIFSD)
{
  if(handle) {
    bool ok = set_t1_config(handle, t1_cfg_dw_fetures, dwFeatures);
    ok = ok && set_t1_config(handle, t1_cfg_ifsd, maxIFSD);
    ok = ok && set_t1_config(handle, t1_cfg_is_usb_reader, 1);
    ok = ok && set_t1_config(handle, t1_cfg_pps_size, 4);
    if(!ok) {
      emit_error(handle, "error configuring USB card reader features");
    }
  }
}
/// Implementations of protocols
const proto_impl_t protocols[] = {
  {
    .id            = T1_protocol,
    .name          = "T=1",
    .init          = init_t1,
    .deinit        = deinit_t1,
    .reset         = reset_t1,
    .timer_task    = timer_task_t1,
    .serial_in     = serial_in_t1,
    .transmit_apdu = transmit_apdu_t1,
    .set_timeouts  = set_timeouts_t1,
    .set_usb_features = set_usb_features_t1
  }
};

const proto_impl_t* proto_get_implementation(mp_int_t protocol) {
  size_t arr_size = sizeof(protocols) / sizeof(protocols[0]);
  for(size_t i = 0; i < arr_size; ++i) {
    if( protocol & ((int)protocols[i].id) ) {
      return &protocols[i];
    }
  }
  return NULL;
}
