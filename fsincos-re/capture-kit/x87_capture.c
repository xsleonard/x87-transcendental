/*
 * x87_capture.c — run the REAL x87 FSINCOS over batch inputs.
 *
 * Runs on x86 Linux (the Intel Skylake VPS).  Reads "se_hex sig_hex" lines
 * (x87 80-bit: 15-bit sign+exponent field, 64-bit significand) on stdin and
 * prints, per line:
 *     OK <sin_se> <sin_sig> <cos_se> <cos_sig>
 *     C2
 * — the same format as `fsincos_ref --batch`, so outputs diff directly.
 * `--status` appends `SW <hex>` with the per-instruction x87 status word;
 * `--timing[=N]` additionally appends the minimum of N serialized cycle
 * measurements as `CYC <decimal>`.  Both are opt-in so historical captures
 * remain byte-compatible.
 *
 * The FPU control word defaults to 0x037F (round-to-nearest, 64-bit
 * precision, all exceptions masked).  The optional pc24/pc53/pc64
 * arguments vary only its precision-control field.
 *
 * Build:  gcc -O2 -o x87_capture x87_capture.c        (x86-64)
 *         gcc -O2 -m32 -o x87_capture32 x87_capture.c (i386, same core ops)
 */
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#if !defined(__i386__) && !defined(__x86_64__)
#error "x87 capture harness requires an x86 host"
#endif

struct x80mem { unsigned char b[10]; };

static void pack(uint16_t se, uint64_t sig, struct x80mem *m)
{
    memcpy(m->b, &sig, 8);
    memcpy(m->b + 8, &se, 2);
}
static void unpack(const struct x80mem *m, uint16_t *se, uint64_t *sig)
{
    memcpy(sig, m->b, 8);
    memcpy(se, m->b + 8, 2);
}

enum {
    INSN_FSINCOS,
    INSN_FSIN,
    INSN_FCOS,
    INSN_FPTAN,
    INSN_F2XM1
};

static int g_insn = INSN_FSINCOS;
static int g_status = 0;
static int g_timing_samples = 0;

/*
 * Status/timing instrumentation for this capture
 * harness.  Timing covers load + transcendental instruction + status/wait,
 * but excludes the result pop; the minimum of repeated samples suppresses
 * interrupt and scheduler noise.
 */
static uint64_t read_tsc(void)
{
    uint32_t lo, hi;
    __asm__ volatile("rdtsc" : "=a" (lo), "=d" (hi) :: "memory");
    return ((uint64_t)hi << 32) | lo;
}

/*
 * Timing serialization for the capture harness.
 * Preserve EBX explicitly under 32-bit PIC; old i686 Linux toolchains often
 * build PIE by default.
 */
static void cpuid_barrier(void)
{
    unsigned a = 0, b, c, d;
#if defined(__i386__) && defined(__PIC__)
    __asm__ volatile(
        "xchgl %%ebx, %1\n\t"
        "cpuid\n\t"
        "xchgl %%ebx, %1"
        : "+a" (a), "=&r" (b), "=c" (c), "=d" (d)
        :
        : "memory");
#else
    __asm__ volatile(
        "cpuid"
        : "+a" (a), "=b" (b), "=c" (c), "=d" (d)
        :
        : "memory");
#endif
    (void)b; (void)c; (void)d;
}

static uint16_t do_fsin1_once(
    const struct x80mem *x, struct x80mem *out, int insn,
    int measure, uint64_t *cycles)
{
    uint16_t sw;
    uint64_t start = 0, end = 0;
    if (measure) {
        cpuid_barrier();
        start = read_tsc();
    }
    if (insn == INSN_FCOS)
        __asm__ volatile(
            "fnclex\n\t"
            "fldt   %[x]\n\t"
            "fcos\n\t"
            "fwait\n\t"
            "fnstsw %%ax\n\t"
            "movw   %%ax, %[sw]\n\t"
            : [sw] "=m" (sw)
            : [x] "m" (*x)
            : "ax", "st", "st(1)", "st(2)", "st(3)", "st(4)", "st(5)", "st(6)", "st(7)");
    else if (insn == INSN_F2XM1)
        __asm__ volatile(
            "fnclex\n\t"
            "fldt   %[x]\n\t"
            "f2xm1\n\t"
            "fwait\n\t"
            "fnstsw %%ax\n\t"
            "movw   %%ax, %[sw]\n\t"
            : [sw] "=m" (sw)
            : [x] "m" (*x)
            : "ax", "st", "st(1)", "st(2)", "st(3)", "st(4)", "st(5)", "st(6)", "st(7)");
    else
        __asm__ volatile(
            "fnclex\n\t"
            "fldt   %[x]\n\t"
            "fsin\n\t"
            "fwait\n\t"
            "fnstsw %%ax\n\t"
            "movw   %%ax, %[sw]\n\t"
            : [sw] "=m" (sw)
            : [x] "m" (*x)
            : "ax", "st", "st(1)", "st(2)", "st(3)", "st(4)", "st(5)", "st(6)", "st(7)");
    if (measure) {
        end = read_tsc();
        cpuid_barrier();
        *cycles = end - start;
    }
    __asm__ volatile("fstpt %[o]" : [o] "=m" (*out) :: "st");
    return sw;
}

