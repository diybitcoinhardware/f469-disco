/**
 * @file       connection.c
 * @brief      MicroPython uscard module: CardConnection class
 * @author     Mike Tolkachev <contact@miketolkachev.dev>
 * @copyright  Copyright 2020 Crypto Advance GmbH. All rights reserved.
 */

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
#include "scard.h"
#include "connection.h"
#include "reader.h"

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

/// Object of CardConnection class
typedef struct connection_obj_ {
  mp_obj_base_t base;            ///< Pointer to type of base class
  mp_obj_t reader;               ///< Reader to which connection is bound
  state_t state;                 ///< Connection state
  scard_handle_t sc_handle;      ///< Handle of smart card interface
  scard_pin_dsc_t rst_pin;       ///< RST pin descriptor
  scard_pin_dsc_t pres_pin;      ///< Card presence pin descriptor
  scard_pin_dsc_t pwr_pin;       ///< PWR pin descriptor
  mp_obj_t timer;                ///< Timer object
  mp_uint_t prev_ticks_ms;       ///< Previous value of millisecond ticks
  const proto_impl_t* protocol;  ///< Protocol used to communicate with card
  proto_handle_t proto_handle;   ///< Protocol handle
  mp_obj_t observers;            ///< List of observers
  bool blocking;                 ///< If true, all operations are blocking
  int32_t atr_timeout_ms;        ///< ATR timeout in ms
  int32_t rsp_timeout_ms;        ///< Response timeout in ms
  int32_t max_timeout_ms;        ///< Maximal response timeout in ms
  bool raise_on_error;           ///< Forces exception for non-blocking mode
  event_t event_buf[MAX_EVENTS]; ///< Event buffer
  size_t event_idx;              ///< Event index within event_buf[]
  mp_obj_t atr;                  ///< ATR as bytes object
  mp_obj_t response;             ///< Card response, a list [data, sw1, sw2]
  mp_int_t next_protocol;        ///< ID of the protocol for the next op.
  uint16_t presence_cycles;      ///< Counter of card presence cycles (debounce)
  bool presence_state;           ///< Card presence state
} connection_obj_t;

/// Type information for CardConnection class
const mp_obj_type_t scard_CardConnection_type;

STATIC mp_obj_t connection_disconnect(mp_obj_t self_in);

/**
 * Scheduled task notifying all observers about all occurred events
 *
 * Not intended to be called by user.
 *
 * @param self    instance of CardConnection class
 * @param unused  unused
 * @return        None
 */
STATIC mp_obj_t connection_notifyAll(mp_obj_t self_in, mp_obj_t unused) {
  connection_obj_t* self = (connection_obj_t*)self_in;
  size_t n_events = self->event_idx;
  self->event_idx = 0U; // Clear event buffer

  // Extract the list of observers
  size_t n_observers;
  mp_obj_t* observers;
  mp_obj_list_get(self->observers, &n_observers, &observers);

  // Loop over all events in the buffer
  const event_t* p_event = self->event_buf;
  while(p_event != self->event_buf + n_events) {
    // Notify all observers
    for(size_t i = 0U; i < n_observers; ++i) {
      (void)mp_call_function_n_kw( observers[i], EVENT_POS_ARGS, p_event->n_kw,
                                   p_event->args );
    }
    ++p_event;
  }

  return mp_const_none;
}

/**
 * Returns length of a list
 *
 * @param list  list
 * @return      list length
 */
static size_t list_get_len(mp_obj_t list) {
  if(list != MP_OBJ_NULL) {
    size_t len;
    mp_obj_t* items;
    mp_obj_list_get(list, &len, &items);
    return len;
  }
  return 0U;
}

/**
 * Creates event and stores it in buffer
 *
 * @param self  instance of CardConnection class
 * @param args  arguments of event passed to observer
 * @param n_kw  number of keyword arguments
 */
static void create_event(connection_obj_t* self, mp_obj_t* args, size_t n_kw) {
  if(self->event_idx + 1U > MAX_EVENTS || n_kw > EVENT_MAX_KW) {
    raise_SmartcardException("event buffer overflow");
  }

  // If we have any observers add event to buffer
  if(list_get_len(self->observers)) {
    event_t* p_event = self->event_buf + self->event_idx;
    for(size_t i = 0U; i < EVENT_POS_ARGS + 2U * n_kw; ++i) {
      p_event->args[i] = args[i];
    }
    p_event->n_kw = n_kw;

    // Schedule call of connection_notifyAll() on the first event
    if(++self->event_idx == 1U) {
      mp_obj_t handler = mp_load_attr(self, MP_QSTR__notifyAll);
      mp_sched_schedule(handler, mp_const_none);
    }
  }
}

/**
 * Notifies observers passing only type arguments
 *
 * @param self        instance of CardConnection class
 * @param event_type  type argument
 */
static void notify_observers(connection_obj_t* self, event_type_t event_type) {
  mp_obj_t args[] =  {
    MP_OBJ_FROM_PTR(self),            // connection
    MP_OBJ_NEW_QSTR((qstr)event_type) // type
  };
  create_event(self, args, 0U);
}

/**
 * Notifies observers passing type and text arguments
 *
 * @param self        instance of CardConnection class
 * @param event_type  type argument
 * @param text        text argument
 */
static void notify_observers_text(connection_obj_t* self,
                                  event_type_t event_type,
                                  const char* text) {
  mp_obj_t text_obj = mp_obj_new_str(text, strlen(text));
  mp_obj_t args_list = mp_obj_new_list(1U, &text_obj);
  mp_obj_t args[] =  {
    MP_OBJ_FROM_PTR(self),                                      // connection
    MP_OBJ_NEW_QSTR((qstr)event_type),                          // type
    MP_OBJ_NEW_QSTR(MP_QSTR_args), MP_OBJ_FROM_PTR(args_list), // args
  };
  create_event(self, args, 1U);
}

/**
 * Notifies observers passing smart card command
 *
 * @param self   instance of CardConnection class
 * @param bytes  command data
 */
