/*
 * x87_prelude_transition_capture.c -- isolate the FCOS sequence-state arm.
 *
 * h1406/h1410 showed that the eleven direct-FLDT frontier misses select the
 * current arithmetic endpoint after many distinct producer sequences.  All
 * of those sequences also contained status/control serialization before
 * FCOS.  This harness separates that common prelude from value provenance.
 *
 * Each frozen row uses one previously unopened instruction sequence and one
 * FCOS.  Direct batch contexts and all earlier FADD contexts are excluded.
 * The no-status variants deliberately avoid reading the x87 status word
 * until after FCOS, because FNSTSW is itself one of the tested transitions.
 *
 * Input:
 *   case mode variant se sig
 */

#include <stdint.h>
#include <stdio.h>
#include <string.h>

#if !defined(__i386__) && !defined(__x86_64__)
#error "x87 prelude-transition capture requires an x86 host"
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

#define CAPTURE_RESULT_ASM \
    "fcos\n\t" \
    "fwait\n\t" \
    "fnstsw %[after_sw]\n\t" \
    "fstpt %[result]"

static int run_variant(const char *variant, const struct x80mem *operand,
                       uint16_t target_cw, uint16_t *pre_sw,
                       uint16_t *after_sw, struct x80mem *result)
{
    struct x80mem scratch;
    *pre_sw = 0xffff;

    if (!strcmp(variant, "init_load")) {
        __asm__ volatile(
            "fninit\n\t"
            "fldcw %[target_cw]\n\t"
            "fldt %[operand]\n\t"
            CAPTURE_RESULT_ASM
            : [after_sw] "=m" (*after_sw), [result] "=m" (*result)
            : [target_cw] "m" (target_cw), [operand] "m" (*operand)
            : "st", "memory");
        return 1;
    }
    if (!strcmp(variant, "init_clex_load")) {
        __asm__ volatile(
            "fninit\n\t"
            "fldcw %[target_cw]\n\t"
            "fnclex\n\t"
            "fldt %[operand]\n\t"
            CAPTURE_RESULT_ASM
            : [after_sw] "=m" (*after_sw), [result] "=m" (*result)
            : [target_cw] "m" (target_cw), [operand] "m" (*operand)
            : "st", "memory");
        return 1;
    }
    if (!strcmp(variant, "init_load_clex")) {
        __asm__ volatile(
            "fninit\n\t"
            "fldcw %[target_cw]\n\t"
            "fldt %[operand]\n\t"
            "fnclex\n\t"
            CAPTURE_RESULT_ASM
            : [after_sw] "=m" (*after_sw), [result] "=m" (*result)
            : [target_cw] "m" (target_cw), [operand] "m" (*operand)
            : "st", "memory");
        return 1;
    }
    if (!strcmp(variant, "init_load_nop")) {
        __asm__ volatile(
            "fninit\n\t"
            "fldcw %[target_cw]\n\t"
            "fldt %[operand]\n\t"
            "nop\n\t"
            CAPTURE_RESULT_ASM
            : [after_sw] "=m" (*after_sw), [result] "=m" (*result)
            : [target_cw] "m" (target_cw), [operand] "m" (*operand)
            : "st", "memory");
        return 1;
    }
    if (!strcmp(variant, "init_load_lfence")) {
        __asm__ volatile(
            "fninit\n\t"
            "fldcw %[target_cw]\n\t"
            "fldt %[operand]\n\t"
            "lfence\n\t"
            CAPTURE_RESULT_ASM
            : [after_sw] "=m" (*after_sw), [result] "=m" (*result)
            : [target_cw] "m" (target_cw), [operand] "m" (*operand)
            : "st", "memory");
        return 1;
    }
    if (!strcmp(variant, "init_load_fwait")) {
        __asm__ volatile(
            "fninit\n\t"
            "fldcw %[target_cw]\n\t"
            "fldt %[operand]\n\t"
            "fwait\n\t"
            CAPTURE_RESULT_ASM
            : [after_sw] "=m" (*after_sw), [result] "=m" (*result)
            : [target_cw] "m" (target_cw), [operand] "m" (*operand)
            : "st", "memory");
        return 1;
    }
    if (!strcmp(variant, "init_load_status")) {
        __asm__ volatile(
            "fninit\n\t"
            "fldcw %[target_cw]\n\t"
            "fldt %[operand]\n\t"
            "fnstsw %[pre_sw]\n\t"
            CAPTURE_RESULT_ASM
            : [pre_sw] "=m" (*pre_sw), [after_sw] "=m" (*after_sw),
              [result] "=m" (*result)
            : [target_cw] "m" (target_cw), [operand] "m" (*operand)
            : "st", "memory");
        return 1;
    }
    if (!strcmp(variant, "init_load_cw")) {
        __asm__ volatile(
            "fninit\n\t"
            "fldcw %[target_cw]\n\t"
            "fldt %[operand]\n\t"
            "fldcw %[target_cw]\n\t"
            CAPTURE_RESULT_ASM
            : [after_sw] "=m" (*after_sw), [result] "=m" (*result)
            : [target_cw] "m" (target_cw), [operand] "m" (*operand)
            : "st", "memory");
        return 1;
    }
    if (!strcmp(variant, "init_load_wait_status_cw")) {
        __asm__ volatile(
            "fninit\n\t"
            "fldcw %[target_cw]\n\t"
            "fldt %[operand]\n\t"
            "fwait\n\t"
            "fnstsw %[pre_sw]\n\t"
            "fldcw %[target_cw]\n\t"
            CAPTURE_RESULT_ASM
            : [pre_sw] "=m" (*pre_sw), [after_sw] "=m" (*after_sw),
              [result] "=m" (*result)
            : [target_cw] "m" (target_cw), [operand] "m" (*operand)
            : "st", "memory");
        return 1;
    }
    if (!strcmp(variant, "init_load_fxam")) {
        __asm__ volatile(
            "fninit\n\t"
            "fldcw %[target_cw]\n\t"
            "fldt %[operand]\n\t"
            "fxam\n\t"
            CAPTURE_RESULT_ASM
            : [after_sw] "=m" (*after_sw), [result] "=m" (*result)
            : [target_cw] "m" (target_cw), [operand] "m" (*operand)
            : "st", "memory");
        return 1;
    }
    if (!strcmp(variant, "init_fchs2_nostatus")) {
        __asm__ volatile(
            "fninit\n\t"
            "fldcw %[target_cw]\n\t"
            "fldt %[operand]\n\t"
            "fchs\n\t"
            "fchs\n\t"
            CAPTURE_RESULT_ASM
            : [after_sw] "=m" (*after_sw), [result] "=m" (*result)
            : [target_cw] "m" (target_cw), [operand] "m" (*operand)
            : "st", "memory");
        return 1;
    }
    if (!strcmp(variant, "init_add0_nostatus")) {
        __asm__ volatile(
            "fninit\n\t"
            "fldcw %[target_cw]\n\t"
            "fldt %[operand]\n\t"
            "fldz\n\t"
            ".byte 0xde, 0xc1\n\t" /* FADDP ST(1), ST(0). */
            CAPTURE_RESULT_ASM
            : [after_sw] "=m" (*after_sw), [result] "=m" (*result)
            : [target_cw] "m" (target_cw), [operand] "m" (*operand)
            : "st", "st(1)", "memory");
        return 1;
    }
    if (!strcmp(variant, "init_add0_store_reload_nostatus")) {
        __asm__ volatile(
            "fninit\n\t"
            "fldcw %[target_cw]\n\t"
            "fldt %[operand]\n\t"
            "fldz\n\t"
            ".byte 0xde, 0xc1\n\t" /* FADDP ST(1), ST(0). */
            "fstpt %[scratch]\n\t"
            "fldt %[scratch]\n\t"
            CAPTURE_RESULT_ASM
            : [after_sw] "=m" (*after_sw), [result] "=m" (*result),
              [scratch] "=m" (scratch)
            : [target_cw] "m" (target_cw), [operand] "m" (*operand)
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
        char case_id[32], mode[8], variant[48];
        unsigned se_value;
        unsigned long long sig_value;
        line_number++;
        if (line[0] == '#' || line[0] == '\n') continue;
        if (sscanf(line, "%31s %7s %47s %x %llx",
                   case_id, mode, variant, &se_value, &sig_value) != 5) {
            fprintf(stderr, "line %u: expected five fields\n", line_number);
            return 2;
        }
        if (se_value > 0xffff) {
            fprintf(stderr, "line %u: bad operand exponent\n", line_number);
            return 2;
        }

        uint16_t target_cw, pre_sw, after_sw, result_se;
        uint64_t result_sig;
        struct x80mem operand, result;
        if (!target_control_word(mode, &target_cw)) {
            fprintf(stderr, "line %u: bad target mode\n", line_number);
            return 2;
        }
        pack_x80((uint16_t)se_value, (uint64_t)sig_value, &operand);
        if (!run_variant(variant, &operand, target_cw, &pre_sw,
                         &after_sw, &result)) {
            fprintf(stderr, "line %u: bad prelude variant\n", line_number);
            return 2;
        }
        unpack_x80(&result, &result_se, &result_sig);
        printf("CASE=%s MODE=%s VARIANT=%s OPERAND=%04x:%016llx "
               "PRE_SW=%04x RESULT=%04x:%016llx AFTER_SW=%04x\n",
               case_id, mode, variant, se_value, sig_value, pre_sw,
               result_se, (unsigned long long)result_sig, after_sw);
    }
    __asm__ volatile("fninit" ::: "memory");
    return 0;
}

