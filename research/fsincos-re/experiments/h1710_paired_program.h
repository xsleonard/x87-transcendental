/* H1710: analysis-only, explicit paired FSINCOS numerical program.
 * Shares the exact reducer and established table/tiny arithmetic, not the
 * standalone polynomial. No captured operands, selectors or history patches.
 * This is a behavioral graph, not a claim that silicon uses a fused unit.
 */
#ifndef G_H1710_PAIRED
#define G_H1710_PAIRED 0
#endif
#ifndef G_H1710_MATERIALIZE
#define G_H1710_MATERIALIZE 0
#endif

static wv_t h1710_fma_rn64(wv_t a, wv_t b, const p5c_t *c)
{
    int32_t pe = a.e2 + b.e2;
    int32_t scale = pe < c->exp2 ? pe : c->exp2;
    u256 sum = {0, 0};
    acc_add_product(&sum, a.sign ^ b.sign, a.sig, b.sig, pe, scale);
    acc_add_product(&sum, c->sign, c->sig, 1, c->exp2, scale);
    return acc_round_bits_mode(sum, scale, 64, P5_ROUND_RN);
}

static sf_t h1710_final(wv_t lead, wv_t tail, int negative,
    sf_rc_t rc, int *c1)
{
    int32_t scale = lead.e2 < tail.e2 ? lead.e2 : tail.e2;
    u256 pre = {0, 0}, stored = {0, 0};
    acc_add_product(&pre, lead.sign, lead.sig, 1, lead.e2, scale);
    acc_add_product(&pre, tail.sign, tail.sig, 1, tail.e2, scale);
    assert(!(pre.hi >> 127));
    sf_t result = acc_round64_rc(pre, scale, negative, rc);
    assert(result.cls == SF_FIN && result.sig);
    acc_add_product(&stored, 0, result.sig, 1, result.exp - 63, scale);
    *c1 = stored.hi > pre.hi || (stored.hi == pre.hi && stored.lo > pre.lo);
    return result;
}

static void h1710_polynomial(wv_t magnitude, int residual_sign,
    int64_t signed_n, sf_rc_t rc, x80_t out[2], int c1[2])
{
    static const p5c_t *const sine[] = {&P5S6_1, &P5S6_2, &P5S6_3,
        &P5S6_4, &P5S6_5, &P5S6_6};
    static const p5c_t *const cosine[] = {&P5C6_1, &P5C6_2, &P5C6_3,
        &P5C6_4, &P5C6_5, &P5C6_6};
    wv_t square = p5_wv_mul_round(magnitude, magnitude, 67, P5_ROUND_CHOP);
    wv_t p = h1630_literal(sine[5]);
    wv_t q = h1630_literal(cosine[5]);
    for (int i = 4; i >= 0; --i) {
        /* Fixed schedule alternatives, never operand classifiers:
         * 0 = archived fused sine graph; 1 = last sine edge materialized,
         * symmetric with cosine; 2 = every Horner product materialized. */
        if (G_H1710_MATERIALIZE == 2 || (G_H1710_MATERIALIZE == 1 && i == 0))
            p = h1630_add(p5_wv_mul_round(p, square, 67, P5_ROUND_CHOP),
                h1630_literal(sine[i]), 64, P5_ROUND_RN);
        else p = h1710_fma_rn64(p, square, sine[i]);
    }
    for (int i = 4; i >= 1; --i) {
        if (G_H1710_MATERIALIZE == 2)
            q = h1630_add(p5_wv_mul_round(q, square, 67, P5_ROUND_CHOP),
                h1630_literal(cosine[i]), 64, P5_ROUND_RN);
        else q = h1710_fma_rn64(q, square, cosine[i]);
    }
    q = p5_wv_mul_round(q, square, 67, P5_ROUND_CHOP);
    q = h1630_add(q, h1630_literal(cosine[0]), 64, P5_ROUND_RN);
    wv_t ps = p5_wv_mul_round(p, square, 64, P5_ROUND_RN);
    wv_t tails[] = {
        p5_wv_mul_round(ps, magnitude, 67, P5_ROUND_CHOP),
        p5_wv_mul_round(q, square, 67, P5_ROUND_CHOP)
    };
    for (int lane = 0; lane < 2; ++lane) {
        unsigned n = (unsigned)(signed_n + lane);
        int cosine_branch = n & 1u;
        int negative = ((n >> 1) & 1u) ^ (cosine_branch ? 0 : residual_sign);
        wv_t lead = cosine_branch ? (wv_t){0, 0, 1, 0} : magnitude;
        sf_t result = h1710_final(lead, tails[cosine_branch], negative, rc, &c1[lane]);
        sf_to_x87(&result, &out[lane].se, &out[lane].sig);
    }
}

