#!/usr/bin/env python3
"""Check firmware layout and real submodule integration. SPDX-License-Identifier: MIT."""
import argparse
import json
import re
import shutil
import struct
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAPACITY = {"STM32F103C8T6": (64 * 1024, 20 * 1024),
            "STM32F103RCT6": (256 * 1024, 48 * 1024)}


class Elf:
    """Only the little-endian ELF32 structures required by these checks."""
    def __init__(self, path):
        self.data = path.read_bytes()
        assert self.data[:6] == b"\x7fELF\x01\x01", "Expected little-endian ELF32"
        fields = struct.unpack_from("<HHIIIIIHHHHHH", self.data, 16)
        assert fields[1] == 40, "Expected ARM machine"
        self.entry = fields[3]
        phoff, shoff = fields[4:6]
        phsize, phcount, shsize, shcount, strindex = fields[8:13]
        rows = [struct.unpack_from("<IIIIIIIIII", self.data, shoff + i * shsize)
                for i in range(shcount)]
        string_row = rows[strindex]
        strings = self.data[string_row[4]:string_row[4] + string_row[5]]

        def cstr(table, index):
            return table[index:table.index(b"\0", index)].decode()

        self.sections = {cstr(strings, row[0]): row for row in rows}
        self.symbols = {}
        for row in rows:
            if row[1] != 2:  # SHT_SYMTAB
                continue
            names = rows[row[6]]
            table = self.data[names[4]:names[4] + names[5]]
            for offset in range(row[4], row[4] + row[5], row[9]):
                name, value, size, info, other, index = struct.unpack_from("<IIIBBH", self.data, offset)
                if name:
                    self.symbols[cstr(table, name)] = (value, size, info, index)
        self.segments = [struct.unpack_from("<IIIIIIII", self.data, phoff + i * phsize)
                         for i in range(phcount)]

    def address(self, name):
        return self.symbols[name][0]

    def contents(self, name):
        row = self.sections[name]
        return self.data[row[4]:row[4] + row[5]]


