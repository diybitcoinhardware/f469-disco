/**
  ******************************************************************************
  * @file    usbh_cdc.c
  * @author  MCD Application Team
  * @version V3.0.0
  * @date    18-February-2014
  * @brief   This file is the CCID Layer Handlers for USB Host CCID class.
  *
  * @verbatim
  *      
  *          ===================================================================      
  *                                CCID Class  Description
  *          =================================================================== 
  *           This module manages the MSC class V1.11 following the "Device Class Definition
  *           for Human Interface Devices (CCID) Version 1.11 Jun 27, 2001".
  *           This driver implements the following aspects of the specification:
  *             - The Boot Interface Subclass
  *             - The Mouse and Keyboard protocols
  *      
  *  @endverbatim
  *
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

/* Includes ------------------------------------------------------------------*/
#include "usbh_ccid.h"

#define USBH_CCID_BUFFER_SIZE                 1024

static USBH_StatusTypeDef USBH_CCID_InterfaceInit  (USBH_HandleTypeDef *phost);

static USBH_StatusTypeDef USBH_CCID_InterfaceDeInit  (USBH_HandleTypeDef *phost);

static USBH_StatusTypeDef USBH_CCID_Process(USBH_HandleTypeDef *phost);

static USBH_StatusTypeDef USBH_CCID_SOFProcess(USBH_HandleTypeDef *phost);

static USBH_StatusTypeDef USBH_CCID_ClassRequest (USBH_HandleTypeDef *phost);

static void CCID_ProcessTransmission(USBH_HandleTypeDef *phost);

static void CCID_ProcessReception(USBH_HandleTypeDef *phost);

USBH_ClassTypeDef  CCID_Class = 
{
  "CCID",
  USB_CCID_CLASS,
  USBH_CCID_InterfaceInit,
  USBH_CCID_InterfaceDeInit,
  USBH_CCID_ClassRequest,
  USBH_CCID_Process,
  USBH_CCID_SOFProcess,
  NULL,
};
/**
* @}
*/ 


/** @defgroup USBH_CCID_CORE_Private_Functions
* @{
*/ 

/**
  * @brief  USBH_CCID_InterfaceInit 
  *         The function init the CCID class.
  * @param  phost: Host handle
  * @retval USBH Status
  */
