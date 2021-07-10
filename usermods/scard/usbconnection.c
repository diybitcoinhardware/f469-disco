/**
 * @file       usbconnection.c
 * @brief      MicroPython uscard usb module: UsbReader class
 * @author     Rostislav Gurin <rgurin@embedity.dev>
 * @copyright  Copyright 2020 Crypto Advance GmbH. All rights reserved.
 */

#include "usbconnection.h"
STATIC mp_obj_t connection_make_new(const mp_obj_type_t* type, size_t n_args,
                                    size_t n_kw, const mp_obj_t* all_args) 
{
  // Create a new connection object
  usb_connection_obj_t* self = m_new_obj_with_finaliser(usb_connection_obj_t);
  memset(self, 0U, sizeof(usb_connection_obj_t));
  self->base.type = &scard_UsbCardConnection_type;
  self->reader = NULL;
  self->state = state_closed;
  self->timer = MP_OBJ_NULL;
  self->pbSeq = 0;
  usb_timer_init(self);
  printf("\r\nNew USB smart card connection\n");
  return MP_OBJ_FROM_PTR(self);                                    
}

STATIC mp_obj_t connection_call(mp_obj_t self_in, size_t n_args, size_t n_kw,
                                const mp_obj_t *args) {
  usb_connection_obj_t* self = (usb_connection_obj_t*)self_in;
  timer_task(self);
  return mp_const_none;
}

/**
 * Timer task
 *
 * @param self  instance of CardConnection class
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

STATIC void usb_timer_init(usb_connection_obj_t* self) 
{
  mp_int_t timer_id = -1;
  // Save system ticks and initialize timer
  self->prev_ticks_ms = mp_hal_ticks_ms();
  self->timer = create_timer(self, timer_id);
}

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
    hUsbHostFS.transferStatus = START_DATA_TRANSFER;
    mp_hal_delay_ms(300);
    if(hUsbHostFS.transferStatus == STOP_DATA_TRANSFER)
    {
      for(int i = 0; i < sizeof(hUsbHostFS.rawRxData); i++)
      {
        printf("0x%X ", hUsbHostFS.rawRxData[i]);
      }
      printf("\n\n");
    }
    m_del(uint8_t, dynamic_buf, hUsbHostFS.apduLen);
    dynamic_buf = NULL;
    memset(hUsbHostFS.rawRxData, 0, sizeof(hUsbHostFS.rawRxData));
    return mp_const_none;
}

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
STATIC mp_obj_t connection_cmd_power_on(mp_obj_t self_in)
{
    usb_connection_obj_t* self = (usb_connection_obj_t*)self_in;
    if(self->state == state_connecting || self->state == state_connected)
    {
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
        hUsbHostFS.transferStatus = START_DATA_TRANSFER;
        mp_hal_delay_ms(350);
        if(hUsbHostFS.transferStatus == STOP_DATA_TRANSFER)
        {
          for(int i = 0; i < sizeof(hUsbHostFS.rawRxData); i++)
          {
            printf("0x%X ", hUsbHostFS.rawRxData[i]);
          }
          printf("\n\n");
        }
        memset(hUsbHostFS.rawRxData, 0, sizeof(hUsbHostFS.rawRxData));
        self->state = state_connected;
    }
    else
    {
        raise_SmartcardException("smart card reader is not connected");
    }
    return mp_const_none;
}
STATIC mp_obj_t connection_disconnect(mp_obj_t self_in) 
{
    usb_connection_obj_t* self = (usb_connection_obj_t*)self_in;
    USBH_ChipCardDescTypeDef chipCardDesc = hUsbHostFS.device.CfgDesc.Itf_Desc[0].CCD_Desc;
    if(self->state == state_connected)
    {
        self->IccCmd[0] = 0x63; /* IccPowerOff */
        self->IccCmd[1] = self->IccCmd[2] = self->IccCmd[3] = self->IccCmd[4] = 0;	/* dwLength */
        self->IccCmd[5] = chipCardDesc.bCurrentSlotIndex;	/* slot number */
        self->IccCmd[6] = self->pbSeq++;
        self->IccCmd[7] = self->IccCmd[8] = self->IccCmd[9] = 0; /* RFU */
        hUsbHostFS.apdu = self->IccCmd;
        hUsbHostFS.transferStatus = START_DATA_TRANSFER;
        mp_hal_delay_ms(350);
        if(hUsbHostFS.transferStatus == STOP_DATA_TRANSFER)
        {
            for(int i = 0; i < sizeof(hUsbHostFS.rawRxData); i++)
            {
              printf("0x%X ", hUsbHostFS.rawRxData[i]);
            }
            printf("\n\n");
        }
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
        self->state = state_disconnected;
    }
    else
    {
        raise_SmartcardException("smart card reader is not connected");
    }
    return mp_const_none;
}

STATIC MP_DEFINE_CONST_FUN_OBJ_1(connection_disconnect_obj, connection_disconnect);
STATIC MP_DEFINE_CONST_FUN_OBJ_1(connection_cmd_power_on_obj, connection_cmd_power_on);
STATIC MP_DEFINE_CONST_FUN_OBJ_KW(connection_transmit_obj, 1, connection_transmit);

STATIC const mp_rom_map_elem_t connection_locals_dict_table[] = {
  // Instance methods
  { MP_ROM_QSTR(MP_QSTR_disconnect),    MP_ROM_PTR(&connection_disconnect_obj)    },
  { MP_ROM_QSTR(MP_QSTR_transmit),      MP_ROM_PTR(&connection_transmit_obj)      },
  { MP_ROM_QSTR(MP_QSTR_connect),       MP_ROM_PTR(&connection_cmd_power_on_obj)  },
};

STATIC MP_DEFINE_CONST_DICT(connection_locals_dict, connection_locals_dict_table);
const mp_obj_type_t scard_UsbCardConnection_type = {
  { &mp_type_type },
  .name = MP_QSTR_CardConnection,
  .make_new = connection_make_new,
  .call = connection_call,
  .locals_dict = (void*)&connection_locals_dict,
};