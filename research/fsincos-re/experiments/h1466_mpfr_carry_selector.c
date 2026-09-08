/* h1466: classify the two forced R59 endpoints against MPFR truth.
 *
 * Input is tab-separated, without a header:
 *   corpus mode op_se op_sig hw_se hw_sig c0_se c0_sig c1_se c1_sig
 *
 * Output appends the required hardware carry, the endpoint nearest the
 * unrounded transcendental value, and the endpoint equal to the correctly
 * rounded binary80 result.  A selector is -1 when neither endpoint is
 * selected (or, for nearest, their errors compare equal).
 */
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <gmp.h>
#include <mpfr.h>

typedef struct {
    uint16_t se;
    uint64_t sig;
} ext80_t;

static int same_ext80(ext80_t a, ext80_t b)
{
    return a.se == b.se && a.sig == b.sig;
}

static void set_ext80(mpfr_t value, ext80_t source)
{
    mpfr_set_uj(value, source.sig, MPFR_RNDN);
    if (source.sig != 0) {
        mpfr_mul_2si(value, value,
            (long)(source.se & 0x7fff) - 16383 - 63, MPFR_RNDN);
    }
    if (source.se & 0x8000)
        mpfr_neg(value, value, MPFR_RNDN);
}

static mpfr_rnd_t parse_mode(const char *mode)
{
    if (strcmp(mode, "rd") == 0)
        return MPFR_RNDD;
    if (strcmp(mode, "ru") == 0)
        return MPFR_RNDU;
    if (strcmp(mode, "rz") == 0)
        return MPFR_RNDZ;
    if (strcmp(mode, "rn") == 0)
        return MPFR_RNDN;
    fprintf(stderr, "bad mode: %s\n", mode);
    exit(2);
}

static ext80_t round_ext80(const mpfr_t exact, mpfr_rnd_t mode)
{
    mpfr_t rounded;
    mpz_t integer;
    mpfr_exp_t exponent;
    ext80_t out = { 0, 0 };
    mpfr_init2(rounded, 64);
    mpz_init(integer);
    mpfr_set(rounded, exact, mode);
    exponent = mpfr_get_z_2exp(integer, rounded);
    if (mpz_sgn(integer) < 0) {
        out.se = 0x8000;
        mpz_neg(integer, integer);
    }
    out.sig = mpz_get_ui(integer);
    if (out.sig != 0)
        out.se |= (uint16_t)(exponent + 63 + 16383);
    mpz_clear(integer);
    mpfr_clear(rounded);
    return out;
}

int main(int argc, char **argv)
{
    mpfr_prec_t precision = 768;
    if (argc == 3 && strcmp(argv[1], "--precision") == 0) {
        char *end = NULL;
        unsigned long parsed = strtoul(argv[2], &end, 10);
        if (!end || *end || parsed < 128 || parsed > 16384) {
            fprintf(stderr, "bad precision\n");
            return 2;
        }
        precision = (mpfr_prec_t)parsed;
    } else if (argc != 1) {
        fprintf(stderr, "usage: %s [--precision bits]\n", argv[0]);
        return 2;
    }

    mpfr_t x, truth, v0, v1, e0, e1;
    mpfr_inits2(precision, x, truth, v0, v1, e0, e1, (mpfr_ptr)0);

    char corpus[32], mode[8];
    unsigned op_se, hw_se, c0_se, c1_se;
    uint64_t op_sig, hw_sig, c0_sig, c1_sig;
    unsigned long row = 0;
    while (scanf("%31s\t%7s\t%x\t%" SCNx64
                 "\t%x\t%" SCNx64 "\t%x\t%" SCNx64
                 "\t%x\t%" SCNx64,
                 corpus, mode, &op_se, &op_sig, &hw_se, &hw_sig,
                 &c0_se, &c0_sig, &c1_se, &c1_sig) == 10) {
        ext80_t op = { (uint16_t)op_se, op_sig };
        ext80_t hardware = { (uint16_t)hw_se, hw_sig };
        ext80_t endpoint0 = { (uint16_t)c0_se, c0_sig };
        ext80_t endpoint1 = { (uint16_t)c1_se, c1_sig };
        int required = same_ext80(hardware, endpoint0) ? 0
            : same_ext80(hardware, endpoint1) ? 1 : -1;

        set_ext80(x, op);
        mpfr_cos(truth, x, MPFR_RNDN);
        set_ext80(v0, endpoint0);
        set_ext80(v1, endpoint1);
        mpfr_sub(e0, v0, truth, MPFR_RNDN);
        mpfr_abs(e0, e0, MPFR_RNDN);
        mpfr_sub(e1, v1, truth, MPFR_RNDN);
        mpfr_abs(e1, e1, MPFR_RNDN);
        int comparison = mpfr_cmp(e0, e1);
        int nearest = comparison < 0 ? 0 : comparison > 0 ? 1 : -1;

        ext80_t correctly_rounded = round_ext80(
            truth, parse_mode(mode));
        int cr = same_ext80(correctly_rounded, endpoint0) ? 0
            : same_ext80(correctly_rounded, endpoint1) ? 1 : -1;

        printf("%s\t%s\t%04x\t%016" PRIx64
               "\t%04x\t%016" PRIx64
               "\t%04x\t%016" PRIx64
               "\t%04x\t%016" PRIx64
               "\t%d\t%d\t%d\t%04x\t%016" PRIx64 "\n",
               corpus, mode, op.se, op.sig,
               hardware.se, hardware.sig,
               endpoint0.se, endpoint0.sig,
               endpoint1.se, endpoint1.sig,
               required, nearest, cr,
               correctly_rounded.se, correctly_rounded.sig);
        row++;
    }
    if (ferror(stdin)) {
        perror("stdin");
        return 3;
    }
    if (!feof(stdin)) {
        fprintf(stderr, "parse failure after row %lu\n", row);
        return 4;
    }
    fprintf(stderr, "precision=%lu rows=%lu\n",
            (unsigned long)precision, row);
    mpfr_clears(x, truth, v0, v1, e0, e1, (mpfr_ptr)0);
    return 0;
}