static USBH_StatusTypeDef USBH_CCID_InterfaceInit (USBH_HandleTypeDef *phost)
{	

  USBH_StatusTypeDef status = USBH_FAIL ;
  uint8_t interface;
  CCID_HandleTypeDef *CCID_Handle;
  
  interface = USBH_FindInterface(phost, 
                                 COMMUNICATION_INTERFACE_CLASS_CODE, 
                                 0xFF, 
                                 0xFF);
  
  if(interface == 0xFF) /* No Valid Interface */
  {
    USBH_DbgLog ("Cannot Find the interface for Communication Interface Class.", phost->pActiveClass->Name);         
  }
  else
  {
    USBH_SelectInterface (phost, interface);
    phost->pActiveClass->pData = (CCID_HandleTypeDef *)m_new (CCID_HandleTypeDef, 1);
    CCID_Handle =  phost->pActiveClass->pData; 
    
    /*Collect the notification endpoint address and length*/
    for(int i = 0; i < USBH_MAX_NUM_ENDPOINTS; i++)
    {
      if(phost->device.CfgDesc.Itf_Desc[interface].Ep_Desc[i].bEndpointAddress & 0x80)
      {
        if(phost->device.CfgDesc.Itf_Desc[interface].Ep_Desc[i].bmAttributes == USB_EP_TYPE_INTR)
        {
          CCID_Handle->CommItf.NotifEp = phost->device.CfgDesc.Itf_Desc[interface].Ep_Desc[0].bEndpointAddress;
          CCID_Handle->CommItf.NotifEpSize  = phost->device.CfgDesc.Itf_Desc[interface].Ep_Desc[0].wMaxPacketSize;
        }
      }
    }
    
    /*Allocate the length for host channel number in*/
    CCID_Handle->CommItf.NotifPipe = USBH_AllocPipe(phost, CCID_Handle->CommItf.NotifEp);
    
    /* Open pipe for Notification endpoint */
    USBH_OpenPipe  (phost,
                    CCID_Handle->CommItf.NotifPipe,
                    CCID_Handle->CommItf.NotifEp,                            
                    phost->device.address,
                    phost->device.speed,
                    USB_EP_TYPE_INTR,
                    CCID_Handle->CommItf.NotifEpSize); 
    
    USBH_LL_SetToggle (phost, CCID_Handle->CommItf.NotifPipe, 0);    
    
    interface = USBH_FindInterface(phost, 
                                   USB_CCID_CLASS, 
                                   RESERVED, 
                                   NO_CLASS_SPECIFIC_PROTOCOL_CODE);
    
    if(interface == 0xFF) /* No Valid Interface */
    {
      USBH_DbgLog ("Cannot Find the interface for Data Interface Class.", phost->pActiveClass->Name);         
    }
    else
    { 
      for(int i = 0; i < USBH_MAX_NUM_ENDPOINTS; i++)
      {   
        /*Collect the class specific endpoint address and length*/
        if(phost->device.CfgDesc.Itf_Desc[interface].Ep_Desc[i].bEndpointAddress & 0x80)
        { 
          if(phost->device.CfgDesc.Itf_Desc[interface].Ep_Desc[i].bmAttributes == USB_EP_TYPE_BULK)
          {     
            CCID_Handle->DataItf.InEp = phost->device.CfgDesc.Itf_Desc[interface].Ep_Desc[i].bEndpointAddress;
            CCID_Handle->DataItf.InEpSize  = phost->device.CfgDesc.Itf_Desc[interface].Ep_Desc[i].wMaxPacketSize;
          }
        }
        else
        {
          if(phost->device.CfgDesc.Itf_Desc[interface].Ep_Desc[i].bmAttributes == USB_EP_TYPE_BULK)
          {    
            CCID_Handle->DataItf.OutEp = phost->device.CfgDesc.Itf_Desc[interface].Ep_Desc[i].bEndpointAddress;
            CCID_Handle->DataItf.OutEpSize  = phost->device.CfgDesc.Itf_Desc[interface].Ep_Desc[i].wMaxPacketSize;
          }
        }
      }

      /*Allocate the length for host channel number out*/
      CCID_Handle->DataItf.OutPipe = USBH_AllocPipe(phost, CCID_Handle->DataItf.OutEp);
      
      /*Allocate the length for host channel number in*/
      CCID_Handle->DataItf.InPipe = USBH_AllocPipe(phost, CCID_Handle->DataItf.InEp);  
      
      /* Open channel for OUT endpoint */
      USBH_OpenPipe  (phost,
                      CCID_Handle->DataItf.OutPipe,
                      CCID_Handle->DataItf.OutEp,
                      phost->device.address,
                      phost->device.speed,
                      USB_EP_TYPE_BULK,
                      CCID_Handle->DataItf.OutEpSize);  
      /* Open channel for IN endpoint */
      USBH_OpenPipe  (phost,
                      CCID_Handle->DataItf.InPipe,
                      CCID_Handle->DataItf.InEp,
                      phost->device.address,
                      phost->device.speed,
                      USB_EP_TYPE_BULK,
                      CCID_Handle->DataItf.InEpSize);
      
      CCID_Handle->state = CCID_IDLE_STATE;
      
      USBH_LL_SetToggle  (phost, CCID_Handle->DataItf.OutPipe,0);
      USBH_LL_SetToggle  (phost, CCID_Handle->DataItf.InPipe,0);
      status = USBH_OK; 
    }
  }
  return status;
}



/**
  * @brief  USBH_CCID_InterfaceDeInit 
  *         The function DeInit the Pipes used for the CCID class.
  * @param  phost: Host handle
  * @retval USBH Status
  */