def check_image(path, mcu, fixture=False):
    flash, ram = CAPACITY[mcu]
    elf = Elf(path)
    vector = elf.contents(".isr_vector")
    sp, reset = struct.unpack_from("<II", vector)
    assert elf.sections[".isr_vector"][3] == 0x08000000
    assert sp == elf.address("_estack") == 0x20000000 + ram
    assert reset & 1 and reset == elf.address("Reset_Handler") == elf.entry
    assert 0x08000000 <= (reset & ~1) < 0x08000000 + flash
    assert elf.address("_heap_end") - elf.address("_heap_start") == 512
    assert elf.address("_estack") - elf.address("_sstack") == 1024
    assert elf.address("_heap_end") <= elf.address("_sstack")
    assert 0x20000000 <= elf.address("_sdata") <= elf.address("_edata") <= elf.address("_sbss")
    assert elf.address("_sbss") <= elf.address("_ebss") <= elf.address("_heap_start")
    for segment in elf.segments:
        kind, offset, virtual, physical, file_size, memory_size, flags, align = segment
        if kind != 1:
            continue
        if file_size:
            assert 0x08000000 <= physical and physical + file_size <= 0x08000000 + flash
        if 0x20000000 <= virtual:
            assert virtual + memory_size <= 0x20000000 + ram
    assert not [(name, info) for name, (_, _, info, index) in elf.symbols.items()
                if index == 0 and info >> 4 == 1], "Undefined global symbols"
    for name in ("SystemInit", "__libc_init_array", "_init"):
        assert elf.address(name)
    for suffix in (".bin", ".hex", ".map"):
        assert path.with_suffix(suffix).stat().st_size > 0
    assert path.with_suffix(".bin").read_bytes()[:len(vector)] == vector
    if "SysTick_Handler" in elf.symbols and path.stem != "uart":
        assert struct.unpack_from("<I", vector, 15 * 4)[0] == elf.address("SysTick_Handler")
        assert elf.address("SysTick_Handler") != elf.address("Default_Handler")
    if fixture:
        assert elf.address("_sdata") <= elf.address("initialized_word") < elf.address("_edata")
        assert elf.address("_sbss") <= elf.address("zero_word") < elf.address("_ebss")
        data_offset = elf.address("initialized_word") - elf.sections[".data"][3]
        assert struct.unpack_from("<I", elf.contents(".data"), data_offset)[0] == 0x1234abcd
        arrays = elf.contents(".init_array")
        entries = struct.unpack("<" + "I" * (len(arrays) // 4), arrays)
        assert elf.address("fixture_constructor") in entries
        for name in ("__get_MSP", "__get_PSP", "__set_MSP", "__set_PSP", "_sbrk", "malloc"):
            assert elf.address(name)
    print(f"PASS ELF layout: {path.name}, {mcu}")


def cache_values(build):
    result = {}
    for line in (build / "CMakeCache.txt").read_text().splitlines():
        match = re.match(r"([^/#][^:]*):[^=]+=(.*)", line)
        if match:
            result[match[1]] = match[2]
    return result


def command(args, log, cwd=None, failure=None):
    result = subprocess.run([str(arg) for arg in args], cwd=cwd, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True)
    log.write_text(result.stdout)
    if failure is not None:
        assert result.returncode != 0 and re.search(failure, result.stdout, re.I), result.stdout[-5000:]
    elif result.returncode:
        raise AssertionError(result.stdout[-7000:])
    return result.stdout


def integration(build, cache):
    work = build / "verification"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir()
    consumer = work / "consumer with spaces"
    consumer.mkdir()
    # A real gitlink, not a source-directory alias. Local file transport is scoped to this test.
    command(["git", "init", "-b", "main", consumer], work / "git-init.log")
    command(["git", "-c", "protocol.file.allow=always", "submodule", "add", str(ROOT),
             "third_party/platform with spaces"], work / "submodule.log", cwd=consumer)
    dependency = consumer / "third_party/platform with spaces"
    shutil.copyfile(ROOT / "tests/fixture.c", consumer / "main.c")
    (consumer / "custom_system.c").write_text('''#include "stm32f10x.h"
uint32_t SystemCoreClock = 8000000U;
void SystemCoreClockUpdate(void) { SystemCoreClock = 8000000U; }
void SystemInit(void) { SystemCoreClockUpdate(); }
''')
    (consumer / "overflow_flash.c").write_text('''#include <stdint.h>
const uint8_t oversized_flash[300 * 1024] = {1};
const uint8_t *volatile keep_flash = oversized_flash;
int main(void) { return keep_flash[0]; }
''')
    (consumer / "overflow_ram.c").write_text('''#include <stdint.h>
volatile uint8_t oversized_ram[64 * 1024];
int main(void) { return oversized_ram[0]; }
''')
    preamble = '''cmake_minimum_required(VERSION 3.22)
project(consumer C ASM)
add_subdirectory("third_party/platform with spaces" platform)
'''
    cmake = preamble
    targets = []
    for chip, mcu in (("c8", "STM32F103C8T6"), ("rc", "STM32F103RCT6")):
        for clock in ("HSE8_72", "HSI8"):
            name = f"{chip}_{clock.lower()}"
            cmake += f"add_executable({name} main.c)\nstm32f1_configure_target({name} MCU {mcu} CLOCK {clock})\n"
            targets.append((name, mcu))
        for area in ("flash", "ram"):
            name = f"overflow_{chip}_{area}"
            cmake += f"add_executable({name} EXCLUDE_FROM_ALL overflow_{area}.c)\nstm32f1_configure_target({name} MCU {mcu})\n"
    cmake += '''add_executable(custom main.c)
stm32f1_configure_target(custom MCU STM32F103C8T6 CLOCK HSI8 SYSTEM_SOURCE custom_system.c)
'''
    (consumer / "CMakeLists.txt").write_text(cmake)
    compiler = "clang" if cache.get("STM32F1_CLANG") else "gcc"
    destination = work / "consumer build"
    flags = [f"-DCMAKE_TOOLCHAIN_FILE={dependency}/cmake/toolchains/{compiler}.cmake",
             f"-DARM_GNU_GCC={cache['ARM_GNU_GCC']}",
             f"-DCMAKE_BUILD_TYPE={cache['CMAKE_BUILD_TYPE']}",
             "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON"]
    for variable in ("STM32F1_CLANG", "STM32F1_LLD", "ARM_NEWLIB_INCLUDE_DIR"):
        if cache.get(variable):
            flags.append(f"-D{variable}={cache[variable]}")
    command(["cmake", "-S", consumer, "-B", destination, *flags], work / "configure.log")
    command(["cmake", "--build", destination, "--parallel", "4"], work / "build.log")
    for name, mcu in targets:
        check_image(destination / f"{name}.elf", mcu, fixture=True)
    check_image(destination / "custom.elf", "STM32F103C8T6", fixture=True)
    commands = json.loads((destination / "compile_commands.json").read_text())
    for entry in commands:
        if entry["file"].endswith("system_stm32f10x.c"):
            if "_hsi8" in entry["file"]:
                assert "STM32F1_CLOCK_HSI8" in entry["command"]
            if "_hse8_72" in entry["file"]:
                assert "STM32F1_CLOCK_HSE8_72" in entry["command"]
    for chip in ("c8", "rc"):
        for area in ("flash", "ram"):
            name = f"overflow_{chip}_{area}"
            command(["cmake", "--build", destination, "--target", name, "--parallel", "4"],
                    work / f"{name}.log", failure=r"overflow|will not fit|exceeds")
            print(f"PASS expected link failure: {name}")
    for name, arguments, error in (("bad_mcu", "MCU STM32F103XX", "Unsupported MCU"),
                                    ("bad_clock", "MCU STM32F103C8T6 CLOCK BAD", "Unsupported CLOCK")):
        (consumer / "CMakeLists.txt").write_text(preamble +
            f"add_executable(bad main.c)\nstm32f1_configure_target(bad {arguments})\n")
        command(["cmake", "-S", consumer, "-B", work / name, *flags],
                work / f"{name}.log", failure=error)
        print(f"PASS expected configure failure: {name}")
    (consumer / "CMakeLists.txt").write_text(cmake)
    command(["git", "diff", "--exit-code"], work / "vendor-clean.log", cwd=dependency)
    print("PASS submodule path with spaces, independent MCU/clock targets, custom SystemInit")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-dir", required=True, type=Path)
    parser.add_argument("--integration", action="store_true")
    args = parser.parse_args()
    build = args.build_dir.resolve()
    cache = cache_values(build)
    for name in ("blink", "uart"):
        check_image(build / "examples" / f"{name}.elf", cache["STM32F1_EXAMPLE_MCU"])
    if args.integration:
        integration(build, cache)
    print("All checks passed (compile/link checks; no hardware execution)")


if __name__ == "__main__":
    main()
