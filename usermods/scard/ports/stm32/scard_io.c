/**
 * @file       scard_io_stm32.c
 * @brief      MicroPython uscard module: STM32 port
 * @author     Mike Tolkachev <contact@miketolkachev.dev>
 * @copyright  Copyright 2020 Crypto Advance GmbH. All rights reserved.
 */

#include <stdio.h>
#include "py/obj.h"
#include "py/runtime.h"
#include "py/builtin.h"
#include "py/mperrno.h"
#include "py/mphal.h"
#include "py/smallint.h"
#include "modmachine.h"
#include "uart.h"
#include "t1_protocol.h"
#include "scard.h"

/// Length of receive buffer
#define RX_BUF_LEN                      (270)

/// USART transmission/reception mode
typedef enum usart_mode_ {
  usart_mode_tx_rx = 0,  ///< TX and RX
  usart_mode_tx          ///< TX only
} usart_mode_t;

/// Type information for smart card interface instance
const mp_obj_type_t scard_inst_type;

/// Table of USART descriptors
static const scard_usart_dsc_t usart_dsc_table[] = {
  #ifdef USART0
    { .id = 0U, .handle = USART0 },
  #endif
  #ifdef USART1
    { .id = 1U, .handle = USART1 },
  #endif
  #ifdef USART2
    { .id = 2U, .handle = USART2 },
  #endif
  #ifdef USART3
    { .id = 3U, .handle = USART3 },
  #endif
  #ifdef USART4
    { .id = 4U, .handle = USART4 },
  #endif
  #ifdef USART5
    { .id = 5U, .handle = USART5 },
  #endif
  #ifdef USART6
    { .id = 6U, .handle = USART6 },
  #endif
  #ifdef USART7
    { .id = 7U, .handle = USART7 },
  #endif
  #ifdef USART8
    { .id = 8U, .handle = USART8 },
  #endif
  #ifdef USART9
    { .id = 9U, .handle = USART9 },
  #endif
  #ifdef USART10
    { .id = 10U, .handle = USART10 },
  #endif
  { .handle = NULL } // Terminating record
};

/**
 * Finds USART descriptor in the table
 *
 * @param usart_id  USART identifier
 * @return          pointer to constant USART descriptor
 */
static const scard_usart_dsc_t* find_descriptor(mp_int_t usart_id) {
  const scard_usart_dsc_t* p_dsc = usart_dsc_table;
  while(p_dsc->handle) {
    if(p_dsc->id == usart_id) {
      return p_dsc;
    }
    ++p_dsc;
  }
  return NULL;
}

bool scard_interface_exists(mp_const_obj_t iface_id) {
  if(mp_obj_is_int(iface_id)) {
    mp_int_t usart_id = mp_obj_get_int(iface_id);
    return uart_exists(usart_id) && find_descriptor(usart_id);
  }
  return false;
}

void scard_interface_print_by_id(const mp_print_t *print, mp_const_obj_t iface_id) {
  if(mp_obj_is_int(iface_id)) {
    mp_int_t usart_id = mp_obj_get_int(iface_id);
    mp_printf(print, "USART%d", usart_id);
  } else {
    mp_print_str(print, "unknown");
  }
}

void scard_interface_print(const mp_print_t *print, scard_handle_t handle) {
  if(handle) {
    scard_interface_print_by_id(
      print, MP_OBJ_NEW_SMALL_INT(handle->p_usart_dsc->id));
  } else {
    mp_print_str(print, "NULL");
  }
}

/**
 * Returns input clock frequency of USART
 *
 * @param usart_id  USART identifier, like 3 for USART3
 * @return          clock frequency in Hz
 */
static inline uint32_t get_usart_clock(uint8_t usart_id) {
#if defined(STM32F4)
  if(usart_id == 1U || usart_id == 6U) { // USART1 & USART6 are connected APB2
    return HAL_RCC_GetPCLK2Freq();
  } else {                               // Other USARTs are connected APB1
    return HAL_RCC_GetPCLK1Freq();
  }
#else // STM32F4
  #error MCU series is not supported by smart card interface yet
#endif // STM32F4
}

/**
 * Sets USART transmission/reception mode
 *
 * @param handle  smart card interface handle
 * @param mode    mode
 */
static void set_usart_mode(scard_handle_t handle, usart_mode_t mode) {
#if defined(STM32F4)
  uint32_t irq_state = disable_irq();
  if(mode == usart_mode_tx) {
    handle->sc_handle.Instance->CR1 &= ~USART_CR1_RE;
  } else {
    handle->sc_handle.Instance->CR1 |= USART_CR1_RE;
  }
  enable_irq(irq_state);
#else // STM32F4
  #error MCU series is not supported by smart card interface yet
#endif // STM32F4
}