USBH_StatusTypeDef USBH_CCID_InterfaceDeInit (USBH_HandleTypeDef *phost)
{
  CCID_HandleTypeDef *CCID_Handle =  phost->pActiveClass->pData;
  
  if ( CCID_Handle->CommItf.NotifPipe)
  {
    USBH_ClosePipe(phost, CCID_Handle->CommItf.NotifPipe);
    USBH_FreePipe  (phost, CCID_Handle->CommItf.NotifPipe);
    CCID_Handle->CommItf.NotifPipe = 0;     /* Reset the Channel as Free */
  }
  
  if ( CCID_Handle->DataItf.InPipe)
  {
    USBH_ClosePipe(phost, CCID_Handle->DataItf.InPipe);
    USBH_FreePipe  (phost, CCID_Handle->DataItf.InPipe);
    CCID_Handle->DataItf.InPipe = 0;     /* Reset the Channel as Free */
  }
  
  if ( CCID_Handle->DataItf.OutPipe)
  {
    USBH_ClosePipe(phost, CCID_Handle->DataItf.OutPipe);
    USBH_FreePipe  (phost, CCID_Handle->DataItf.OutPipe);
    CCID_Handle->DataItf.OutPipe = 0;     /* Reset the Channel as Free */
  } 
  
  if(phost->pActiveClass->pData)
  {
    m_free (phost->pActiveClass->pData);
    phost->pActiveClass->pData = 0;
  }
   
  return USBH_OK;
}

/**
  * @brief  USBH_CCID_ClassRequest 
  *         The function is responsible for handling Standard requests
  *         for CCID class.
  * @param  phost: Host handle
  * @retval USBH Status
  */
static USBH_StatusTypeDef USBH_CCID_ClassRequest (USBH_HandleTypeDef *phost)
{   
  USBH_StatusTypeDef status = USBH_OK;  
  CCID_HandleTypeDef *CCID_Handle =  phost->pActiveClass->pData;  
  return status;
}

int pbSeq = 0;
/**
  * @brief  USBH_CCID_Process 
  *         The function is for managing state machine for CCID data transfers 
  * @param  phost: Host handle
  * @retval USBH Status
  */
static USBH_StatusTypeDef USBH_CCID_Process (USBH_HandleTypeDef *phost)
{
  USBH_StatusTypeDef status = USBH_BUSY;
  USBH_StatusTypeDef req_status = USBH_OK;
  CCID_HandleTypeDef *CCID_Handle =  phost->pActiveClass->pData;
  USBH_ChipCardDescTypeDef chipCardDesc = phost->device.CfgDesc.Itf_Desc[0].CCD_Desc;
  switch(CCID_Handle->state)
  {
    case CCID_IDLE_STATE:
      status = USBH_OK;
      if(phost->transferStatus == START_DATA_TRANSFER)
      {
        CCID_Handle->state = CCID_TRANSFER_DATA;
      }
      break;
    
    case CCID_GET_DATA_HOST:
      USBH_InterruptReceiveData(phost, 
                                phost->rawRxData,
                                8,
                                CCID_Handle->CommItf.NotifPipe);
      break;
    case CCID_TRANSFER_DATA:
      USBH_CCID_Transmit(phost, phost->apdu, phost->apduLen);
      CCID_ProcessTransmission(phost);
      USBH_Delay(200);
      USBH_CCID_Receive(phost, phost->rawRxData, sizeof(phost->rawRxData));
      CCID_ProcessReception(phost);
      phost->transferStatus = STOP_DATA_TRANSFER;
      CCID_Handle->state = CCID_IDLE_STATE;
      break;   
      
    case CCID_ERROR_STATE:
      req_status = USBH_ClrFeature(phost, 0x00); 
      
      if(req_status == USBH_OK )
      {        
        /*Change the state to waiting*/
        CCID_Handle->state = CCID_IDLE_STATE ;
      }    
      break;
      
    default:
      break;
    
  }
  
  return status;
}

/**
  * @brief  USBH_CCID_SOFProcess 
  *         The function is for managing SOF callback 
  * @param  phost: Host handle
  * @retval USBH Status
  */
