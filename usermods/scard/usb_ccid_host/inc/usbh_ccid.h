/**
  ******************************************************************************
  * @file    usbh_ccid.h
  * @author  MCD Application Team
  * @version V3.0.0
  * @date    18-February-2014
  * @brief   This file contains all the prototypes for the usbh_ccid.c
  ******************************************************************************
  * @attention
  *
  * <h2><center>&copy; COPYRIGHT 2014 STMicroelectronics</center></h2>
  *
  * Licensed under MCD-ST Liberty SW License Agreement V2, (the "License");
  * You may not use this file except in compliance with the License.
  * You may obtain a copy of the License at:
  *
  *        http://www.st.com/software_license_agreement_liberty_v2
  *
  * Unless required by applicable law or agreed to in writing, software 
  * distributed under the License is distributed on an "AS IS" BASIS, 
  * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
  * See the License for the specific language governing permissions and
  * limitations under the License.
  *
  ******************************************************************************
  */ 

/* Define to prevent recursive  ----------------------------------------------*/
#ifndef __USBH_CCID_CORE_H
#define __USBH_CCID_CORE_H

/* Includes ------------------------------------------------------------------*/
#include "usbh_core.h"

/*Communication Class codes*/
#define USB_CCID_CLASS                                          0x0b
#define COMMUNICATION_INTERFACE_CLASS_CODE                      0x0b
#define RESERVED                                                0x00
#define NO_CLASS_SPECIFIC_PROTOCOL_CODE                         0x00

/* States for CCID State Machine */
typedef enum
{
  CCID_IDLE= 0,
  CCID_SEND_DATA,
  CCID_SEND_DATA_WAIT,
  CCID_RECEIVE_DATA,
  CCID_RECEIVE_DATA_WAIT,  
}
CCID_DataStateTypeDef;

typedef enum
{
  CCID_IDLE_STATE= 0,
  CCID_GET_SLOT_STATUS, 
  CCID_DATA_RECEIVED, 
  CCID_ERROR_STATE, 
}
CCID_StateTypeDef;