/**
 * Initializes USART in smart card mode
 * @param sc_handle     handle of smart card low-level driver
 * @param usart_handle  USART handle
 * @return              true if successful
 */
static bool init_smartcard(SMARTCARD_HandleTypeDef* sc_handle,
                           USART_TypeDef* usart_handle, uint8_t usart_id) {
#if defined(STM32F4)
  // Calculate clock prescaler, programmed into USART_GTPR.PSC
  uint32_t clk_in = get_usart_clock(usart_id);
  uint32_t prescaler = (clk_in + 2U * SCARD_MAX_CLK_FREQUENCY_HZ - 1U) /
                       (2U * SCARD_MAX_CLK_FREQUENCY_HZ);
  if(prescaler < 1U) {         // Should not be less than 1
    prescaler = 1U;            // Always divide clock at least by 2
  } else if(prescaler > 31U) { // Should have at most 5 significant bits
    return false;              // Error: input clock is too high
  }

  // Calculate baudrate depending on smart card clock and etu
  // Ideally should be 9600 @ 3.5712MHz CLK
  uint32_t card_clk = clk_in / (2U * prescaler);
  uint32_t baudrate = (card_clk + SCARD_ETU / 2U) / SCARD_ETU;

  sc_handle->Instance = usart_handle;
  sc_handle->Init = (SMARTCARD_InitTypeDef) {
    .WordLength  = SMARTCARD_WORDLENGTH_9B,
    .StopBits    = SMARTCARD_STOPBITS_1_5,
    .Parity      = SMARTCARD_PARITY_EVEN,
    .Mode        = SMARTCARD_MODE_TX_RX,
    .BaudRate    = baudrate,
    .CLKPolarity = SMARTCARD_POLARITY_LOW,
    .CLKPhase    = SMARTCARD_PHASE_1EDGE,
    .CLKLastBit  = SMARTCARD_LASTBIT_ENABLE,
    .Prescaler   = prescaler,
    .GuardTime   = 16U,
    .NACKState   = SMARTCARD_NACK_DISABLE
  };

  if(HAL_OK == HAL_SMARTCARD_Init(sc_handle)) {
    // Disable smart card USART to tweak registers
    __HAL_SMARTCARD_DISABLE(sc_handle);
    // Disable parity interrupt
    __HAL_SMARTCARD_DISABLE_IT(sc_handle, SMARTCARD_IT_PE);
    // Enable smart card USART
    __HAL_SMARTCARD_ENABLE(sc_handle);
    return true;
  }
#else // STM32F4
  #error MCU series is not supported by smart card interface yet
#endif // STM32F4

  return false;
}

/**
 * Initializes pins of USART
 * @param io_pin    IO pin
 * @param clk_pin   CLK pin
 * @param usart_id  USART identifier
 * @return          true if successful
 */
static bool init_pins(mp_obj_t io_pin, mp_obj_t clk_pin, uint8_t usart_id) {
  // Configure USART pins
  bool ok = mp_hal_pin_config_alt(
    pin_find(io_pin), MP_HAL_PIN_MODE_ALT_OPEN_DRAIN, MP_HAL_PIN_PULL_UP,
    AF_FN_USART, usart_id);
  ok = ok && mp_hal_pin_config_alt(
    pin_find(clk_pin), MP_HAL_PIN_MODE_ALT, MP_HAL_PIN_PULL_UP, AF_FN_USART,
    usart_id);

  return ok;
}

/**
 * Create a machine.UART object and sets callback
 *
 * @param handle     smart card interface handle
 * @param uart_id    identifier of UART
 * @param callback   callable object scheduled on receive event
 * @return           machine.UART object
 */
