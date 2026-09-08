/* h1004: compare every R95 union miss with correctly rounded MPFR truth.
 *
 * Build:
 *   cc -O2 h1004_mpfr_union.c -o h1004_mpfr_union \
 *      $(pkg-config --cflags --libs mpfr)
 * Run in the h991 scratch directory so h989_union_legs.tsv is visible.
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

static int parse_ext80(const char *text, ext80_t *out)
{
    unsigned se;
    uint64_t sig;
    if (sscanf(text, "%x %" SCNx64, &se, &sig) != 2)
        return 0;
    out->se = (uint16_t)se;
    out->sig = sig;
    return 1;
}

static int same_ext80(ext80_t a, ext80_t b)
{
    return a.se == b.se && a.sig == b.sig;
}

static mpfr_rnd_t parse_mode(const char *mode)
{
    if (strcmp(mode, "rd") == 0)
        return MPFR_RNDD;
    if (strcmp(mode, "ru") == 0)
        return MPFR_RNDU;
    if (strcmp(mode, "rz") == 0)
        return MPFR_RNDZ;
    return MPFR_RNDN;
}

static void set_ext80(mpfr_t value, ext80_t source)
{
    mpfr_set_uj(value, source.sig, MPFR_RNDN);
    mpfr_mul_2si(value, value,
        (long)(source.se & 0x7fff) - 16383 - 63, MPFR_RNDN);
    if (source.se & 0x8000)
        mpfr_neg(value, value, MPFR_RNDN);
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

static int split_tabs(char *line, char **fields, int capacity)
{
    int count = 0;
    char *save = NULL;
    for (char *token = strtok_r(line, "\t\n", &save);
         token != NULL && count < capacity;
         token = strtok_r(NULL, "\t\n", &save))
        fields[count++] = token;
    return count;
}

int main(void)
{
    int verbose = getenv("H1004_VERBOSE") != NULL;
    FILE *input = fopen("h989_union_legs.tsv", "r");
    if (!input) {
        perror("h989_union_legs.tsv");
        return 1;
    }
    char *line = NULL;
    size_t size = 0;
    ssize_t length;
    unsigned long total = 0, misses = 0;
    unsigned long hardware_cr = 0, model_cr = 0, neither = 0;
    unsigned long hardware_closer = 0, model_closer = 0, equal_error = 0;
    unsigned long by_mode[4][5] = {{0}};
    const char *mode_names[] = {"rn", "rd", "ru", "rz"};

    mpfr_t x, truth, hardware_value, model_value, hardware_error, model_error;
    mpfr_inits2(384, x, truth, hardware_value, model_value,
                hardware_error, model_error, (mpfr_ptr)0);

    getline(&line, &size, input); /* header */
    while ((length = getline(&line, &size, input)) >= 0) {
        char *fields[8];
        int count = split_tabs(line, fields, 8);
        if (count < 6)
            continue;
        const char *insn = fields[0];
        const char *mode_text = fields[2];
        ext80_t operand, hardware, model;
        if (!parse_ext80(fields[1], &operand)
            || !parse_ext80(fields[3], &hardware)
            || !parse_ext80(fields[5], &model)) {
            fprintf(stderr, "parse failure on row %lu\n", total + 1);
            return 2;
        }
        int mode_index = 0;
        while (mode_index < 4
               && strcmp(mode_text, mode_names[mode_index]) != 0)
            mode_index++;
        if (mode_index == 4)
            return 3;

        total++;
        if (same_ext80(hardware, model))
            continue;
        misses++;
        by_mode[mode_index][0]++;
        set_ext80(x, operand);
        if (strcmp(insn, "sin") == 0)
            mpfr_sin(truth, x, MPFR_RNDN);
        else
            mpfr_cos(truth, x, MPFR_RNDN);
        ext80_t correctly_rounded = round_ext80(
            truth, parse_mode(mode_text));
        int hcr = same_ext80(hardware, correctly_rounded);
        int mcr = same_ext80(model, correctly_rounded);
        if (verbose)
            printf("ROW %s %s %04x %016" PRIx64
                   " hw=%04x:%016" PRIx64
                   " model=%04x:%016" PRIx64
                   " cr=%04x:%016" PRIx64 " class=%s\n",
                   insn, mode_text, operand.se, operand.sig,
                   hardware.se, hardware.sig, model.se, model.sig,
                   correctly_rounded.se, correctly_rounded.sig,
                   hcr ? "HW_CR" : (mcr ? "MODEL_CR" : "NEITHER"));
        if (hcr) {
            hardware_cr++;
            by_mode[mode_index][1]++;
        }
        if (mcr) {
            model_cr++;
            by_mode[mode_index][2]++;
        }
        if (!hcr && !mcr) {
            neither++;
            by_mode[mode_index][3]++;
        }

        set_ext80(hardware_value, hardware);
        set_ext80(model_value, model);
        mpfr_sub(hardware_error, hardware_value, truth, MPFR_RNDN);
        mpfr_abs(hardware_error, hardware_error, MPFR_RNDN);
        mpfr_sub(model_error, model_value, truth, MPFR_RNDN);
        mpfr_abs(model_error, model_error, MPFR_RNDN);
        int comparison = mpfr_cmp(hardware_error, model_error);
        if (comparison < 0) {
            hardware_closer++;
            by_mode[mode_index][4]++;
        } else if (comparison > 0) {
            model_closer++;
        } else {
            equal_error++;
        }
    }

    printf("union legs %lu, R95 misses %lu\n", total, misses);
    printf("correctly rounded among misses: hardware %lu, R95 %lu, "
           "neither %lu\n", hardware_cr, model_cr, neither);
    printf("closer to MPFR truth: hardware %lu, R95 %lu, ties %lu\n",
           hardware_closer, model_closer, equal_error);
    for (int index = 0; index < 4; index++)
        printf("  %s misses %lu hw-CR %lu model-CR %lu neither %lu "
               "hw-closer %lu\n", mode_names[index],
               by_mode[index][0], by_mode[index][1], by_mode[index][2],
               by_mode[index][3], by_mode[index][4]);

    mpfr_clears(x, truth, hardware_value, model_value,
                hardware_error, model_error, (mpfr_ptr)0);
    free(line);
    fclose(input);
    return 0;
}