static void notify_observers_command(connection_obj_t* self, mp_obj_t bytes) {
  // Make a list with arguments [bytes, protocol]
  protocol_t protocol_id = self->protocol ? self->protocol->id : protocol_na;
  mp_obj_list_t* args_list = mp_obj_new_list(2U, NULL);
  args_list->items[0] = bytes;                             // bytes
  args_list->items[1] = MP_OBJ_NEW_SMALL_INT(protocol_id); // protocol

  mp_obj_t args[] =  {
    MP_OBJ_FROM_PTR(self),                                     // connection
    MP_OBJ_NEW_QSTR((qstr)event_command),                      // type
    MP_OBJ_NEW_QSTR(MP_QSTR_args), MP_OBJ_FROM_PTR(args_list), // args
  };
  create_event(self, args, 1U);
}

/**
 * Notifies observers passing smart card response
 *
 * @param self      instance of CardConnection class
 * @param response  smart card response list
 */
static void notify_observers_response(connection_obj_t* self,
                                      mp_obj_t response) {
  mp_obj_t args[] =  {
    MP_OBJ_FROM_PTR(self),                                    // connection
    MP_OBJ_NEW_QSTR((qstr)event_response),                    // type
    MP_OBJ_NEW_QSTR(MP_QSTR_args), MP_OBJ_FROM_PTR(response), // args
  };
  create_event(self, args, 1U);
}

/**
 * Creates a new response list from raw data
 *
 * @param data  smart card response data
 * @param len   number of data bytes
 * @return      list object [data, sw1, sw2]
 */
static mp_obj_t make_response_list(const uint8_t* data, size_t len) {
  mp_obj_list_t* response = MP_OBJ_NULL;

  if(len >= 2U) {
    response = mp_obj_new_list(3U, NULL);
    response->items[0] = mp_obj_new_bytes(data, len - 2U);     // data
    response->items[1] = MP_OBJ_NEW_SMALL_INT(data[len - 2U]); // sw1
    response->items[2] = MP_OBJ_NEW_SMALL_INT(data[len - 1U]); // sw2
  } else {
    response = mp_obj_new_list(1U, NULL);
    response->items[0] = mp_obj_new_bytes(data, len); // data
  }

  return MP_OBJ_TO_PTR(response);
}

/**
 * Callback function that outputs bytes to serial port
 *
 * @param self_in  instance of user class
 * @param buf      buffer containing data to transmit
 * @param len      length of data block in bytes
 */
static bool proto_cb_serial_out(mp_obj_t self_in, const uint8_t* buf,
                                size_t len) {
  connection_obj_t* self = (connection_obj_t*)self_in;
  return scard_tx_write(self->sc_handle, buf, len);
}

/**
 * Callback function that handles protocol events
 *
 * This protocol implementation guarantees that event handler is always called
 * just before termination of any external API function. It allows to call
 * safely any other API function(s) within user handler code.
 *
 * @param self_in  instance of user class
 * @param ev_code  event code
 * @param ev_prm   event parameter depending on event code, typically NULL
 */
static void proto_cb_handle_event(mp_obj_t self_in, proto_ev_code_t ev_code,
                                  proto_ev_prm_t prm) {
  connection_obj_t* self = (connection_obj_t*)self_in;

  switch(ev_code) {
    case proto_ev_atr_received:
      self->atr = mp_obj_new_bytes(prm.atr_received->atr,
                                   prm.atr_received->len);
      break;

    case proto_ev_connect:
      if(state_connecting == self->state) {
        self->state = state_connected;
        notify_observers(self, event_connect);
      }
      break;

    case proto_ev_apdu_received:
      if(state_connected == self->state) {
        mp_obj_t response = make_response_list(prm.apdu_received->apdu,
                                                prm.apdu_received->len);
        notify_observers_response(self, response);
        if(self->blocking) {
          self->response = response;
        }
      }
      break;

    case proto_ev_error:
      connection_disconnect(self);
      self->state = state_error;
      notify_observers_text(self, event_error, prm.error);
      if(self->raise_on_error || self->blocking) {
        self->raise_on_error = false;
        raise_SmartcardException(prm.error);
      }
      break;
  }
}

/**
 * Handles change of smart card presence state
 *
 * @param self       instance of CardConnection class
 * @param new_state  new state: true - card present, false - card absent
 */
static void handle_card_presence_change(connection_obj_t* self,
                                        bool new_state) {
  const char* err_unexp_removal = "unexpected card removal";

  if(new_state != self->presence_state) {
    self->presence_state = new_state;
    if(new_state) { // Card present
      notify_observers(self, event_insertion);
    } else { // Card absent
      notify_observers(self, event_removal);
      // Check if the card is in use
      if(state_connecting == self->state ||
         state_connected  == self->state ) {
        // Handle unexpected card removal
        connection_disconnect(self);
        self->state = state_error;
        notify_observers_text(self, event_error, err_unexp_removal);
        if(self->blocking) {
          raise_SmartcardException(err_unexp_removal);
        }
      }
    }
  }
}

/**
 * Checks if smart card is present
 *
 * @param self  an instance of CardConnection class
 * @return      true if card present
 */
static bool card_present(connection_obj_t* self) {
  // Read pin with blocking debounce algorithm if no timer is created or
  // non-blocking debounce algorithm has not come to a stable state yet.
  if( MP_OBJ_NULL == self->timer ||
      self->presence_cycles < CARD_PRESENCE_CYCLES ) {
    scard_pin_state_t state =
      scard_pin_read_debounce(&self->pres_pin, DEBOUNCE_TIME_MS);
    handle_card_presence_change(self, (state == ACT) ? true : false);
  }
  return self->presence_state;
}

/**
 * The periodic task that detects presence of smart card
 *
 * This task is called each 1ms ... 50ms.
 *
 * @param self  instance of CardConnection class
 */
static void card_detection_task(connection_obj_t* self) {
  bool state = scard_pin_read(&self->pres_pin) == ACT;
  bool state_valid = false;

  // Non-blocking debounce algorithm. When the pin is active, counter is
  // incremented until it reaches threshold value; at that point pin state is
  // considered valid. When the pin is inactive the counter is set to zero and
  // pin state is valid (absent state).
  if(state) { // Looks like the card is present
    if(self->presence_cycles >= CARD_PRESENCE_CYCLES) {
      state_valid = true;
    } else {
      ++self->presence_cycles;
    }
  } else { // Card is absent
    self->presence_cycles = 0;
    state_valid = true;
  }

  if(state_valid) {
    handle_card_presence_change(self, state);
  }
}

