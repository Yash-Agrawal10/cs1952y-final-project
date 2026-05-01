#pragma once

// Region-of-interest markers for gem5 stat capture.
//
// When GEM5_M5OPS is defined (set by the Makefile for RISC-V builds), these
// emit gem5's magic instructions inline. We don't link libm5.a because its
// address-based variants pull in <sys/mman.h>, which newlib doesn't ship.
//
// Encoding (per gem5/util/m5/src/abi/riscv/m5op.S):
//   bits 6:0   = 0x7B (custom-1 opcode)
//   bits 31:25 = M5FUNC (function code from gem5/asm/generic/m5ops.h)
// Args go in a0/a1 per RISC-V calling convention.
//
// Function codes:
//   M5OP_DUMP_STATS         = 0x41 -> 0x8200007B
//   M5OP_DUMP_RESET_STATS   = 0x42 -> 0x8400007B
//   M5OP_EXIT               = 0x21 -> 0x4200007B

#ifdef GEM5_M5OPS

static inline void m5_dump_reset_stats_inline() {
    register unsigned long a0 asm("a0") = 0;
    register unsigned long a1 asm("a1") = 0;
    asm volatile (".long 0x8400007B" : : "r"(a0), "r"(a1) : "memory");
}

static inline void m5_dump_stats_inline() {
    register unsigned long a0 asm("a0") = 0;
    register unsigned long a1 asm("a1") = 0;
    asm volatile (".long 0x8200007B" : : "r"(a0), "r"(a1) : "memory");
}

static inline void m5_exit_inline() {
    register unsigned long a0 asm("a0") = 0;
    asm volatile (".long 0x4200007B" : : "r"(a0) : "memory");
}

#define M5_ROI_BEGIN() m5_dump_reset_stats_inline()
#define M5_ROI_END()   m5_dump_stats_inline()
#define M5_EXIT()      m5_exit_inline()

#else

#define M5_ROI_BEGIN() ((void)0)
#define M5_ROI_END()   ((void)0)
#define M5_EXIT()      ((void)0)

#endif
