/*
 * x87_arith.c — run REAL x87 FMUL / FADD / FSUB over batch inputs on
 * the Skylake host, so model intermediates can be checked against the
 * chip's own multiplier/adder.
 *
 * Reads "se1 sig1 se2 sig2" lines (two x87 80-bit operands: 16-bit
 * sign+exponent field, 64-bit significand with explicit integer bit).
 * Prints per line:  OK <se> <sig>   (result of op1 <op> op2)
 *   --status appends " SW <hex>".
 * Args: fmul|fadd|fsub ; rn|rd|ru|rz ; pc24|pc53|pc64 ; --status
 * Default control word 0x037F (RN, PC=64-bit, all exceptions masked).
 *
 * NOTE: architectural x87 rounds the result significand to <=64 bits
 * (PC64).  FCOS microcode intermediates use wider internal precision,
 * so this oracle reproduces 64-bit ops exactly but NOT 67-bit internal
 * products.  Build: gcc -O2 -o x87_arith x87_arith.c
 */
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#if !defined(__i386__) && !defined(__x86_64__)
#error "x87 harness requires an x86 host"
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

enum { OP_FMUL, OP_FADD, OP_FSUB };
static int g_op = OP_FMUL;
static int g_status = 0;

static uint16_t do_op(const struct x80mem *a, const struct x80mem *b,
                      struct x80mem *out)
{
    uint16_t sw;
    /* load a then b: st0=b, st1=a; op-and-pop => st0 = a OP b */
    if (g_op == OP_FMUL)
        __asm__ volatile(
            "fnclex\n\t fldt %[a]\n\t fldt %[b]\n\t"
            "fmulp %%st, %%st(1)\n\t"
            "fwait\n\t fnstsw %%ax\n\t movw %%ax, %[sw]\n\t"
            : [sw] "=m" (sw) : [a] "m" (*a), [b] "m" (*b)
            : "ax", "st", "st(1)", "st(2)", "st(3)", "st(4)",
              "st(5)", "st(6)", "st(7)");
    else if (g_op == OP_FADD)
        __asm__ volatile(
            "fnclex\n\t fldt %[a]\n\t fldt %[b]\n\t"
            "faddp %%st, %%st(1)\n\t"
            "fwait\n\t fnstsw %%ax\n\t movw %%ax, %[sw]\n\t"
            : [sw] "=m" (sw) : [a] "m" (*a), [b] "m" (*b)
            : "ax", "st", "st(1)", "st(2)", "st(3)", "st(4)",
              "st(5)", "st(6)", "st(7)");
    else /* FSUB: a - b.  st0=b, st1=a; fsubrp st(1) => st1 = st1 - st0 */
        __asm__ volatile(
            "fnclex\n\t fldt %[a]\n\t fldt %[b]\n\t"
            "fsubrp %%st, %%st(1)\n\t"
            "fwait\n\t fnstsw %%ax\n\t movw %%ax, %[sw]\n\t"
            : [sw] "=m" (sw) : [a] "m" (*a), [b] "m" (*b)
            : "ax", "st", "st(1)", "st(2)", "st(3)", "st(4)",
              "st(5)", "st(6)", "st(7)");
    __asm__ volatile("fstpt %[o]" : [o] "=m" (*out) :: "st");
    return sw;
}

int main(int argc, char **argv)
{
    uint16_t cw = 0x037F;
    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "rn")) cw = (cw & ~0x0C00U) | 0x0000U;
        else if (!strcmp(argv[i], "rd")) cw = (cw & ~0x0C00U) | 0x0400U;
        else if (!strcmp(argv[i], "ru")) cw = (cw & ~0x0C00U) | 0x0800U;
        else if (!strcmp(argv[i], "rz")) cw = (cw & ~0x0C00U) | 0x0C00U;
        else if (!strcmp(argv[i], "pc24")) cw = (cw & ~0x0300U) | 0x0000U;
        else if (!strcmp(argv[i], "pc53")) cw = (cw & ~0x0300U) | 0x0200U;
        else if (!strcmp(argv[i], "pc64")) cw = (cw & ~0x0300U) | 0x0300U;
        else if (!strcmp(argv[i], "fmul")) g_op = OP_FMUL;
        else if (!strcmp(argv[i], "fadd")) g_op = OP_FADD;
        else if (!strcmp(argv[i], "fsub")) g_op = OP_FSUB;
        else if (!strcmp(argv[i], "--status")) g_status = 1;
        else { fprintf(stderr, "unknown arg: %s\n", argv[i]); return 2; }
    }
    __asm__ volatile("fclex; fldcw %0" :: "m"(cw));

    unsigned se1, se2;
    unsigned long long sig1, sig2;
    while (scanf("%x %llx %x %llx", &se1, &sig1, &se2, &sig2) == 4) {
        struct x80mem a, b, o = {{0}};
        pack((uint16_t)se1, (uint64_t)sig1, &a);
        pack((uint16_t)se2, (uint64_t)sig2, &b);
        uint16_t sw = do_op(&a, &b, &o);
        uint16_t ose; uint64_t osig;
        unpack(&o, &ose, &osig);
        printf("OK %04x %016llx", ose, (unsigned long long)osig);
        if (g_status) printf(" SW %04x", sw);
        putchar('\n');
    }
    return 0;
}
