/* Shared FSIN and FCOS evaluation: TRIG_SINE computes sine and TRIG_COSINE
 * computes cosine. Handle raw80 special encodings first; finite |x| >= 2^63
 * returns C2. Public entry points set exceptions and tell the caller
 * whether to write the result. All numerical work uses integer arithmetic.
 *
 * Write x = k*pi/2 + t and let n = (k+function) modulo 4. For n=0,1,2,3,
 * the result is sin(t), cos(t), -sin(t), -cos(t). The actual reduction uses
 * stored M66 in place of pi/2. r+c is its exact remainder t, and
 * reduced_to_wide combines the two without rounding.
 *
 * For |x| < 2^-68, return x for sine or 1 for cosine. Other tiny residuals
 * use a leading value or its predecessor. Use the standalone polynomial
 * for 2^-32 <= |t| < 1/4 and a table for |t| >= 1/4. Apply the quadrant
 * sign before rounding to 64 significant bits using guest RC. The earlier
 * 67-bit truncations and 64-bit nearest/even operations have fixed widths.
 * H1707-H1708 checks found that these choices agreed with the saved results
 * for all three paths.
 */
/* Fixed FSIN/FCOS dispatch, extracted from general_standalone_ref and the
 * selected operation-class core. The caller supplies all per-call metadata.
 * Read the evaluator first, then its polynomial below. Reduction, tiny
 * results and table evaluation are shared with FSINCOS in adjacent files.
 */
#include "internal/numeric.h"

static sf_t sin_cos_polynomial(
    wv_t magnitude, int residual_sign, int64_t quadrant, sf_rc_t rc, numerical_metadata *meta);

trig_status_t x87t_internal_sin_cos_evaluate(
    x80_t in, trig_function_t function, x80_t *out, sf_rc_t rc, numerical_metadata *meta)
{
    meta->c1 = 0;
    meta->c1_known = 1;
    /* Reject unnormal encodings before sf_from_parts normalizes the
     * significand and hides the invalid integer bit. Pseudo-denormals are
     * valid inputs and continue below. */
    if (x87t_internal_raw80_classify(in) == RAW_UNSUPPORTED) {
        *out = x87t_internal_X87_INDEFINITE;
        return TRIG_OK;
    }
    sf_t x = x87t_internal_sf_from_parts(in.se >> 15, in.se & 0x7fff, in.sig);
    sf_t value;
    if (x.cls == SF_NAN) {
        value = x;
        value.sig |= UINT64_C(1) << 62;
    } else if (x.cls == SF_INF) {
        value = x87t_internal_sf_qnan();
    } else if (x87t_internal_sf_is_zero(&x)) {
        value = function == TRIG_COSINE ? x87t_internal_ONE : x;
    } else {
        if (x.exp >= 63) {
            meta->c1_known = 0;
            return TRIG_RANGE;
        }
        sf_t magnitude = x87t_internal_sf_abs(&x), r = x, c = x87t_internal_ZERO;
        int64_t quadrant = function;
        /* Reduce at equality too. PI_BY_4 is the stored raw80 value
         * 3ffe:c90fdaa22168c234, rather than exact pi/4. */
        if (!x87t_internal_sf_lt(&magnitude, &x87t_internal_PI_BY_4)) {
            uint64_t quotient = x87t_internal_reduce_quotient(x.sig, x.exp);
            quadrant += x.sign ? -(int64_t)quotient : (int64_t)quotient;
            x87t_internal_reduce_remainder(&x, quotient, &r, &c);
            if (r.cls != SF_FIN)
                return TRIG_RANGE;
        }
        wv_t residual = x87t_internal_reduced_to_wide(&r, &c);
        /* Both kernels approximate |t|, so keep its sign separately.
         * Bit 0 of quadrant selects cosine; bit 1 negates the result. */
        int residual_sign = residual.sign;
        residual.sign = 0;
        if (!residual.sig) {
            value = ((unsigned)quadrant & 1u) ? x87t_internal_ONE : x87t_internal_sf_zero(residual_sign);
            value.sign ^= ((unsigned)quadrant >> 1) & 1u;
        } else {
            int exponent = residual.e2 + x87t_internal_uint128_width(residual.sig) - 1;
            /* The tiny kernel handles every nonzero residual below 2^-32,
             * including reduced arguments. At that size r is exact (c=0).
             * Only an original input below 2^-68 takes the direct bypass. */
            if (exponent < -32) {
                assert(c.sig == 0);
                value = x87t_internal_sin_cos_tiny(r, quadrant, x.exp < -68, rc, meta);
            } else if (exponent < -2) {
                value = sin_cos_polynomial(residual, residual_sign, quadrant, rc, meta);
            } else {
                value = x87t_internal_sin_cos_table(residual, residual_sign, quadrant, rc, meta);
            }
        }
    }
    /* The result already has 64 significant bits; sf_to_x87 encodes it
     * without rounding. For tiny denormal sine results, this also shifts
     * away normalization padding to restore the raw80 subnormal encoding. */
    x87t_internal_sf_to_x87(&value, &out->se, &out->sig);
    return TRIG_OK;
}

/* Approximate sine or cosine for a small residual t. The dispatcher
 * supplies magnitude u = |t| in [2^-32,1/4), t's sign, and quadrant for
 * the quadrant and function selection. After trailing zeros are removed,
 * u has at most 64 significant bits. Special inputs and other residual
 * sizes are handled by the dispatcher.
 *
 * For signed ROM coefficients K1..K6, the polynomial correction is
 *     K1*u^2 + K2*u^4 + ... + K6*u^12.
 * Sine multiplies its correction by u and adds u; cosine adds 1 to its
 * correction. Grouping odd and even coefficient indices gives two chains
 * in u^4. Use the stored coefficients rather than exact Taylor fractions.
 * Products are chopped to 67 significant bits (CHOP67), and coefficient
 * sums round to nearest/even at 64 bits (RN64).
 *
 * The final steps differ: sine combines the chains at RN64 before
 * multiplying by u; cosine combines them at CHOP67. H1630-H1632 found
 * that these choices matched the saved results. Apply the quadrant sign
 * before the final rounding to 64 bits using guest RC.
 */
