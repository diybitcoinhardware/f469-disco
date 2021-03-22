/**
 * @file       connection.h
 * @brief      MicroPython uscard module: CardConnection class
 * @author     Mike Tolkachev <contact@miketolkachev.dev>
 * @copyright  Copyright 2020 Crypto Advance GmbH. All rights reserved.
 */

#ifndef CONNECTION_H_INCLUDED
/// Avoids multiple inclusion of this file
#define CONNECTION_H_INCLUDED

#include "py/obj.h"

/// Connection parameters PODO
typedef struct scard_reader_conn_params_ {
  mp_obj_base_t base; ///< Pointer to type of base class
  mp_obj_t iface_id;  ///< Interface identifier, like 3 for USART3
  mp_obj_t io_pin;    ///< Bidirectional IO pin to use
  mp_obj_t clk_pin;   ///< CLK output pin to use
  mp_obj_t rst_pin;   ///< RST output pin to use
  mp_obj_t pres_pin;  ///< Card presence detect pin to use
  mp_obj_t pwr_pin;   ///< Pin controling power to the card
  mp_int_t rst_pol;   ///< RST polarity, active low by default
  mp_int_t pres_pol;  ///< Polarity of card presence detect pin
  mp_int_t pwr_pol;   ///< Polarity of power control pin
  mp_obj_t timer_id;  ///< ID of the timer to be used use for background tasks
} scard_conn_params_t;

/// Connection parameters PODO type
extern const mp_obj_type_t scard_conn_params_type;
/// Connection class type
extern const mp_obj_type_t scard_CardConnection_type;

#endif // CONNECTION_H_INCLUDED