static mp_obj_t create_machine_uart(mp_int_t usart_id, mp_obj_t callback) {
  // Call constructor of machine.UART class
  mp_obj_t args_new[] = {
    // Positional arguments
    MP_OBJ_NEW_SMALL_INT(usart_id), // id
    MP_OBJ_NEW_SMALL_INT(9600),     // baudrate
    MP_OBJ_NEW_SMALL_INT(8),        // bits
    // Keyword arguments
    MP_OBJ_NEW_QSTR(MP_QSTR_timeout), MP_OBJ_NEW_SMALL_INT(0),
    MP_OBJ_NEW_QSTR(MP_QSTR_timeout_char), MP_OBJ_NEW_SMALL_INT(0),
    MP_OBJ_NEW_QSTR(MP_QSTR_rxbuf), MP_OBJ_NEW_SMALL_INT(RX_BUF_LEN)
  };
  mp_obj_t uart = pyb_uart_type.make_new(&pyb_uart_type, 3, 3, args_new);

  // Call machine.UART.irq()
  mp_obj_t args_irq[] = {
      callback,                             // handler
      MP_OBJ_NEW_SMALL_INT(UART_FLAG_IDLE), // trigger
      mp_const_false,                       // hard
  };
  (void)mp_call_function_n_kw(mp_load_attr(uart, MP_QSTR_irq), 3, 0, args_irq);

  return uart;
}

/**
 * Removes IRQ handler and deinitializes machine.UART
 *
 * @param machine_uart_obj  machine.UART object
 */
static void deinit_machine_uart(mp_obj_t machine_uart_obj) {
  // Call machine.UART.irq()
  mp_obj_t args_irq[] = {
      mp_const_none,                        // handler = None
      MP_OBJ_NEW_SMALL_INT(UART_FLAG_IDLE), // trigger
      mp_const_false,                       // hard
  };
  mp_obj_t irq_fn = mp_load_attr(machine_uart_obj, MP_QSTR_irq);
  (void)mp_call_function_n_kw(irq_fn, 3, 0, args_irq);

  // Call machine.UART.deinit()
  mp_obj_t deinit_fn = mp_load_attr(machine_uart_obj, MP_QSTR_deinit);
  (void)mp_call_function_0(deinit_fn);
}

scard_handle_t scard_interface_init(mp_const_obj_t iface_id, mp_obj_t io_pin,
                                    mp_obj_t clk_pin,
                                    scard_cb_data_rx_t cb_data_rx,
                                    mp_obj_t cb_self) {
  scard_handle_t self = NULL;

  if(mp_obj_is_int(iface_id)) {
    mp_int_t usart_id = mp_obj_get_int(iface_id);
    const scard_usart_dsc_t* p_usart_dsc = find_descriptor(usart_id);
    if(p_usart_dsc) {
      // Create a new interface instance
      self = m_new0(scard_inst_t, 1);
      self->base.type = &scard_inst_type;
      self->p_usart_dsc = p_usart_dsc;
      self->suppress_loopback = true; // Should be conditional for other MCUs
      self->skip_bytes = 0;

      // Create machine.UART and set callback
      mp_obj_t uart_cb = mp_load_attr(self, MP_QSTR_uart_callback);
      self->machine_uart_obj = create_machine_uart(usart_id, uart_cb);
      // Get pointer to underlying system object to use C API instead of Python.
      // Yes, this is an abstraction leak, made intentionally for the sake of
      // performance.
      self->uart_obj = MP_STATE_PORT(pyb_uart_obj_all)[usart_id - 1];
      if(self->uart_obj == NULL) {
        raise_CardConnectionException("failed to obtain system UART object");
      }

      // Overwrite USART registers with settings for smart card
      if(!init_smartcard(&self->sc_handle, p_usart_dsc->handle, usart_id)) {
        raise_CardConnectionException("failed to initialize USART");
      }

      // Initialize pins
      if(!init_pins(io_pin, clk_pin, p_usart_dsc->id)) {
        raise_CardConnectionException("failed to configure USART pins");
      }

      // Save callback and self parameter
      self->cb_data_rx = cb_data_rx;
      self->cb_self = cb_self;

      if(scard_module_debug) {
        printf("\r\nSTM32 SC interface created");
      }
    } else {
      mp_raise_ValueError("USART does not exists");
    }
  } else {
    mp_raise_TypeError("usart_id is not an integer");
  }

  return self;
}

size_t scard_rx_readinto(scard_handle_t handle, uint8_t* buf, size_t nbytes) {
  size_t bytes_read = 0;
  uint8_t* p_data = buf;

  while(bytes_read <= nbytes && uart_rx_any(handle->uart_obj)) {
    if(handle->skip_bytes) {
      volatile int dummy = uart_rx_char(handle->uart_obj);
      (void)dummy;
      --handle->skip_bytes;
    } else {
      *p_data++ = uart_rx_char(handle->uart_obj);
      ++bytes_read;
    }
  }
  return bytes_read;
}