/* Header Functional Descriptor
--------------------------------------------------------------------------------
Offset|  field              | Size  |    Value   |   Description                    
------|---------------------|-------|------------|------------------------------
0     |  bFunctionLength    | 1     |   number   |  Size of this descriptor.
1     |  bDescriptorType    | 1     |   Constant |  CS_INTERFACE (0x24)
2     |  bDescriptorSubtype | 1     |   Constant |  Identifier (ID) of functional 
      |                     |       |            | descriptor.
3     |  bcdCCID             | 2     |            |
      |                     |       |   Number   | USB Class Definitions for 
      |                     |       |            | Communication Devices Specification 
      |                     |       |            | release number in binary-coded 
      |                     |       |            | decimal
------|---------------------|-------|------------|------------------------------
*/
typedef struct _FunctionalDescriptorHeader
{
  uint8_t     bLength;            /*Size of this descriptor.*/
  uint8_t     bDescriptorType;    /*CS_INTERFACE (0x24)*/
  uint8_t     bDescriptorSubType; /* Header functional descriptor subtype as*/
  uint16_t    bcdCCID;             /* USB Class Definitions for Communication
                                    Devices Specification release number in
                                  binary-coded decimal. */
}
CCID_HeaderFuncDesc_TypeDef;
/* Call Management Functional Descriptor
--------------------------------------------------------------------------------
Offset|  field              | Size  |    Value   |   Description                    
------|---------------------|-------|------------|------------------------------
0     |  bFunctionLength    | 1     |   number   |  Size of this descriptor.
1     |  bDescriptorType    | 1     |   Constant |  CS_INTERFACE (0x24)
2     |  bDescriptorSubtype | 1     |   Constant |  Call Management functional 
      |                     |       |            |  descriptor subtype.
3     |  bmCapabilities     | 1     |   Bitmap   | The capabilities that this configuration
      |                     |       |            | supports:
      |                     |       |            | D7..D2: RESERVED (Reset to zero)
      |                     |       |            | D1: 0 - Device sends/receives call
      |                     |       |            | management information only over
      |                     |       |            | the Communication Class
      |                     |       |            | interface.
      |                     |       |            | 1 - Device can send/receive call
      |                     \       |            | management information over a
      |                     |       |            | Data Class interface.
      |                     |       |            | D0: 0 - Device does not handle call
      |                     |       |            | management itself.
      |                     |       |            | 1 - Device handles call
      |                     |       |            | management itself.
      |                     |       |            | The previous bits, in combination, identify
      |                     |       |            | which call management scenario is used. If bit
      |                     |       |            | D0 is reset to 0, then the value of bit D1 is
      |                     |       |            | ignored. In this case, bit D1 is reset to zero for
      |                     |       |            | future compatibility.
4     | bDataInterface      | 1     | Number     | Interface number of Data Class interface
      |                     |       |            | optionally used for call management.        
------|---------------------|-------|------------|------------------------------
*/
typedef struct _CallMgmtFunctionalDescriptor
{
  uint8_t    bLength;            /*Size of this functional descriptor, in bytes.*/
  uint8_t    bDescriptorType;    /*CS_INTERFACE (0x24)*/
  uint8_t    bDescriptorSubType; /* Call Management functional descriptor subtype*/
  uint8_t    bmCapabilities;      /* bmCapabilities: D0+D1 */
  uint8_t    bDataInterface;      /*bDataInterface: 1*/
}
CCID_CallMgmtFuncDesc_TypeDef;
/* Abstract Control Management Functional Descriptor
--------------------------------------------------------------------------------
Offset|  field              | Size  |    Value   |   Description                    
------|---------------------|-------|------------|------------------------------
0     |  bFunctionLength    | 1     |   number   |  Size of functional descriptor, in bytes.
1     |  bDescriptorType    | 1     |   Constant |  CS_INTERFACE (0x24)
2     |  bDescriptorSubtype | 1     |   Constant |  Abstract Control Management 
      |                     |       |            |  functional  descriptor subtype.
3     |  bmCapabilities     | 1     |   Bitmap   | The capabilities that this configuration
      |                     |       |            | supports ((A bit value of zero means that the
      |                     |       |            | request is not supported.) )
                                                   D7..D4: RESERVED (Reset to zero)
      |                     |       |            | D3: 1 - Device supports the notification
      |                     |       |            | Network_Connection.
      |                     |       |            | D2: 1 - Device supports the request
      |                     |       |            | Send_Break
      |                     |       |            | D1: 1 - Device supports the request
      |                     \       |            | combination of Set_Line_Coding,
      |                     |       |            | Set_Control_Line_State, Get_Line_Coding, and the
                                                   notification Serial_State.
      |                     |       |            | D0: 1 - Device supports the request
      |                     |       |            | combination of Set_Comm_Feature,
      |                     |       |            | Clear_Comm_Feature, and Get_Comm_Feature.
      |                     |       |            | The previous bits, in combination, identify
      |                     |       |            | which requests/notifications are supported by
      |                     |       |            | a Communication Class interface with the
      |                     |       |            |   SubClass code of Abstract Control Model.
------|---------------------|-------|------------|------------------------------
*/
typedef struct _AbstractCntrlMgmtFunctionalDescriptor
{
  uint8_t    bLength;            /*Size of this functional descriptor, in bytes.*/
  uint8_t    bDescriptorType;    /*CS_INTERFACE (0x24)*/
  uint8_t    bDescriptorSubType; /* Abstract Control Management functional
                                  descriptor subtype*/
  uint8_t    bmCapabilities;      /* The capabilities that this configuration supports */
}
CCID_AbstCntrlMgmtFuncDesc_TypeDef;
/* Union Functional Descriptor
--------------------------------------------------------------------------------
Offset|  field              | Size  |    Value   |   Description                    
------|---------------------|-------|------------|------------------------------
0     |  bFunctionLength    | 1     |   number   |  Size of this descriptor.
1     |  bDescriptorType    | 1     |   Constant |  CS_INTERFACE (0x24)
2     |  bDescriptorSubtype | 1     |   Constant |  Union functional 
      |                     |       |            |  descriptor subtype.
3     |  bMasterInterface   | 1     |   Constant | The interface number of the 
      |                     |       |            | Communication or Data Class interface
4     | bSlaveInterface0    | 1     | Number     | nterface number of first slave or associated
      |                     |       |            | interface in the union.        
------|---------------------|-------|------------|------------------------------
*/
typedef struct _UnionFunctionalDescriptor
{
  uint8_t    bLength;            /*Size of this functional descriptor, in bytes*/
  uint8_t    bDescriptorType;    /*CS_INTERFACE (0x24)*/
  uint8_t    bDescriptorSubType; /* Union functional descriptor SubType*/
  uint8_t    bMasterInterface;   /* The interface number of the Communication or
                                 Data Class interface,*/
  uint8_t    bSlaveInterface0;   /*Interface number of first slave*/
}
CCID_UnionFuncDesc_TypeDef;

