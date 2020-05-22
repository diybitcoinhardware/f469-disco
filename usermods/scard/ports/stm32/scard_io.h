/**
 * @file       scard_io.h
 * @brief      MicroPython uscard module: STM32 port definitions
 * @author     Mike Tolkachev <contact@miketolkachev.dev>
 * @copyright  Copyright 2020 Crypto Advance GmbH. All rights reserved.
 */

#ifndef SCARD_IO_H_INCLUDED
/// Avoids multiple inclusion of this file
#define SCARD_IO_H_INCLUDED

#include "uart.h"

/// USART descriptor
typedef struct scard_usart_dsc_ {
  uint8_t id;                ///< USART identifier, e.g. 3 for USART3
  USART_TypeDef* handle;     ///< USART handle
} scard_usart_dsc_t;

/// Smart card interface instance and handle
typedef struct scard_inst_ {
  mp_obj_base_t base;                    ///< Pointer to type of base class
  SMARTCARD_HandleTypeDef sc_handle;     ///< HAL Smartcard handle structure
  const scard_usart_dsc_t* p_usart_dsc;  ///< Pointer to USART descriptor
  mp_obj_t machine_uart_obj;             ///< machine.UART object used for IO
  pyb_uart_obj_t* uart_obj;              ///< Underlying UART object
  scard_cb_data_rx_t cb_data_rx;         ///< Callback for received data
  mp_obj_t cb_self;                      ///< Self parameter for callback(s)
  bool suppress_loopback;                ///< If true suppresses loopback echo
  size_t skip_bytes;                     ///< Counter of skipped bytes
} scard_inst_t, *scard_handle_t;

/// Pin descriptor
typedef struct scard_pin_dsc_ {
  mp_hal_pin_obj_t pin;     ///< Pin object
  unsigned int invert : 1;  ///< Logic: 0 - normal, 1 - inverted
} scard_pin_dsc_t;

/**
 * Writes state to output register of a pin
 * @param p_pin  pointer to pin descriptor
 * @param state  pin state
 */
static inline void scard_pin_write(scard_pin_dsc_t* p_pin, scard_pin_state_t state) {
  mp_hal_pin_write(p_pin->pin, (unsigned int)state ^ p_pin->invert);
}

/**
 * Returns state of a pin
 * @param p_pin  pointer to pin descriptor
 */
static inline scard_pin_state_t scard_pin_read(scard_pin_dsc_t* p_pin) {
  uint32_t state = mp_hal_pin_read(p_pin->pin) ? 1U : 0U;
  return (scard_pin_state_t)(state ^ p_pin->invert);
}

#endif // SCARD_IO_H_INCLUDED