/* Fixed standalone polynomial. Original numerical comments are retained. */

/* The polynomial is c1 + fourth*(c3 + fourth*c5). Each multiply
 * truncates its inputs and product through mul_x67_y64_chop67, and each
 * coefficient addition rounds to RN64. Keeping a wider product until
 * after the addition can change the sum. */
static wv_t polynomial_chain(wv_t fourth, const p5c_t *c5, const p5c_t *c3, const p5c_t *c1)
{
    wv_t value = x87t_internal_mul_x67_y64_chop67(fourth, x87t_internal_constant_exact(c5));
    value = x87t_internal_wide_add_plain(x87t_internal_constant_exact(c3), value, 64, P5_ROUND_RN);
    value = x87t_internal_mul_x67_y64_chop67(fourth, value);
    return x87t_internal_wide_add_plain(x87t_internal_constant_exact(c1), value, 64, P5_ROUND_RN);
}

static sf_t sin_cos_polynomial(
    wv_t magnitude, int residual_sign, int64_t quadrant, sf_rc_t rc, numerical_metadata *meta)
{
    static const p5c_t *const sine_coefficients[6] = {
        &x87t_internal_P5S6_1,
        &x87t_internal_P5S6_2,
        &x87t_internal_P5S6_3,
        &x87t_internal_P5S6_4,
        &x87t_internal_P5S6_5,
        &x87t_internal_P5S6_6
    };
    static const p5c_t *const cosine_coefficients[6] = {
        &x87t_internal_P5C6_1,
        &x87t_internal_P5C6_2,
        &x87t_internal_P5C6_3,
        &x87t_internal_P5C6_4,
        &x87t_internal_P5C6_5,
        &x87t_internal_P5C6_6
    };
    int cosine = (unsigned)quadrant & 1u;
    int neg = ((unsigned)quadrant >> 1) & 1u;
    const p5c_t *const *coefficients = cosine ? cosine_coefficients : sine_coefficients;
    assert(magnitude.sig && !magnitude.sign);
    u128 odd = magnitude.sig;
    while (!(odd & 1))
        odd >>= 1;
    assert(x87t_internal_uint128_width(odd) <= 64);
    assert(magnitude.e2 + x87t_internal_uint128_width(magnitude.sig) - 1 >= -32);
    assert(magnitude.e2 + x87t_internal_uint128_width(magnitude.sig) - 1 <= -3);

    /* Element i-1 stores Ki. square approximates u^2 and fourth
     * approximates u^4; computing fourth truncates its second square
     * operand to 64 bits first. negative uses K1,K3,K5 and positive uses
     * K2,K4,K6, named for their ROM signs. Multiplying these chains by
     * square and fourth gives left+right, the correction defined above. */
    wv_t square = x87t_internal_mul_x67_y64_chop67(magnitude, magnitude);
    wv_t fourth = x87t_internal_mul_x67_y64_chop67(square, square);
    wv_t negative = polynomial_chain(fourth, coefficients[4], coefficients[2], coefficients[0]);
    wv_t positive = polynomial_chain(fourth, coefficients[5], coefficients[3], coefficients[1]);
    wv_t left = x87t_internal_mul_x67_y64_chop67(square, negative);
    wv_t right = x87t_internal_mul_x67_y64_chop67(fourth, positive);
    wv_t combined, correction, leading;
    if (cosine) {
        combined = x87t_internal_wide_add_plain(left, right, 67, P5_ROUND_CHOP);
        correction = combined;
        leading = (wv_t){0, 0, 1, 0};
    } else {
        /* The sine terminal is not the cosine terminal: combine at RN64,
         * multiply by the residual, then round residual+tail under RC. */
        combined = x87t_internal_wide_add_plain(left, right, 64, P5_ROUND_RN);
        correction = x87t_internal_mul_x67_y64_chop67(magnitude, combined);
        leading = magnitude;
        neg ^= residual_sign;
    }
    /* Add leading+correction exactly. The sum is positive throughout
     * this kernel's input range; neg gives the final result's sign.
     * Round that signed sum to 64 bits using guest RC. To determine C1,
     * put the rounded magnitude at the same scale and compare stored > pre.
     * Only an increase in this final magnitude sets C1. The public wrapper
     * sets PE from the input, independently of the bits discarded here. */
    int32_t scale = leading.e2 < correction.e2 ? leading.e2 : correction.e2;
    u256 pre = {0, 0};
    x87t_internal_acc_add_product(&pre, leading.sign, leading.sig, 1, leading.e2, scale);
    x87t_internal_acc_add_product(&pre, correction.sign, correction.sig, 1, correction.e2, scale);
    assert(!(pre.hi >> 127));
    sf_t result = x87t_internal_acc_round64_rc(pre, scale, neg, rc);
    assert(result.cls == SF_FIN && result.sig);
    u256 stored = {0, 0};
    x87t_internal_acc_add_product(&stored, 0, result.sig, 1, result.exp - 63, scale);
    int c1 = stored.hi > pre.hi || (stored.hi == pre.hi && stored.lo > pre.lo);
    meta->c1 = c1;
    meta->c1_known = 1;
    return result;
}
