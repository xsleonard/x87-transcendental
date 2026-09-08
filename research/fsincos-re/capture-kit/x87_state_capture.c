/*
 * x87_state_capture.c -- one-shot architectural-state capture for h1400.
 *
 * This is intentionally separate from x87_capture.c.  The older harness
 * clears exceptions before every instruction and pops the results, which is
 * ideal for value comparison but cannot establish sticky-flag, TOP, tag, or
 * stack-preservation semantics.  This harness executes the requested
 * transcendental instruction exactly once and snapshots FXSAVE immediately
 * before and after it without popping anything.
 *
 * Input (the frozen h1400 architecture-state-inputs.txt format):
 *   case instruction mode pc exception_masks_hex pre_depth prior_flags se sig
 *
 * instruction: fsin | fcos | fsincos
 * mode:        rn | rd | ru | rz
 * pc:          pc24 | pc53 | pc64
 * prior_flags: clear | ie | pe
 * pre_depth includes the operand in ST(0), and must be 1..8.  Distinct exact
 * sentinel values occupy the deeper stack registers.
 *
 * Build and run on the target x86 Linux machine:
 *   gcc -O2 -Wall -Wextra -o x87_state_capture x87_state_capture.c
 *   ./x87_state_capture < architecture-state-inputs.txt > state-output.txt
 *
 * The exception-mask field is accepted so the complete control word is
 * explicit, but this version requires all six exceptions masked (0x3f).
 * Unmasked exception delivery needs a signal/ucontext harness and is not
 * silently approximated here.
 */

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#if !defined(__i386__) && !defined(__x86_64__)
#error "x87 architectural-state capture requires an x86 host"
#endif

struct x80mem {
    unsigned char bytes[10];
};

struct fxsave_area {
    unsigned char bytes[512];
} __attribute__((aligned(16)));

static uint16_t load_u16(const unsigned char *bytes)
{
    uint16_t value;
    memcpy(&value, bytes, sizeof value);
    return value;
}

static uint64_t load_u64(const unsigned char *bytes)
{
    uint64_t value;
    memcpy(&value, bytes, sizeof value);
    return value;
}

static void pack_x80(uint16_t se, uint64_t sig, struct x80mem *out)
{
    memcpy(out->bytes, &sig, sizeof sig);
    memcpy(out->bytes + 8, &se, sizeof se);
}

static void snapshot(struct fxsave_area *area)
{
    memset(area, 0, sizeof *area);
    __asm__ volatile("fxsave %0" : "=m" (*area) :: "memory");
}

static int parse_mode(const char *text, uint16_t *bits)
{
    if (!strcmp(text, "rn")) *bits = 0x0000;
    else if (!strcmp(text, "rd")) *bits = 0x0400;
    else if (!strcmp(text, "ru")) *bits = 0x0800;
    else if (!strcmp(text, "rz")) *bits = 0x0c00;
    else return 0;
    return 1;
}

static int parse_precision(const char *text, uint16_t *bits)
{
    if (!strcmp(text, "pc24")) *bits = 0x0000;
    else if (!strcmp(text, "pc53")) *bits = 0x0200;
    else if (!strcmp(text, "pc64")) *bits = 0x0300;
    else return 0;
    return 1;
}

/* Seed a sticky invalid-operation flag, then remove the temporary result. */
static void seed_ie(void)
{
    __asm__ volatile(
        "fldz\n\t"
        "fldz\n\t"
        "fdivp %%st, %%st(1)\n\t"
        "fwait\n\t"
        "fstp %%st(0)"
        :
        :
        : "st", "st(1)", "memory");
}

/* Seed a sticky precision flag with the masked, inexact value 1/3. */
static void seed_pe(void)
{
    const struct x80mem one = {
        {0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x80, 0xff, 0x3f}
    };
    const struct x80mem three = {
        {0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xc0, 0x00, 0x40}
    };
    __asm__ volatile(
        "fldt %[three]\n\t"
        "fldt %[one]\n\t"
        "fdivp %%st, %%st(1)\n\t"
        "fwait\n\t"
        "fstp %%st(0)"
        :
        : [one] "m" (one), [three] "m" (three)
        : "st", "st(1)", "memory");
}

static int seed_prior_flags(const char *name)
{
    if (!strcmp(name, "clear")) return 1;
    if (!strcmp(name, "ie")) {
        seed_ie();
        return 1;
    }
    if (!strcmp(name, "pe")) {
        seed_pe();
        return 1;
    }
    return 0;
}

