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
    x87t_internal_sf_to_x87(&result, &out->se, &out->sig);
    int c1 = bypass ? 0 : !toward_zero;
    meta->c1 = c1;
    meta->c1_known = 1;
    return 1;
}
