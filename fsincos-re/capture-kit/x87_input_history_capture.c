/*
 * x87_input_history_capture.c -- one-shot FCOS input-history discriminator.
 *
 * Every row constructs the frozen architectural ST(0) value with one of
 * three FADD producers before executing FCOS exactly once:
 *
 *   add_zero          x + 0             -> x, exact
 *   add_plus_quarter  x + 1/4 ulp(x)    -> x, rounded downward under RN
 *   add_minus_quarter x - 1/4 ulp(x)    -> x, rounded upward under RN
 *
 * The producer always uses PC64/RN.  FCOS then uses the row's requested
 * rounding mode.  No direct-load baseline is captured: its immutable result
 * is already present in the source manifest.  This makes every hardware row
 * a new execution context while preserving the same visible 80-bit operand.
 *
 * Input:
 *   case mode variant se sig
 *
 * Build only on x86 Linux:
 *   gcc -O2 -Wall -Wextra -o x87_input_history_capture \
 *       x87_input_history_capture.c
 */

#include <stdint.h>
#include <stdio.h>
#include <string.h>

#if !defined(__i386__) && !defined(__x86_64__)
#error "x87 input-history capture requires an x86 host"
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

static int make_delta(const char *variant, uint16_t operand_se,
                      struct x80mem *delta)
{
    uint16_t exponent = operand_se & 0x7fff;
    if (!strcmp(variant, "add_zero")) {
        pack_x80(0, 0, delta);
        return 1;
    }
    if ((operand_se & 0x8000) || exponent <= 65 || exponent == 0x7fff)
        return 0;
    /* A 64-significand-bit value has ulp exponent E-63.  A quarter ulp
       is therefore the exact power of two with encoded exponent e-65. */
    uint16_t delta_se = (uint16_t)(exponent - 65);
    if (!strcmp(variant, "add_plus_quarter")) {
        pack_x80(delta_se, UINT64_C(0x8000000000000000), delta);
        return 1;
    }
    if (!strcmp(variant, "add_minus_quarter")) {
        pack_x80((uint16_t)(delta_se | 0x8000),
                 UINT64_C(0x8000000000000000), delta);
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

        uint16_t target_cw;
        struct x80mem operand, delta, result;
        uint16_t producer_sw, after_sw, result_se;
        uint64_t result_sig;
        const uint16_t producer_cw = 0x037f; /* PC64, RN, all masked. */
        if (!target_control_word(mode, &target_cw)
            || !make_delta(variant, (uint16_t)se_value, &delta)) {
            fprintf(stderr, "line %u: bad mode, variant, or operand\n",
                    line_number);
            return 2;
        }
        pack_x80((uint16_t)se_value, (uint64_t)sig_value, &operand);

        __asm__ volatile(
            "fninit\n\t"
            "fldcw %[producer_cw]\n\t"
            "fldt %[operand]\n\t"
            "fldt %[delta]\n\t"
            "faddp %%st, %%st(1)\n\t"
            "fwait\n\t"
            "fnstsw %[producer_sw]\n\t"
            "fldcw %[target_cw]\n\t"
            "fcos\n\t"
            "fwait\n\t"
            "fnstsw %[after_sw]\n\t"
            "fstpt %[result]"
            : [producer_sw] "=m" (producer_sw),
              [after_sw] "=m" (after_sw),
              [result] "=m" (result)
            : [producer_cw] "m" (producer_cw),
              [target_cw] "m" (target_cw),
              [operand] "m" (operand), [delta] "m" (delta)
            : "st", "st(1)", "memory");
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
