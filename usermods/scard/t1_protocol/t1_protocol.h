/**
 * @file       t1_protocol.h
 * @brief      ISO/IEC 7816 T=1 Protocol Implementation, external API
 * @author     Mike Tolkachev <contact@miketolkachev.dev>
 * @copyright  Copyright 2020 Crypto Advance GmbH. All rights reserved.
 */

#ifndef T1_PROTOCOL_H
#define T1_PROTOCOL_H

#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>
#include "fifo_buf.h"

// Include common types definition in Part 1
#include "t1_protocol_defs.h" // Part 1

// Compile-time settings
#ifndef T1_TX_FIFO_SIZE
  /// Transmit FIFO size
  #define T1_TX_FIFO_SIZE               1024
#endif
#ifndef T1_MAX_APDU_SIZE
  /// Maximal size of APDU supported by protocol implementation
  #define T1_MAX_APDU_SIZE              255
#endif
#ifndef T1_MAX_TIMEOUT_MS
  /// Maximal timeout in milliseconds
  #define T1_MAX_TIMEOUT_MS             (100*1000L)
#endif

/// Protocol events
///
/// If parameter is not specified it equals to NULL.
typedef enum {
  t1_ev_none = 0,           ///< Not an event
  t1_ev_atr_received,       ///< ATR is received; parameter: t1_atr_decoded_t*
  t1_ev_connect,            ///< Connection established
  t1_ev_apdu_received,      ///< APDU is received; parameter: t1_apdu_t*
  t1_ev_err_internal = 100, ///< Internal error, also beginning of error codes
  t1_ev_err_serial_out,     ///< Serial output error
  t1_ev_err_comm_failure,   ///< Smart card connection failed
  t1_ev_err_atr_timeout,    ///< ATR timeout
  t1_ev_err_bad_atr,        ///< Incorrect ATR format
  t1_ev_err_incompatible,   ///< Incompatible card; parameter: t1_atr_decoded_t*
  t1_ev_err_oversized_apdu, ///< Received APDU does not fit in buffer
  t1_ev_err_sc_abort,       ///< Operation aborted by smart card
  t1_ev_pps_failed          ///< PPS exchange failed
} t1_ev_code_t;

/// Identifiers of configuration parameters
typedef enum {
  t1_cfg_tm_interbyte = 0, ///< Inter-byte timeout in ms
  t1_cfg_tm_atr,           ///< ATR timeout in ms
  t1_cfg_tm_response,      ///< Response timeout in ms
  t1_cfg_tm_response_max,  ///< Maximal response timeout in ms after WTX request
  t1_cfg_use_crc,          ///< Error detection code: 0 - LRC, 1 - CRC
  t1_cfg_ifsc,             ///< IFSC, card's maximum information block size
  t1_cfg_rx_skip_bytes,    ///< Number of dummy bytes to skip while receiving
  t1_config_size           ///< Size of configuration, not an identifier
} t1_config_prm_id_t;

/**
 * Callback function that outputs bytes to serial port
 *
 * This function may be either blocking or non-blocking, but latter is
 * recommended for completely asynchronous operation.
 * IMPORTANT: Calling API functions of the protocol implementation from this
 * callback function may cause side effects and must be avoided!
 * @param buf         buffer containing data to transmit
 * @param len         length of data block in bytes
 * @param p_user_prm  user defined parameter
 */
typedef bool (*t1_cb_serial_out_t)(const uint8_t* buf, size_t len,
                                   void* p_user_prm);

/**
 * Callback function that handles protocol events
 *
 * This protocol implementation guarantees that event handler is always called
 * just before termination of any external API function. It allows to call
 * safely any other API function(s) within user handler code.
 * Helper function t1_is_error_event() may be used to check if an occurred event
 * is an error.
 * @param ev_code     event code
 * @param ev_prm      event parameter depending on event code, typically NULL
 * @param p_user_prm  user defined parameter
 */
typedef void (*t1_cb_handle_event_t)(t1_ev_code_t ev_code, const void* ev_prm,
                                     void* p_user_prm);

/// Coding convention
typedef enum {
  t1_cnv_direct = 0, ///< Direct
  t1_cnv_inverse     ///< Inverse
} t1_convention_t;

/// Indexes within global_bytes[] and t1_bytes[] arrays of t1_atr_decoded_t
typedef enum {
  t1_atr_ta1 = 0,   ///< global_bytes[]: TA1;         t1_bytes[]: 1-st TA
  t1_atr_tb1,       ///< global_bytes[]: TB1;         t1_bytes[]: 1-st TB
  t1_atr_tc1,       ///< global_bytes[]: TC1;         t1_bytes[]: 1-st TC
  t1_atr_ta2,       ///< global_bytes[]: TA2;         t1_bytes[]: 2-nd TA
  t1_atr_tb2,       ///< global_bytes[]: TB2;         t1_bytes[]: 2-nd TB
  t1_atr_tc2,       ///< global_bytes[]: TC2 of T=0;  t1_bytes[]: 2-nd TC
  t1_atr_ta3,       ///< global_bytes[]: TA (T=15);   t1_bytes[]: 3-rd TA
  t1_atr_tb3,       ///< global_bytes[]: TB (T=15);   t1_bytes[]: 3-rd TB
  t1_atr_tc3,       ///< global_bytes[]: TC (T=15);   t1_bytes[]: 3-rd TC
  t1_atr_intf_bytes ///< Supported number of interface bytes, not an index
} t1_intf_byte_idx_t;

