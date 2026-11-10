/* SPDX-License-Identifier: MIT */
#include "stm32f10x.h"
#include <stdio.h>
#include <stdlib.h>

#if defined(STM32F10X_MD) && defined(STM32F10X_HD)
#error Target density definitions leaked between firmware targets
#endif

volatile uint32_t initialized_word = 0x1234abcdU;
volatile uint32_t zero_word;
volatile uint32_t constructor_ran;
volatile uintptr_t intrinsic_address;
volatile uint32_t runtime_result;

__attribute__((constructor)) void fixture_constructor(void)
{
    constructor_ran = 1U;
}

void SysTick_Handler(void)
{
    ++zero_word;
}

int main(void)
{
    /* Keep the patched ABI entry points in the final image without changing SP. */
    intrinsic_address = (uintptr_t)__get_MSP ^ (uintptr_t)__get_PSP ^
                        (uintptr_t)__set_MSP ^ (uintptr_t)__set_PSP;
    runtime_result = initialized_word + zero_word + constructor_ran;
    char text[32];
    runtime_result += (uint32_t)snprintf(text, sizeof(text), "%lu", (unsigned long)runtime_result);
    void *allocation = malloc(16U);
    runtime_result += allocation != NULL;
    free(allocation);
    for (;;) {
        __WFI();
    }
}
