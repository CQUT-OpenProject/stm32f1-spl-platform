/* SPDX-License-Identifier: MIT */
#include <errno.h>
#include <stddef.h>
#include <stdint.h>

extern unsigned char _heap_start;
extern unsigned char _heap_end;

/* The ST reset handler calls __libc_init_array, without a hosted crt0. */
__attribute__((weak)) void _init(void) {}
__attribute__((weak)) void _fini(void) {}

/* Single-threaded default. An RTOS/application may provide its own allocator. */
__attribute__((weak)) void *_sbrk(ptrdiff_t increment)
{
    static uintptr_t current;
    const uintptr_t start = (uintptr_t)&_heap_start;
    const uintptr_t end = (uintptr_t)&_heap_end;
    if (current == 0U) {
        current = start;
    }
    uintptr_t amount = increment < 0 ? (uintptr_t)(-(increment + 1)) + 1U
                                     : (uintptr_t)increment;
    if ((increment >= 0 && amount > end - current) ||
        (increment < 0 && amount > current - start)) {
        errno = ENOMEM;
        return (void *)-1;
    }
    const uintptr_t previous = current;
    current = increment < 0 ? current - amount : current + amount;
    return (void *)previous;
}
