set(STM32F1_EXAMPLE_MCU STM32F103C8T6 CACHE STRING "Example MCU")
set(STM32F1_EXAMPLE_CLOCK HSE8_72 CACHE STRING "Example clock profile")

foreach(example blink uart)
    add_executable(${example} "${example}.c")
    stm32f1_configure_target(${example}
        MCU "${STM32F1_EXAMPLE_MCU}" CLOCK "${STM32F1_EXAMPLE_CLOCK}")
endforeach()
