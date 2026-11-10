include_guard(GLOBAL)

function(stm32f1_configure_target target)
    cmake_parse_arguments(P "" "MCU;CLOCK;SYSTEM_SOURCE" "" ${ARGN})
    if(P_UNPARSED_ARGUMENTS OR P_KEYWORDS_MISSING_VALUES)
        message(FATAL_ERROR "Invalid stm32f1_configure_target arguments: ${ARGN}")
    endif()
    if(NOT TARGET "${target}")
        message(FATAL_ERROR "Create executable ${target} before configuring it")
    endif()
    get_target_property(_type "${target}" TYPE)
    get_target_property(_configured "${target}" STM32F1_MCU)
    if(NOT _type STREQUAL "EXECUTABLE" OR _configured)
        message(FATAL_ERROR "${target} must be an unconfigured executable")
    endif()
    if(NOT CMAKE_SYSTEM_PROCESSOR STREQUAL "arm" OR NOT ARM_GNU_GCC)
        message(FATAL_ERROR "Select cmake/toolchains/gcc.cmake or clang.cmake before project()")
    endif()
    get_filename_component(root "${CMAKE_CURRENT_FUNCTION_LIST_DIR}/.." ABSOLUTE)
    if(P_MCU STREQUAL "STM32F103C8T6")
        set(density md)
        set(device_define STM32F10X_MD)
        set(flash_kb 64)
        set(ram_kb 20)
    elseif(P_MCU STREQUAL "STM32F103RCT6")
        set(density hd)
        set(device_define STM32F10X_HD)
        set(flash_kb 256)
        set(ram_kb 48)
    else()
        message(FATAL_ERROR "Unsupported MCU '${P_MCU}'; use STM32F103C8T6 or STM32F103RCT6")
    endif()
    if(NOT P_CLOCK)
        set(P_CLOCK HSE8_72)
    endif()
    if(NOT P_CLOCK MATCHES "^(HSE8_72|HSI8)$")
        message(FATAL_ERROR "Unsupported CLOCK '${P_CLOCK}'; use HSE8_72 or HSI8")
    endif()
    if(NOT CMAKE_C_COMPILER_ID MATCHES "^(GNU|Clang|AppleClang)$")
        message(FATAL_ERROR "Only GCC and Clang are supported")
    endif()

    find_package(Python3 3.9 REQUIRED COMPONENTS Interpreter)
    set(vendor "${root}/vendor/st")
    set(cmsis "${vendor}/Libraries/CMSIS/CM3")
    set(device "${cmsis}/DeviceSupport/ST/STM32F10x")
    set(spl "${vendor}/Libraries/STM32F10x_StdPeriph_Driver")
    set(generated "${CMAKE_CURRENT_BINARY_DIR}/stm32f1/${target}")
    file(MAKE_DIRECTORY "${generated}")
    set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS
        "${root}/patches/cmsis-compiler.patch" "${root}/patches/system-clock.patch"
        "${root}/scripts/prepare_sources.py" "${vendor}/manifest.json"
        "${cmsis}/CoreSupport/core_cm3.c" "${device}/system_stm32f10x.c")
    execute_process(COMMAND "${Python3_EXECUTABLE}" "${root}/scripts/prepare_sources.py"
        --root "${root}" --output "${generated}"
        COMMAND_ERROR_IS_FATAL ANY)
    configure_file("${root}/linker/flash.ld.in" "${generated}/flash.ld" @ONLY)
    configure_file("${vendor}/Project/STM32F10x_StdPeriph_Template/stm32f10x_conf.h"
        "${generated}/stm32f10x_conf.h" COPYONLY)

    if(P_SYSTEM_SOURCE)
        get_filename_component(system_source "${P_SYSTEM_SOURCE}" ABSOLUTE
            BASE_DIR "${CMAKE_CURRENT_SOURCE_DIR}")
        if(NOT EXISTS "${system_source}")
            message(FATAL_ERROR "SYSTEM_SOURCE does not exist: ${system_source}")
        endif()
    else()
        set(system_source "${generated}/system_stm32f10x.c")
    endif()

    # Select only drivers present on the supported MCU family/density.
    set(drivers adc bkp can crc dbgmcu dma exti flash gpio i2c iwdg pwr
        rcc rtc spi tim usart wwdg)
    if(density STREQUAL "hd")
        list(APPEND drivers dac fsmc sdio)
    endif()
    set(driver_sources "${spl}/src/misc.c")
    foreach(driver IN LISTS drivers)
        list(APPEND driver_sources "${spl}/src/stm32f10x_${driver}.c")
    endforeach()
    target_sources("${target}" PRIVATE ${driver_sources} "${system_source}"
        "${generated}/core_cm3.c" "${root}/runtime/newlib.c"
        "${device}/startup/TrueSTUDIO/startup_stm32f10x_${density}.s")
    target_include_directories("${target}" PRIVATE "${generated}"
        "${cmsis}/CoreSupport" "${device}" "${spl}/inc")
    target_compile_definitions("${target}" PRIVATE
        "$<$<COMPILE_LANGUAGE:C>:USE_STDPERIPH_DRIVER;${device_define};HSE_VALUE=8000000U;STM32F1_CLOCK_${P_CLOCK}=1>")
    target_compile_options("${target}" PRIVATE -mcpu=cortex-m3 -mthumb
        "$<$<COMPILE_LANGUAGE:C>:-ffunction-sections;-fdata-sections;-fno-common;-Wall;-Wextra>"
        "$<$<AND:$<COMPILE_LANGUAGE:C>,$<CONFIG:Release>>:-Os>")
    set_target_properties("${target}" PROPERTIES
        C_STANDARD 11 C_STANDARD_REQUIRED YES C_EXTENSIONS NO SUFFIX .elf
        STM32F1_MCU "${P_MCU}" STM32F1_CLOCK "${P_CLOCK}")

    # Query the GCC installation for the exact Cortex-M3 soft-float multilib.
    set(runtime_libraries "")
    foreach(library libc_nano.a libm.a libnosys.a libgcc.a)
        execute_process(COMMAND "${ARM_GNU_GCC}" -mcpu=cortex-m3 -mthumb
            "-print-file-name=${library}" OUTPUT_VARIABLE location
            OUTPUT_STRIP_TRAILING_WHITESPACE COMMAND_ERROR_IS_FATAL ANY)
        if(NOT IS_ABSOLUTE "${location}" OR NOT EXISTS "${location}")
            message(FATAL_ERROR "Arm GNU runtime ${library} missing; install toolchain with Newlib")
        endif()
        list(APPEND runtime_libraries "${location}")
    endforeach()
    if(CMAKE_C_COMPILER_ID MATCHES "Clang")
        get_filename_component(gnu_bin "${ARM_GNU_GCC}" DIRECTORY)
        find_path(ARM_NEWLIB_INCLUDE_DIR stdio.h
            HINTS "${gnu_bin}/../arm-none-eabi/include" /usr/include/newlib
                  /usr/arm-none-eabi/include
            NO_DEFAULT_PATH REQUIRED)
        target_include_directories("${target}" SYSTEM PRIVATE
            "$<$<COMPILE_LANGUAGE:C>:${ARM_NEWLIB_INCLUDE_DIR}>")
        target_link_options("${target}" PRIVATE "--ld-path=${STM32F1_LLD}")
    endif()
    target_link_options("${target}" PRIVATE -mcpu=cortex-m3 -mthumb -nostdlib
        "LINKER:-T,${generated}/flash.ld" LINKER:--gc-sections
        "LINKER:-Map,${CMAKE_CURRENT_BINARY_DIR}/${target}.map"
        LINKER:--print-memory-usage)
    target_link_libraries("${target}" PRIVATE -Wl,--start-group
        ${runtime_libraries} -Wl,--end-group)
    set_property(TARGET "${target}" APPEND PROPERTY LINK_DEPENDS "${generated}/flash.ld")
    add_custom_command(TARGET "${target}" POST_BUILD
        COMMAND "${CMAKE_OBJCOPY}" -O binary "$<TARGET_FILE:${target}>"
            "$<TARGET_FILE_DIR:${target}>/${target}.bin"
        COMMAND "${CMAKE_OBJCOPY}" -O ihex "$<TARGET_FILE:${target}>"
            "$<TARGET_FILE_DIR:${target}>/${target}.hex"
        COMMAND "${CMAKE_SIZE}" "$<TARGET_FILE:${target}>"
        VERBATIM)
    message(STATUS "${target}: ${P_MCU}, ${P_CLOCK}, Flash ${flash_kb}K, RAM ${ram_kb}K")
endfunction()
