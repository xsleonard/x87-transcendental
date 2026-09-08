/* H1700 software-only tests of the existing exact-reduction C helpers.
 * Numerical fields only: wv_from_rc does not initialize legacy rh metadata.
 * No x87 capture and no change to the production implementation. */
#define main h1700_unused_emulator_main
#include "../src/fsincos_skylake.c"
#undef main
#include <assert.h>

_Static_assert(sizeof(unsigned) == 4, "The current quadrant casts use unsigned32");

int main(void)
{
    unsigned sign, phase;
    int exponent;
    unsigned long long significand;
    while (scanf("%u %d %llx %u", &sign, &exponent, &significand, &phase) == 4) {
        assert(sign <= 1 && phase <= 1 && exponent >= -1 && exponent <= 62);
        assert(significand >> 63);
        sf_t x = { SF_FIN, (uint8_t)sign, exponent, (uint64_t)significand };
        uint64_t quotient = fsincos_compat_reduce_n_exact(x.sig, x.exp);
        sf_t r, c;
        sky_reduce_rc(&x, quotient, &r, &c);
        assert(r.cls == SF_FIN && c.cls == SF_FIN && r.sig);
        wv_t w = wv_from_rc(&r, &c);
        int64_t n = (sign ? -(int64_t)quotient : (int64_t)quotient) + phase;
        printf("%llu %u %d %016llx %u %d %016llx %u %d %016llx%016llx %lld %u %u\n",
            (unsigned long long)quotient, r.sign, r.exp, (unsigned long long)r.sig,
            c.sign, c.exp, (unsigned long long)c.sig, w.sign, w.e2,
            (unsigned long long)(w.sig >> 64), (unsigned long long)w.sig,
            (long long)n, (unsigned)n & 1u, ((unsigned)n >> 1) & 1u);
    }
    return feof(stdin) ? 0 : 2;
}