/**
 * Timer task
 *
 * @param self  instance of CardConnection class
 */
static void timer_task(connection_obj_t* self) {
  if(self->state != state_closed) {
    mp_uint_t ticks_ms = mp_hal_ticks_ms();
    mp_uint_t elapsed = scard_ticks_diff(ticks_ms, self->prev_ticks_ms);
    self->prev_ticks_ms = ticks_ms;

    // Run protocol timer task only when we are connecting or connected
    if(state_connecting == self->state || state_connected == self->state) {
      if(self->protocol) {
        self->protocol->timer_task(self->proto_handle, (uint32_t)elapsed);
      }
    }

    // Call card detection task at least once in 1ms
    if(elapsed) {
      card_detection_task(self);
    }
  }
}

/**
 * __call__ special method running background tasks, usually by timer
 * @param self_in  instance of CardConnection class casted to mp_obj_t
 * @param n_args   number of arguments
 * @param n_kw     number of keywords arguments
 * @param args     array containing arguments
 * @return         None
 */
STATIC mp_obj_t connection_call(mp_obj_t self_in, size_t n_args, size_t n_kw,
                                const mp_obj_t *args) {
  connection_obj_t* self = (connection_obj_t*)self_in;
  timer_task(self);

  return mp_const_none;
}

/**
 * Creates a new machine.Timer object for background tasks
 * @param self      instance of CardConnection class
 * @param timer_id  numerical timer identifier
 * @return          new instance of machine.Timer
 */
static mp_obj_t create_timer(connection_obj_t* self, mp_int_t timer_id) {
  mp_obj_t args[] =  {
    // Positional arguments
    MP_OBJ_NEW_SMALL_INT(timer_id), // id
    // Keyword arguments
    MP_OBJ_NEW_QSTR(MP_QSTR_callback), self,
    MP_OBJ_NEW_QSTR(MP_QSTR_period), MP_OBJ_NEW_SMALL_INT(TIMER_PERIOD_MS)
  };
  return machine_timer_type.make_new(&machine_timer_type, 1, 2, args);
}

/**
 * Callback function handling received data
 *
 * @param self_in  instance of a class which method is called
 * @param buf      buffer containing received data
 * @param len      length of data block in bytes
 */
static void cb_data_rx(mp_obj_t self_in, const uint8_t* buf, size_t len) {
  connection_obj_t* self = (connection_obj_t*)self_in;
  if(state_connecting == self->state ||
     state_connected  == self->state ) {
    if(self->protocol) {
      self->protocol->serial_in(self->proto_handle, buf, len);
    }
  }
}

/**
 * Initializes a newly created CardConnection object
 * @param self      instance of CardConnection class
 * @param params    connection parameters
 */
static void connection_init(connection_obj_t* self,
                            const scard_conn_params_t* params) {
  // Initialize smart card hardware interface
  self->sc_handle = scard_interface_init(params->iface_id, params->io_pin,
                                         params->clk_pin, cb_data_rx, self);
  if(!self->sc_handle) {
    raise_CardConnectionException("failed to initialize interface");
  }

  // Configure GPIO pins
  self->rst_pin = scard_pin_out(params->rst_pin, params->rst_pol, ACT);
  self->pres_pin = scard_pin_in(params->pres_pin, params->pres_pol);
  self->pwr_pin = scard_pin_out(params->pwr_pin, params->pwr_pol, INACT);

  // Save system ticks and initialize timer
  self->prev_ticks_ms = mp_hal_ticks_ms();
  if(mp_obj_is_type(params->timer_id, &mp_type_NoneType)) {
    self->timer = MP_OBJ_NULL;
  } else if(mp_obj_is_int(params->timer_id)) {
    self->timer = create_timer(self, mp_obj_get_int(params->timer_id));
  } else {
    mp_raise_TypeError("timer_id must be integer or None");
  }

  // Make connection alive
  self->state = state_disconnected;
}

/**
 * @brief Constructor of CardConnection
 *
 * Constructor
 * .. class:: CardConnection(reader, connParams)
 *
 *  Constructs a connection object
 *
 *    - *reader* reader to which connection is bound, instance of Reader class
 *    - *connParams* connection parameters provided by the reader
 *
 * CardConnection object must not be constructed by user! Use
 * Reader.createConnection instead.
 *
 * @param type      pointer to type structure
 * @param n_args    number of arguments
 * @param n_kw      number of keyword arguments
 * @param all_args  array containing arguments
 * @return          a new instance of CardConnection class
 */
STATIC mp_obj_t connection_make_new(const mp_obj_type_t* type, size_t n_args,
                                    size_t n_kw, const mp_obj_t* all_args) {
  // Arguments
  enum {
    ARG_reader = 0, ARG_connParams,
    ARG_n_min // Minimal number of arguments
  };
  static const mp_arg_t allowed_args[] = {
    { MP_QSTR_reader,     MP_ARG_REQUIRED|MP_ARG_OBJ, {.u_obj = MP_OBJ_NULL} },
    { MP_QSTR_connParams, MP_ARG_REQUIRED|MP_ARG_OBJ, {.u_obj = MP_OBJ_NULL} }
  };
  mp_arg_val_t args[MP_ARRAY_SIZE(allowed_args)];

  // Parse and check parameters
  mp_arg_parse_all_kw_array(n_args, n_kw, all_args, MP_ARRAY_SIZE(allowed_args),
                            allowed_args, args);
  if( args[ARG_reader].u_obj == MP_OBJ_NULL ||
      args[ARG_connParams].u_obj == MP_OBJ_NULL ||
      !mp_obj_is_type(args[ARG_reader].u_obj, &scard_Reader_type) ||
      !mp_obj_is_type(args[ARG_connParams].u_obj, &scard_conn_params_type) ) {
    raise_SmartcardException("connection not bound to reader");
  }
  const scard_conn_params_t* conn_params =
    (const scard_conn_params_t*)args[ARG_connParams].u_obj;

  if(scard_module_debug) {
    printf("\r\nNew smart card connection");
  }

  // Create a new connection object
  connection_obj_t* self = m_new_obj_with_finaliser(connection_obj_t);
  memset(self, 0U, sizeof(connection_obj_t));
  self->base.type = &scard_CardConnection_type;
  self->reader = args[ARG_reader].u_obj;
  self->state = state_closed;
  self->timer = MP_OBJ_NULL;
  self->protocol = NULL;
  self->proto_handle = NULL;
  self->observers = mp_obj_new_list(0, NULL);
  self->blocking = true;
  self->atr_timeout_ms = proto_prm_unchanged;
  self->rsp_timeout_ms = proto_prm_unchanged;
  self->max_timeout_ms = proto_prm_unchanged;
  self->raise_on_error = false;
  self->event_idx = 0;
  self->atr = MP_OBJ_NULL;
  self->response = MP_OBJ_NULL;
  self->next_protocol = protocol_na;
  self->presence_cycles = 0;
  self->presence_state = false;
  connection_init(self, conn_params);

  return MP_OBJ_FROM_PTR(self);
}

