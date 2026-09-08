/* Reconstruct sine or cosine from a table for FSIN, FCOS and FSINCOS.
 * residual holds u = |t|, with 1/4 <= u < 13/16. residual_sign holds t's
 * sign; signed_n selects the function and quadrant sign. The caller has
 * already handled special inputs and smaller residuals.
 *
 * Choose a center T = b/64 and subtract it exactly: a = u-T. Then
 *     sin(T+a) = sin(T) + cos(T)*sin(a) + sin(T)*(cos(a)-1),
 *     cos(T+a) = cos(T) - sin(T)*sin(a) + cos(T)*(cos(a)-1).
 * tsin and tcos store approximations to sin(T) and cos(T). Four-coefficient
 * polynomials give sine_state for sin(a) and cosine_tail for cos(a)-1.
 * The code chops products to 67 significant bits (CHOP67) and rounds sums
 * to nearest/even at 64 bits (RN64), with exceptions described below.
 * These equations explain the terms; they do not allow the rounded
 * operations to be rearranged. Apply the quadrant sign before rounding
 * to 64 bits using guest RC and setting C1.
 *
 * H1633-H1635 tested an extra CHOP67 step before the product that rounds
 * directly to RN64. That extra truncation changed both result bits and C1
 * in the saved tests.
 */
/* Shared table program; each destination precision is explicit. */
#include "internal/numeric.h"

/* Let Tn truncate a magnitude to n significant bits and keep its sign.
 * Compute RN64(T67(x)*T64(y)): form the exact product of the truncated
 * inputs, then round directly to nearest/even at 64 bits.
 * mul_x67_y64_chop67 instead truncates that product to 67 bits. */
wv_t x87t_internal_mul_x67_y64_rn64(wv_t x, wv_t y)
{
    /* RN64 of the exact port product, NOT RN64 of a CHOP67 product. */
    wv_t one = {0, 0, 1, 0};
    x = x87t_internal_wide_mul(x, one, 67, P5_ROUND_CHOP);
    y = x87t_internal_wide_mul(y, one, 64, P5_ROUND_CHOP);
    return x87t_internal_wide_mul(x, y, 64, P5_ROUND_RN);
}

/* Evaluate c1 + square*(c2 + square*(c3 + square*c4)), where square
 * already approximates a^2. Truncate each product to CHOP67 before adding
 * the next coefficient at RN64. Copying a wv_t does not round it. */
wv_t x87t_internal_table_horner4(wv_t square, const p5c_t *c4, const p5c_t *c3, const p5c_t *c2, const p5c_t *c1)
{
    /* Orient the <=67-bit square on X and the <=64-bit coefficient or
     * prior Horner sum on Y. This is a numerical commutation, not recovered
     * physical operand-port routing. The native c4 values fit <=64 bits. */
    const p5c_t *coefficients[] = {c3, c2, c1};
    wv_t value = x87t_internal_constant_exact(c4);
    for (int i = 0; i < 3; i++) {
        value = x87t_internal_mul_x67_y64_chop67(square, value);
        value = x87t_internal_wide_add_plain(value, x87t_internal_constant_exact(coefficients[i]), 64, P5_ROUND_RN);
    }
    return value;
}