bool scard_tx_write(scard_handle_t handle, const uint8_t* buf, size_t nbytes) {
  // UART driver does not like empty operations
  if(!nbytes) {
    return true;
  }

  int errcode = 0;

  // If transmitted bytes are returned as received data we need to suppress
  // loopback. Using set_usart_mode() instead causes missing of quick responses
  // like PPS exchange responses.
  if(handle->suppress_loopback && handle->skip_bytes <= (SIZE_MAX - nbytes)) {
    handle->skip_bytes += nbytes;
  }
  size_t bytes_written = uart_tx_data(handle->uart_obj, buf, nbytes, &errcode);

  return (errcode == 0 && bytes_written == nbytes);
}

void scard_interface_deinit(scard_handle_t handle) {
  scard_inst_t* self = (scard_inst_t*)handle;

  // Deinitialize machine.UART
  if(self->machine_uart_obj) {
    deinit_machine_uart(self->machine_uart_obj);
    self->machine_uart_obj = NULL;
    self->uart_obj = NULL;
  }

  // Delete interface instance
  m_del(scard_inst_t, self, 1);

  if(scard_module_debug) {
    printf("\r\nSTM32 SC interface deleted");
  }
}

scard_pin_dsc_t scard_pin(mp_obj_t user_obj, mp_int_t polarity, bool output,
                          scard_pin_state_t def_state) {
  scard_pin_dsc_t pin = {
    .pin = pin_find(user_obj),
    .invert = polarity ? 0U : 1U
  };
  uint32_t mode = output ? MP_HAL_PIN_MODE_OUTPUT : MP_HAL_PIN_MODE_INPUT;
  uint32_t input_pull = polarity ? MP_HAL_PIN_PULL_DOWN : MP_HAL_PIN_PULL_UP;
  uint32_t pull = output ? MP_HAL_PIN_PULL_NONE : input_pull;
  if(output) {
    scard_pin_write(&pin, def_state);
  }
  mp_hal_pin_config(pin.pin, mode, pull, 0U);
  return pin;
}

scard_pin_state_t scard_pin_read_debounce(scard_pin_dsc_t* p_pin,
                                          uint32_t time_ms) {
  scard_pin_state_t state = scard_pin_read(p_pin);
  scard_pin_state_t prev_state = state;
  mp_uint_t prev_ticks = mp_hal_ticks_ms();
  mp_uint_t delay = time_ms;
  mp_uint_t timeout = 10U * time_ms;

  do {
    // Read pin state
    prev_state = state;
    state = scard_pin_read(p_pin);

    // Calculate elapsed time
    mp_uint_t ticks = mp_hal_ticks_ms();
    mp_uint_t elapsed = scard_ticks_diff(ticks, prev_ticks);
    prev_ticks = ticks;

    // Check if state is changed
    if(state != prev_state) {
      delay = time_ms; // Re-initialize delay
    } else {
      delay -= min_mp_uint_t(elapsed, delay);
    }

    // Update timeout
    timeout -= min_mp_uint_t(elapsed, timeout);
  } while(state != prev_state && delay && timeout);

  return state;
}

/**
 * Callback method for UART interrupt
 *
 * @param self_in  an instance of smart card interface
 * @param unused   UART object (unused)
 * @return         None
 */
STATIC mp_obj_t uart_callback(mp_obj_t self_in, mp_obj_t unused) {
  scard_inst_t* self = (scard_inst_t*)self_in;
  (void)unused;

  uint8_t buf[32];
  uint8_t* p_buf = buf;

  while(uart_rx_any(self->uart_obj)) {
    if(self->skip_bytes) {
      volatile int dummy = uart_rx_char(self->uart_obj);
      (void)dummy;
      --self->skip_bytes;
    } else {
      *p_buf++ = uart_rx_char(self->uart_obj);
      if(p_buf >= buf + sizeof(buf)) {
        self->cb_data_rx(self->cb_self, buf, sizeof(buf));
        p_buf = buf;
      }
    }
  }

  if(p_buf > buf) {
    self->cb_data_rx(self->cb_self, buf, p_buf - buf);
  }
  return mp_const_none;
}
STATIC MP_DEFINE_CONST_FUN_OBJ_2(uart_callback_obj, uart_callback);

STATIC const mp_rom_map_elem_t scard_inst_locals_dict_table[] = {
  // Instance methods
  { MP_ROM_QSTR(MP_QSTR_uart_callback), MP_ROM_PTR(&uart_callback_obj) },
};
STATIC MP_DEFINE_CONST_DICT(scard_inst_locals_dict, scard_inst_locals_dict_table);

const mp_obj_type_t scard_inst_type = {
  { &mp_type_type },
  .locals_dict = (void*)&scard_inst_locals_dict,
};