/**
 * Changes smart card protocol
 *
 * @param self           instance of CardConnection class
 * @param protocol_id    identifier of the new protocol
 * @param reset_if_same  if true resets protocol instance if it's not changed
 * @param wait_atr       if true sets protocol instance into "waiting for ATR"
 *                       state when the protocol is replaced or reset
 */
static void change_protocol(connection_obj_t* self, mp_int_t protocol_id,
                            bool reset_if_same, bool wait_atr) {

  // Get implementation of the new smart card protocol
  const proto_impl_t* protocol = proto_get_implementation(protocol_id);
  if(!protocol) {
    raise_SmartcardException("protocol not supported");
  }

  // Check if protocol is already in use
  if(self->proto_handle && protocol == self->protocol) {
    // Already in use, we need to reset it if requested
    if(reset_if_same) {
      self->protocol->reset(self->proto_handle, wait_atr);
    }
  } else {
    // Release previous protocol handle if available
    if(self->protocol && self->proto_handle) {
      self->protocol->deinit(self->proto_handle);
    }

    // Allocate the new protocol instance and get handle
    self->protocol = protocol;
    self->proto_handle = protocol->init( proto_cb_serial_out,
                                         proto_cb_handle_event, self );
    if(!self->proto_handle) {
      self->protocol = NULL;
      raise_SmartcardException("error initializing protocol");
    }
    if(!wait_atr) { // The caller asks to skip "waiting for ATR" state
      self->protocol->reset(self->proto_handle, false);
    }

    // Set timeouts, raise exception if failed even for non-blocking connection
    self->raise_on_error = true;
    protocol->set_timeouts(self->proto_handle, self->atr_timeout_ms,
                           self->rsp_timeout_ms, self->max_timeout_ms);
    self->raise_on_error = false;
  }
}

/**
 * Waits for connection to complete in blocking mode
 *
 * @param self  instance of CardConnection class
 */
static inline void wait_connect_blocking(connection_obj_t* self) {
  uint8_t rx_buf[WAIT_LOOP_RX_BUF_SIZE];

  // Loop while the state is not changed in the handler of protocol events or
  // exception is not raised.
  while(self->state == state_connecting) {
    size_t n_bytes = scard_rx_readinto(self->sc_handle, rx_buf, sizeof(rx_buf));
    self->protocol->serial_in(self->proto_handle, rx_buf, n_bytes);
    timer_task(self);
    MICROPY_EVENT_POLL_HOOK
  }
}

/**
 * @brief Connects to a smart card
 *
 * .. method:: CardConnection.connect(protocol=None)
 *
 *  Connects to a smart card. Arguments:
 *    - *protocol* protocol identifier, if None uses previously selected
 *      protocol (if any), or default protocol if nothing selected
 *
 * @param n_args    number of arguments
 * @param pos_args  positional arguments
 * @param kw_args   keyword arguments
 * @return          None
 */
STATIC mp_obj_t connection_connect(size_t n_args, const mp_obj_t *pos_args,
                                   mp_map_t *kw_args) {
  // Get self
  assert(n_args >= 1U);
  connection_obj_t* self = (connection_obj_t*)MP_OBJ_TO_PTR(pos_args[0]);

  // Parse and check arguments
  enum { ARG_protocol = 0 };
  static const mp_arg_t allowed_args[] = {
    { MP_QSTR_protocol, MP_ARG_INT, { .u_int = protocol_na } },
  };
  mp_arg_val_t args[MP_ARRAY_SIZE(allowed_args)];
  mp_arg_parse_all(n_args - 1U, pos_args + 1U, kw_args,
                   MP_ARRAY_SIZE(allowed_args), allowed_args, args);

  // Check if the state allows connection
  switch(self->state) {
    case state_closed:
      raise_CardConnectionException("connection is closed");
      return mp_const_none;

    case state_connecting:
    case state_connected:
      raise_CardConnectionException("already connected");
      return mp_const_none;

    default:
      break;
  }

  // Change smart card protocol if requested
  mp_int_t new_protocol = (protocol_na != args[ARG_protocol].u_int) ?
    args[ARG_protocol].u_int : self->next_protocol;
  self->next_protocol = protocol_na;
  // If protocol not defined, use default protocol
  new_protocol = (protocol_na == new_protocol) ? protocol_any : new_protocol;
  change_protocol( self, new_protocol, true, true );

  // Apply power and reset the card
  if(!card_present(self)) {
    raise_NoCardException("no card inserted");
  }
  scard_pin_write(&self->rst_pin, ACT);
  scard_pin_write(&self->pwr_pin, ACT);
  mp_hal_delay_ms(RESET_TIME_MS);
  scard_pin_write(&self->rst_pin, INACT);

  // Update state
  self->state = state_connecting;

  if(self->blocking) {
    wait_connect_blocking(self);
  }

  return mp_const_none;
}

/**
 * @brief Checks if smart card is inserted
 *
 * .. method:: CardConnection.isCardInserted()
 *
 * @param self_in   instance of CardConnection class
 * @return          True if smart card is inserted
 */
STATIC mp_obj_t connection_isCardInserted(mp_obj_t self_in) {
  connection_obj_t* self = (connection_obj_t*)self_in;
  return card_present(self) ? mp_const_true : mp_const_false;
}

/**
 * @brief Enables/disables blocking operation
 *
 * .. method:: CardConnection.setBlocking(blocking)
 *
 * @param self_in   instance of CardConnection class
 * @param blocking  if true, all operations are blocking
 * @return          None
 */
