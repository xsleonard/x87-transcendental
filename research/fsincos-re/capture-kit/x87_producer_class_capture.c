/*
 * x87_producer_class_capture.c -- one-shot FCOS producer-class matrix.
 *
 * Each row presents the same architectural 80-bit value to FCOS after one
 * previously unopened producer sequence.  The variants distinguish exact
 * arithmetic results from non-arithmetic register traffic and from an
 * extended-precision memory round trip:
 *
 *   sub_zero               x - 0
 *   mul_one                x * 1
 *   div_one                x / 1
 *   chs_twice              FCHS(FCHS(x))
 *   copy_pop               FLD ST(0), then copy back/pop
 *   fxch_roundtrip         move x through a two-register FXCH round trip
 *   add_zero_store_reload  (x + 0), FSTP m80, then FLD m80
 *
 * Every sequence is exact at PC64/RN and leaves one copy of x in ST(0).
 * The existing direct-FLDT and FADD-only contexts are deliberately absent.
 * FCOS then runs once under the requested target rounding mode.
 *
 * Input:
 *   case mode variant se sig
 *
 * Build only on x86 Linux:
 *   gcc -O2 -Wall -Wextra -o x87_producer_class_capture \
 *       x87_producer_class_capture.c
 */

#include <stdint.h>
#include <stdio.h>
#include <string.h>

#if !defined(__i386__) && !defined(__x86_64__)
#error "x87 producer-class capture requires an x86 host"
#endif

struct x80mem {
    unsigned char bytes[10];
};

static void pack_x80(uint16_t se, uint64_t sig, struct x80mem *out)
{
    memcpy(out->bytes, &sig, sizeof sig);
    memcpy(out->bytes + 8, &se, sizeof se);
}

static void unpack_x80(const struct x80mem *value, uint16_t *se, uint64_t *sig)
{
    memcpy(sig, value->bytes, sizeof *sig);
    memcpy(se, value->bytes + 8, sizeof *se);
}

static int target_control_word(const char *mode, uint16_t *cw)
{
    uint16_t rc;
    if (!strcmp(mode, "rn")) rc = 0x0000;
    else if (!strcmp(mode, "rd")) rc = 0x0400;
    else if (!strcmp(mode, "ru")) rc = 0x0800;
    else if (!strcmp(mode, "rz")) rc = 0x0c00;
    else return 0;
    *cw = (uint16_t)(0x037f | rc);
    return 1;
}

#define FINISH_FCOS_ASM \
    "fwait\n\t" \
    "fnstsw %[producer_sw]\n\t" \
    "fldcw %[target_cw]\n\t" \
    "fcos\n\t" \
    "fwait\n\t" \
    "fnstsw %[after_sw]\n\t" \
    "fstpt %[result]"

static int run_variant(const char *variant, const struct x80mem *operand,
                       uint16_t producer_cw, uint16_t target_cw,
                       uint16_t *producer_sw, uint16_t *after_sw,
                       struct x80mem *result)
{
    struct x80mem scratch;

