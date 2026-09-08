/* LOCAL ONLY: use the current authoritative FPTAN implementation unchanged.
 * This adapter selects the instruction, not a numerical policy. No source
 * or predictions from this program are copied to a capture host.
 * C1 is obtained from the same directed-output interval method used by the
 * historical sibling verifier. Exception-latch predictions are not added.
 */
#define main historical_trig_cli_main
#include "../src/fsincos_skylake.c"
#undef main

static int equal(x80_t a, x80_t b)
{
    return a.se == b.se && a.sig == b.sig;
}

int main(int argc, char **argv)
{
    if (argc == 2 && !strcmp(argv[1], "--selftest")) return selftest();
    if (argc != 1) return 2;
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
        if (pc != 24 && pc != 53 && pc != 64) return 2;
        x80_t input = {(uint16_t)se, (uint64_t)sig}, outputs[4];
        fsincos_status_t statuses[4];
        for (unsigned m = 0; m < 4; m++) {
            outputs[m] = input;
            statuses[m] = fptan_ref(input, &outputs[m], (sf_rc_t)m);
            if (statuses[m] != FSINCOS_OK && statuses[m] != FSINCOS_C2) return 3;
        }
        int c2 = statuses[mode] == FSINCOS_C2;
        int c1 = 0;
        if (!c2 && !equal(outputs[SF_RD], outputs[SF_RU])) {
            x80_t away = outputs[mode].se >> 15 ? outputs[SF_RD] : outputs[SF_RU];
            x80_t toward = outputs[mode].se >> 15 ? outputs[SF_RU] : outputs[SF_RD];
            if (!equal(outputs[mode], away) && !equal(outputs[mode], toward)) return 3;
            c1 = equal(outputs[mode], away);
        }
        x80_t pushed = {0, 0};
        if (!c2) pushed = (outputs[mode].se & 0x7fff) == 0x7fff
            ? outputs[mode] : (x80_t){0x3fff, UINT64_C(0x8000000000000000)};
        printf("%s %04x %016llx %04x %016llx %d %d\n", id,
            outputs[mode].se, (unsigned long long)outputs[mode].sig,
            pushed.se, (unsigned long long)pushed.sig, c2, c1);
    }
    return ferror(stdin) || fflush(stdout) ? 3 : 0;
}
