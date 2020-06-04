/**
 * @file       scard.h
 * @brief      MicroPython uscard module: common definitions
 * @author     Mike Tolkachev <contact@miketolkachev.dev>
 * @copyright  Copyright 2020 Crypto Advance GmbH. All rights reserved.
 */

#ifndef SCARD_H_INCLUDED
/// Avoids multiple inclusion of this file
#define SCARD_H_INCLUDED

#include <stdio.h>
#include "py/obj.h"
#include "py/mphal.h"
#include "py/smallint.h"
#include "py/runtime.h"

/// Maximum frequency of CLK clock provided to smart card, 5MHz
#define SCARD_MAX_CLK_FREQUENCY_HZ      (5000000LU)
/// Elementary time unit, etu, equals to 372 clock cycles
#define SCARD_ETU                       (372U)

/** @defgroup scard_ansi ANSI colors, used for debug output
 * @{ */
/// Red
#define SCARD_ANSI_RED                  "\e[0;31m"
/// Green
#define SCARD_ANSI_GREEN                "\e[0;32m"
/// Yellow
#define SCARD_ANSI_YELLOW               "\e[0;33m"
/// Blue
#define SCARD_ANSI_BLUE                 "\e[0;34m"
/// Magenta
#define SCARD_ANSI_MAGENTA              "\e[0;35m"
/// Cyan
#define SCARD_ANSI_CYAN                 "\e[0;36m"
/// White
#define SCARD_ANSI_WHITE                "\e[0;37m"
/// Resets color to default
#define SCARD_ANSI_RESET                "\e[0m"
/** @} */

/// State of a pin
typedef enum scard_pin_state_ {
  INACT = 0, ///< Active state
  ACT   = 1, ///< Inactive state
} scard_pin_state_t;

/**
 * Callback function handling received data
 *
 * This function is called by smart card interface when any data is received
 * from the card. It is guaranteed that this callback function is called from
 * a normal context, not from an interrupt service routine.
 * @param self  instance of a class which method is called
 * @param buf   buffer containing received data
 * @param len   length of data block in bytes
 */
typedef void (*scard_cb_data_rx_t)(mp_obj_t self, const uint8_t* buf,
                                   size_t len);

#include "scard_io.h"

#if defined(NDEBUG)
  /// Disables debug output forever
  #define scard_module_debug (0)
  /// Disables ANSI support for debug output forever
  #define scard_module_debug_ansi (0)
#else
  /// Flag variable enabling debug output
  extern bool scard_module_debug;
  /// Flag variable enabling ANSI support for debug output
  extern bool scard_module_debug_ansi;
#endif

/// SmartcardException exception
extern const mp_obj_type_t mp_type_SmartcardException;
/// CardConnectionException exception
extern const mp_obj_type_t mp_type_CardConnectionException;
/// NoCardException exception
extern const mp_obj_type_t mp_type_NoCardException;

/**
 * Checks if smart card interface exists with given ID
 *
 * @param iface_id  interface ID (platform-dependant)
 * @return          true if interface exists
 */
extern bool scard_interface_exists(mp_const_obj_t iface_id);

/**
 * Prints interface name
 *
 * @param print     output stream for mp_printf()
 * @param iface_id  interface ID (platform-dependant)
 */
extern void scard_interface_print_by_id(const mp_print_t *print,
                                        mp_const_obj_t iface_id);

/**
 * Prints interface name
 *
 * @param print   output stream for mp_printf()
 * @param handle  handle to smart card interface
 */
extern void scard_interface_print(const mp_print_t *print,
                                  scard_handle_t handle);

/**
 * Initializes smart card interface
 *
 * @param iface_id    interface ID (platform-dependant)
 * @param io_pin      IO pin
 * @param clk_pin     CLK pin
 * @param cb_data_rx  callback function handling received data
 * @param self        self parameter for callback function
 * @return            handle to smart card interface or NULL if failed
 */
extern scard_handle_t scard_interface_init(mp_const_obj_t iface_id,
                                           mp_obj_t io_pin,
                                           mp_obj_t clk_pin,
                                           scard_cb_data_rx_t cb_data_rx,
                                           mp_obj_t cb_self);

/**
 * Reads bytes from smart card interface into buffer, if available
 *
 * @param handle  handle to smart card interface
 * @param buf     buffer receiving received data
 * @param nbytes  maximum number of bytes to read
 * @return        actual number of received bytes, 0 if no data available
 */
