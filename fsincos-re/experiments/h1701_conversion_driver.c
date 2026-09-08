/* H1701 software-only conversion and actual isolated tiny-entry checks.
 * Direct decoder calls intentionally include invalid encodings to expose
 * why callers must retain the existing raw invalid-encoding guard.
 * No hardware capture, production edit or default promotion. */
#define main h1701_unused_emulator_main
#include "../src/fsincos_skylake.c"
#undef main
#include <assert.h>
static unsigned long long h1630_row;
#include "h1638_tiny_closed_form.h"

int main(void)
{
    char operation;
    unsigned sign, ef, cls, phase, rc;
    int exponent;
    unsigned long long significand, row = 0;
    assert(g_round63_invalid_encoding && !g_round84_errata);
    while (scanf(" %c", &operation) == 1) {
        if (operation == 'D') {
            assert(scanf("%u %x %llx", &sign, &ef, &significand) == 3);
            assert(sign <= 1 && ef <= 0x7fff);
            x80_t in = { (uint16_t)((sign << 15) | ef), (uint64_t)significand };
            sf_t value = sf_from_parts(sign, ef, significand);
            x80_t out;
            sf_to_x87(&value, &out.se, &out.sig);
            printf("D %d %u %u %d %016llx %04x %016llx\n",
                x87_invalid_encoding(in), value.cls, value.sign, value.exp,
                (unsigned long long)value.sig, out.se, (unsigned long long)out.sig);
        } else if (operation == 'S') {
            assert(scanf("%u %u %d %llx", &cls, &sign, &exponent, &significand) == 4);
            assert(cls <= SF_NAN && sign <= 1 && exponent >= -20000 && exponent <= 16383);
            sf_t value = { (uint8_t)cls, (uint8_t)sign, exponent, (uint64_t)significand };
            x80_t out;
            sf_to_x87(&value, &out.se, &out.sig);
            printf("S %04x %016llx\n", out.se, (unsigned long long)out.sig);
        } else if (operation == 'B') {
            assert(scanf("%u %u %u %x %llx", &phase, &rc, &sign, &ef, &significand) == 5);
            assert(phase <= 1 && rc <= 3 && sign <= 1 && ef <= 0x7fff);
            x80_t in = { (uint16_t)((sign << 15) | ef), (uint64_t)significand };
            x80_t original = in, out = { 0, 0 };
            h1630_row = row + 1;
            int hit = h1638_tiny_entry(in, phase, (sf_rc_t)rc, &out);
            /* The original E/J/class bits belong to the caller, not sf_t. */
            assert(in.se == original.se && in.sig == original.sig);
            printf("B %d %04x %016llx\n", hit, out.se, (unsigned long long)out.sig);
        } else {
            return 2;
        }
        ++row;
    }
    return feof(stdin) ? 0 : 2;
}
