/* H1708 promoted standalone arithmetic, mechanically preserved from h1630_shared_polynomial.h.
 * Historical development comments below are retained. Only C1 export and
 * opt-in trace emission were added; no numerical operation was changed.
 */
/* H1630 analysis-only, fixed shared-operator sine/cosine polynomial.
 * No operand ledger, fitted selector, carrier/history patch or promotion.
 * Original reduction, quadrant and polynomial/table/tiny dispatch are kept.
 */
#include <assert.h>
#ifndef G_H1630_POLYNOMIAL
#define G_H1630_POLYNOMIAL 0
#endif
static unsigned long long h1630_row;

static wv_t h1630_literal(const p5c_t *c)
{
    return (wv_t){ c->sign, c->exp2, c->sig, 0 };
}

static wv_t h1630_mul(wv_t x, wv_t y)
{
    /* Uniform X67/Y64 input ports. H1629 bounds every reachable initial
     * polynomial residual; only the fourth-power Y cut can change value. */
    wv_t one = { 0, 0, 1, 0 };
    x = p5_wv_mul_round(x, one, 67, P5_ROUND_CHOP);
    y = p5_wv_mul_round(y, one, 64, P5_ROUND_CHOP);
    return p5_wv_mul_round(x, y, 67, P5_ROUND_CHOP);
}

static wv_t h1630_add(wv_t x, wv_t y, int bits, p5_round_t mode)
{
    /* Plain signed addition followed by one specified materialization.
     * Incumbent FADD history classifiers are not part of this program. */
    int32_t scale = x.e2 < y.e2 ? x.e2 : y.e2;
    u256 sum = { 0, 0 };
    acc_add_product(&sum, x.sign, x.sig, 1, x.e2, scale);
    acc_add_product(&sum, y.sign, y.sig, 1, y.e2, scale);
    return acc_round_bits_mode(sum, scale, bits, mode);
}

static wv_t h1630_chain(wv_t fourth, const p5c_t *c5,
                        const p5c_t *c3, const p5c_t *c1)
{
    wv_t value = h1630_mul(fourth, h1630_literal(c5));
    value = h1630_add(h1630_literal(c3), value, 64, P5_ROUND_RN);
    value = h1630_mul(fourth, value);
    return h1630_add(h1630_literal(c1), value, 64, P5_ROUND_RN);
}

static sf_t h1630_polynomial(wv_t magnitude, int residual_sign,
                             int64_t signed_n, sf_rc_t rc)
{
    static const p5c_t *const sine_coefficients[6] = {
        &P5S6_1, &P5S6_2, &P5S6_3, &P5S6_4, &P5S6_5, &P5S6_6
    };
    static const p5c_t *const cosine_coefficients[6] = {
        &P5C6_1, &P5C6_2, &P5C6_3, &P5C6_4, &P5C6_5, &P5C6_6
    };
    int cosine = (unsigned)signed_n & 1u;
    int neg = ((unsigned)signed_n >> 1) & 1u;
    const p5c_t *const *coefficients = cosine
        ? cosine_coefficients : sine_coefficients;
    assert(magnitude.sig && !magnitude.sign);
    u128 odd = magnitude.sig;
    while (!(odd & 1)) odd >>= 1;
    int precision = u128_width(odd);
    int top = magnitude.e2 + u128_width(magnitude.sig) - 1;
    assert(precision <= 64 && top >= -32 && top <= -3);

    wv_t square = h1630_mul(magnitude, magnitude);
    wv_t fourth = h1630_mul(square, square);
    wv_t negative = h1630_chain(
        fourth, coefficients[4], coefficients[2], coefficients[0]);
    wv_t positive = h1630_chain(
        fourth, coefficients[5], coefficients[3], coefficients[1]);
    wv_t left = h1630_mul(square, negative);
    wv_t right = h1630_mul(fourth, positive);
    wv_t combined, correction, leading;
    if (cosine) {
        combined = h1630_add(left, right, 67, P5_ROUND_CHOP);
        correction = combined;
        leading = (wv_t){ 0, 0, 1, 0 };
    } else {
        /* The sine terminal is not the cosine terminal: combine at RN64,
         * multiply by the residual, then round residual+tail under RC. */
        combined = h1630_add(left, right, 64, P5_ROUND_RN);
        correction = h1630_mul(magnitude, combined);
        leading = magnitude;
        neg ^= residual_sign;
    }
    int32_t scale = leading.e2 < correction.e2 ? leading.e2 : correction.e2;
    u256 pre = { 0, 0 };
    acc_add_product(&pre, leading.sign, leading.sig, 1, leading.e2, scale);
    acc_add_product(&pre, correction.sign, correction.sig, 1, correction.e2, scale);
    assert(!(pre.hi >> 127));
    sf_t result = acc_round64_rc(pre, scale, neg, rc);
    assert(result.cls == SF_FIN && result.sig);
    u256 stored = { 0, 0 };
    acc_add_product(&stored, 0, result.sig, 1, result.exp - 63, scale);
    int c1 = stored.hi > pre.hi || (stored.hi == pre.hi && stored.lo > pre.lo);
    g_general_c1 = c1;
    g_general_c1_known = 1;
    if (g_general_trace || g_dump_internals)
        fprintf(stderr, "HPOLY %llu %d %d %d %d %d %d " DIWF "\n",
        h1630_row - 1, cosine, top, precision, residual_sign, neg, c1, DIW(magnitude));
    if (g_dump_internals) {
        fprintf(stderr, "HSTAGE sq=" DIWF " f4=" DIWF " n=" DIWF
            " p=" DIWF " left=" DIWF " right=" DIWF
            " combined=" DIWF " correction=" DIWF "\n",
            DIW(square), DIW(fourth), DIW(negative), DIW(positive),
            DIW(left), DIW(right), DIW(combined), DIW(correction));
    }
    return result;
}
