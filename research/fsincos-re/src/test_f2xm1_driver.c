/* Offline adapter for the F2XM1 numerical program; no x87 execution.
 * The public unary API returns the value only. For this test, derive C1
 * from the directed internal results: it records a magnitude increment
 * at the final rounding step, including the raw80 subnormal spacing.
 * PC is accepted to replay saved tuples; F2XM1's numerical result does
 * not depend on the x87 precision-control field.
 */
#define main historical_trig_cli_main
#ifndef F2XM1_SOURCE
#define F2XM1_SOURCE "fsincos_skylake.c"
#endif
#include F2XM1_SOURCE
#undef main

static int same_carrier(sf_t a, sf_t b)
{
    return a.cls == b.cls && a.sign == b.sign && a.exp == b.exp && a.sig == b.sig;
}

int main(void)
{
    char line[256], id[64], rc_name[4], extra;
    unsigned pc, se;
    unsigned long long sig;
    while (fgets(line, sizeof(line), stdin)) {
        if (sscanf(line, "%63s %3s %u %x %llx %c", id, rc_name, &pc, &se, &sig, &extra) != 5)
            return 2;
        unsigned mode;
        if (!strcmp(rc_name, "rn")) mode = SF_RN;
        else if (!strcmp(rc_name, "rd")) mode = SF_RD;
        else if (!strcmp(rc_name, "ru")) mode = SF_RU;
        else if (!strcmp(rc_name, "rz")) mode = SF_RZ;
        else return 2;
        if (se > 65535 || (pc != 24 && pc != 53 && pc != 64)) return 2;
        sf_t input = sf_from_parts(se >> 15, se & 0x7fff, sig);
        sf_t result = f2xm1_core(input, mode);
        sf_t down = f2xm1_core(input, SF_RD), up = f2xm1_core(input, SF_RU);
        int c1 = result.cls == SF_FIN && !same_carrier(down, up)
            && same_carrier(result, result.sign ? down : up);
        x80_t output;
        sf_to_x87(&result, &output.se, &output.sig);
        printf("%s %04x %016llx %d\n", id, output.se, (unsigned long long)output.sig, c1);
    }
    return ferror(stdin) || fflush(stdout) ? 3 : 0;
}