sf_t x87t_internal_trig_table(
    wv_t residual, int residual_sign, int64_t signed_n, sf_rc_t rc, numerical_metadata *meta)
{
    int rw = x87t_internal_uint128_width(residual.sig);
    int top = residual.e2 + rw - 1;
    assert(!residual.sign && (top == -2 || top == -1));
    /* The top three significand bits give 4+lane, with lane in [0,3].
     * In [1/4,1/2), cell j is [1/4+j/16,1/4+(j+1)/16) and uses b=18+4*j.
     * For u >= 1/2, j=floor(8*(u-1/2)) selects cells of width 1/8, with
     * b=36+8*min(j,2). Each cell includes its lower boundary and excludes
     * its upper boundary. Thus b is one of 18,22,26,30,36,44,52; index
     * finds the corresponding row in the ROM. */
    int lane = (int)(residual.sig >> (rw - 3)) - 4;
    int b = top == -2 ? 18 + 4 * lane : 36 + 8 * (lane > 2 ? 2 : lane);
    int index = 0;
    while (index < 8 && x87t_internal_P5TAB[index].b != b)
        ++index;
    assert(index < 7); /* The b=60 ROM row is unreachable in this dispatcher. */
    /* residual is sig*2^e2 and the center is b*2^-6. Shift b to the
     * residual's scale before subtracting; delta*2^e2 then equals a
     * exactly, including a=0 at a table center. For inputs from the
     * dispatcher, shift is nonnegative. */
    int shift = -6 - residual.e2;
    assert(shift >= 0 && shift < 120);
    __int128 delta = (__int128)residual.sig - (__int128)((u128)b << shift);
    wv_t a = {delta < 0, residual.e2, delta < 0 ? (u128)-delta : (u128)delta, 0};
    u128 odd = a.sig;
    while (odd && !(odd & 1))
        odd >>= 1;
    assert(x87t_internal_uint128_width(odd) <= 61);
    /* After trailing zeros are removed, a needs at most 61 bits.
     * This first 67-bit truncation therefore leaves it unchanged, for
     * both direct inputs and remainders from range reduction. */
    a = x87t_internal_mul_x67_y64_chop67(a, (wv_t){0, 0, 1, 0});
    wv_t square = x87t_internal_mul_x67_y64_chop67(a, a);
    p5c_t sine4 = x87t_internal_P5S4_4;
    /* sine4 has scale 2^-85, so subtracting 2^60 from sig subtracts
     * 2^-25 from the coefficient. H1633-H1635 used this adjusted value,
     * inherited from the earlier implementation. */
    sine4.sig -= (u128)1 << 60; /* Established P6 coefficient, not a new fit. */
    wv_t p = x87t_internal_table_horner4(square, &sine4, &x87t_internal_P5S4_3, &x87t_internal_P5S4_2, &x87t_internal_P5S4_1);
    wv_t q = x87t_internal_table_horner4(square, &x87t_internal_P5C4_4, &x87t_internal_P5C4_3, &x87t_internal_P5C4_2, &x87t_internal_P5C4_1);
    /* Treating square as a^2, p and q are cubic polynomials. Thus
     * sine_state approximates a + a^3*p and cosine_tail approximates a^2*q.
     * Chop the products for sine_tail to 67 bits before adding a at RN64.
     * The cosine product rounds directly to RN64 after the input cuts. */
    wv_t p_square = x87t_internal_mul_x67_y64_chop67(square, p);
    wv_t sine_tail = x87t_internal_mul_x67_y64_chop67(p_square, a);
    wv_t sine_state = x87t_internal_wide_add_plain(a, sine_tail, 64, P5_ROUND_RN);
    wv_t cosine_tail = x87t_internal_mul_x67_y64_rn64(square, q);
    wv_t tsin = x87t_internal_constant_exact(&x87t_internal_P5TAB[index].sinT);
    wv_t tcos = x87t_internal_constant_exact(&x87t_internal_P5TAB[index].cosT);
    int cosine = (unsigned)signed_n & 1u;
    int negative = ((unsigned)signed_n >> 1) & 1u;
    /* first and second are the two correction terms in the identities
     * above. For cosine, negate first. For sine, use t's sign when choosing
     * the final sign. Chop each product and their signed sum to 67 bits.
     * Add leading+correction exactly before the final guest rounding. */
    wv_t first = x87t_internal_mul_x67_y64_chop67(cosine ? tsin : tcos, sine_state);
    wv_t second = x87t_internal_mul_x67_y64_chop67(cosine ? tcos : tsin, cosine_tail);
    if (cosine)
        first.sign ^= 1;
    else
        negative ^= residual_sign;
    wv_t correction = x87t_internal_wide_add_plain(first, second, 67, P5_ROUND_CHOP);
    wv_t leading = cosine ? tcos : tsin;
    int32_t scale = leading.e2 < correction.e2 ? leading.e2 : correction.e2;
    u256 pre = {0, 0};
    x87t_internal_acc_add_product(&pre, leading.sign, leading.sig, 1, leading.e2, scale);
    x87t_internal_acc_add_product(&pre, correction.sign, correction.sig, 1, correction.e2, scale);
    assert(!(pre.hi >> 127));
    sf_t result = x87t_internal_acc_round64_rc(pre, scale, negative, rc);
    assert(result.cls == SF_FIN && result.sig);
    /* pre holds the positive sum before rounding, in units of 2^scale.
     * Set C1 if rounding increased its magnitude, using the same scale for
     * the comparison even when the final result is negative. The public
     * wrapper sets PE separately from the input. */
    u256 stored = {0, 0};
    x87t_internal_acc_add_product(&stored, 0, result.sig, 1, result.exp - 63, scale);
    int c1 = stored.hi > pre.hi || (stored.hi == pre.hi && stored.lo > pre.lo);
    meta->c1 = c1;
    meta->c1_known = 1;
    return result;
}
