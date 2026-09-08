/* Compare the h1135 hardware endpoint choice with correctly rounded cos(x).
 *
 * This is a falsifier for the simple hypothesis that the missing carry
 * selector merely chooses the mathematically nearer of the two exact
 * endpoint candidates.  It does not attempt to emulate the hardware.
 *
 * Build:
 *   cc -O2 experiments/h1156_lower_binade_mpfr_selector.c \
 *      -o /tmp/h1156_mpfr $(pkg-config --cflags --libs mpfr)
 * Run:
 *   /tmp/h1156_mpfr tmp/ledger33/current/h1136_3ffb_blind_score.tsv
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

static int parse_operand(const char *text, ext80_t *out)
{
    unsigned se;
    if (sscanf(text, "%x %" SCNx64, &se, &out->sig) != 2)
        return 0;
    out->se = (uint16_t)se;
    return 1;
}

static int parse_result(const char *text, ext80_t *out)
{
    unsigned se;
    if (sscanf(text, "%x:%" SCNx64, &se, &out->sig) != 2)
        return 0;
    out->se = (uint16_t)se;
    return 1;
}

static int equal(ext80_t a, ext80_t b)
{
    return a.se == b.se && a.sig == b.sig;
}

static void set_ext80(mpfr_t value, ext80_t source)
{
    mpfr_set_uj(value, source.sig, MPFR_RNDN);
    mpfr_mul_2si(value, value,
        (long)(source.se & 0x7fff) - 16383 - 63, MPFR_RNDN);
    if (source.se & 0x8000)
        mpfr_neg(value, value, MPFR_RNDN);
}

static mpfr_rnd_t rounding_mode(const char *text)
{
    if (strcmp(text, "rd") == 0)
        return MPFR_RNDD;
    if (strcmp(text, "ru") == 0)
        return MPFR_RNDU;
    return MPFR_RNDN;
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
    if (out.sig)
        out.se |= (uint16_t)(exponent + 63 + 16383);
    mpz_clear(integer);
    mpfr_clear(rounded);
    return out;
}

static size_t split_tabs(char *line, char **fields, size_t capacity)
{
    size_t count = 0;
    char *cursor = line;
    while (count < capacity) {
        fields[count++] = cursor;
        char *tab = strchr(cursor, '\t');
        if (!tab)
            break;
        *tab = '\0';
        cursor = tab + 1;
    }
    if (count && fields[count - 1][strlen(fields[count - 1]) - 1] == '\n')
        fields[count - 1][strlen(fields[count - 1]) - 1] = '\0';
    return count;
}

static int column(char **fields, size_t count, const char *name)
{
    for (size_t index = 0; index < count; index++)
        if (strcmp(fields[index], name) == 0)
            return (int)index;
    return -1;
}

int main(int argc, char **argv)
{
    if (argc != 2) {
        fprintf(stderr, "usage: %s score.tsv\n", argv[0]);
        return 2;
    }
    FILE *source = fopen(argv[1], "r");
    if (!source) {
        perror(argv[1]);
        return 2;
    }
    char *line = NULL;
    size_t line_size = 0;
    if (getline(&line, &line_size, source) < 0)
        return 2;
    char *fields[128];
    size_t count = split_tabs(line, fields, 128);
    int i_mode = column(fields, count, "mode");
    int i_op = column(fields, count, "op");
    int i_hw = column(fields, count, "hw");
    int i_base = column(fields, count, "base");
    int i_minus = column(fields, count, "force_minus2");
    int i_plus = column(fields, count, "force_plus1");
    if (i_mode < 0 || i_op < 0 || i_hw < 0 || i_base < 0
        || i_minus < 0 || i_plus < 0) {
        fprintf(stderr, "missing required column\n");
        return 2;
    }

    mpfr_t x, truth, value, error_minus, error_plus;
    mpfr_inits2(512, x, truth, value, error_minus, error_plus, (mpfr_ptr)0);
    unsigned long rows = 0, distinct = 0;
    unsigned long hw_cr = 0, base_cr = 0, minus_cr = 0, plus_cr = 0;
    unsigned long hw_nearer = 0, hw_farther = 0, equal_error = 0;
    unsigned long hw_minus = 0, hw_plus = 0, hw_other = 0;
    while (getline(&line, &line_size, source) >= 0) {
        count = split_tabs(line, fields, 128);
        if ((int)count <= i_plus)
            continue;
        ext80_t op, hw, base, minus, plus;
        if (!parse_operand(fields[i_op], &op)
            || !parse_result(fields[i_hw], &hw)
            || !parse_result(fields[i_base], &base)
            || !parse_result(fields[i_minus], &minus)
            || !parse_result(fields[i_plus], &plus)) {
            fprintf(stderr, "parse failure at row %lu\n", rows + 2);
            return 2;
        }
        rows++;
        set_ext80(x, op);
        mpfr_cos(truth, x, MPFR_RNDN);
        ext80_t cr = round_ext80(truth, rounding_mode(fields[i_mode]));
        hw_cr += equal(hw, cr);
        base_cr += equal(base, cr);
        minus_cr += equal(minus, cr);
        plus_cr += equal(plus, cr);
        if (equal(minus, plus))
            continue;
        distinct++;
        hw_minus += equal(hw, minus);
        hw_plus += equal(hw, plus);
        hw_other += !equal(hw, minus) && !equal(hw, plus);

        set_ext80(value, minus);
        mpfr_sub(error_minus, value, truth, MPFR_RNDN);
        mpfr_abs(error_minus, error_minus, MPFR_RNDN);
        set_ext80(value, plus);
        mpfr_sub(error_plus, value, truth, MPFR_RNDN);
        mpfr_abs(error_plus, error_plus, MPFR_RNDN);
        int comparison = mpfr_cmp(error_minus, error_plus);
        if (comparison == 0) {
            equal_error++;
        } else {
            int nearer_is_minus = comparison < 0;
            int hardware_is_nearer = (nearer_is_minus && equal(hw, minus))
                || (!nearer_is_minus && equal(hw, plus));
            hw_nearer += hardware_is_nearer;
            hw_farther += !hardware_is_nearer;
        }
    }
    printf("rows=%lu distinct_endpoints=%lu\n", rows, distinct);
    printf("correctly_rounded hw=%lu base=%lu minus2=%lu plus1=%lu\n",
           hw_cr, base_cr, minus_cr, plus_cr);
    printf("hardware_endpoint minus2=%lu plus1=%lu other=%lu\n",
           hw_minus, hw_plus, hw_other);
    printf("hardware_vs_nearer nearer=%lu farther=%lu equal_error=%lu\n",
           hw_nearer, hw_farther, equal_error);

    mpfr_clears(x, truth, value, error_minus, error_plus, (mpfr_ptr)0);
    free(line);
    fclose(source);
    return 0;
}