static void load_stack(const struct x80mem *operand, int depth)
{
    struct x80mem sentinels[7];
    for (int index = 0; index < 7; index++) {
        /* 1 + (index+1)*2^-60: normal, exact, and readily distinguishable. */
        pack_x80(
            0x3fff,
            UINT64_C(0x8000000000000000) + ((uint64_t)index + 1) * 8,
            &sentinels[index]);
    }
    for (int index = depth - 2; index >= 0; index--)
        __asm__ volatile("fldt %0" :: "m" (sentinels[index]) : "st", "memory");
    __asm__ volatile("fldt %0" :: "m" (*operand) : "st", "memory");
}

static int execute_once(const char *instruction)
{
    if (!strcmp(instruction, "fsin")) {
        __asm__ volatile(
            "fsin\n\tfwait"
            :
            :
            : "st", "st(1)", "st(2)", "st(3)", "st(4)", "st(5)",
              "st(6)", "st(7)", "memory");
        return 1;
    }
    if (!strcmp(instruction, "fcos")) {
        __asm__ volatile(
            "fcos\n\tfwait"
            :
            :
            : "st", "st(1)", "st(2)", "st(3)", "st(4)", "st(5)",
              "st(6)", "st(7)", "memory");
        return 1;
    }
    if (!strcmp(instruction, "fsincos")) {
        __asm__ volatile(
            "fsincos\n\tfwait"
            :
            :
            : "st", "st(1)", "st(2)", "st(3)", "st(4)", "st(5)",
              "st(6)", "st(7)", "memory");
        return 1;
    }
    return 0;
}

static void print_area(const char *label, const struct fxsave_area *area)
{
    uint16_t cw = load_u16(area->bytes + 0);
    uint16_t sw = load_u16(area->bytes + 2);
    unsigned ftw = area->bytes[4];
    unsigned top = (sw >> 11) & 7;
    printf(" %s_CW=%04x %s_SW=%04x %s_TOP=%u %s_FTW=%02x",
           label, cw, label, sw, label, top, label, ftw);
    for (int index = 0; index < 8; index++) {
        const unsigned char *slot = area->bytes + 32 + 16 * index;
        uint64_t sig = load_u64(slot);
        uint16_t se = load_u16(slot + 8);
        printf(" %s_R%d=%04x:%016llx", label, index, se,
               (unsigned long long)sig);
    }
}

int main(void)
{
    char line[512];
    unsigned line_number = 0;
    while (fgets(line, sizeof line, stdin)) {
        char case_id[32], instruction[16], mode[8], precision[8], prior[8];
        unsigned masks, depth, se;
        unsigned long long sig;
        line_number++;
        if (line[0] == '#' || line[0] == '\n') continue;
        int fields = sscanf(
            line, "%31s %15s %7s %7s %x %u %7s %x %llx",
            case_id, instruction, mode, precision, &masks, &depth, prior,
            &se, &sig);
        if (fields != 9) {
            fprintf(stderr, "line %u: expected 9 fields\n", line_number);
            return 2;
        }
        if (masks != 0x3f) {
            fprintf(stderr,
                    "line %u: unmasked exceptions require a signal harness\n",
                    line_number);
            return 2;
        }
        if (depth < 1 || depth > 8 || se > 0xffff) {
            fprintf(stderr, "line %u: bad depth or operand\n", line_number);
            return 2;
        }
        uint16_t rc_bits, pc_bits;
        if (!parse_mode(mode, &rc_bits)
            || !parse_precision(precision, &pc_bits)) {
            fprintf(stderr, "line %u: bad mode or precision\n", line_number);
            return 2;
        }
        if (strcmp(instruction, "fsin") && strcmp(instruction, "fcos")
            && strcmp(instruction, "fsincos")) {
            fprintf(stderr, "line %u: bad instruction\n", line_number);
            return 2;
        }

        /* Bit 6 is the architecturally fixed control-word bit. */
        uint16_t cw = (uint16_t)(0x0040 | masks | rc_bits | pc_bits);
        struct x80mem operand;
        struct fxsave_area before, after;
        pack_x80((uint16_t)se, (uint64_t)sig, &operand);

        __asm__ volatile("fninit\n\tfldcw %0" :: "m" (cw) : "memory");
        if (!seed_prior_flags(prior)) {
            fprintf(stderr, "line %u: bad prior_flags\n", line_number);
            return 2;
        }
        load_stack(&operand, (int)depth);
        snapshot(&before);
        if (!execute_once(instruction)) return 2;
        snapshot(&after);

        printf("CASE=%s INSN=%s MODE=%s PC=%s MASKS=%02x DEPTH=%u PRIOR=%s",
               case_id, instruction, mode, precision, masks, depth, prior);
        print_area("B", &before);
        print_area("A", &after);
        putchar('\n');
    }
    __asm__ volatile("fninit" ::: "memory");
    return 0;
}