static USBH_StatusTypeDef USBH_CCID_SOFProcess (USBH_HandleTypeDef *phost)
{
  return USBH_OK;  
}
                                   
  
  /**
  * @brief  USBH_CCID_Stop 
  *         Stop current CCID Transmission 
  * @param  phost: Host handle
  * @retval USBH Status
  */
USBH_StatusTypeDef  USBH_CCID_Stop(USBH_HandleTypeDef *phost)
{
  CCID_HandleTypeDef *CCID_Handle =  phost->pActiveClass->pData; 
  
  if(phost->gState == HOST_CLASS)
  {
    CCID_Handle->state = CCID_IDLE_STATE;
    
    USBH_ClosePipe(phost, CCID_Handle->CommItf.NotifPipe);
    USBH_ClosePipe(phost, CCID_Handle->DataItf.InPipe);
    USBH_ClosePipe(phost, CCID_Handle->DataItf.OutPipe);
  }
  return USBH_OK;  
}

/**
  * @brief  This function return last recieved data size
  * @param  None
  * @retval None
  */
uint16_t USBH_CCID_GetLastReceivedDataSize(USBH_HandleTypeDef *phost)
{
  CCID_HandleTypeDef *CCID_Handle =  phost->pActiveClass->pData; 
  
  if(phost->gState == HOST_CLASS)
  {
    return USBH_LL_GetLastXferSize(phost, CCID_Handle->DataItf.InPipe);;
  }
  else
  {
    return 0;
  }
}

/**
  * @brief  This function prepares the state before issuing the class specific commands
  * @param  None
  * @retval None
  */
USBH_StatusTypeDef  USBH_CCID_Transmit(USBH_HandleTypeDef *phost, uint8_t *pbuff, uint32_t length)
{
  USBH_StatusTypeDef Status = USBH_BUSY;
  CCID_HandleTypeDef *CCID_Handle =  phost->pActiveClass->pData;
  
  if((CCID_Handle->state == CCID_IDLE_STATE) || (CCID_Handle->state == CCID_TRANSFER_DATA))
  {
    CCID_Handle->pTxData = pbuff;
    CCID_Handle->TxDataLength = length;  
    CCID_Handle->state = CCID_TRANSFER_DATA;
    CCID_Handle->data_tx_state = CCID_SEND_DATA; 
    Status = USBH_OK;
  }
  return Status;    
}
  
  
/**
* @brief  This function prepares the state before issuing the class specific commands
* @param  None
* @retval None
*/
USBH_StatusTypeDef  USBH_CCID_Receive(USBH_HandleTypeDef *phost, uint8_t *pbuff, uint32_t length)
{
  USBH_StatusTypeDef Status = USBH_BUSY;
  CCID_HandleTypeDef *CCID_Handle =  phost->pActiveClass->pData;
  
  if((CCID_Handle->state == CCID_IDLE_STATE) || (CCID_Handle->state == CCID_TRANSFER_DATA))
  {
    CCID_Handle->pRxData = pbuff;
    CCID_Handle->RxDataLength = length;  
    CCID_Handle->state = CCID_TRANSFER_DATA;
    CCID_Handle->data_rx_state = CCID_RECEIVE_DATA;     
    Status = USBH_OK;
  }
  return Status;    
} 

