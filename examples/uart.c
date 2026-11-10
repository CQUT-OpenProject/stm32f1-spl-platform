/* SPDX-License-Identifier: MIT */
#include "stm32f10x.h"

static void send(char value)
{
    while (USART_GetFlagStatus(USART1, USART_FLAG_TXE) == RESET) {}
    USART_SendData(USART1, (uint8_t)value);
}

int main(void)
{
    RCC_APB2PeriphClockCmd(RCC_APB2Periph_GPIOA | RCC_APB2Periph_USART1, ENABLE);
    GPIO_InitTypeDef gpio = {
        .GPIO_Pin = GPIO_Pin_9,
        .GPIO_Speed = GPIO_Speed_2MHz,
        .GPIO_Mode = GPIO_Mode_AF_PP,
    };
    GPIO_Init(GPIOA, &gpio);
    gpio.GPIO_Pin = GPIO_Pin_10;
    gpio.GPIO_Mode = GPIO_Mode_IN_FLOATING;
    GPIO_Init(GPIOA, &gpio);
    USART_InitTypeDef serial;
    USART_StructInit(&serial);
    serial.USART_BaudRate = 115200;
    USART_Init(USART1, &serial);
    USART_Cmd(USART1, ENABLE);

    const char *message = "STM32F1 SPL ready\r\n";
    while (*message != '\0') {
        send(*message++);
    }
    for (;;) {
        if (USART_GetFlagStatus(USART1, USART_FLAG_RXNE) != RESET) {
            send((char)USART_ReceiveData(USART1));
        }
    }
}
