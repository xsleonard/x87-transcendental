/* H1646: fresh architectural-input transitions, one transcendental per row.
 *
 * Reuse the existing raw packing, snapshot and single-instruction primitives,
 * but restore explicit condition/sticky bits immediately before observation.
 * No software 1/3 seed, no timing/warmup/selftest, no unmasked exceptions.
 * Input:
 * case fsin|fcos rn|rd|ru|rz pc24|pc53|pc64 depth cc_hex flags_hex empty se sig
 * cc_hex uses SW positions 0x4700; flags_hex uses 0x007f, SF implies IE.
 * Each row still requires a frozen, fresh full architectural-input manifest.
 * This source alone authorizes no execution or recapture of prior tuples.
 */
#if !defined(__x86_64__)
#error "H1646 requires the authorized x86-64 research host"
#endif

#define main h1400_archived_main_not_used
#include "x87_state_capture.c"
#undef main

static void set_u16(unsigned char *bytes, uint16_t value)
{
    memcpy(bytes, &value, sizeof value);
}

static void restore_seed(const struct fxsave_area *area)
{
    /* FXSAVE contains the live SSE state too. Declare every restored register
     * clobbered so the compiler cannot keep temporaries across FXRSTOR. */
    __asm__ volatile("fxrstor %0" :: "m" (*area) :
        "memory", "st", "st(1)", "st(2)", "st(3)", "st(4)", "st(5)", "st(6)", "st(7)",
        "xmm0", "xmm1", "xmm2", "xmm3", "xmm4", "xmm5", "xmm6", "xmm7",
        "xmm8", "xmm9", "xmm10", "xmm11", "xmm12", "xmm13", "xmm14", "xmm15");
}

int main(void)
{
    char line[512];
    unsigned line_number = 0;
    while (fgets(line, sizeof line, stdin)) {
        char case_id[32], instruction[16], mode[8], precision[8], extra;
        unsigned depth, cc, flags, empty, se;
        unsigned long long sig;
        ++line_number;
        if (line[0] == '#' || line[0] == '\n') continue;
        int fields = sscanf(line, "%31s %15s %7s %7s %u %x %x %u %x %llx %c",
            case_id, instruction, mode, precision, &depth, &cc, &flags, &empty, &se, &sig, &extra);
        uint16_t rc_bits, pc_bits;
        if (fields != 10 || (strcmp(instruction, "fsin") && strcmp(instruction, "fcos"))
            || !parse_mode(mode, &rc_bits) || !parse_precision(precision, &pc_bits)
            || depth < 1 || depth > 8 || empty > 1 || se > 0xffff
            || (cc & ~0x4700u) || (flags & ~0x007fu) || ((flags & 0x40) && !(flags & 1))) {
            fprintf(stderr, "line %u: invalid masked transition input\n", line_number);
            return 2;
        }
        uint16_t cw = (uint16_t)(0x007f | rc_bits | pc_bits);
        struct x80mem operand;
        struct fxsave_area seed, before, after;
        pack_x80((uint16_t)se, (uint64_t)sig, &operand);
        __asm__ volatile("fninit\n\tfldcw %0" :: "m" (cw) : "memory");
        load_stack(&operand, (int)depth);
        snapshot(&seed);
        unsigned top = (load_u16(seed.bytes + 2) >> 11) & 7;
        uint16_t sw = (uint16_t)((top << 11) | cc | flags);
        set_u16(seed.bytes + 2, sw);
        if (empty) seed.bytes[4] &= (unsigned char)~(1u << top);
        restore_seed(&seed);
        snapshot(&before);
        /* Verify the requested prestate before executing any transcendental.
         * A mismatch aborts this campaign row; never retry it automatically. */
        if (load_u16(before.bytes) != cw || load_u16(before.bytes + 2) != sw
            || before.bytes[4] != seed.bytes[4]
            || memcmp(before.bytes + 32, seed.bytes + 32, 10)) {
            fprintf(stderr, "line %u: requested prestate was not restored\n", line_number);
            return 3;
        }
        if (!execute_once(instruction)) return 2;
        snapshot(&after);
        printf("CASE=%s INSN=%s MODE=%s PC=%s MASKS=3f DEPTH=%u CC=%04x FLAGS=%02x EMPTY=%u",
            case_id, instruction, mode, precision, depth, cc, flags, empty);
        print_area("B", &before);
        print_area("A", &after);
        putchar('\n');
    }
    __asm__ volatile("fninit" ::: "memory");
    return 0;
}
