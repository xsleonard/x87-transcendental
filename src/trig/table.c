/* Shared table program; each destination precision is explicit. */
#include "internal/numeric.h"

wv_t mul_x67_y64_rn64(wv_t x, wv_t y)
{
    /* RN64 of the exact port product, NOT RN64 of a CHOP67 product. */
    wv_t one = {0, 0, 1, 0};
    x = wide_mul(x, one, 67, P5_ROUND_CHOP);
    y = wide_mul(y, one, 64, P5_ROUND_CHOP);
    return wide_mul(x, y, 64, P5_ROUND_RN);
}

wv_t table_horner4(wv_t square, const p5c_t *c4, const p5c_t *c3, const p5c_t *c2, const p5c_t *c1)
{
    /* Orient the <=67-bit square on X and the <=64-bit coefficient or
     * prior Horner sum on Y. This is a numerical commutation, not recovered
     * physical operand-port routing. The native c4 values fit <=64 bits. */
    const p5c_t *coefficients[] = {c3, c2, c1};
    wv_t value = constant_exact(c4);
    for (int i = 0; i < 3; i++) {
        value = mul_x67_y64_chop67(square, value);
        value = wide_add_plain(value, constant_exact(coefficients[i]), 64, P5_ROUND_RN);
    }
    return value;
}

sf_t trig_table(
    wv_t residual, int residual_sign, int64_t signed_n, sf_rc_t rc, numerical_metadata *meta)
{
    int rw = uint128_width(residual.sig);
    int top = residual.e2 + rw - 1;
    assert(!residual.sign && (top == -2 || top == -1));
    int lane = (int)(residual.sig >> (rw - 3)) - 4;
    int b = top == -2 ? 18 + 4 * lane : 36 + 8 * (lane > 2 ? 2 : lane);
    int index = 0;
    while (index < 8 && P5TAB[index].b != b)
        ++index;
    assert(index < 7); /* The b=60 ROM row is unreachable in this dispatcher. */
    int shift = -6 - residual.e2;
    assert(shift >= 0 && shift < 120);
    __int128 delta = (__int128)residual.sig - (__int128)((u128)b << shift);
    wv_t a = {delta < 0, residual.e2, delta < 0 ? (u128)-delta : (u128)delta, 0};
    u128 odd = a.sig;
    while (odd && !(odd & 1))
        odd >>= 1;
    assert(uint128_width(odd) <= 61);
    a = mul_x67_y64_chop67(a, (wv_t){0, 0, 1, 0});
    wv_t square = mul_x67_y64_chop67(a, a);
    p5c_t sine4 = P5S4_4;
    sine4.sig -= (u128)1 << 60; /* Established P6 coefficient, not a new fit. */
    wv_t p = table_horner4(square, &sine4, &P5S4_3, &P5S4_2, &P5S4_1);
    wv_t q = table_horner4(square, &P5C4_4, &P5C4_3, &P5C4_2, &P5C4_1);
    wv_t p_square = mul_x67_y64_chop67(square, p);
    wv_t sine_tail = mul_x67_y64_chop67(p_square, a);
    wv_t sine_state = wide_add_plain(a, sine_tail, 64, P5_ROUND_RN);
    wv_t cosine_tail = mul_x67_y64_rn64(square, q);
    wv_t tsin = constant_exact(&P5TAB[index].sinT);
    wv_t tcos = constant_exact(&P5TAB[index].cosT);
    int cosine = (unsigned)signed_n & 1u;
    int negative = ((unsigned)signed_n >> 1) & 1u;
    wv_t first = mul_x67_y64_chop67(cosine ? tsin : tcos, sine_state);
    wv_t second = mul_x67_y64_chop67(cosine ? tcos : tsin, cosine_tail);
    if (cosine)
        first.sign ^= 1;
    else
        negative ^= residual_sign;
    wv_t correction = wide_add_plain(first, second, 67, P5_ROUND_CHOP);
    wv_t leading = cosine ? tcos : tsin;
    int32_t scale = leading.e2 < correction.e2 ? leading.e2 : correction.e2;
    u256 pre = {0, 0};
    acc_add_product(&pre, leading.sign, leading.sig, 1, leading.e2, scale);
    acc_add_product(&pre, correction.sign, correction.sig, 1, correction.e2, scale);
    assert(!(pre.hi >> 127));
    sf_t result = acc_round64_rc(pre, scale, negative, rc);
    assert(result.cls == SF_FIN && result.sig);
    u256 stored = {0, 0};
    acc_add_product(&stored, 0, result.sig, 1, result.exp - 63, scale);
    int c1 = stored.hi > pre.hi || (stored.hi == pre.hi && stored.lo > pre.lo);
    meta->c1 = c1;
    meta->c1_known = 1;
    return result;
}
