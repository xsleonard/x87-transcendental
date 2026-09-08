/* Compute both FSINCOS results. Handle special encodings and finite
 * |x| >= 2^63 before reducing x = k*M66 + t, where M66 is the stored
 * approximation to pi/2 and k is a signed integer. The quadrant selects
 * signed sin(t) or cos(t) for each result. Tiny results and table evaluation
 * use the standalone helpers. Only 2^-32 <= |t| < 1/4 uses this polynomial.
 *
 * With u = |t|, the polynomials approximate sine by u + u^3*P(u^2) and
 * cosine by 1 + u^2*Q(u^2). P and Q have degree five and signed ROM
 * coefficients. Both use the same square, chopped to 67 significant bits
 * (CHOP67). Separate Horner chains chop every product to 67 bits, then
 * round each coefficient addition to nearest/even at 64 bits (RN64).
 * The final correction products differ between sine and cosine as shown
 * below. Apply quadrant signs before rounding to 64 bits using guest RC;
 * C1 comes from the final cosine result. Keeping wider products can change
 * the result bits, so these truncations must precede the additions.
 */
/* Paired all-product CHOP67/RN64 schedule, with per-call C1 metadata. */
#include "internal/numeric.h"

static void sincos_polynomial(
    wv_t magnitude, int residual_sign, int64_t quadrant, sf_rc_t rc, x80_t out[2], int c1[2]);

trig_status_t
x87t_internal_sincos_evaluate(x80_t in, x80_t *sin_out, x80_t *cos_out, sf_rc_t rc, numerical_metadata *meta)
{
    int c1[] = {0, 0};
    int known = 0;
    x80_t out[2];
    meta->c1 = 0;
    meta->c1_known = 0;
    /* Check the integer bit before sf_from_parts normalizes the value:
     * normalization could hide an unsupported unnormal encoding. Special
     * results return without rounding, so meta keeps its initial C1=0. */
    if ((in.se & 0x7fff) && !(in.sig >> 63)) {
        out[0] = out[1] = x87t_internal_X87_INDEFINITE;
    } else {
        sf_t x = x87t_internal_sf_from_parts(in.se >> 15, in.se & 0x7fff, in.sig);
        if (x.cls == SF_NAN) {
            x.sig |= 0x4000000000000000ull;
            x87t_internal_sf_to_x87(&x, &out[0].se, &out[0].sig);
            out[1] = out[0];
        } else if (x.cls == SF_INF) {
            out[0] = out[1] = x87t_internal_X87_INDEFINITE;
        } else if (x87t_internal_sf_is_zero(&x)) {
            out[0] = in;
            out[1] = (x80_t){0x3fff, 0x8000000000000000ull};
        } else if (x.exp >= 63) {
            return TRIG_RANGE;
        } else {
            sf_t magnitude = x87t_internal_sf_abs(&x), r = x, c = x87t_internal_ZERO;
            int64_t quadrant = 0;
            /* Reduce when |x| equals or exceeds the stored PI_BY_4 value.
             * The sum r+c is the exact remainder after subtracting q*M66
             * with x's sign. Both outputs use this one reduction. */
            if (!x87t_internal_sf_lt(&magnitude, &x87t_internal_PI_BY_4)) {
                uint64_t q = x87t_internal_reduce_quotient(x.sig, x.exp);
                quadrant = x.sign ? -(int64_t)q : (int64_t)q;
                x87t_internal_reduce_remainder(&x, q, &r, &c);
            }
            wv_t residual = x87t_internal_reduced_to_wide(&r, &c);
            int residual_sign = residual.sign;
            residual.sign = 0;
            int exponent = residual.e2 + x87t_internal_uint128_width(residual.sig) - 1;
            assert(residual.sig);
            /* Tiny results use |t| < 2^-32. Since exponent is floor(log2(|t|)),
             * exponent < -2 then selects the polynomial for |t| < 1/4.
             * Exactly 1/4 uses the table. */
            if (exponent < -32) {
                assert(c.sig == 0);
                for (int lane = 0; lane < 2; ++lane) {
                    sf_t value = x87t_internal_sin_cos_tiny(
                        r, quadrant + lane, x.exp < -68, rc, meta);
                    x87t_internal_sf_to_x87(&value, &out[lane].se, &out[lane].sig);
                    c1[lane] = meta->c1;
                }
            } else if (exponent < -2) {
                sincos_polynomial(residual, residual_sign, quadrant, rc, out, c1);
            } else {
                for (int lane = 0; lane < 2; ++lane) {
                    sf_t value = x87t_internal_sin_cos_table(
                        residual, residual_sign, quadrant + lane, rc, meta);
                    x87t_internal_sf_to_x87(&value, &out[lane].se, &out[lane].sig);
                    c1[lane] = meta->c1;
                }
            }
            known = 1;
        }
    }
    /* C1 is an explicit hypothesis: the final external cosine lane's
     * magnitude increment, not sine OR cosine or an internal-branch label.
     * Special C1 remains outside this numerical claim. */
    /* No rounding occurs for special results. Leave C1 unknown here;
     * the public FSINCOS wrapper sets it to zero for those cases. */
    meta->c1 = c1[1];
    meta->c1_known = known;
    *sin_out = out[0];
    *cos_out = out[1];
    return TRIG_OK;
}