STATIC mp_obj_t connection_setBlocking(mp_obj_t self_in, mp_obj_t blocking_in) {
  connection_obj_t* self = (connection_obj_t*)self_in;
  bool blocking  = mp_obj_is_true(blocking_in);

  if(!blocking && MP_OBJ_NULL == self->timer) {
    mp_raise_ValueError("no timer for non-blocking operation");
  }
  self->blocking = blocking;
  return mp_const_none;
}

/**
 * @brief Checks if connection is in blocking mode
 *
 * .. method:: CardConnection.isBlocking()
 *
 * @param self_in   instance of CardConnection class
 * @return          True if connection is blocking
 */
STATIC mp_obj_t connection_isBlocking(mp_obj_t self_in) {
  connection_obj_t* self = (connection_obj_t*)self_in;
  return self->blocking ? mp_const_true : mp_const_false;
}

/**
 * @brief Sets timeouts for blocking and non-blocking operations
 *
 * .. method:: CardConnection.setTimeouts( atrTimeout=None,
 *                                         responseTimeout=None,
 *                                         maxTimeout=None )
 *
 *  Configures protocol timeouts, all arguments are optional:
 *
 *    - *atrTimeout* ATR timeout in ms, -1 = default
 *    - *responseTimeout* response timeout in ms, -1 = default
 *    - *maxTimeout* maximal response timeout in ms used when smart card
 *      (repeatedly) requesting timeout extension, -1 = default
 *
 * @param n_args    number of arguments
 * @param pos_args  positional arguments
 * @param kw_args   keyword arguments
 * @return          None
 */
STATIC mp_obj_t connection_setTimeouts(size_t n_args, const mp_obj_t *pos_args,
                                       mp_map_t *kw_args) {
  // Get self
  assert(n_args >= 1U);
  connection_obj_t* self = (connection_obj_t*)MP_OBJ_TO_PTR(pos_args[0]);

  // Parse and check arguments
  enum { ARG_atrTimeout = 0, ARG_responseTimeout, ARG_maxTimeout };
  static const mp_arg_t allowed_args[] = {
    { MP_QSTR_atrTimeout,      MP_ARG_OBJ, {.u_obj = mp_const_none} },
    { MP_QSTR_responseTimeout, MP_ARG_OBJ, {.u_obj = mp_const_none} },
    { MP_QSTR_maxTimeout,      MP_ARG_OBJ, {.u_obj = mp_const_none} }
  };
  mp_arg_val_t args[MP_ARRAY_SIZE(allowed_args)];
  mp_arg_parse_all(n_args - 1U, pos_args + 1U, kw_args,
                   MP_ARRAY_SIZE(allowed_args), allowed_args, args);

  // Check if connection is closed
  if(state_closed == self->state) {
    raise_CardConnectionException("connection is closed");
  }

  // Save parameters
  self->atr_timeout_ms =
    mp_obj_is_type(args[ARG_atrTimeout].u_obj, &mp_type_NoneType) ?
      proto_prm_unchanged : mp_obj_get_int(args[ARG_atrTimeout].u_obj);

  self->rsp_timeout_ms =
    mp_obj_is_type(args[ARG_responseTimeout].u_obj, &mp_type_NoneType) ?
      proto_prm_unchanged : mp_obj_get_int(args[ARG_responseTimeout].u_obj);

  self->max_timeout_ms =
    mp_obj_is_type(args[ARG_maxTimeout].u_obj, &mp_type_NoneType) ?
      proto_prm_unchanged : mp_obj_get_int(args[ARG_maxTimeout].u_obj);

  // Configure protocol if it is initialized
  if(self->protocol) {
    self->protocol->set_timeouts(self->proto_handle, self->atr_timeout_ms,
                                 self->rsp_timeout_ms, self->max_timeout_ms);
  }

  return mp_const_none;
}

/**
 * Waits for response from smart card in blocking mode
 *
 * @param self  instance of CardConnection class
 */
static void wait_response_blocking(connection_obj_t* self) {
  uint8_t rx_buf[WAIT_LOOP_RX_BUF_SIZE];

  // Loop while there is no response from the smart card. May be interrupted by
  // an exception raised inside handler of the protocol as well.
  while(self->response == MP_OBJ_NULL) {
    size_t n_bytes = scard_rx_readinto(self->sc_handle, rx_buf, sizeof(rx_buf));
    self->protocol->serial_in(self->proto_handle, rx_buf, n_bytes);
    timer_task(self);
    MICROPY_EVENT_POLL_HOOK
  }
}

/**
 * Converts objects to byte buffer
 *
 * @param dst        destination buffer of bytes
 * @param objects    source array of objects
 * @param n_objects  number of objects to convert
 * @return           true if successful
 */
static bool objects_to_buf(uint8_t* buf, const mp_obj_t* objects,
                           size_t n_objects) {
  const mp_obj_t* p_obj = objects;
  const mp_obj_t* arr_end = objects + n_objects;
  uint8_t* p_dst = buf;
  mp_int_t value = 0;

  while(p_obj != arr_end) {
    if( mp_obj_get_int_maybe(*p_obj++, &value) &&
        value >= 0U && value <= UINT8_MAX ) {
      *p_dst++ = (uint8_t)value;
    } else {
      return false;
    }
  }

  return true;
}

/**
 * @brief Transmit an APDU to the smart card
 *
 * .. method:: CardConnection.transmit(bytes, protocol=None)
 *
 *  Transmit an APDU to the smart card. Arguments:
 *    - *bytes* buffer containing APDU
 *    - *protocol* protocol identifier, if None uses previously selected
 *      protocol (if any), or default protocol if nothing selected
 *
 * @param n_args    number of arguments
 * @param pos_args  positional arguments
 * @param kw_args   keyword arguments
 * @return          None
 */
