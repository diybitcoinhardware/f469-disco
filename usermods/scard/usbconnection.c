/**
 * @file       usbconnection.c
 * @brief      MicroPython uscard usb module: UsbReader class
 * @author     Rostislav Gurin <rgurin@embedity.dev>
 * @copyright  Copyright 2021 Crypto Advance GmbH. All rights reserved.
 */

#include "usbconnection.h"

/**
 * @brief Constructor of UsbCardConnection
 *
 * Constructor
 * .. class:: UsbCardConnection(usbreader, connParams)
 *
 *  Constructs a connection object
 *
 *    - *usbreader* reader to which connection is bound, instance of Reader class
 *    - *connParams* connection parameters provided by the reader
 *
 * CardConnection object must not be constructed by user! Use
 * UsbReader.createConnection instead.
 *
 * @param type      pointer to type structure
 * @param n_args    number of arguments
 * @param n_kw      number of keyword arguments
 * @param all_args  array containing arguments
 * @return          a new instance of CardConnection class
 */
STATIC mp_obj_t connection_make_new(const mp_obj_type_t* type, size_t n_args,
                                    size_t n_kw, const mp_obj_t* all_args) 
{
  // Create a new connection object
  // Arguments
  enum {
    ARG_reader = 0,
  };
  static const mp_arg_t allowed_args[] = {
    { MP_QSTR_reader,     MP_ARG_REQUIRED|MP_ARG_OBJ, {.u_obj = MP_OBJ_NULL} },
  };
  mp_arg_val_t args[MP_ARRAY_SIZE(allowed_args)];

  // Parse and check parameters
  mp_arg_parse_all_kw_array(n_args, n_kw, all_args, MP_ARRAY_SIZE(allowed_args),
                            allowed_args, args);
  if( args[ARG_reader].u_obj == MP_OBJ_NULL ||
      !mp_obj_is_type(args[ARG_reader].u_obj, &scard_UsbReader_type))
  {
    raise_SmartcardException("connection not bound to usb reader");
  }
    
  usb_connection_obj_t* self = m_new_obj_with_finaliser(usb_connection_obj_t);
  memset(self, 0U, sizeof(usb_connection_obj_t));
  self->base.type = &scard_UsbCardConnection_type;
  self->reader = args[ARG_reader].u_obj;;
  self->state = state_closed;
  self->CCID_Handle = NULL;
  self->timer = MP_OBJ_NULL;
  self->pbSeq = 0;
  self->atr_timeout_ms = 350;
  self->rsp_timeout_ms = 350;
  self->max_timeout_ms = 500;
  usb_timer_init(self);
  printf("\r\nNew USB smart card connection\n");
  return MP_OBJ_FROM_PTR(self);                                    
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
 * @param self  instance of UsbCardConnection class
 * @param args  arguments of event passed to observer
 * @param n_kw  number of keyword arguments
 */
static void create_event(usb_connection_obj_t* self, mp_obj_t* args, size_t n_kw) {
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
 * @param self        instance of UsbCardConnection class
 * @param event_type  type argument
 */
static void notify_observers(usb_connection_obj_t* self, event_type_t event_type) {
  mp_obj_t args[] =  {
    MP_OBJ_FROM_PTR(self),            // connection
    MP_OBJ_NEW_QSTR((qstr)event_type) // type
  };
  create_event(self, args, 0U);
}

/**
 * Notifies observers passing type and text arguments
 *
 * @param self        instance of UsbCardConnection class
 * @param event_type  type argument
 * @param text        text argument
 */
static void notify_observers_text(usb_connection_obj_t* self,
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
 * @param self   instance of UsbCardConnection class
 * @param bytes  command data
 */
static void notify_observers_command(usb_connection_obj_t* self, mp_obj_t bytes) {
  // Make a list with arguments [bytes, protocol]
  mp_obj_list_t* args_list = mp_obj_new_list(2U, NULL);
  args_list->items[0] = bytes;                             // bytes

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
 * @param self      instance of UsbCardConnection class
 * @param response  smart card response list
 */
static void notify_observers_response(usb_connection_obj_t* self,
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
 * __call__ special method running background tasks, usually by timer
 * @param self_in  instance of CardConnection class casted to mp_obj_t
 * @param n_args   number of arguments
 * @param n_kw     number of keywords arguments
 * @param args     array containing arguments
 * @return         None
 */
STATIC mp_obj_t connection_call(mp_obj_t self_in, size_t n_args, size_t n_kw,
                                const mp_obj_t *args) {
  usb_connection_obj_t* self = (usb_connection_obj_t*)self_in;
  timer_task(self);
  return mp_const_none;
}

/**
 * Timer task
 *
 * @param self  instance of UsbCardConnection class
 */
static void timer_task(usb_connection_obj_t* self) {
    mp_uint_t ticks_ms = mp_hal_ticks_ms();
    mp_uint_t elapsed = scard_ticks_diff(ticks_ms, self->prev_ticks_ms);
    self->prev_ticks_ms = ticks_ms;
    if(elapsed)
    {
      led_state(4, 0);
      USBH_Process(&hUsbHostFS);
      if(hUsbHostFS.gState == HOST_CLASS)
      {
        if(self->state != state_connected)
        {
          self->state = state_connecting;
        }
      }
      else
      {
        self->state = state_closed;
      }
      mp_hal_delay_ms(100);
      led_state(4, 1);
    }
}

/**
 * Creates a new machine.Timer object for background tasks
 * @param self      instance of CardConnection class
 * @param timer_id  numerical timer identifier
 * @return          new instance of machine.Timer
 */
static mp_obj_t create_timer(usb_connection_obj_t* self, mp_int_t timer_id) {
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
 * Init a new timer. Timer object for background tasks
 * @param self      instance of UsbCardConnection class
 */
STATIC void usb_timer_init(usb_connection_obj_t* self) 
{
  mp_int_t timer_id = -1;
  // Save system ticks and initialize timer
  self->prev_ticks_ms = mp_hal_ticks_ms();
  self->timer = create_timer(self, timer_id);
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

  while(p_obj != arr_end) 
  {
      if( mp_obj_get_int_maybe(*p_obj++, &value) && value >= 0U && value <= UINT8_MAX )
      {
        *p_dst++ = (uint8_t)value;
      } 
      else 
      {
        return false;
      }
  }

  return true;
}

/**
 * Get voltage from CCID device descriptor
 *
 * @param ccidDescriptor  CCID device descriptor
 * @return                supported voltage
 */
static uint8_t getVoltageSupport(USBH_ChipCardDescTypeDef* ccidDescriptor)
{
  uint8_t voltage = 0;
  if ((ccidDescriptor->dwFeatures & CCID_CLASS_AUTO_VOLTAGE)
    || (ccidDescriptor->dwFeatures & CCID_CLASS_AUTO_ACTIVATION))
    voltage = 0;	/* automatic voltage selection */
  else
  {
      if (ccidDescriptor->bVoltageSupport == 0x01 || ccidDescriptor->bVoltageSupport == 0x07)
      {
        //5V
        voltage = 0x01;
      }

      if (ccidDescriptor->bVoltageSupport == 0x02)
      {
        //3V
        voltage = 0x02;
      }

      if (ccidDescriptor->bVoltageSupport == 0x04)
      {
        //1.8V
        voltage = 0x03;
      }
  }
  return voltage;
}

/**
 * @brief Transmit an APDU to the smart card
 *
 * .. method:: UsbCardConnection.transmit(bytes, protocol=None)
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
                                    mp_map_t *kw_args)
{
    led_state(3, 1);
    // Get self
    assert(n_args >= 1U);
    usb_connection_obj_t* self = (usb_connection_obj_t*)MP_OBJ_TO_PTR(pos_args[0]);

    // Parse and check arguments
    enum { ARG_bytes = 0, ARG_protocol };
    static const mp_arg_t allowed_args[] = {
      { MP_QSTR_bytes,    MP_ARG_REQUIRED | MP_ARG_OBJ, {.u_obj = mp_const_none}},
      { MP_QSTR_protocol, MP_ARG_OBJ,                   {.u_obj = mp_const_none}}
    };
    mp_arg_val_t args[MP_ARRAY_SIZE(allowed_args)];
    mp_arg_parse_all(n_args - 1U, pos_args + 1U, kw_args,
                    MP_ARRAY_SIZE(allowed_args), allowed_args, args);
    // Get data buffer of 'bytes' argument
    uint8_t* dynamic_buf = NULL;
    // Check if bytes is a list
    notify_observers_command(self, args[ARG_bytes].u_obj);
    if(mp_obj_is_type(args[ARG_bytes].u_obj, &mp_type_list)) 
    {   
        // 'bytes' is list
        // Get properties of the list
        mp_obj_t* items;
        mp_obj_list_get(args[ARG_bytes].u_obj, &hUsbHostFS.apduLen, &items);
        // Chose static buffer or allocate dynamic buffer if needed
        dynamic_buf = m_new(uint8_t, hUsbHostFS.apduLen);
        hUsbHostFS.apdu = dynamic_buf;
        if(!objects_to_buf(hUsbHostFS.apdu, items, hUsbHostFS.apduLen)) 
        {
            mp_raise_ValueError("incorrect data format");
        }
    } 
    else 
    {
        return mp_const_none;
    }
    if(self->state == state_connecting || self->state == state_connected)
    {
        if(connection_slot_status(MP_OBJ_TO_PTR(pos_args[0])) == ICC_INSERTED)
        {
          self->CCID_Handle->state = CCID_TRANSFER_DATA;
          mp_hal_delay_ms(self->rsp_timeout_ms);
          for(int i = 0; i < sizeof(hUsbHostFS.rawRxData); i++)
          {
            printf("0x%X ", hUsbHostFS.rawRxData[i]);
          }
          printf("\n\n");
          m_del(uint8_t, dynamic_buf, hUsbHostFS.apduLen);
          dynamic_buf = NULL;
          self->apdu_recived.apdu = hUsbHostFS.rawRxData;
          self->apdu_recived.len = sizeof(hUsbHostFS.rawRxData);
          self->apdu = mp_obj_new_bytes(self->apdu_recived.apdu, self->apdu_recived.len);
          mp_obj_t response = make_response_list(self->apdu_recived.apdu, self->apdu_recived.len);
          notify_observers_response(self, response);
          memset(hUsbHostFS.rawRxData, 0, sizeof(hUsbHostFS.rawRxData));
          notify_observers(self, event_response);
        }
        else
        {
          notify_observers(self, event_removal);
          raise_SmartcardException("smart card is not inserted");
        }
    }
    else
    {
      raise_SmartcardException("smart card reader is not connected");
    }
    return mp_const_none;
}

/**
 * @brief Connects to a smart card
 *
 * .. method:: UsbCardConnection.connect()
 *
 *  Connects to a smart card.
 *
 * @param self      instance of UsbCardConnection class
 * @return          None
 */
STATIC mp_obj_t connection_connect(mp_obj_t self_in)
{
    usb_connection_obj_t* self = (usb_connection_obj_t*)self_in;
    self->CCID_Handle = hUsbHostFS.pActiveClass->pData;
    if(self->state == state_connecting || self->state == state_connected)
    {
          if(connection_slot_status(self_in) == ICC_INSERTED)
          {
              notify_observers(self, event_insertion);
              USBH_ChipCardDescTypeDef chipCardDesc = hUsbHostFS.device.CfgDesc.Itf_Desc[0].CCD_Desc;
              hUsbHostFS.apduLen = CCID_ICC_POWER_ON_CMD_LENGTH;
              self->IccCmd[0] = 0x62; 
              self->IccCmd[1] = 0x00;
              self->IccCmd[2] = 0x00;
              self->IccCmd[3] = 0x00;
              self->IccCmd[4] = 0x00;
              self->IccCmd[5] = chipCardDesc.bCurrentSlotIndex;	
              self->IccCmd[6] = self->pbSeq++;
              self->IccCmd[7] = getVoltageSupport(&chipCardDesc);
              self->IccCmd[8] = 0x00;
              self->IccCmd[9] = 0x00;
              hUsbHostFS.apdu = self->IccCmd;
              notify_observers_command(self, self->IccCmd);
              self->CCID_Handle->state = CCID_TRANSFER_DATA;
              mp_hal_delay_ms(self->atr_timeout_ms);
              for(int i = 0; i < sizeof(hUsbHostFS.rawRxData); i++)
              {
                printf("0x%X ", hUsbHostFS.rawRxData[i]);
              }
              printf("\n\n");
              self->atr_received.atr = hUsbHostFS.rawRxData;
              self->atr_received.len = sizeof(hUsbHostFS.rawRxData);
              self->atr = mp_obj_new_bytes(self->atr_received.atr, self->atr_received.len);
              mp_obj_t response = make_response_list(self->atr_received.atr, self->atr_received.len);
              notify_observers_response(self, response);
              memset(hUsbHostFS.rawRxData, 0, sizeof(hUsbHostFS.rawRxData));
              self->state = state_connected;
              notify_observers(self, event_connect);
        }
        else
        {
            notify_observers(self, event_removal);
            raise_SmartcardException("smart card is not inserted");
        }
    }
    else
    {
        raise_SmartcardException("smart card reader is not connected");
    }
    return mp_const_none;
}

/**
 * @brief Terminates communication with a smart card and removes power
 *
 * .. method:: UsbCardConnection.disconnect()
 *
 *  Terminates communication with a smart card and removes power. Call this
 *  function before asking the user to remove a smart card. This function does
 *  not close connection but makes it inactive. When a new card is inserted, the
 *  connection object may be reused with the same parameters.
 *
 * @param self_in  instance of CardConnection class
 * @return         None
 */
STATIC mp_obj_t connection_disconnect(mp_obj_t self_in) 
{
    usb_connection_obj_t* self = (usb_connection_obj_t*)self_in;
    USBH_ChipCardDescTypeDef chipCardDesc = hUsbHostFS.device.CfgDesc.Itf_Desc[0].CCD_Desc;
    if(self->state == state_connected)
    {
        if(connection_slot_status(self_in) == ICC_INSERTED)
        {
          notify_observers(self, event_insertion);
          self->IccCmd[0] = 0x63; /* IccPowerOff */
          self->IccCmd[1] = self->IccCmd[2] = self->IccCmd[3] = self->IccCmd[4] = 0;	/* dwLength */
          self->IccCmd[5] = chipCardDesc.bCurrentSlotIndex;	/* slot number */
          self->IccCmd[6] = self->pbSeq++;
          self->IccCmd[7] = self->IccCmd[8] = self->IccCmd[9] = 0; /* RFU */
          hUsbHostFS.apdu = self->IccCmd;
          self->CCID_Handle->state = CCID_TRANSFER_DATA;
          mp_hal_delay_ms(self->rsp_timeout_ms);
          for(int i = 0; i < sizeof(hUsbHostFS.rawRxData); i++)
          {
            printf("0x%X ", hUsbHostFS.rawRxData[i]);
          }
          printf("\n\n");
          memset(hUsbHostFS.rawRxData, 0, sizeof(hUsbHostFS.rawRxData));
          //Stop USB CCID communication
          USBH_CCID_Stop(&hUsbHostFS);
          // Deinitialize timer
          if(self->timer) 
          {
            mp_obj_t deinit_fn = mp_load_attr(self->timer, MP_QSTR_deinit);
            (void)mp_call_function_0(deinit_fn);
            self->timer = MP_OBJ_NULL;
          }
          // Detach from reader
          usbreader_deleteConnection(self->reader, MP_OBJ_FROM_PTR(self));
          self->reader = MP_OBJ_NULL;
          // Mark connection object as closed
          self->state = state_closed;
          notify_observers(self, event_disconnect);
        }
        else
        {
          notify_observers(self, event_removal);
          raise_SmartcardException("smart card is not inserted");
        }
    }
    else
    {
        raise_SmartcardException("smart card reader is not connected");
    }
    return mp_const_none;
}

/**
 * @brief Connects to a smart card
 *
 * .. method:: UsbCardConnection.connection_slot_status()
 *  
 * Get status of usb smart card reader active slot.
 * 
 * @param self      instance of UsbCardConnection class
 * @return          hUsbHostFS.iccSlotStatus
 */
STATIC USBH_SlotStatusTypeDef connection_slot_status(mp_obj_t self_in) 
{
    usb_connection_obj_t* self = (usb_connection_obj_t*)self_in;
    self->CCID_Handle->state = CCID_GET_SLOT_STATUS;
    mp_hal_delay_ms(100);
    return hUsbHostFS.iccSlotStatus;
}

/**
 * @brief Checks if smart card is inserted
 *
 * .. method:: UsbCardConnection.isCardInserted()
 *
 * @param self_in   instance of CardConnection class
 * @return          True if smart card is inserted
 */
STATIC mp_obj_t connection_isCardInserted(mp_obj_t self_in) {
  usb_connection_obj_t* self = (usb_connection_obj_t*)self_in;
  if(connection_slot_status(self_in) == ICC_INSERTED)
  {
      return mp_const_true;  
  }
  return mp_const_false;
}

/**
 * @brief Return card connection reader
 *
 * .. method:: UsbCardConnection.getReader()
 *
 * @param self_in  instance of UsbCardConnection class
 * @return         reader object
 */
STATIC mp_obj_t connection_getReader(mp_obj_t self_in) {
  usb_connection_obj_t* self = (usb_connection_obj_t*)self_in;
  if(self->reader) {
    return MP_OBJ_FROM_PTR(self->reader);
  }
  return mp_const_none;
}

/**
 * @brief Checks if connection is active
 *
 * .. method:: UsbCardConnection.isActive()
 *
 *  Checks connection state, returning True if card is inserted and powered
 *
 * @param self_in  instance of UsbCardConnection class
 * @return         connection state: True - active, False - not active
 */
STATIC mp_obj_t connection_isActive(mp_obj_t self_in) {
  usb_connection_obj_t* self = (usb_connection_obj_t*)self_in;

  switch(self->state) {
    case state_connecting:
    case state_connected:
      return mp_const_true;

    default:
      return mp_const_false;
  }
}

/**
 * @brief Returns APDU sentence received from the smart card
 *
 * .. method:: UsbCardConnection.getAPDU()
 *
 * @param self_in  instance of CardConnection class
 * @return         APDU sentence as array bytes or None if not available
 */
STATIC mp_obj_t connection_getAPDU(mp_obj_t self_in) {
  usb_connection_obj_t* self = (usb_connection_obj_t*)self_in;
  if(state_closed != self->state && self->apdu) {
    return self->apdu;
  }
  return mp_const_none;
}

/**
 * @brief Returns ATR sentence received from the smart card
 *
 * .. method:: UsbCardConnection.getATR()
 *
 * @param self_in  instance of CardConnection class
 * @return         ATR sentence as array bytes or None if not available
 */
STATIC mp_obj_t connection_getATR(mp_obj_t self_in) {
  usb_connection_obj_t* self = (usb_connection_obj_t*)self_in;
  if(state_closed != self->state && self->atr) {
    return self->atr;
  }
  return mp_const_none;
}
/**
 * @brief Returns connection state
 *
 * .. method:: UsbCardConnection.getState()
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
  usb_connection_obj_t* self = (usb_connection_obj_t*)self_in;
  return MP_OBJ_NEW_QSTR((qstr)self->state);
}

/**
 * @brief Adds observer
 *
 * .. method:: UsbCardConnection.addObserver(observer)
 *
 *  Adds observer receiving notifications on events of connection. The
 *  *observer* should be a callable object, a function or a method having the
 *  following signature:
 *
 *  def my_function(usbcardconnection, type, args=None)
 *  def my_method(self, usbcardconnection, type, args=None)
 *
 *  Observer arguments:
 *
 *    - *usbscardconnection* smart card connection
 *    - *type* event type: 'connect', 'disconnect', 'command', 'response',
 *                         'insertion', 'removal', 'error'
 *    - *args* event arguments, a list
 *
 * @param self_in   instance of CardConnection class
 * @param observer  observer, a callable object
 * @return          None
 */
STATIC mp_obj_t connection_addObserver(mp_obj_t self_in, mp_obj_t observer) {
  usb_connection_obj_t* self = (usb_connection_obj_t*)self_in;

  if(!mp_obj_is_callable(observer)) {
    mp_raise_TypeError("observer must be callable");
  }
  (void)mp_obj_list_append(self->observers, observer);

  return mp_const_none;
}

/**
 * @brief Deletes observer
 *
 * .. method:: UsbCardConnection.deleteObserver(observer)
 *
 *  Deletes observer. The *observer* should be a callable object.
 *
 * @param self_in   instance of UsbCardConnection class
 * @param observer  observer, a callable object
 * @return          None
 */
STATIC mp_obj_t connection_deleteObserver(mp_obj_t self_in, mp_obj_t observer) {
  usb_connection_obj_t* self = (usb_connection_obj_t*)self_in;

  if(!mp_obj_is_callable(observer)) {
    mp_raise_TypeError("observer must be callable");
  }
  (void)mp_obj_list_remove(self->observers, observer);

  return mp_const_none;
}

/**
 * @brief Deletes all observers
 *
 * .. method:: UsbCardConnection.deleteObservers()
 *
 *  Deletes all observers.
 *
 * @param self_in  instance of UsbCardConnection class
 * @return         None
 */
STATIC mp_obj_t connection_deleteObservers(mp_obj_t self_in) {
  usb_connection_obj_t* self = (usb_connection_obj_t*)self_in;

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
 * .. method:: UsbCardConnection.countObservers()
 *
 *  Returns number of registered observers.
 *
 * @param self_in  instance of UsbCardConnection class
 * @return         number of registered observers
 */
STATIC mp_obj_t connection_countObservers(mp_obj_t self_in) {
  usb_connection_obj_t* self = (usb_connection_obj_t*)self_in;
  return MP_OBJ_NEW_SMALL_INT(list_get_len(self->observers));
}

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
  usb_connection_obj_t* self = (usb_connection_obj_t*)self_in;
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
}

STATIC mp_obj_t connection_setTimeouts(size_t n_args, const mp_obj_t *pos_args,
                                       mp_map_t *kw_args) {
  // Get self
  assert(n_args >= 1U);
  usb_connection_obj_t* self = (usb_connection_obj_t*)MP_OBJ_TO_PTR(pos_args[0]);

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
  self->atr_timeout_ms = mp_obj_get_int(args[ARG_atrTimeout].u_obj);

  self->rsp_timeout_ms = mp_obj_get_int(args[ARG_responseTimeout].u_obj);

  self->max_timeout_ms = mp_obj_get_int(args[ARG_maxTimeout].u_obj);

  return mp_const_none;
}

/**
 * @brief Closes connection releasing hardware resources
 *
 * .. method:: UsbCardConnection.close()
 *
 *  Closes connection releasing hardware resources
 *
 * @param self_in  instance of CardConnection class
 * @return         None
 */
STATIC mp_obj_t connection_close(mp_obj_t self_in) {

  usb_connection_obj_t* self = (usb_connection_obj_t*)self_in;
  if(self->state != state_closed) {
    connection_disconnect(self_in);
    connection_deleteObservers(self_in);

    // Deinitialize timer
    if(self->timer) {
      mp_obj_t deinit_fn = mp_load_attr(self->timer, MP_QSTR_deinit);
      (void)mp_call_function_0(deinit_fn);
      self->timer = MP_OBJ_NULL;
    }
    // Detach from reader
    usbreader_deleteConnection(self->reader, MP_OBJ_FROM_PTR(self));
    self->reader = MP_OBJ_NULL;

    // Mark connection object as closed
    self->state = state_closed;
  }
}

STATIC MP_DEFINE_CONST_FUN_OBJ_1(connection_disconnect_obj, connection_disconnect);
STATIC MP_DEFINE_CONST_FUN_OBJ_1(connection_connect_obj, connection_connect);
STATIC MP_DEFINE_CONST_FUN_OBJ_KW(connection_transmit_obj, 1, connection_transmit);
STATIC MP_DEFINE_CONST_FUN_OBJ_1(connection_getATR_obj, connection_getATR);
STATIC MP_DEFINE_CONST_FUN_OBJ_1(connection_getAPDU_obj, connection_getAPDU);
STATIC MP_DEFINE_CONST_FUN_OBJ_1(connection_isCardInserted_obj, connection_isCardInserted);
STATIC MP_DEFINE_CONST_FUN_OBJ_1(connection_getReader_obj, connection_getReader);
STATIC MP_DEFINE_CONST_FUN_OBJ_1(connection_getState_obj, connection_getState);
STATIC MP_DEFINE_CONST_FUN_OBJ_1(connection_isActive_obj, connection_isActive);
STATIC MP_DEFINE_CONST_FUN_OBJ_2(connection_addObserver_obj, connection_addObserver);
STATIC MP_DEFINE_CONST_FUN_OBJ_2(connection_deleteObserver_obj, connection_deleteObserver);
STATIC MP_DEFINE_CONST_FUN_OBJ_1(connection_deleteObservers_obj, connection_deleteObservers);
STATIC MP_DEFINE_CONST_FUN_OBJ_1(connection_countObservers_obj, connection_countObservers);
STATIC MP_DEFINE_CONST_FUN_OBJ_2(connection_notifyAll_obj, connection_notifyAll);
STATIC MP_DEFINE_CONST_FUN_OBJ_1(connection_close_obj, connection_close);
STATIC MP_DEFINE_CONST_FUN_OBJ_KW(connection_setTimeouts_obj, 1, connection_setTimeouts);

STATIC const mp_rom_map_elem_t connection_locals_dict_table[] = {
  // Instance methods
  { MP_ROM_QSTR(MP_QSTR___del__),         MP_ROM_PTR(&connection_close_obj)             },
  { MP_ROM_QSTR(MP_QSTR___enter__),       MP_ROM_PTR(&mp_identity_obj)                  },
  { MP_ROM_QSTR(MP_QSTR___exit__),        MP_ROM_PTR(&connection_close_obj)             },
  { MP_ROM_QSTR(MP_QSTR_connect),         MP_ROM_PTR(&connection_connect_obj)           },
  { MP_ROM_QSTR(MP_QSTR_disconnect),      MP_ROM_PTR(&connection_disconnect_obj)        },
  { MP_ROM_QSTR(MP_QSTR_transmit),        MP_ROM_PTR(&connection_transmit_obj)          },
  { MP_ROM_QSTR(MP_QSTR_getATR),          MP_ROM_PTR(&connection_getATR_obj)            },
  { MP_ROM_QSTR(MP_QSTR_getAPDU),         MP_ROM_PTR(&connection_getAPDU_obj)           },
  { MP_ROM_QSTR(MP_QSTR_isCardInserted),  MP_ROM_PTR(&connection_isCardInserted_obj)    },
  { MP_ROM_QSTR(MP_QSTR_getReader),       MP_ROM_PTR(&connection_getReader_obj)         },
  { MP_ROM_QSTR(MP_QSTR_getState),        MP_ROM_PTR(&connection_getState_obj)          },
  { MP_ROM_QSTR(MP_QSTR_isActive),        MP_ROM_PTR(&connection_isActive_obj)          },
  { MP_ROM_QSTR(MP_QSTR_addObserver),     MP_ROM_PTR(&connection_addObserver_obj)       },
  { MP_ROM_QSTR(MP_QSTR_deleteObserver),  MP_ROM_PTR(&connection_deleteObserver_obj)    },
  { MP_ROM_QSTR(MP_QSTR_deleteObservers), MP_ROM_PTR(&connection_deleteObservers_obj)   },
  { MP_ROM_QSTR(MP_QSTR_countObservers),  MP_ROM_PTR(&connection_countObservers_obj)    },
  { MP_ROM_QSTR(MP_QSTR_close),           MP_ROM_PTR(&connection_close_obj)             },
  { MP_ROM_QSTR(MP_QSTR__notifyAll),      MP_ROM_PTR(&connection_notifyAll_obj)         },
  { MP_ROM_QSTR(MP_QSTR_setTimeouts),     MP_ROM_PTR(&connection_setTimeouts_obj)       },
};

STATIC MP_DEFINE_CONST_DICT(connection_locals_dict, connection_locals_dict_table);
const mp_obj_type_t scard_UsbCardConnection_type = {
  { &mp_type_type },
  .name = MP_QSTR_CardConnection,
  .make_new = connection_make_new,
  .call = connection_call,
  .locals_dict = (void*)&connection_locals_dict,
};