static uint16_t do_fsin1(
    const struct x80mem *x, struct x80mem *out, int insn,
    uint64_t *best_cycles)
{
    int samples = g_timing_samples ? g_timing_samples : 1;
    uint16_t best_sw = 0;
    *best_cycles = UINT64_MAX;
    for (int i = 0; i < samples; i++) {
        struct x80mem candidate;
        uint64_t cycles = 0;
        uint16_t sw = do_fsin1_once(
            x, &candidate, insn, g_timing_samples != 0, &cycles);
        if (!g_timing_samples || cycles < *best_cycles) {
            *out = candidate;
            best_sw = sw;
            *best_cycles = cycles;
        }
    }
    return best_sw;
}

/*
 * capture FPTAN's architectural pair in the same
 * mathematical-result-first order used by the FSINCOS output format.
 */
static uint16_t do_fptan_once(
    const struct x80mem *x, struct x80mem *tangent, struct x80mem *one,
    int measure, uint64_t *cycles)
{
    uint16_t sw;
    uint64_t start = 0, end = 0;
    if (measure) {
        cpuid_barrier();
        start = read_tsc();
    }
    __asm__ volatile(
        "fnclex\n\t"
        "fldt   %[x]\n\t"
        "fptan\n\t"
        "fwait\n\t"
        "fnstsw %%ax\n\t"
        "movw   %%ax, %[sw]\n\t"
        : [sw] "=m" (sw)
        : [x] "m" (*x)
        : "ax", "st", "st(1)", "st(2)", "st(3)", "st(4)", "st(5)", "st(6)", "st(7)");
    if (measure) {
        end = read_tsc();
        cpuid_barrier();
        *cycles = end - start;
    }
    if (sw & 0x0400) {
        struct x80mem scratch;
        __asm__ volatile("fstpt %[o]" : [o] "=m" (scratch) :: "st");
    } else {
        __asm__ volatile(
            "fstpt  %[one]\n\t"             /* ST(0) = pushed 1.0 */
            "fstpt  %[tan]\n\t"             /* ST(1) = tangent */
            : [one] "=m" (*one), [tan] "=m" (*tangent)
            :
            : "st", "st(1)");
    }
    return sw;
}

/* repeated-minimum timing wrapper for FPTAN. */
static uint16_t do_fptan(
    const struct x80mem *x, struct x80mem *tangent, struct x80mem *one,
    uint64_t *best_cycles)
{
    int samples = g_timing_samples ? g_timing_samples : 1;
    uint16_t best_sw = 0;
    *best_cycles = UINT64_MAX;
    for (int i = 0; i < samples; i++) {
        struct x80mem candidate_tangent, candidate_one;
        uint64_t cycles = 0;
        uint16_t sw = do_fptan_once(
            x, &candidate_tangent, &candidate_one,
            g_timing_samples != 0, &cycles);
        if (!g_timing_samples || cycles < *best_cycles) {
            if (!(sw & 0x0400)) {
                *tangent = candidate_tangent;
                *one = candidate_one;
            }
            best_sw = sw;
            *best_cycles = cycles;
        }
    }
    return best_sw;
}

static uint16_t do_fsincos_once(
    const struct x80mem *x, struct x80mem *s, struct x80mem *c,
    int measure, uint64_t *cycles)
{
    uint16_t sw;
    uint64_t start = 0, end = 0;
    if (measure) {
        cpuid_barrier();
        start = read_tsc();
    }
    __asm__ volatile(
        "fnclex\n\t"
        "fldt   %[x]\n\t"
        "fsincos\n\t"
        "fwait\n\t"
        "fnstsw %%ax\n\t"
        "movw   %%ax, %[sw]\n\t"
        : [sw] "=m" (sw)
        : [x] "m" (*x)
        : "ax", "st", "st(1)", "st(2)", "st(3)", "st(4)", "st(5)", "st(6)", "st(7)");
    if (measure) {
        end = read_tsc();
        cpuid_barrier();
        *cycles = end - start;
    }
    if (sw & 0x0400) {
        struct x80mem scratch;
        __asm__ volatile("fstpt %[o]" : [o] "=m" (scratch) :: "st");
    } else {
        __asm__ volatile(
            "fstpt  %[c]\n\t"               /* ST(0) = cos */
            "fstpt  %[s]\n\t"               /* ST(1) = sin */
            : [c] "=m" (*c), [s] "=m" (*s)
            :
            : "st", "st(1)");
    }
    return sw;
}