/* H1717: promoted all-product H1710 paired FSINCOS numerical program.
 * The independent review separates this schedule from H1713's last-product
 * schedule. Every Horner product is CHOP67 before its RN64 add. No policy selector,
 * captured operands or history patches participate in the promoted route.
 * Shared reduction/table/tiny arithmetic is unchanged from H1708.
 * This is a behavioral graph, not a claim that silicon uses a fused unit.
 */
/* H1717 kept this sequence because a saved nearest/even test changes
 * sine by one ulp when earlier Horner products are left unchopped. An
 * independent calculation with exact dyadics traced the difference to a
 * coefficient addition after one of those products.
 *
 * lead and tail are signed dyadics with a positive sum. Align them and add
 * exactly in the signed 256-bit accumulator; the caller must ensure they
 * fit. Apply the result's sign from negative, then round once to 64 bits
 * using rc. Set C1 if the rounded magnitude exceeds the sum before rounding.
 * The public wrapper sets PE and decides whether to write the result. */
static sf_t round_polynomial_result(wv_t lead, wv_t tail, int negative, sf_rc_t rc, int *c1)
{
    int32_t scale = lead.e2 < tail.e2 ? lead.e2 : tail.e2;
    u256 pre = {0, 0}, stored = {0, 0};
    x87t_internal_acc_add_product(&pre, lead.sign, lead.sig, 1, lead.e2, scale);
    x87t_internal_acc_add_product(&pre, tail.sign, tail.sig, 1, tail.e2, scale);
    assert(!(pre.hi >> 127));
    sf_t result = x87t_internal_acc_round64_rc(pre, scale, negative, rc);
    assert(result.cls == SF_FIN && result.sig);
    x87t_internal_acc_add_product(&stored, 0, result.sig, 1, result.exp - 63, scale);
    *c1 = stored.hi > pre.hi || (stored.hi == pre.hi && stored.lo > pre.lo);
    return result;
}

static void sincos_polynomial(
    wv_t magnitude, int residual_sign, int64_t quadrant, sf_rc_t rc, x80_t out[2], int c1[2])
{
    static const p5c_t *const sine[] = {
        &x87t_internal_P5S6_1,
        &x87t_internal_P5S6_2,
        &x87t_internal_P5S6_3,
        &x87t_internal_P5S6_4,
        &x87t_internal_P5S6_5,
        &x87t_internal_P5S6_6
    };
    static const p5c_t *const cosine[] = {
        &x87t_internal_P5C6_1,
        &x87t_internal_P5C6_2,
        &x87t_internal_P5C6_3,
        &x87t_internal_P5C6_4,
        &x87t_internal_P5C6_5,
        &x87t_internal_P5C6_6
    };
    /* Element i stores K_(i+1). The loop starts at K6 and works down to
     * K2; the operations after it include K1. Here wide_mul uses the stored
     * operands without truncating them first, then chops the product.
     * The standalone M helper also truncates its inputs. */
    wv_t square = x87t_internal_wide_mul(magnitude, magnitude, 67, P5_ROUND_CHOP);
    wv_t p = x87t_internal_constant_exact(sine[5]);
    wv_t q = x87t_internal_constant_exact(cosine[5]);
    for (int i = 4; i >= 1; --i) {
        p = x87t_internal_wide_mul(p, square, 67, P5_ROUND_CHOP);
        p = x87t_internal_wide_add_plain(p, x87t_internal_constant_exact(sine[i]), 64, P5_ROUND_RN);
        q = x87t_internal_wide_mul(q, square, 67, P5_ROUND_CHOP);
        q = x87t_internal_wide_add_plain(q, x87t_internal_constant_exact(cosine[i]), 64, P5_ROUND_RN);
    }
    /* Both final Horner products are materialized before their RN64 adds.
     * This fixed cut is not conditional on the input or a rounding history. */
    p = x87t_internal_wide_mul(p, square, 67, P5_ROUND_CHOP);
    p = x87t_internal_wide_add_plain(p, x87t_internal_constant_exact(sine[0]), 64, P5_ROUND_RN);
    q = x87t_internal_wide_mul(q, square, 67, P5_ROUND_CHOP);
    q = x87t_internal_wide_add_plain(q, x87t_internal_constant_exact(cosine[0]), 64, P5_ROUND_RN);
    /* With T67 denoting CHOP67, the corrections are
     *     sine:   T67(RN64(p*square)*u)
     *     cosine: T67(q*square).
     * The sine product p*square rounds directly to RN64. Chopping it to
     * 67 bits first would introduce an extra rounding step. */
    wv_t ps = x87t_internal_wide_mul(p, square, 64, P5_ROUND_RN);
    wv_t tails[] = {x87t_internal_wide_mul(ps, magnitude, 67, P5_ROUND_CHOP),
                    x87t_internal_wide_mul(q, square, 67, P5_ROUND_CHOP)};
    for (int lane = 0; lane < 2; ++lane) {
        /* out[0] is sin(x) and out[1] is cos(x), even when the quadrant swaps
         * which polynomial supplies them. Bit 0 of n selects the cosine
         * polynomial; bit 1 negates the result. */
        unsigned n = (unsigned)(quadrant + lane);
        int cosine_branch = n & 1u;
        int negative = ((n >> 1) & 1u) ^ (cosine_branch ? 0 : residual_sign);
        wv_t lead = cosine_branch ? (wv_t){0, 0, 1, 0} : magnitude;
        sf_t result = round_polynomial_result(lead, tails[cosine_branch], negative, rc, &c1[lane]);
        x87t_internal_sf_to_x87(&result, &out[lane].se, &out[lane].sig);
    }
}
