/* Software values use integer significands and an unbounded exponent.
 * Extracted from ia64_sf.h; no host floating-point environment is used. */
/* The exponent can exceed raw80 limits, but must fit int32_t. A finite nonzero
 * sf_t has a normalized 64-bit significand. These routines convert the
 * representation; arithmetic helpers elsewhere perform the rounding
 * requested by guest RC. */
#include "internal/numeric.h"

const x80_t x87t_internal_X87_INDEFINITE = {0xffff, UINT64_C(0xc000000000000000)};

sf_t x87t_internal_sf_zero(int sign)
{
    sf_t z;
    z.cls = SF_FIN;
    z.sign = (uint8_t)sign;
    z.exp = 0;
    z.sig = 0;
    return z;
}

sf_t x87t_internal_sf_qnan(void)
{
    sf_t n;
    n.cls = SF_NAN;
    n.sign = 1;
    n.exp = 0;
    n.sig = 0xC000000000000000ull;
    return n;
}

int x87t_internal_sf_is_zero(const sf_t *a)
{
    return a->cls == SF_FIN && a->sig == 0;
}

/* Construct from x87/IA-64 memory format pieces: 15-bit biased exponent
 * field (bias 0x3FFF... note: EXTENDED format bias 16383) + 64-bit
 * significand with explicit integer bit.  Used for table constants and I/O.
 * A biased field of 0 with nonzero sig = pseudo-denormal/denormal input:
 * normalize (fnorm semantics; wre absorbs the range). */
sf_t x87t_internal_sf_from_parts(int sign, uint32_t expfield, uint64_t sig)
{
    /* Requires sign=0 or 1 and a 15-bit expfield. The caller must handle
     * unsupported encodings first. A pseudo-denormal has the same value as
     * exponent field 1. Keep its original classification in the caller so
     * the caller can set DE; normalization loses that distinction. */
    sf_t r;
    r.cls = SF_FIN;
    r.sign = (uint8_t)sign;
    if (sig == 0)
        return x87t_internal_sf_zero(sign);
    if (expfield == 0x7FFF) {
        if (sig == 0x8000000000000000ull) {
            r.cls = SF_INF;
            r.exp = 0;
            r.sig = sig;
            return r;
        }
        r.cls = SF_NAN;
        r.exp = 0;
        r.sig = sig;
        return r;
    }
    r.exp = (int32_t)expfield - 16383;
    if (expfield == 0)
        r.exp = 1 - 16383; /* denormal: exp field 0 means 2^-16382 */
    r.sig = sig;
    while (!(r.sig & 0x8000000000000000ull)) {
        r.sig <<= 1;
        r.exp--;
    } /* fnorm */
    return r;
}

/* Emit to x87 80-bit memory format (sign:1, expfield:15, sig:64).
 * Values out of double-extended range would need denormalization; the
 * algorithm's outputs are in [-1-ulp, 1+ulp] or sin(x)~x for normal x, so
 * only denormal-range results (sin of denormal x) need the shift path. */
/* This helper now also serves instructions other than trig. Pass a value
 * that has already been rounded. The subnormal shift simply discards bits:
 * it does not use RC, save guard or sticky bits, or set C1, UE or PE.
 * Finite results must fit the raw80 range; NaNs and infinities use their
 * own branches. Round subnormal results to multiples of 2^-16445 before
 * calling, as the F2XM1 tiny helper does. Rounding first to 64 significant
 * bits and then discarding bits here can give the wrong result and C1. */
void x87t_internal_sf_to_x87(const sf_t *a, uint16_t *se, uint64_t *sig)
{
    if (a->cls == SF_NAN) {
        *se = (uint16_t)(0x7FFF | (a->sign << 15));
        *sig = a->sig;
        return;
    }
    if (a->cls == SF_INF) {
        *se = (uint16_t)(0x7FFF | (a->sign << 15));
        *sig = 0x8000000000000000ull;
        return;
    }
    if (a->sig == 0) {
        *se = (uint16_t)(a->sign << 15);
        *sig = 0;
        return;
    }
    int32_t ef = a->exp + 16383;
    uint64_t s = a->sig;
    if (ef <= 0) { /* denormal on store */
        int32_t sh = 1 - ef;
        s = (sh >= 64) ? 0 : s >> sh; /* truncation; fine for I/O of tiny sin results */
        ef = 0;
    }
    *se = (uint16_t)(((uint32_t)a->sign << 15) | (uint32_t)ef);
    *sig = s;
}

/* negate / abs (fmerge idioms) */
sf_t x87t_internal_sf_neg(const sf_t *a)
{
    sf_t r = *a;
    r.sign ^= 1;
    return r;
}

sf_t x87t_internal_sf_abs(const sf_t *a)
{
    sf_t r = *a;
    r.sign = 0;
    return r;
}

/* magnitude compare of finite values: |a| < |b| */
int x87t_internal_sf_lt_abs(const sf_t *a, const sf_t *b)
{
    if (x87t_internal_sf_is_zero(a))
        return !x87t_internal_sf_is_zero(b);
    if (x87t_internal_sf_is_zero(b))
        return 0;
    if (a->exp != b->exp)
        return a->exp < b->exp;
    return a->sig < b->sig;
}

/* signed compare a < b (finite) */
int x87t_internal_sf_lt(const sf_t *a, const sf_t *b)
{
    int az = x87t_internal_sf_is_zero(a), bz = x87t_internal_sf_is_zero(b);
    if (az && bz)
        return 0;
    if (az)
        return !b->sign;
    if (bz)
        return a->sign;
    if (a->sign != b->sign)
        return a->sign;
    int lt = x87t_internal_sf_lt_abs(a, b);
    return a->sign ? x87t_internal_sf_lt_abs(b, a) : lt;
}