static uint16_t do_fsincos(
    const struct x80mem *x, struct x80mem *s, struct x80mem *c,
    uint64_t *best_cycles)
{
    int samples = g_timing_samples ? g_timing_samples : 1;
    uint16_t best_sw = 0;
    *best_cycles = UINT64_MAX;
    for (int i = 0; i < samples; i++) {
        struct x80mem candidate_s, candidate_c;
        uint64_t cycles = 0;
        uint16_t sw = do_fsincos_once(
            x, &candidate_s, &candidate_c,
            g_timing_samples != 0, &cycles);
        if (!g_timing_samples || cycles < *best_cycles) {
            if (!(sw & 0x0400)) {
                *s = candidate_s;
                *c = candidate_c;
            }
            best_sw = sw;
            *best_cycles = cycles;
        }
    }
    return best_sw;
}

static void print_suffix(uint16_t sw, uint64_t cycles)
{
    if (g_status) printf(" SW %04x", sw);
    if (g_timing_samples)
        printf(" CYC %llu", (unsigned long long)cycles);
    putchar('\n');
}

int main(int argc, char **argv)
{
    uint16_t cw = 0x037F;               /* RN, PC=64-bit, exceptions masked */
    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "rn")) cw = (cw & ~0x0C00U) | 0x0000U;
        else if (!strcmp(argv[i], "rd")) cw = (cw & ~0x0C00U) | 0x0400U;
        else if (!strcmp(argv[i], "ru")) cw = (cw & ~0x0C00U) | 0x0800U;
        else if (!strcmp(argv[i], "rz")) cw = (cw & ~0x0C00U) | 0x0C00U;
        else if (!strcmp(argv[i], "pc24")) cw = (cw & ~0x0300U) | 0x0000U;
        else if (!strcmp(argv[i], "pc53")) cw = (cw & ~0x0300U) | 0x0200U;
        else if (!strcmp(argv[i], "pc64")) cw = (cw & ~0x0300U) | 0x0300U;
        else if (!strcmp(argv[i], "sincos")) g_insn = INSN_FSINCOS;
        else if (!strcmp(argv[i], "sin")) g_insn = INSN_FSIN;
        else if (!strcmp(argv[i], "cos")) g_insn = INSN_FCOS;
        else if (!strcmp(argv[i], "fptan")) g_insn = INSN_FPTAN;
        else if (!strcmp(argv[i], "f2xm1")) g_insn = INSN_F2XM1;
        else if (!strcmp(argv[i], "--status")) g_status = 1;
        else if (!strcmp(argv[i], "--timing")) g_timing_samples = 9;
        else if (!strncmp(argv[i], "--timing=", 9)) {
            g_timing_samples = atoi(argv[i] + 9);
            if (g_timing_samples < 1 || g_timing_samples > 1000) {
                fprintf(stderr, "timing sample count must be 1..1000\n");
                return 2;
            }
        } else {
            fprintf(stderr, "unknown argument: %s\n", argv[i]);
            return 2;
        }
    }
    __asm__ volatile("fclex; fldcw %0" :: "m"(cw));

    unsigned se; unsigned long long sig;
    while (scanf("%x %llx", &se, &sig) == 2) {
        struct x80mem xin, xs = {{0}}, xc = {{0}};
        uint16_t sw;
        uint64_t cycles;
        pack((uint16_t)se, (uint64_t)sig, &xin);
        if (g_insn == INSN_FSIN || g_insn == INSN_FCOS
            || g_insn == INSN_F2XM1) {
            struct x80mem xo = {{0}};
            sw = do_fsin1(&xin, &xo, g_insn, &cycles);
            if (g_insn != INSN_F2XM1 && (sw & 0x0400)) {
                fputs("C2", stdout);
                print_suffix(sw, cycles);
                continue;
            }
            uint16_t ose; uint64_t osig;
            unpack(&xo, &ose, &osig);
            printf("OK %04x %016llx", ose, (unsigned long long)osig);
            print_suffix(sw, cycles);
            continue;
        }
        if (g_insn == INSN_FPTAN) {
            struct x80mem xt = {{0}}, xone = {{0}};
            sw = do_fptan(&xin, &xt, &xone, &cycles);
            if (sw & 0x0400) {
                fputs("C2", stdout);
                print_suffix(sw, cycles);
                continue;
            }
            uint16_t tse, ose; uint64_t tsig, osig;
            unpack(&xt, &tse, &tsig);
            unpack(&xone, &ose, &osig);
            printf("OK %04x %016llx %04x %016llx",
                   tse, (unsigned long long)tsig,
                   ose, (unsigned long long)osig);
            print_suffix(sw, cycles);
            continue;
        }
        sw = do_fsincos(&xin, &xs, &xc, &cycles);
        if (sw & 0x0400) {
            fputs("C2", stdout);
            print_suffix(sw, cycles);
            continue;
        }
        uint16_t sse, cse; uint64_t ssig, csig;
        unpack(&xs, &sse, &ssig);
        unpack(&xc, &cse, &csig);
        printf("OK %04x %016llx %04x %016llx",
               sse, (unsigned long long)ssig, cse, (unsigned long long)csig);
        print_suffix(sw, cycles);
    }
    return 0;
}