    if (!strcmp(variant, "sub_zero")) {
        __asm__ volatile(
            "fninit\n\t"
            "fldcw %[producer_cw]\n\t"
            "fldt %[operand]\n\t"
            "fldz\n\t"
            /* DE E9: FSUBP ST(1), ST(0), hence x - 0. */
            ".byte 0xde, 0xe9\n\t"
            FINISH_FCOS_ASM
            : [producer_sw] "=m" (*producer_sw),
              [after_sw] "=m" (*after_sw), [result] "=m" (*result)
            : [producer_cw] "m" (producer_cw),
              [target_cw] "m" (target_cw), [operand] "m" (*operand)
            : "st", "st(1)", "memory");
        return 1;
    }
    if (!strcmp(variant, "mul_one")) {
        __asm__ volatile(
            "fninit\n\t"
            "fldcw %[producer_cw]\n\t"
            "fldt %[operand]\n\t"
            "fld1\n\t"
            /* DE C9: FMULP ST(1), ST(0), hence x * 1. */
            ".byte 0xde, 0xc9\n\t"
            FINISH_FCOS_ASM
            : [producer_sw] "=m" (*producer_sw),
              [after_sw] "=m" (*after_sw), [result] "=m" (*result)
            : [producer_cw] "m" (producer_cw),
              [target_cw] "m" (target_cw), [operand] "m" (*operand)
            : "st", "st(1)", "memory");
        return 1;
    }
    if (!strcmp(variant, "div_one")) {
        __asm__ volatile(
            "fninit\n\t"
            "fldcw %[producer_cw]\n\t"
            "fldt %[operand]\n\t"
            "fld1\n\t"
            /* DE F9: FDIVP ST(1), ST(0), hence x / 1. */
            ".byte 0xde, 0xf9\n\t"
            FINISH_FCOS_ASM
            : [producer_sw] "=m" (*producer_sw),
              [after_sw] "=m" (*after_sw), [result] "=m" (*result)
            : [producer_cw] "m" (producer_cw),
              [target_cw] "m" (target_cw), [operand] "m" (*operand)
            : "st", "st(1)", "memory");
        return 1;
    }
    if (!strcmp(variant, "chs_twice")) {
        __asm__ volatile(
            "fninit\n\t"
            "fldcw %[producer_cw]\n\t"
            "fldt %[operand]\n\t"
            "fchs\n\t"
            "fchs\n\t"
            FINISH_FCOS_ASM
            : [producer_sw] "=m" (*producer_sw),
              [after_sw] "=m" (*after_sw), [result] "=m" (*result)
            : [producer_cw] "m" (producer_cw),
              [target_cw] "m" (target_cw), [operand] "m" (*operand)
            : "st", "memory");
        return 1;
    }
    if (!strcmp(variant, "copy_pop")) {
        __asm__ volatile(
            "fninit\n\t"
            "fldcw %[producer_cw]\n\t"
            "fldt %[operand]\n\t"
            /* Copy ST(0), write that copy to ST(1), and pop to depth one. */
            ".byte 0xd9, 0xc0\n\t"
            ".byte 0xdd, 0xd9\n\t"
            FINISH_FCOS_ASM
            : [producer_sw] "=m" (*producer_sw),
              [after_sw] "=m" (*after_sw), [result] "=m" (*result)
            : [producer_cw] "m" (producer_cw),
              [target_cw] "m" (target_cw), [operand] "m" (*operand)
            : "st", "st(1)", "memory");
        return 1;
    }
    if (!strcmp(variant, "fxch_roundtrip")) {
        __asm__ volatile(
            "fninit\n\t"
            "fldcw %[producer_cw]\n\t"
            "fldt %[operand]\n\t"
            "fldz\n\t"
            "fxch %%st(1)\n\t"
            "fxch %%st(1)\n\t"
            "fstp %%st(0)\n\t"
            FINISH_FCOS_ASM
            : [producer_sw] "=m" (*producer_sw),
              [after_sw] "=m" (*after_sw), [result] "=m" (*result)
            : [producer_cw] "m" (producer_cw),
              [target_cw] "m" (target_cw), [operand] "m" (*operand)
            : "st", "st(1)", "memory");
        return 1;
    }
    if (!strcmp(variant, "add_zero_store_reload")) {
        __asm__ volatile(
            "fninit\n\t"
            "fldcw %[producer_cw]\n\t"
            "fldt %[operand]\n\t"
            "fldz\n\t"
            /* DE C1: FADDP ST(1), ST(0), hence x + 0. */
            ".byte 0xde, 0xc1\n\t"
            "fstpt %[scratch]\n\t"
            "fldt %[scratch]\n\t"
            FINISH_FCOS_ASM
            : [producer_sw] "=m" (*producer_sw),
              [after_sw] "=m" (*after_sw), [result] "=m" (*result),
              [scratch] "=m" (scratch)
            : [producer_cw] "m" (producer_cw),
              [target_cw] "m" (target_cw), [operand] "m" (*operand)
            : "st", "st(1)", "memory");
        return 1;
    }
    return 0;
}

int main(void)
{
    char line[256];
    unsigned line_number = 0;
    while (fgets(line, sizeof line, stdin)) {
        char case_id[32], mode[8], variant[32];
        unsigned se_value;
        unsigned long long sig_value;
        line_number++;
        if (line[0] == '#' || line[0] == '\n') continue;
        if (sscanf(line, "%31s %7s %31s %x %llx",
                   case_id, mode, variant, &se_value, &sig_value) != 5) {
            fprintf(stderr, "line %u: expected five fields\n", line_number);
            return 2;
        }
        if (se_value > 0xffff) {
            fprintf(stderr, "line %u: bad operand exponent\n", line_number);
            return 2;
        }

        const uint16_t producer_cw = 0x037f; /* PC64, RN, all masked. */
        uint16_t target_cw, producer_sw, after_sw, result_se;
        uint64_t result_sig;
        struct x80mem operand, result;
        if (!target_control_word(mode, &target_cw)) {
            fprintf(stderr, "line %u: bad target mode\n", line_number);
            return 2;
        }
        pack_x80((uint16_t)se_value, (uint64_t)sig_value, &operand);
        if (!run_variant(variant, &operand, producer_cw, target_cw,
                         &producer_sw, &after_sw, &result)) {
            fprintf(stderr, "line %u: bad producer variant\n", line_number);
            return 2;
        }
        unpack_x80(&result, &result_se, &result_sig);
        printf("CASE=%s MODE=%s VARIANT=%s OPERAND=%04x:%016llx "
               "PRODUCER_SW=%04x RESULT=%04x:%016llx AFTER_SW=%04x\n",
               case_id, mode, variant, se_value, sig_value,
               producer_sw, result_se, (unsigned long long)result_sig,
               after_sw);
    }
    __asm__ volatile("fninit" ::: "memory");
    return 0;
}

