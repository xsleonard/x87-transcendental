/* H1633 analysis-only table arithmetic. No canonical/default promotion.
 * Uses the H1630 plain add and X67/Y64 multiply helpers, with a separate
 * RN64-destination multiply. Native ROM and the established table dispatch
 * are retained. No operand-error ledger or history-state correction. */
#ifndef G_H1633_TABLE
#define G_H1633_TABLE 0
#endif

static wv_t h1633_mul_rn64(wv_t x, wv_t y)
{
    /* RN64 of the exact port product, NOT RN64 of a CHOP67 product. */
    wv_t one = { 0, 0, 1, 0 };
    x = p5_wv_mul_round(x, one, 67, P5_ROUND_CHOP);
    y = p5_wv_mul_round(y, one, 64, P5_ROUND_CHOP);
    return p5_wv_mul_round(x, y, 64, P5_ROUND_RN);
}

static wv_t h1633_horner4(wv_t square, const p5c_t *c4,
    const p5c_t *c3, const p5c_t *c2, const p5c_t *c1)
{
    /* Orient the <=67-bit square on X and the <=64-bit coefficient or
     * prior Horner sum on Y. This is a numerical commutation, not recovered
     * physical operand-port routing. The native c4 values fit <=64 bits. */
    const p5c_t *coefficients[] = { c3, c2, c1 };
    wv_t value = h1630_literal(c4);
    for (int i = 0; i < 3; i++) {
        value = h1630_mul(square, value);
        value = h1630_add(value, h1630_literal(coefficients[i]),
                           64, P5_ROUND_RN);
    }
    return value;
}

static sf_t h1633_table(wv_t residual, int residual_sign,
    int64_t signed_n, sf_rc_t rc)
{
    int rw = u128_width(residual.sig);
    int top = residual.e2 + rw - 1;
    assert(!residual.sign && (top == -2 || top == -1));
    int lane = (int)(residual.sig >> (rw - 3)) - 4;
    int b = top == -2 ? 18 + 4 * lane : 36 + 8 * (lane > 2 ? 2 : lane);
    int index = 0;
    while (index < 8 && P5TAB[index].b != b) ++index;
    assert(index < 7); /* The b=60 ROM row is unreachable in this dispatcher. */
    int shift = -6 - residual.e2;
    assert(shift >= 0 && shift < 120);
    __int128 delta = (__int128)residual.sig - (__int128)((u128)b << shift);
    wv_t a = { delta < 0, residual.e2, delta < 0 ? (u128)-delta : (u128)delta, 0 };
    u128 odd = a.sig;
    while (odd && !(odd & 1)) odd >>= 1;
    int precision = u128_width(odd);
    assert(precision <= 61);
    a = h1630_mul(a, (wv_t){0, 0, 1, 0});
    wv_t square = h1630_mul(a, a);
    p5c_t sine4 = P5S4_4;
    sine4.sig -= (u128)1 << 60; /* Established P6 coefficient, not a new fit. */
    wv_t p = h1633_horner4(square, &sine4, &P5S4_3, &P5S4_2, &P5S4_1);
    wv_t q = h1633_horner4(square, &P5C4_4, &P5C4_3, &P5C4_2, &P5C4_1);
    wv_t p_square = h1630_mul(square, p);
    wv_t sine_tail = h1630_mul(p_square, a);
    wv_t sine_state = h1630_add(a, sine_tail, 64, P5_ROUND_RN);
    wv_t cosine_tail = h1633_mul_rn64(square, q);
    wv_t tsin = h1630_literal(&P5TAB[index].sinT);
    wv_t tcos = h1630_literal(&P5TAB[index].cosT);
    int cosine = (unsigned)signed_n & 1u;
    int negative = ((unsigned)signed_n >> 1) & 1u;
    wv_t first = h1630_mul(cosine ? tsin : tcos, sine_state);
    wv_t second = h1630_mul(cosine ? tcos : tsin, cosine_tail);
    if (cosine) first.sign ^= 1;
    else negative ^= residual_sign;
    wv_t correction = h1630_add(first, second, 67, P5_ROUND_CHOP);
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
    fprintf(stderr, "HTABLE %llu %d %d %d %d %d %d %d " DIWF "\n",
        h1630_row - 1, cosine, top, b, precision, residual_sign, negative, c1, DIW(residual));
    if (g_dump_internals)
        fprintf(stderr, "HTSTAGE a=" DIWF " sq=" DIWF " p=" DIWF
            " q=" DIWF " psq=" DIWF " stail=" DIWF " sstate=" DIWF
            " ctail=" DIWF " first=" DIWF " second=" DIWF " correction=" DIWF "\n",
            DIW(a), DIW(square), DIW(p), DIW(q), DIW(p_square), DIW(sine_tail),
            DIW(sine_state), DIW(cosine_tail), DIW(first), DIW(second), DIW(correction));
    return result;
}
