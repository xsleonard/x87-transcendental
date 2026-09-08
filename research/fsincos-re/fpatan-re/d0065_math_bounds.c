/* Independent mathematical target construction, not silicon emulation.
 * Input: id, positive dyadic angle significand (hex), binary step, precision.
 * Output: exact dyadic lower/upper bounds for tan(angle), obtained using
 * MPFR directed rounding. No candidate coefficients or arithmetic are used.
 */
#include <stdio.h>
#include <mpfr.h>

int main(void)
{
    char line[256], id[64], significand[80], extra;
    long step;
    unsigned precision;
    mpz_t integer, lower_integer, upper_integer;
    mpfr_t angle, lower, upper;
    mpz_inits(integer, lower_integer, upper_integer, NULL);
    mpfr_inits2(192, angle, lower, upper, (mpfr_ptr)0);

    while (fgets(line, sizeof(line), stdin)) {
        if (sscanf(line, "%63s %79s %ld %u %c", id, significand,
                   &step, &precision, &extra) != 4)
            return 2;
        if (precision < 128 || precision > 49152 ||
            mpz_set_str(integer, significand, 16) || mpz_sgn(integer) <= 0)
            return 2;
        mpfr_set_prec(angle, precision);
        mpfr_set_prec(lower, precision);
        mpfr_set_prec(upper, precision);
        if (mpfr_set_z_2exp(angle, integer, step, MPFR_RNDN) != 0 ||
            mpfr_cmp_ui(angle, 1) >= 0)
            return 2;
        mpfr_tan(lower, angle, MPFR_RNDD);
        mpfr_tan(upper, angle, MPFR_RNDU);
        if (!mpfr_number_p(lower) || !mpfr_number_p(upper) ||
            mpfr_cmp_ui(lower, 0) <= 0 || mpfr_cmp(lower, upper) > 0)
            return 3;
        mpfr_exp_t lower_step = mpfr_get_z_2exp(lower_integer, lower);
        mpfr_exp_t upper_step = mpfr_get_z_2exp(upper_integer, upper);
        gmp_printf("%s %Zx %ld %Zx %ld\n", id, lower_integer,
                   (long)lower_step, upper_integer, (long)upper_step);
    }
    mpfr_clears(angle, lower, upper, (mpfr_ptr)0);
    mpz_clears(integer, lower_integer, upper_integer, NULL);
    return ferror(stdin) || fflush(stdout) ? 3 : 0;
}
