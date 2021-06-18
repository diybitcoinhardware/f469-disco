/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file           : usbh_platform.c

  * @brief          : This file implements the USB platform
  ******************************************************************************
  * @attention
  *
  * <h2><center>&copy; Copyright (c) 2021 STMicroelectronics.
  * All rights reserved.</center></h2>
  *
  * This software component is licensed by ST under Ultimate Liberty license
  * SLA0044, the "License"; You may not use this file except in compliance with
  * the License. You may obtain a copy of the License at:
  *                             www.st.com/SLA0044
  *
  ******************************************************************************
  */
/* USER CODE END Header */

/* Includes ------------------------------------------------------------------*/
#include "usbh_platform.h"

/* USER CODE BEGIN INCLUDE */

/* USER CODE END INCLUDE */

static void VBUS_GPIO_Init(void) {

	GPIO_InitTypeDef GPIO_InitStruct;
	/*Configure GPIO pin Output Level */
	HAL_GPIO_WritePin(GPIOB, GPIO_PIN_2, GPIO_PIN_RESET);

	/*Configure GPIO pin : PG6 */
	GPIO_InitStruct.Pin = GPIO_PIN_2;
	GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
	GPIO_InitStruct.Pull = GPIO_NOPULL;
	GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
	HAL_GPIO_Init(GPIOB, &GPIO_InitStruct);

}
/**
  * @brief  Drive VBUS.
  * @param  state : VBUS state
  *          This parameter can be one of the these values:
  *           - 1 : VBUS Active
  *           - 0 : VBUS Inactive
  */
void MX_DriverVbusFS(uint8_t state)
{
  uint8_t data = state;
  /* USER CODE BEGIN PREPARE_GPIO_DATA_VBUS_FS */
  VBUS_GPIO_Init();
  if(state == 0)
  {
    /* Drive low Charge pump */
    data = GPIO_PIN_RESET;
  }
  else
  {
    /* Drive high Charge pump */
    data = GPIO_PIN_SET;
  }
  /* USER CODE END PREPARE_GPIO_DATA_VBUS_FS */
  HAL_GPIO_WritePin(GPIOB,GPIO_PIN_2,(GPIO_PinState)data);
}

/************************ (C) COPYRIGHT STMicroelectronics *****END OF FILE****/
