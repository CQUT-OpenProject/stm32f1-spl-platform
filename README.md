# STM32F1 SPL Platform

供 C 工程通过 Git 子模块使用的 STM32F1 标准外设库与构建支持。基于 ST 官方 **STSW-STM32054 V3.6.0**，支持 STM32F103C8T6、STM32F103RCT6、GCC 和 Clang/LLD。

## 支持范围

| 芯片 | SPL 宏 | 启动文件 | Flash | SRAM | 初始栈顶 |
| --- | --- | --- | --- | --- | --- |
| STM32F103C8T6 | `STM32F10X_MD` | MD / TrueSTUDIO GCC 语法 | 64 KB | 20 KB | `0x20005000` |
| STM32F103RCT6 | `STM32F10X_HD` | HD / TrueSTUDIO GCC 语法 | 256 KB | 48 KB | `0x2000C000` |

代码从 `0x08000000` 启动，不预留 bootloader 偏移。使用 Cortex-M3 Thumb 指令和软浮点 ABI。默认堆大小 512 字节、栈保留量 1 KB；链接器检查静态数据、堆和预留栈是否超出 SRAM。

## 安装工具

需要 CMake ≥ 3.22、Git、Python ≥ 3.9、Make，以及包含 **Newlib/Newlib-nano** 的 Arm GNU `arm-none-eabi` 工具链。

Ubuntu 24.04：

```sh
sudo apt-get update
sudo apt-get install --no-install-recommends gcc-arm-none-eabi libnewlib-arm-none-eabi cmake make git python3 clang lld
```

macOS 可安装 Arm 官方 [Arm GNU Toolchain](https://developer.arm.com/Tools%20and%20Software/GNU%20Toolchain)，或通过 Homebrew 安装：

```sh
brew install cmake llvm lld
brew install --cask gcc-arm-embedded
```

将 `arm-none-eabi-gcc` 加入 PATH，或通过环境变量/CMake 参数指定工具链根目录：

```sh
export ARM_GNU_ROOT=/absolute/path/to/arm-gnu-toolchain
```

Clang 使用 ARM 目标和 LLD 链接，复用 Arm GNU 提供的 Cortex-M3 Newlib 与 libgcc。可显式设置：

```sh
cmake --preset clang-c8-debug \
  -DSTM32F1_CLANG="$(brew --prefix llvm)/bin/clang" \
  -DSTM32F1_LLD="$(brew --prefix lld)/bin/ld.lld"
```

自定义安装布局可传入 `ARM_GNU_GCC`（编译器完整路径）和 `ARM_NEWLIB_INCLUDE_DIR`（包含 Newlib `stdio.h` 的目录）。不同工具链使用独立构建目录。

## 编译示例

```sh
cmake --preset gcc-c8-debug
cmake --build --preset gcc-c8-debug --parallel
```

预设名称为 `{gcc|clang}-{c8|rc}-{debug|release}`。每组都构建 `blink` 和 `uart`，在 `build/<预设>/examples/` 输出 `.elf`、`.bin`、`.hex`、`.map`，并报告容量。

默认使用外部 8 MHz 晶振倍频到 72 MHz。使用内部 8 MHz HSI：

```sh
cmake --preset gcc-c8-debug -DSTM32F1_EXAMPLE_CLOCK=HSI8
cmake --build --preset gcc-c8-debug --parallel
```

`HSE8_72` 的 HSE 启动失败时保留 HSI，并更新 `SystemCoreClock` 为实际频率。

示例接线：

- `blink`：PA8 输出，500 ms 翻转一次。使用串联限流电阻的外接 LED，或示波器观察 PA8。SysTick 由示例使用。
- `uart`：USART1 的 PA9 为 TX、PA10 为 RX，连接 3.3 V USB-TTL 的 RX/TX 并共地；115200、8N1。启动发送 `STM32F1 SPL ready`，随后轮询回显收到的字符。

## 作为子模块接入

在应用仓库中执行：

```sh
git submodule add https://github.com/CQUT-OpenProject/stm32f1-spl-platform.git third_party/stm32f1-spl-platform
git add .gitmodules third_party/stm32f1-spl-platform
git commit -m "📦 引入 STM32F1 SPL 平台"
```

应用的 `CMakeLists.txt`：

```cmake
cmake_minimum_required(VERSION 3.22)
project(my_firmware LANGUAGES C ASM)

add_subdirectory(third_party/stm32f1-spl-platform)
add_executable(firmware src/main.c src/interrupts.c)
stm32f1_configure_target(firmware
    MCU STM32F103C8T6
    CLOCK HSE8_72
)
```

首次配置时选择工具链文件：

```sh
cmake -S . -B build/gcc \
  -DCMAKE_TOOLCHAIN_FILE=third_party/stm32f1-spl-platform/cmake/toolchains/gcc.cmake \
  -DCMAKE_BUILD_TYPE=Debug
cmake --build build/gcc --parallel
```

将工具链文件换成 `clang.cmake` 即可选择 Clang。

接口参数：

| 参数 | 行为 |
| --- | --- |
| `MCU` | 必填，`STM32F103C8T6` 或 `STM32F103RCT6` |
| `CLOCK` | 可选，默认 `HSE8_72`，也支持 `HSI8` |
| `SYSTEM_SOURCE` | 可选，自定义系统初始化 C 文件，相对于调用方源目录解析；提供 `SystemInit`、`SystemCoreClock`、`SystemCoreClockUpdate` |

`SYSTEM_SOURCE` 替换默认系统初始化，`HSE_VALUE` 默认为 8 MHz。

平台提供启动文件、CMSIS、芯片宏和默认 `stm32f10x_conf.h`。需要改变断言等标准库配置时可由应用提供同名头文件，并用 `target_include_directories(firmware BEFORE PRIVATE ...)` 放在默认配置前。

芯片定义和构建参数作用于指定目标。自行构建的库需使用与目标芯片匹配的 SPL 宏。

平台使用 Newlib-nano，提供单线程 `_sbrk`；应用可通过强符号重定向系统调用，例如将 `printf` 接到串口。

## 固定与升级版本

应用通过 Git 的子模块提交指针固定依赖。其他人克隆应用时使用：

```sh
git clone --recurse-submodules <应用仓库地址>
# 已经克隆：
git submodule update --init --recursive
```

更新时先在子模块获取并检出经过验证的提交或已发布标签，再在应用仓库提交新的指针。

## 烧录与调试

连接 ST-Link 的 SWDIO/PA13、SWCLK/PA14、GND 和目标电压参考，按开发板要求供电，BOOT0 设为 0。安装 OpenOCD 0.12 后，在本仓库根目录执行：

```sh
openocd -f tools/openocd/stlink.cfg \
  -c "program build/gcc-c8-debug/examples/blink.elf verify reset exit"
```

配置使用 OpenOCD 0.12 的 ST-Link HLA 驱动和 `stm32f1x` 目标。