typedef struct _USBH_CCIDInterfaceDesc
{
  CCID_HeaderFuncDesc_TypeDef           CCID_HeaderFuncDesc;
  CCID_CallMgmtFuncDesc_TypeDef         CCID_CallMgmtFuncDesc;
  CCID_AbstCntrlMgmtFuncDesc_TypeDef    CCID_AbstCntrlMgmtFuncDesc;
  CCID_UnionFuncDesc_TypeDef            CCID_UnionFuncDesc;  
}
CCID_InterfaceDesc_Typedef;


/* Structure for CCID process */
typedef struct
{
  uint8_t              NotifPipe; 
  uint8_t              NotifEp;
  uint8_t              buff[8];
  uint16_t             NotifEpSize;
}
CCID_CommItfTypedef ;

typedef struct
{
  uint8_t              InPipe; 
  uint8_t              OutPipe;
  uint8_t              OutEp;
  uint8_t              InEp;
  uint8_t              buff[8];
  uint16_t             OutEpSize;
  uint16_t             InEpSize;  
}
CCID_DataItfTypedef ;

/* Structure for CCID process */
typedef struct _CCID_Process
{
  CCID_CommItfTypedef                CommItf;
  CCID_DataItfTypedef                DataItf;
  uint8_t                           *pTxData;
  uint8_t                           *pRxData; 
  uint32_t                           TxDataLength;
  uint32_t                           RxDataLength;  
  CCID_InterfaceDesc_Typedef         CCID_Desc;
  CCID_StateTypeDef                  state;
  CCID_DataStateTypeDef              data_tx_state;
  CCID_DataStateTypeDef              data_rx_state; 
  uint8_t                            Rx_Poll;
}
CCID_HandleTypeDef;

extern USBH_ClassTypeDef  CCID_Class;
#define USBH_CCID_CLASS    &CCID_Class

void CCID_ProcessTransmission(USBH_HandleTypeDef *phost);

void CCID_ProcessReception(USBH_HandleTypeDef *phost);

USBH_StatusTypeDef  USBH_CCID_Transmit(USBH_HandleTypeDef *phost, 
                                      uint8_t *pbuff, 
                                      uint32_t length);

USBH_StatusTypeDef  USBH_CCID_Receive(USBH_HandleTypeDef *phost, 
                                     uint8_t *pbuff, 
                                     uint32_t length);


uint16_t            USBH_CCID_GetLastReceivedDataSize(USBH_HandleTypeDef *phost);

USBH_StatusTypeDef  USBH_CCID_Stop(USBH_HandleTypeDef *phost);

void USBH_CCID_LineCodingChanged(USBH_HandleTypeDef *phost);

void USBH_CCID_TransmitCallback(USBH_HandleTypeDef *phost);

void USBH_CCID_ReceiveCallback(USBH_HandleTypeDef *phost);

#endif /* __USBH_CCID_CORE_H */

/************************ (C) COPYRIGHT STMicroelectronics *****END OF FILE****/