extern size_t scard_rx_readinto(scard_handle_t handle, uint8_t* buf,
                                size_t nbytes);

/**
 * Writes a buffer of data to smart card
 *
 * This function can be either blocking or non-blocking depending on
 * implementation for the specific platform.
 *
 * @param handle  handle to smart card interface
 * @param buf     buffer containing bytes to transmit
 * @param nbytes  number of bytes to transmit
 * @return        true if successful
 */
extern bool scard_tx_write(scard_handle_t handle, const uint8_t* buf,
                           size_t nbytes);

/**
 * Deinitializes smart card interface
 *
 * @param handle  handle to smart card interface
 */
extern void scard_interface_deinit(scard_handle_t handle);

/**
 * Creates a new pin
 * @param user_obj   user-provided pin object
 * @param polarity   polarity: 0 - active low, 1 - active high
 * @param output     if true pin is configured as output
 * @param def_state  default state for an output pin
 * @return           pin descriptor
 */
extern scard_pin_dsc_t scard_pin(mp_obj_t user_obj, mp_int_t polarity,
                                 bool output, scard_pin_state_t def_state);

/**
 * Creates a new input pin
 * @param user_obj  user-provided pin object
 * @param polarity  polarity: 0 - active low, 1 - active high
 * @return          pin descriptor
 */
static inline scard_pin_dsc_t scard_pin_in(mp_obj_t user_obj,
                                           mp_int_t polarity) {
  return scard_pin(user_obj, polarity, false, 0U);
}

/**
 * Creates a new output pin
 * @param user_obj   user-provided pin object
 * @param polarity   polarity: 0 - active low, 1 - active high
 * @param def_state  default state
 * @return           pin descriptor
 */
static inline scard_pin_dsc_t scard_pin_out(mp_obj_t user_obj, mp_int_t polarity,
                                      scard_pin_state_t def_state) {
  return scard_pin(user_obj, polarity, true, def_state);
}

/**
 * Returns state of a pin with debounce
 * @param p_pin    pointer to pin descriptor
 * @param time_ms  debounce time in milliseconds
 */
extern scard_pin_state_t scard_pin_read_debounce(scard_pin_dsc_t* p_pin,
                                                 uint32_t time_ms);

/**
 * Raises the SmartcardException
 * @param message  message associated with exception
 */
static inline void raise_SmartcardException(const char* message) {
  mp_raise_msg(&mp_type_SmartcardException, message);
}

/**
 * Raises the CardConnectionException
 * @param message  message associated with exception
 */
static inline void raise_CardConnectionException(const char* message) {
  mp_raise_msg(&mp_type_CardConnectionException, message);
}

/**
 * Raises the SmartcardException
 * @param message  message associated with exception
 */
static inline void raise_NoCardException(const char* message) {
  mp_raise_msg(&mp_type_NoCardException, message);
}

/**
 * Local implementation of utime.ticks_diff()
 *
 * Formula taken from micropython/extmod/utime_mphal.c
 * @param end    ending time
 * @param start  starting time
 * @return       ticks difference between end and start values
 */
static inline mp_uint_t scard_ticks_diff(mp_uint_t end, mp_uint_t start) {
  // Optimized formula avoiding if conditions. We adjust difference "forward",
  // wrap it around and adjust back.
  mp_uint_t diff = ( (end - start + MICROPY_PY_UTIME_TICKS_PERIOD / 2) &
                     (MICROPY_PY_UTIME_TICKS_PERIOD - 1) ) -
                   MICROPY_PY_UTIME_TICKS_PERIOD / 2;
  return diff;
}

/**
 * Returns minimal of two mp_uint_t operands
 * @param a  operand A
 * @param b  operand B
 * @return   minimal of A and B
 */
static inline mp_uint_t min_mp_uint_t(mp_uint_t a, mp_uint_t b) {
    return a < b ? a : b;
}

/**
 * Sets ANSI color
 *
 * @param color  color
 */
static inline void scard_ansi_color(const char* color) {
#if !defined(NDEBUG)
  if(scard_module_debug && scard_module_debug_ansi) {
    printf(color);
  }
#endif
}

/**
 * Resets ANSI color to default
 */
static inline void scard_ansi_reset(void) {
#if !defined(NDEBUG)
  if(scard_module_debug && scard_module_debug_ansi) {
    printf(SCARD_ANSI_RESET);
  }
#endif
}

#endif // SCARD_H_INCLUDED
