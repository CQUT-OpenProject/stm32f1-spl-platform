/* SPDX-License-Identifier: MIT */
#include "stm32f10x.h"

static volatile uint32_t ticks;

void SysTick_Handler(void)
{
    ++ticks;
}

int main(void)
{
    RCC_APB2PeriphClockCmd(RCC_APB2Periph_GPIOA, ENABLE);
    GPIO_InitTypeDef gpio = {
        .GPIO_Pin = GPIO_Pin_8,
        .GPIO_Speed = GPIO_Speed_2MHz,
        .GPIO_Mode = GPIO_Mode_Out_PP,
    };
    GPIO_Init(GPIOA, &gpio);
    if (SysTick_Config(SystemCoreClock / 1000U) != 0U) {
        for (;;) {}
    }
    uint32_t last = 0U;
    for (;;) {
        if ((uint32_t)(ticks - last) >= 500U) {
            last = ticks;
            GPIO_WriteBit(GPIOA, GPIO_Pin_8,
                GPIO_ReadOutputDataBit(GPIOA, GPIO_Pin_8) ? Bit_RESET : Bit_SET);
        }
        __WFI();
    }
}
