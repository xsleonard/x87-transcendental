/* Public FPTAN observation program. Exactly one FPTAN per admitted line.
 * No model, timing repetitions, warmups, or transcendental selftest.
 * A durable external guard reserves the complete input before execution.
 * Save status before stores; C2 changes whether FPTAN pushed a stack value.
 */
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <cpuid.h>

typedef struct { unsigned char bytes[10]; } raw80;

static raw80 pack(uint16_t se, uint64_t sig)
{
    raw80 value;
    memcpy(value.bytes, &sig, 8);
    memcpy(value.bytes + 8, &se, 2);
    return value;
}

int main(int argc, char **argv)
{
    if (argc == 2 && !strcmp(argv[1], "--identity")) {
        unsigned a, b, c, d;
        __cpuid(1, a, b, c, d);
        printf("CPUID1 %08x %08x %08x %08x\n", a, b, c, d);
        return 0;
    }
    if (argc != 1) return 2;
    char line[256], id[64], rc[4], extra;
    unsigned pc, se;
    unsigned long long sig;
    unsigned long count = 0;
    while (fgets(line, sizeof(line), stdin)) {
        if (sscanf(line, "%63s %3s %u %x %llx %c", id, rc, &pc, &se, &sig, &extra) != 5 || se > 65535)
            return 2;
        uint16_t cw = 0x7f, actual, before, after, end;
        if (!strcmp(rc, "rd")) cw |= 0x400;
        else if (!strcmp(rc, "ru")) cw |= 0x800;
        else if (!strcmp(rc, "rz")) cw |= 0xc00;
        else if (strcmp(rc, "rn")) return 2;
        if (pc == 64) cw |= 0x300;
        else if (pc == 53) cw |= 0x200;
        else if (pc != 24) return 2;
        raw80 input = pack((uint16_t)se, sig), tangent, pushed = {{0}};
        __asm__ volatile(
            "fninit\n\tfldcw %[cw]\n\tfldt %[in]\n\tfnstsw %[before]\n\t"
            "fptan\n\tfwait\n\tfnstsw %[after]\n\tfnstcw %[actual]"
            : [before] "=m" (before), [after] "=m" (after), [actual] "=m" (actual)
            : [cw] "m" (cw), [in] "m" (input)
            : "st", "st(1)", "memory");
        if (after & 0x400) {
            __asm__ volatile("fstpt %[tan]\n\tfnstsw %[end]"
                : [tan] "=m" (tangent), [end] "=m" (end) : : "st", "memory");
        } else {
            __asm__ volatile("fstpt %[push]\n\tfstpt %[tan]\n\tfnstsw %[end]"
                : [push] "=m" (pushed), [tan] "=m" (tangent), [end] "=m" (end)
                : : "st", "st(1)", "memory");
        }
        uint16_t ts, ps;
        uint64_t tm, pm;
        memcpy(&tm, tangent.bytes, 8); memcpy(&ts, tangent.bytes + 8, 2);
        memcpy(&pm, pushed.bytes, 8); memcpy(&ps, pushed.bytes + 8, 2);
        printf("%s %s %u %04x %016llx %04x %04x %04x %04x %04x %016llx %04x %016llx\n",
            id, rc, pc, se, sig, actual, before, after, end,
            ts, (unsigned long long)tm, ps, (unsigned long long)pm);
        count++;
        if (ferror(stdout)) return 3;
    }
    if (ferror(stdin) || fflush(stdout)) return 3;
    fprintf(stderr, "COMPLETE %lu\n", count);
    return 0;
}