STATIC mp_obj_t connection_transmit(size_t n_args, const mp_obj_t *pos_args,
                                    mp_map_t *kw_args) {
  // Get self
  assert(n_args >= 1U);
  connection_obj_t* self = (connection_obj_t*)MP_OBJ_TO_PTR(pos_args[0]);

  // Parse and check arguments
  enum { ARG_bytes = 0, ARG_protocol };
  static const mp_arg_t allowed_args[] = {
    { MP_QSTR_bytes,    MP_ARG_REQUIRED | MP_ARG_OBJ, {.u_obj = mp_const_none}},
    { MP_QSTR_protocol, MP_ARG_OBJ,                   {.u_obj = mp_const_none}}
  };
  mp_arg_val_t args[MP_ARRAY_SIZE(allowed_args)];
  mp_arg_parse_all(n_args - 1U, pos_args + 1U, kw_args,
                   MP_ARRAY_SIZE(allowed_args), allowed_args, args);

  // Check connection state
  if(state_connected != self->state) {
    raise_SmartcardException("card not connected");
  }

  // Change smart card protocol if requested
  mp_int_t new_protocol = self->next_protocol;
  self->next_protocol = protocol_na;
  if(!mp_obj_is_type(args[ARG_protocol].u_obj, &mp_type_NoneType)) {
    new_protocol = mp_obj_get_int(args[ARG_protocol].u_obj);
  }
  if(new_protocol != protocol_na) {
    change_protocol(self, new_protocol, false, false);
  }
  if(!self->protocol) {
    raise_SmartcardException("no protocol selected");
  }

  // Notify observers of transmitted command
  notify_observers_command(self, args[ARG_bytes].u_obj);

  // Get data buffer of 'bytes' argument
  mp_buffer_info_t bufinfo = { .buf = NULL, .len = 0U };
  uint8_t static_buf[32];
  uint8_t* dynamic_buf = NULL;
  // Check if bytes is a list
  if(mp_obj_is_type(args[ARG_bytes].u_obj, &mp_type_list)) { // 'bytes' is list
    // Get properties of the list
    mp_obj_t* items;
    mp_obj_list_get(args[ARG_bytes].u_obj, &bufinfo.len, &items);
    // Chose static buffer or allocate dynamic buffer if needed
    if(bufinfo.len <= sizeof(static_buf)) {
      bufinfo.buf = static_buf;
    } else {
      dynamic_buf = m_new(uint8_t, bufinfo.len);
      bufinfo.buf = dynamic_buf;
    }
    // Convert list to a buffer of bytes
    if(!objects_to_buf(bufinfo.buf, items, bufinfo.len)) {
      mp_raise_ValueError("incorrect data format");
    }
  } else { // 'bytes' is bytes array or anything supporting buffer protocol
    mp_get_buffer_raise(args[ARG_bytes].u_obj, &bufinfo, MP_BUFFER_READ);
  }

  // Transmit APDU
  self->response = MP_OBJ_NULL;
  self->protocol->transmit_apdu(self->proto_handle, bufinfo.buf, bufinfo.len);
  // Let's free dynamic buffer manually to help the GC
  if(dynamic_buf) {
    m_del(uint8_t, dynamic_buf, bufinfo.len);
    dynamic_buf = NULL;
  }
  if(self->blocking) {
    wait_response_blocking(self);
    // Do not keep the reference to allow GC to remove response later
    mp_obj_t response = self->response;
    self->response = MP_OBJ_NULL;
    return response;
  }

  return mp_const_none;
}

/**
 * @brief Checks if connection is active
 *
 * .. method:: CardConnection.isActive()
 *
 *  Checks connection state, returning True if card is inserted and powered
 *
 * @param self_in  instance of CardConnection class
 * @return         connection state: True - active, False - not active
 */
STATIC mp_obj_t connection_isActive(mp_obj_t self_in) {
  connection_obj_t* self = (connection_obj_t*)self_in;

  switch(self->state) {
    case state_connecting:
    case state_connected:
      return mp_const_true;

    default:
      return mp_const_false;
  }
}

/**
 * @brief Returns connection state
 *
 * .. method:: CardConnection.getState()
 *
 *  Returns connection state, one of the following QSTR strings:
 *
 *    - *'closed'* - connection is closed
 *    - *'disconnected'* - smart card is disconnected
 *    - *'connecting'* - smart card connection is in progress
 *    - *'connected'* - smart card is connected and ready to use
 *    - *'error'* - smart card error
 *
 * @param self_in  instance of CardConnection class
 * @return         connection state, one of uscard.STATE_* constants
 */
STATIC mp_obj_t connection_getState(mp_obj_t self_in) {
  connection_obj_t* self = (connection_obj_t*)self_in;
  return MP_OBJ_NEW_QSTR((qstr)self->state);
}

/**
 * @brief Returns ATR sentence received from the smart card
 *
 * .. method:: CardConnection.getATR()
 *
 * @param self_in  instance of CardConnection class
 * @return         ATR sentence as array bytes or None if not available
 */
STATIC mp_obj_t connection_getATR(mp_obj_t self_in) {
  connection_obj_t* self = (connection_obj_t*)self_in;
  if(state_closed != self->state && self->atr) {
    return self->atr;
  }
  return mp_const_none;
}

/**
 * @brief Sets smart card protocol
 *
 * .. method:: CardConnection.setProtocol(protocol)
 *
 * NOTE: This protocol change does not affect current transmission
 *
 * @param self_in   instance of CardConnection class
 * @param protocol  protocol identifier
 * @return          None
 */
STATIC mp_obj_t connection_setProtocol(mp_obj_t self_in, mp_obj_t protocol) {
  connection_obj_t* self = (connection_obj_t*)self_in;
  self->next_protocol = mp_obj_get_int(protocol);
  return mp_const_none;
}

/**
 * @brief Returns identifier of selected protocol
 *
 * .. method:: CardConnection.getProtocol()
 *
 * @param self_in  instance of CardConnection class
 * @return         protocol identifier or None if no protocol selected
 */
STATIC mp_obj_t connection_getProtocol(mp_obj_t self_in) {
  connection_obj_t* self = (connection_obj_t*)self_in;
  if(state_closed != self->state && self->protocol) {
    if(protocol_na != self->next_protocol) {
      return MP_OBJ_NEW_SMALL_INT(self->next_protocol);
    }
    return MP_OBJ_NEW_SMALL_INT((mp_int_t)self->protocol->id);
  }
  return mp_const_none;
}

/**
 * @brief Return card connection reader
 *
 * .. method:: CardConnection.getReader()
 *
 * @param self_in  instance of CardConnection class
 * @return         reader object
 */
