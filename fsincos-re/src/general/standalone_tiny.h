/* H1708 promoted standalone arithmetic, mechanically preserved from h1638_tiny_closed_form.h.
 * Historical development comments below are retained. Only C1 export and
 * opt-in trace emission were added; no numerical operation was changed.
 */
/* H1638 analysis-only tiny entry with explicit predecessor rounding/C1.
 * No arbitrary far-sticky magnitude, fitted operand selector or promotion.
 * The existing external exponent<-68 bypass remains distinct from reduced
 * tiny arguments. Polynomial/table and special inputs are not handled here. */
#ifndef G_H1638_TINY
#define G_H1638_TINY 0
#endif

static int h1638_tiny_entry(x80_t in, int phase, sf_rc_t rc, x80_t *out)
{
    if (x87_invalid_encoding(in)) return 0;
    sf_t x = sf_from_parts(in.se >> 15, in.se & 0x7fff, in.sig);
    if (x.cls != SF_FIN || !x.sig || x.exp >= 63) return 0;
    sf_t magnitude = sf_abs(&x), r, c;
    int reduced = !sf_lt(&magnitude, &PI_BY_4);
    int64_t n = phase;
    if (!reduced) {
        if (x.exp >= -32) return 0;
        r = x;
        c = ZERO;
    } else {
        uint64_t q = fsincos_compat_reduce_n_exact(x.sig, x.exp);
        n = (x.sign ? -(int64_t)q : (int64_t)q) + phase;
        sky_reduce_rc(&x, q, &r, &c);
        if (r.cls != SF_FIN || !r.sig || c.sig || r.exp >= -32) return 0;
    }
    int cosine = (unsigned)n & 1u;
    int negative = (((unsigned)n >> 1) & 1u) ^ (cosine ? 0 : r.sign);
    int bypass = !reduced && x.exp < -68;
    int toward_zero = rc == SF_RZ || (rc == SF_RD && !negative)
        || (rc == SF_RU && negative);
    sf_t result = cosine ? ONE : sf_abs(&r);
    if (!bypass && toward_zero) {
        /* pred64 crosses to the preceding binade at an exact power of two.
         * Non-bypass tiny arguments are normal, so no subnormal rounding is
         * hidden in this step. Denormals take the separate bypass above. */
        if (result.sig > 0x8000000000000000ull) --result.sig;
        else { result.sig = UINT64_MAX; --result.exp; }
    }
    result.sign = negative;
    sf_to_x87(&result, &out->se, &out->sig);
    int c1 = bypass ? 0 : !toward_zero;
    g_general_c1 = c1;
    g_general_c1_known = 1;
    if (g_general_trace || g_dump_internals)
        fprintf(stderr, "HTINY %llu %d %d %d %d %d %d %d\n",
        h1630_row - 1, reduced, cosine, bypass, negative, c1, x.exp, r.exp);
    return 1;
}