/// Decoded ATR message
typedef struct {
  /// Raw ATR message
  const uint8_t* atr;
  /// Length of raw ATR in bytes
  size_t atr_len;
  /// Coding convention
  t1_convention_t convention;
  /// Global bytes
  int16_t global_bytes[t1_atr_intf_bytes];
  /// Interface bytes
  int16_t t1_bytes[t1_atr_intf_bytes];
  /// Flag indicating that T=0 protocol is suppoted
  bool t0_supported;
  /// Flag indicating that T=1 protocol is suppoted
  bool t1_supported;
  /// Historical bytes
  const uint8_t* hist_bytes;
  /// Number of historical bytes
  size_t hist_nbytes;
} t1_atr_decoded_t;

/// Parameter of t1_ev_apdu_received event
typedef struct {
  const uint8_t *apdu; ///< Pointer to buffer containing APDU
  size_t len;          ///< Length of APDU in bytes
} t1_apdu_t;

// Include instance structure definition in Part 2
#include "t1_protocol_defs.h"

/**
 * Initializes protocol instance
 *
 * By default protocol instance is in "waiting for ATR" state after
 * initialization with default ATR timeout. If ATR is parsed beforhand by host
 * software, then t1_reset() should be called with wait_atr = false to transit
 * protocol FSM into "idle" state. In this case ATR parameters should be
 * supplied manually using t1_set_config() function.
 * If custom ATR timeout is needed after initialisation, then t1_init() should
 * be followed by t1_set_config() and t1_reset() to define new timeout value and
 * to restart timeout timer.
 * @param inst             pre-allocated instance, contents are "don't-care"
 * @param cb_serial_out    callback function outputting bytes to serial port
 * @param cb_handle_event  callback function handling protocol events
 * @param p_user_prm       user defined parameter passed to all calbacks
 * @return                 true - OK, false - failure
 */
T1_EXTERN bool t1_init(t1_inst_t* inst, t1_cb_serial_out_t cb_serial_out,
                       t1_cb_handle_event_t cb_handle_event, void* p_user_prm);

/**
 * Sets configuration parameter
 *
 * Note: configuration parameters may be overriden by incoming ATR sentence.
 * @param inst    protocol instance
 * @param prm_id  parameter identifier
 * @param value   parameter value
 * @return        true - OK, false - failure
 */
T1_EXTERN bool t1_set_config(t1_inst_t* inst, t1_config_prm_id_t prm_id,
                             int32_t value);

/**
 * Sets configuration parameter to default value
 *
 * Note: configuration parameters may be overriden by incoming ATR sentence.
 * @param inst    protocol instance
 * @param prm_id  parameter identifier
 * @return        true - OK, false - failure
 */
T1_EXTERN bool t1_set_default_config(t1_inst_t* inst,
                                     t1_config_prm_id_t prm_id);

/**
 * Returns value of configuration parameter
 * @param inst    protocol instance
 * @param prm_id  parameter identifier
 * @return        value of parameter; -1 if failed or parameter not initialized
 */
T1_EXTERN int32_t t1_get_config(const t1_inst_t* inst,
                                t1_config_prm_id_t prm_id);

/**
 * Re-initializes protocol instance cleaning receive and transmit buffers
 * @param inst      protocol instance
 * @param wait_atr  if true sets protocol instance into "waiting for ATR" state
 */
T1_EXTERN void t1_reset(t1_inst_t* inst, bool wait_atr);

/**
 * Timer task, called by host periodically to implement timeouts
 *
 * This function must be called periodically by host application at least once
 * in 50ms.
 *
 * @param inst        protocol instance
 * @param elapsed_ms  time in milliseconds passed since previous call
 */
T1_EXTERN void t1_timer_task(t1_inst_t* inst, uint32_t elapsed_ms);

/**
 * Returns the number of milliseconds that protocol implementation can sleep
 *
 * This function is used to determine how long the protocol implementation can
 * sleep, assuming that t1_timer_task() is not called by host during sleep. If
 * there is no activity, a maximal value, UINT32_MAX is returned.
 *
 * IMPORTANT: returned result is valid only until any other function of this
 * protocol is called!
 *
 * @param  inst  protocol instance
 * @return       the maximal time in ms the protocol implementation can sleep
 */
T1_EXTERN uint32_t t1_can_sleep_ms(const t1_inst_t* inst);

/**
 * Handles received bytes from serial port
 * @param inst   protocol instance
 * @param buf    buffer holding received bytes
 * @param len    number of bytes received
 */
T1_EXTERN void t1_serial_in(t1_inst_t* inst, const uint8_t* buf, size_t len);

/**
 * Transmits APDU
 * @param inst  protocol instance
 * @param apdu  buffer containing APDU
 * @param len   length of APDU in bytes
 * @return      true - OK, false - error
 */
T1_EXTERN bool t1_transmit_apdu(t1_inst_t* inst, const uint8_t* apdu,
                                size_t len);

/**
 * Helper function checking if protocol event signifies an error
 * @param ev_code  event code
 * @return         true if given event code signifies an error
 */
T1_EXTERN bool t1_is_error_event(t1_ev_code_t ev_code);

/**
 * Helper function checking if protocol implementation is in error state
 *
 * T=1 protocol implementation is always locked in error state in case any
 * critical error is encountered that is signaled by error event. To continue
 * normal operation, protocol implementation needs to be reset by calling
 * t1_reset() function.
 * @param inst  protocol instance
 * @return      true if protocol implementation is locked in error state
 */
T1_EXTERN bool t1_has_error(const t1_inst_t* inst);

#endif // T1_PROTOCOL_H