static fsincos_status_t h1710_paired_ref(
    x80_t in, x80_t *sin_out, x80_t *cos_out, sf_rc_t rc)
{
    int c1[] = {0, 0};
    int known = 1;
    const char *path = "special";
    x80_t out[2];
    if ((in.se & 0x7fff) && !(in.sig >> 63)) {
        out[0] = out[1] = X87_INDEFINITE;
    } else {
        sf_t x = sf_from_parts(in.se >> 15, in.se & 0x7fff, in.sig);
        if (x.cls == SF_NAN) {
            x.sig |= 0x4000000000000000ull;
            sf_to_x87(&x, &out[0].se, &out[0].sig); out[1] = out[0];
        } else if (x.cls == SF_INF) {
            out[0] = out[1] = X87_INDEFINITE;
        } else if (sf_is_zero(&x)) {
            out[0] = in; out[1] = (x80_t){0x3fff, 0x8000000000000000ull};
        } else if (x.exp >= 63) {
            return FSINCOS_C2;
        } else {
            int previous_trace = g_general_trace;
            g_general_trace = 0;
            int tiny = h1638_tiny_entry(in, 0, rc, &out[0]);
            c1[0] = g_general_c1;
            if (tiny) {
                int other = h1638_tiny_entry(in, 1, rc, &out[1]);
                assert(other); c1[1] = g_general_c1; path = "tiny";
            } else {
                sf_t magnitude = sf_abs(&x), r = x, c = ZERO;
                int64_t signed_n = 0;
                if (!sf_lt(&magnitude, &PI_BY_4)) {
                    uint64_t q = fsincos_compat_reduce_n_exact(x.sig, x.exp);
                    signed_n = x.sign ? -(int64_t)q : (int64_t)q;
                    sky_reduce_rc(&x, q, &r, &c);
                }
                wv_t residual = wv_from_rc(&r, &c);
                int residual_sign = residual.sign; residual.sign = 0;
                int top = residual.e2 + u128_width(residual.sig) - 1;
                assert(residual.sig && top >= -32);
                if (top < -2) {
                    path = "polynomial";
                    h1710_polynomial(residual, residual_sign, signed_n, rc, out, c1);
                } else {
                    path = "table";
                    for (int lane = 0; lane < 2; ++lane) {
                        sf_t value = h1633_table(residual, residual_sign, signed_n + lane, rc);
                        sf_to_x87(&value, &out[lane].se, &out[lane].sig);
                        c1[lane] = g_general_c1;
                    }
                }
            }
            g_general_trace = previous_trace;
        }
    }
    /* C1 is an explicit hypothesis: the final external cosine lane's
     * magnitude increment, not sine OR cosine or an internal-branch label.
     * Special C1 remains outside this numerical claim. */
    if (!strcmp(path, "special")) known = 0;
    if (g_general_trace)
        fprintf(stderr, "HPAIR %llu %s %d %d %d\n", h1630_row - 1,
            path, known, c1[0], c1[1]);
    *sin_out = out[0]; *cos_out = out[1];
    return FSINCOS_OK;
}