STATIC mp_obj_t connection_getReader(mp_obj_t self_in) {
  connection_obj_t* self = (connection_obj_t*)self_in;
  if(self->reader) {
    return MP_OBJ_FROM_PTR(self->reader);
  }
  return mp_const_none;
}

/**
 * @brief Adds observer
 *
 * .. method:: CardConnection.addObserver(observer)
 *
 *  Adds observer receiving notifications on events of connection. The
 *  *observer* should be a callable object, a function or a method having the
 *  following signature:
 *
 *  def my_function(cardconnection, type, args=None)
 *  def my_method(self, cardconnection, type, args=None)
 *
 *  Observer arguments:
 *
 *    - *cardconnection* smart card connection
 *    - *type* event type: 'connect', 'disconnect', 'command', 'response',
 *                         'insertion', 'removal', 'error'
 *    - *args* event arguments, a list
 *
 * @param self_in   instance of CardConnection class
 * @param observer  observer, a callable object
 * @return          None
 */
STATIC mp_obj_t connection_addObserver(mp_obj_t self_in, mp_obj_t observer) {
  connection_obj_t* self = (connection_obj_t*)self_in;

  if(!mp_obj_is_callable(observer)) {
    mp_raise_TypeError("observer must be callable");
  }
  (void)mp_obj_list_append(self->observers, observer);

  return mp_const_none;
}

/**
 * @brief Deletes observer
 *
 * .. method:: CardConnection.deleteObserver(observer)
 *
 *  Deletes observer. The *observer* should be a callable object.
 *
 * @param self_in   instance of CardConnection class
 * @param observer  observer, a callable object
 * @return          None
 */
STATIC mp_obj_t connection_deleteObserver(mp_obj_t self_in, mp_obj_t observer) {
  connection_obj_t* self = (connection_obj_t*)self_in;

  if(!mp_obj_is_callable(observer)) {
    mp_raise_TypeError("observer must be callable");
  }
  (void)mp_obj_list_remove(self->observers, observer);

  return mp_const_none;
}

/**
 * @brief Deletes all observers
 *
 * .. method:: CardConnection.deleteObservers()
 *
 *  Deletes all observers.
 *
 * @param self_in  instance of CardConnection class
 * @return         None
 */
STATIC mp_obj_t connection_deleteObservers(mp_obj_t self_in) {
  connection_obj_t* self = (connection_obj_t*)self_in;

  // Remove references to each observer to help the GC
  size_t n_observers;
  mp_obj_t* observers;
  mp_obj_list_get(self->observers, &n_observers, &observers);
  for(size_t i = 0U; i < n_observers; ++i) {
    observers[i] = MP_OBJ_NULL;
  }

  // Replace with a new empty list
  self->observers = mp_obj_new_list(0, NULL);

  return mp_const_none;
}

/**
 * @brief Returns number of registered observers
 *
 * .. method:: CardConnection.countObservers()
 *
 *  Returns number of registered observers.
 *
 * @param self_in  instance of CardConnection class
 * @return         number of registered observers
 */
STATIC mp_obj_t connection_countObservers(mp_obj_t self_in) {
  connection_obj_t* self = (connection_obj_t*)self_in;
  return MP_OBJ_NEW_SMALL_INT(list_get_len(self->observers));
}

/**
 * @brief Terminates communication with a smart card and removes power
 *
 * .. method:: CardConnection.disconnect()
 *
 *  Terminates communication with a smart card and removes power. Call this
 *  function before asking the user to remove a smart card. This function does
 *  not close connection but makes it inactive. When a new card is inserted, the
 *  connection object may be reused with the same parameters.
 *
 * @param self_in  instance of CardConnection class
 * @return         None
 */
STATIC mp_obj_t connection_disconnect(mp_obj_t self_in) {
  connection_obj_t* self = (connection_obj_t*)self_in;

  if(state_closed       != self->state &&
     state_disconnected != self->state) {
    if(self->protocol) {
      self->protocol->reset(self->proto_handle, false);
    }

    self->atr = MP_OBJ_NULL;
    self->response = MP_OBJ_NULL;

    // Apply reset and remove power
    scard_pin_write(&self->rst_pin, ACT);
    scard_pin_write(&self->pwr_pin, INACT);

    self->state = state_disconnected;
    notify_observers(self, event_disconnect);
  }
  return mp_const_none;
}

/**
 * @brief Closes connection releasing hardware resources
 *
 * .. method:: CardConnection.close()
 *
 *  Closes connection releasing hardware resources
 *
 * @param self_in  instance of CardConnection class
 * @return         None
 */
STATIC mp_obj_t connection_close(mp_obj_t self_in) {

  connection_obj_t* self = (connection_obj_t*)self_in;
  if(self->state != state_closed) {
    connection_disconnect(self_in);
    connection_deleteObservers(self_in);

    // Deinitialize timer
    if(self->timer) {
      mp_obj_t deinit_fn = mp_load_attr(self->timer, MP_QSTR_deinit);
      (void)mp_call_function_0(deinit_fn);
      self->timer = MP_OBJ_NULL;
    }

    // Release hardware interface
    scard_interface_deinit(self->sc_handle);
    self->sc_handle = NULL;

    // Release protocol context
    if(self->protocol && self->proto_handle) {
      self->protocol->deinit(self->proto_handle);
    }
    self->proto_handle = NULL;
    self->protocol = NULL;

    // Detach from reader
    reader_deleteConnection(self->reader, MP_OBJ_FROM_PTR(self));
    self->reader = MP_OBJ_NULL;

    // Mark connection object as closed
    self->state = state_closed;
  }

  return mp_const_none;
}

/**
 * Prints CardConnection object
 *
 * @param print    output stream
 * @param self_in  instance of CardConnection class
 * @param kind     print kind
 */
STATIC void connection_print(const mp_print_t *print, mp_obj_t self_in,
                             mp_print_kind_t kind) {
  connection_obj_t* self = (connection_obj_t*)self_in;

  mp_print_str(print, "<CardConnection at '");
  scard_interface_print(print, self->sc_handle);
  printf( "' inserted=%b, state='%q', protocol='%s', blocking=%b, observers=%u>",
          card_present(self),
          (qstr)self->state,
          self->protocol ? self->protocol->name : "None",
          self->blocking,
          list_get_len(self->observers) );
}