/**
* @brief  The function is responsible for sending data to the device
*  @param  pdev: Selected device
* @retval None
*/
static void CCID_ProcessTransmission(USBH_HandleTypeDef *phost)
{
  CCID_HandleTypeDef *CCID_Handle =  phost->pActiveClass->pData;
  USBH_URBStateTypeDef URB_Status = USBH_URB_IDLE;
  
  switch(CCID_Handle->data_tx_state)
  {
 
  case CCID_SEND_DATA:
    if(CCID_Handle->TxDataLength > CCID_Handle->DataItf.OutEpSize)
    {
      USBH_BulkSendData (phost,
                         CCID_Handle->pTxData, 
                         CCID_Handle->DataItf.OutEpSize, 
                         CCID_Handle->DataItf.OutPipe,
                         1);
    }
    else
    {
      USBH_BulkSendData (phost,
                         CCID_Handle->pTxData, 
                         CCID_Handle->TxDataLength, 
                         CCID_Handle->DataItf.OutPipe,
                         1);
    }
    
    CCID_Handle->data_tx_state = CCID_SEND_DATA_WAIT;
    
    break;
    
  case CCID_SEND_DATA_WAIT:
    
    URB_Status = USBH_LL_GetURBState(phost, CCID_Handle->DataItf.OutPipe); 
    
    /*Check the status done for transmssion*/
    if(URB_Status == USBH_URB_DONE )
    {         
      if(CCID_Handle->TxDataLength > CCID_Handle->DataItf.OutEpSize)
      {
        CCID_Handle->TxDataLength -= CCID_Handle->DataItf.OutEpSize ;
        CCID_Handle->pTxData += CCID_Handle->DataItf.OutEpSize;
      }
      else
      {
        CCID_Handle->TxDataLength = 0;
      }
      
      if( CCID_Handle->TxDataLength > 0)
      {
       CCID_Handle->data_tx_state = CCID_SEND_DATA; 
      }
      else
      {
        CCID_Handle->data_tx_state = CCID_IDLE;    
        USBH_CCID_TransmitCallback(phost);

      }
    }
    else if( URB_Status == USBH_URB_NOTREADY )
    {
      CCID_Handle->data_tx_state = CCID_SEND_DATA; 
    }
    break;
  default:
    break;
  }
}
/**
* @brief  This function responsible for reception of data from the device
*  @param  pdev: Selected device
* @retval None
*/

static void CCID_ProcessReception(USBH_HandleTypeDef *phost)
{
  CCID_HandleTypeDef *CCID_Handle =  phost->pActiveClass->pData;
  USBH_URBStateTypeDef URB_Status = USBH_URB_IDLE;
  uint16_t length;

  switch(CCID_Handle->data_rx_state)
  {
    
  case CCID_RECEIVE_DATA:

    USBH_BulkReceiveData (phost,
                          CCID_Handle->pRxData, 
                          CCID_Handle->DataItf.InEpSize, 
                          CCID_Handle->DataItf.InPipe);
    
    CCID_Handle->data_rx_state = CCID_RECEIVE_DATA_WAIT;
    
    break;
    
  case CCID_RECEIVE_DATA_WAIT:
    
    URB_Status = USBH_LL_GetURBState(phost, CCID_Handle->DataItf.InPipe); 
    
    /*Check the status done for reception*/
    if(URB_Status == USBH_URB_DONE )
    {  
      length = USBH_LL_GetLastXferSize(phost, CCID_Handle->DataItf.InPipe);
        
      if(((CCID_Handle->RxDataLength - length) > 0) && (length > CCID_Handle->DataItf.InEpSize))
      {
        CCID_Handle->RxDataLength -= length ;
        CCID_Handle->pRxData += length;
        CCID_Handle->data_rx_state = CCID_RECEIVE_DATA; 
      }
      else
      {
        CCID_Handle->data_rx_state = CCID_IDLE;
        USBH_CCID_ReceiveCallback(phost);
      }
    }
    break;
    
  default:
    break;
  }
}

/**
* @brief  The function informs user that data have been received
*  @param  pdev: Selected device
* @retval None
*/
__weak void USBH_CCID_TransmitCallback(USBH_HandleTypeDef *phost)
{
  
}
  
  /**
* @brief  The function informs user that data have been sent
*  @param  pdev: Selected device
* @retval None
*/
__weak void USBH_CCID_ReceiveCallback(USBH_HandleTypeDef *phost)
{
  
}

  /**
* @brief  The function informs user that Settings have been changed
*  @param  pdev: Selected device
* @retval None
*/
__weak void USBH_CCID_LineCodingChanged(USBH_HandleTypeDef *phost)
{
  
}

/**
* @}
*/ 

/**
* @}
*/ 

/**
* @}
*/


/**
* @}
*/


/**
* @}
*/

/************************ (C) COPYRIGHT STMicroelectronics *****END OF FILE****/
