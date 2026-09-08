/* Model-independent MPFR bounds for atan(target) and mathematical pi.
 * Used only to select inputs, never as a bit-exact silicon specification.
 */
#include <stdio.h>
#include <string.h>
#include <mpfr.h>

int main(void)
{
    char line[256], id[64], kind[8], hex[80], extra;
    long step;
    unsigned precision;
    mpfr_t value, lo, hi;
    mpz_t integer, lm, hm;
    mpfr_inits2(768, value, lo, hi, (mpfr_ptr)0);
    mpz_inits(integer, lm, hm, NULL);
    while (fgets(line, sizeof(line), stdin)) {
        if (sscanf(line, "%63s %7s %79s %ld %u %c", id, kind, hex, &step, &precision, &extra) != 5)
            return 2;
        if (precision < 128 || precision > 4096) return 2;
        mpfr_set_prec(value, precision);
        mpfr_set_prec(lo, precision);
        mpfr_set_prec(hi, precision);
        if (!strcmp(kind, "pi")) {
            mpfr_const_pi(lo, MPFR_RNDD);
            mpfr_const_pi(hi, MPFR_RNDU);
        } else if (!strcmp(kind, "atan")) {
            if (mpz_set_str(integer, hex, 16) || mpz_sgn(integer) < 0 ||
                mpfr_set_z_2exp(value, integer, step, MPFR_RNDN)) return 2;
            mpfr_atan(lo, value, MPFR_RNDD);
            mpfr_atan(hi, value, MPFR_RNDU);
        } else return 2;
        mpfr_exp_t ls = mpfr_get_z_2exp(lm, lo), hs = mpfr_get_z_2exp(hm, hi);
        gmp_printf("%s %Zx %ld %Zx %ld\n", id, lm, (long)ls, hm, (long)hs);
    }
    mpfr_clears(value, lo, hi, (mpfr_ptr)0);
    mpz_clears(integer, lm, hm, NULL);
    return ferror(stdin) || fflush(stdout) ? 3 : 0;
}
