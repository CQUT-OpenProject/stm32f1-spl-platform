cmake_minimum_required(VERSION 3.22)

if(CMAKE_SOURCE_DIR STREQUAL CMAKE_CURRENT_SOURCE_DIR)
    project(stm32f1_spl_platform VERSION 0.1.0 LANGUAGES C ASM)
    set(STM32F1_BUILD_EXAMPLES ON CACHE BOOL "Build platform examples")
else()
    set(STM32F1_BUILD_EXAMPLES OFF CACHE BOOL "Build platform examples")
endif()

include("${CMAKE_CURRENT_LIST_DIR}/cmake/stm32f1.cmake")

if(STM32F1_BUILD_EXAMPLES)
    add_subdirectory(examples)
endif()
