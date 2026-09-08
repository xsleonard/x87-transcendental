/* Handle tiny residuals for FSIN, FCOS and FSINCOS. The caller has decoded
 * the input and reduced it once using M66 and the quadrant rule in reduce.c.
 * residual is the exact signed remainder t, with 0 < |t| < 2^-32. At that
 * size the reducer's correction c is zero, so t fits in 64 significant bits.
 * quadrant includes the requested function: add 0 for sine or 1 for cosine.
 *
 * For u = |t|, sin(u) = u - u^3/6 + ... and cos(u) = 1 - u^2/2 + ... .
 * Both are slightly smaller than their leading values, u and 1. Choose
 * the leading value or the next smaller 64-bit value according to the
 * final sign and guest RC; no polynomial is evaluated here.
 *
 * For direct |x| < 2^-68, including all denormals, the caller sets bypass.
 * Return x for sine or 1 for cosine in every rounding mode, with C1=0. H1638-H1643
 * saved-data checks supported both this shortcut and the predecessor rule.
 */
#include "internal/numeric.h"

sf_t x87t_internal_sin_cos_tiny(
    sf_t residual, int64_t quadrant, int bypass, sf_rc_t rc, numerical_metadata *meta)
{
    assert(residual.cls == SF_FIN && residual.sig && residual.exp < -32);
    int cosine = (unsigned)quadrant & 1u;
    int negative = (((unsigned)quadrant >> 1) & 1u) ^ (cosine ? 0 : residual.sign);
    /* At |x| = 2^-68, use the usual leading-value or predecessor rule.
     * The final sign determines whether RD or RU rounds toward zero.
     * PC does not reduce the 64-bit precision used here. */
    int toward_zero = rc == SF_RZ || (rc == SF_RD && !negative) || (rc == SF_RU && negative);
    sf_t result = cosine ? x87t_internal_ONE : x87t_internal_sf_abs(&residual);
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
    /* For a denormal sine input, the caller's sf_to_x87 undoes normalization
     * exactly by shifting away padding zeros. For a pseudo-denormal, it preserves
     * the value and writes the canonical normal encoding. */
    /* Outside the shortcut, the small correction reduces the magnitude.
     * Choosing the leading value therefore rounds up in magnitude (C1=1);
     * choosing its predecessor gives C1=0. trig_flags sets PE, DE and UE
     * separately. */
    int c1 = bypass ? 0 : !toward_zero;
    meta->c1 = c1;
    meta->c1_known = 1;
    return result;
}
