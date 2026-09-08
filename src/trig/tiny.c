/* Handle tiny residuals for FSIN, FCOS and FSINCOS. phase=0 computes
 * sine and phase=1 cosine. Accept only nonzero finite x with |x| < 2^63;
 * return 0 if the caller must use another path. Reduction uses the M66
 * constant and quadrant rule from reduce.c. The remainder t must satisfy
 * 0 < |t| < 2^-32. After reduction, also require c=0 so that r represents
 * t exactly with 64 significant bits.
 *
 * For u = |t|, sin(u) = u - u^3/6 + ... and cos(u) = 1 - u^2/2 + ... .
 * Both are slightly smaller than their leading values, u and 1. Choose
 * the leading value or the next smaller 64-bit value according to the
 * final sign and guest RC; no polynomial is evaluated here.
 *
 * For direct |x| < 2^-68, including all denormals, instead return x for
 * sine or 1 for cosine in every rounding mode, with C1=0. H1638-H1643
 * saved-data checks supported both this shortcut and the predecessor rule.
 */
#include "internal/numeric.h"

int x87t_internal_trig_tiny(x80_t in, int phase, sf_rc_t rc, x80_t *out, numerical_metadata *meta)
{
    if (x87t_internal_raw80_classify(in) == RAW_UNSUPPORTED)
        return 0;
    sf_t x = x87t_internal_sf_from_parts(in.se >> 15, in.se & 0x7fff, in.sig);
    if (x.cls != SF_FIN || !x.sig || x.exp >= 63)
        return 0;
    sf_t magnitude = x87t_internal_sf_abs(&x), r, c;
    int reduced = !x87t_internal_sf_lt(&magnitude, &x87t_internal_PI_BY_4);
    int64_t n = phase;
    if (!reduced) {
        if (x.exp >= -32)
            return 0;
        r = x;
        c = x87t_internal_ZERO;
    } else {
        uint64_t q = x87t_internal_reduce_quotient(x.sig, x.exp);
        n = (x.sign ? -(int64_t)q : (int64_t)q) + phase;
        x87t_internal_reduce_remainder(&x, q, &r, &c);
        if (r.cls != SF_FIN || !r.sig || c.sig || r.exp >= -32)
            return 0;
    }
    int cosine = (unsigned)n & 1u;
    int negative = (((unsigned)n >> 1) & 1u) ^ (cosine ? 0 : r.sign);
    /* At |x| = 2^-68, use the usual leading-value or predecessor rule.
     * The final sign determines whether RD or RU rounds toward zero.
     * PC does not reduce the 64-bit precision used here. */
    int bypass = !reduced && x.exp < -68;
    int toward_zero = rc == SF_RZ || (rc == SF_RD && !negative) || (rc == SF_RU && negative);
    sf_t result = cosine ? x87t_internal_ONE : x87t_internal_sf_abs(&r);
    if (!bypass && toward_zero) {
        /* pred64 crosses to the preceding binade at an exact power of two.
         * Non-bypass tiny arguments are normal, so no subnormal rounding is
         * hidden in this step. Denormals take the separate bypass above. */
        if (result.sig > 0x8000000000000000ull)
            --result.sig;
        else {
            result.sig = UINT64_MAX;
            --result.exp;
        }
    }
    result.sign = negative;
    /* For a denormal sine input, sf_to_x87 undoes normalization exactly
     * by shifting away padding zeros. For a pseudo-denormal, it preserves
     * the value and writes the canonical normal encoding. */
    x87t_internal_sf_to_x87(&result, &out->se, &out->sig);
    /* Outside the shortcut, the small correction reduces the magnitude.
     * Choosing the leading value therefore rounds up in magnitude (C1=1);
     * choosing its predecessor gives C1=0. trig_flags sets PE, DE and UE
     * separately. */
    int c1 = bypass ? 0 : !toward_zero;
    meta->c1 = c1;
    meta->c1_known = 1;
    return 1;
}
