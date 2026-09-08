/* Independent MPFR check of rational Taylor enclosures, LOCAL ONLY.
 * Input: x lower upper, each a GMP rational. The generated bank is positive.
 * Directed input conversion followed by directed atan gives an independent
 * enclosure. Require it to lie inside the claimed rational Taylor bounds.
 * This is not an FPATAN implementation and executes no native x87 capture.
 */
#include <stdio.h>
#include <gmp.h>
#include <mpfr.h>

int main(void)
{
    mpq_t x, lower, upper;
    mpq_inits(x, lower, upper, NULL);
    mpfr_t xl, xu, al, au;
    mpfr_inits2(768, xl, xu, al, au, (mpfr_ptr)0);
    unsigned long count = 0;
    int fields;
    while ((fields = gmp_fscanf(stdin, "%Qd %Qd %Qd", x, lower, upper)) == 3) {
        mpq_canonicalize(x);
        mpq_canonicalize(lower);
        mpq_canonicalize(upper);
        if (mpq_sgn(x) <= 0 || mpq_cmp(lower, upper) >= 0) return 2;
        mpfr_set_q(xl, x, MPFR_RNDD);
        mpfr_set_q(xu, x, MPFR_RNDU);
        mpfr_atan(al, xl, MPFR_RNDD);
        mpfr_atan(au, xu, MPFR_RNDU);
        if (mpfr_cmp_q(al, lower) < 0 || mpfr_cmp_q(au, upper) > 0) {
            fprintf(stderr, "Enclosure failure at record %lu\n", count);
            return 3;
        }
        count++;
    }
    if (fields != EOF || ferror(stdin)) return 4;
    printf("PASS %lu rational atan enclosures at 768 bits\n", count);
    mpq_clears(x, lower, upper, NULL);
    mpfr_clears(xl, xu, al, au, (mpfr_ptr)0);
    return fflush(stdout) ? 5 : 0;
}
