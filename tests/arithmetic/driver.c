/* Private arithmetic protocol; never installed or exported by the library. */
#include "internal/finite.h"
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(void)
{
    char op[16], ah[65], bh[65];
    int bits, rc, ae, be;
    unsigned an, bn;
    while (scanf("%15s %d %d %u %d %64s %u %d %64s",
                 op, &bits, &rc, &an, &ae, ah, &bn, &be, bh) == 9) {
        fv a = x87t_internal_fhex(ah, ae, an), b = x87t_internal_fhex(bh, be, bn), v;
        if (!strcmp(op, "add")) v = x87t_internal_fadd(a, b, bits, (enum mode)rc);
        else if (!strcmp(op, "mul")) v = x87t_internal_fmul(a, b);
        else if (!strcmp(op, "round")) v = x87t_internal_fround(a, bits, (enum mode)rc);
        else if (!strcmp(op, "div")) v = x87t_internal_fdiv(a, b, bits, (enum mode)rc);
        else if (!strcmp(op, "scale")) v = x87t_internal_fscale(a, be);
        else if (!strcmp(op, "decode"))
            v = x87t_internal_fdecode((raw80){(uint16_t)ae, strtoull(ah, NULL, 16)});
        else if (!strcmp(op, "cmp")) {
            printf("I %d\n", x87t_internal_fcmp(a, b));
            continue;
        } else if (!strcmp(op, "ratio")) {
            printf("I %d\n", x87t_internal_fratio_exp(a, b));
            continue;
        } else if (!strcmp(op, "floor")) {
            printf("I %" PRIu64 "\n", x87t_internal_ffloor(a));
            continue;
        } else if (!strcmp(op, "encode") || !strcmp(op, "sum")) {
            int c1, tiny = 0;
            raw80 r = !strcmp(op, "encode") ? x87t_internal_fencode(a, (enum mode)rc, &c1) :
                x87t_internal_fencode_sum(a, b, (enum mode)rc, (unsigned)bits, &c1, &tiny);
            printf("R %04x %016" PRIx64 " %d %d\n", r.se, r.sig, c1, tiny);
            continue;
        } else return 2;
        printf("V %u %d %016" PRIx64 "%016" PRIx64 "%016" PRIx64 "%016" PRIx64 "\n",
               v.negative, v.exponent, v.word[3], v.word[2], v.word[1], v.word[0]);
    }
    return ferror(stdin) || fflush(stdout) ? 3 : 0;
}