STATIC MP_DEFINE_CONST_FUN_OBJ_KW(connection_connect_obj, 1, connection_connect);
STATIC MP_DEFINE_CONST_FUN_OBJ_1(connection_isCardInserted_obj, connection_isCardInserted);
STATIC MP_DEFINE_CONST_FUN_OBJ_2(connection_setBlocking_obj, connection_setBlocking);
STATIC MP_DEFINE_CONST_FUN_OBJ_1(connection_isBlocking_obj, connection_isBlocking);
STATIC MP_DEFINE_CONST_FUN_OBJ_KW(connection_setTimeouts_obj, 1, connection_setTimeouts);
STATIC MP_DEFINE_CONST_FUN_OBJ_KW(connection_transmit_obj, 1, connection_transmit);
STATIC MP_DEFINE_CONST_FUN_OBJ_1(connection_isActive_obj, connection_isActive);
STATIC MP_DEFINE_CONST_FUN_OBJ_1(connection_getState_obj, connection_getState);
STATIC MP_DEFINE_CONST_FUN_OBJ_1(connection_getATR_obj, connection_getATR);
STATIC MP_DEFINE_CONST_FUN_OBJ_2(connection_setProtocol_obj, connection_setProtocol);
STATIC MP_DEFINE_CONST_FUN_OBJ_1(connection_getProtocol_obj, connection_getProtocol);
STATIC MP_DEFINE_CONST_FUN_OBJ_1(connection_getReader_obj, connection_getReader);
STATIC MP_DEFINE_CONST_FUN_OBJ_2(connection_addObserver_obj, connection_addObserver);
STATIC MP_DEFINE_CONST_FUN_OBJ_2(connection_deleteObserver_obj, connection_deleteObserver);
STATIC MP_DEFINE_CONST_FUN_OBJ_1(connection_deleteObservers_obj, connection_deleteObservers);
STATIC MP_DEFINE_CONST_FUN_OBJ_1(connection_countObservers_obj, connection_countObservers);
STATIC MP_DEFINE_CONST_FUN_OBJ_1(connection_disconnect_obj, connection_disconnect);
STATIC MP_DEFINE_CONST_FUN_OBJ_1(connection_close_obj, connection_close);
STATIC MP_DEFINE_CONST_FUN_OBJ_2(connection_notifyAll_obj, connection_notifyAll);

STATIC const mp_rom_map_elem_t connection_locals_dict_table[] = {
  // Instance methods
  { MP_ROM_QSTR(MP_QSTR___del__),         MP_ROM_PTR(&connection_close_obj)            },
  { MP_ROM_QSTR(MP_QSTR___enter__),       MP_ROM_PTR(&mp_identity_obj)                 },
  { MP_ROM_QSTR(MP_QSTR___exit__),        MP_ROM_PTR(&connection_close_obj)            },
  { MP_ROM_QSTR(MP_QSTR_connect),         MP_ROM_PTR(&connection_connect_obj)          },
  { MP_ROM_QSTR(MP_QSTR_isCardInserted),  MP_ROM_PTR(&connection_isCardInserted_obj)   },
  { MP_ROM_QSTR(MP_QSTR_setBlocking),     MP_ROM_PTR(&connection_setBlocking_obj)      },
  { MP_ROM_QSTR(MP_QSTR_isBlocking),      MP_ROM_PTR(&connection_isBlocking_obj)       },
  { MP_ROM_QSTR(MP_QSTR_setTimeouts),     MP_ROM_PTR(&connection_setTimeouts_obj)      },
  { MP_ROM_QSTR(MP_QSTR_transmit),        MP_ROM_PTR(&connection_transmit_obj)         },
  { MP_ROM_QSTR(MP_QSTR_isActive),        MP_ROM_PTR(&connection_isActive_obj)         },
  { MP_ROM_QSTR(MP_QSTR_getState),        MP_ROM_PTR(&connection_getState_obj)         },
  { MP_ROM_QSTR(MP_QSTR_getATR),          MP_ROM_PTR(&connection_getATR_obj)           },
  { MP_ROM_QSTR(MP_QSTR_setProtocol),     MP_ROM_PTR(&connection_setProtocol_obj)      },
  { MP_ROM_QSTR(MP_QSTR_getProtocol),     MP_ROM_PTR(&connection_getProtocol_obj)      },
  { MP_ROM_QSTR(MP_QSTR_getReader),       MP_ROM_PTR(&connection_getReader_obj)        },
  { MP_ROM_QSTR(MP_QSTR_addObserver),     MP_ROM_PTR(&connection_addObserver_obj)      },
  { MP_ROM_QSTR(MP_QSTR_deleteObserver),  MP_ROM_PTR(&connection_deleteObserver_obj)   },
  { MP_ROM_QSTR(MP_QSTR_deleteObservers), MP_ROM_PTR(&connection_deleteObservers_obj)  },
  { MP_ROM_QSTR(MP_QSTR_countObservers),  MP_ROM_PTR(&connection_countObservers_obj)   },
  { MP_ROM_QSTR(MP_QSTR_disconnect),      MP_ROM_PTR(&connection_disconnect_obj)       },
  { MP_ROM_QSTR(MP_QSTR_close),           MP_ROM_PTR(&connection_close_obj)            },
  { MP_ROM_QSTR(MP_QSTR__notifyAll),      MP_ROM_PTR(&connection_notifyAll_obj)        },
  // Class constants
  { MP_ROM_QSTR(MP_QSTR_T0_protocol),     MP_ROM_INT(T0_protocol)                      },
  { MP_ROM_QSTR(MP_QSTR_T1_protocol),     MP_ROM_INT(T1_protocol)                      },
};
STATIC MP_DEFINE_CONST_DICT(connection_locals_dict, connection_locals_dict_table);

const mp_obj_type_t scard_CardConnection_type = {
  { &mp_type_type },
  .name = MP_QSTR_CardConnection,
  .print = connection_print,
  .make_new = connection_make_new,
  .call = connection_call,
  .locals_dict = (void*)&connection_locals_dict,
};

const mp_obj_type_t scard_conn_params_type = {
  { &mp_type_type }
};
