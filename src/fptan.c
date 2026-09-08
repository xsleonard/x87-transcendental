/* FPTAN evaluates its own quotient pair before final division. */
#include "internal/numeric.h"

/*
 * h184-h185's shared wide-table FIRC route.
 * The lookup constants have native 67-bit significands.  Materializing the
 * cross constant at RN64 before only the cross*p product models placement on
 * FMUL's 64-bit Y operand while the linear cross*a product and leading
 * addend retain the native ROM67 value:
 *
 *   p = (S + s_bias) - a
 *   correction = RN67(T1*q +/- (T2*a + RN64(T2)*p))
 *   result = architectural_round(T1 + correction)
 *
 * The complete old joint-lane corpus leaves this as the sole changed FIRC
 * survivor.  The hardware-blind h185 Skylake capture validates it on both
 * lanes and rejects the away/odd alternatives.  It is enabled only for the
 * wide family where h184 observes a changed architectural result.
 */
/*
 * evaluate the four-term P6 table polynomial with
 * the operation widths used by the exact Python oracle.  The reconstructed
 * P6 kernel uses four sine and four cosine coefficients
 * for every table cell.  Its highest-degree sine coefficient differs from
 * the P5 value at payload bit 60; without that change the four-term graph is
 * grossly incompatible with processor captures.
 */
static sf_t tangent_horner4(
    const p5c_t *c4, const p5c_t *c3, const p5c_t *c2, const p5c_t *c1, const wv_t *square)
{
    wv_t value = constant_round(c4, 67, P5_ROUND_RN);
    value = wide_mul(value, *square, 67, P5_ROUND_CHOP);
    value = wide_add_constant(value, c3, 67, P5_ROUND_RN, 64, P5_ROUND_RN);
    value = wide_mul(value, *square, 67, P5_ROUND_CHOP);
    value = wide_add_constant(value, c2, 67, P5_ROUND_RN, 64, P5_ROUND_RN);
    value = wide_mul(value, *square, 67, P5_ROUND_CHOP);
    value = wide_add_constant(value, c1, 67, P5_ROUND_RN, 64, P5_ROUND_RN);
    return wv_rn64(value);
}

/*
 * h260/h264 reconstructed FPTAN arithmetic.
 * Every ordinary multiply and subtract uses magnitude chop67, Horner adds
 * use RN64, and the multiply-class sine scaling uses RN64.  Table inputs
 * read the complete sine state through its 64-bit materialization before
 * reconstruction.  The final quotient is rounded directly under the x87
 * architectural rounding control.
 */
static wv_t fptan_horner6(const p5c_t *c6,
                          const p5c_t *c5,
                          const p5c_t *c4,
                          const p5c_t *c3,
                          const p5c_t *c2,
                          const p5c_t *c1,
                          wv_t square)
{
    const p5c_t *coefficients[] = {c5, c4, c3, c2, c1};
    wv_t value = {c6->sign, c6->exp2, c6->sig, 0};
    for (unsigned index = 0; index < 5; index++) {
        value = wide_mul(value, square, 67, P5_ROUND_CHOP);
        wv_t constant = {
            coefficients[index]->sign, coefficients[index]->exp2, coefficients[index]->sig, 0};
        value = wide_add(value, constant, 64, P5_ROUND_RN);
    }
    return value;
}

/* h260 shared reconstructed subtract class. */
static wv_t fptan_sub_chop67(wv_t left, wv_t right)
{
    right.sign ^= 1;
    return wide_add(left, right, 67, P5_ROUND_CHOP);
}

/* quadrant rotation for the FPTAN quotient pair. */
static void fptan_rotate(wv_t *sine, wv_t *cosine, int64_t signed_n)
{
    wv_t old_sine = *sine, old_cosine = *cosine;
    switch ((unsigned)signed_n & 3u) {
    case 0:
        break;
    case 1:
        *sine = old_cosine;
        *cosine = old_sine;
        cosine->sign ^= 1;
        break;
    case 2:
        sine->sign ^= 1;
        cosine->sign ^= 1;
        break;
    default:
        *sine = old_cosine;
        sine->sign ^= 1;
        *cosine = old_sine;
        break;
    }
}

/* h264 six-coefficient polynomial quotient pair. */
static void fptan_polynomial_values(
    wv_t magnitude, int residual_sign, int64_t signed_n, wv_t *numerator, wv_t *denominator)
{
    wv_t square = wide_mul(magnitude, magnitude, 67, P5_ROUND_CHOP);
    wv_t p = fptan_horner6(&P5S6_6, &P5S6_5, &P5S6_4, &P5S6_3, &P5S6_2, &P5S6_1, square);
    wv_t q = fptan_horner6(&P5C6_6, &P5C6_5, &P5C6_4, &P5C6_3, &P5C6_2, &P5C6_1, square);
    wv_t p_square = wide_mul(square, p, 64, P5_ROUND_RN);
    wv_t q_square = wide_mul(square, q, 67, P5_ROUND_CHOP);
    wv_t sine_tail = wide_mul(magnitude, p_square, 67, P5_ROUND_CHOP);
    wv_t sine = wide_add(magnitude, sine_tail, 67, P5_ROUND_CHOP);
    wv_t one = {0, -63, (u128)1 << 63, 0};
    wv_t cosine = wide_add(one, q_square, 67, P5_ROUND_CHOP);
    sine.sign ^= residual_sign ? 1 : 0;
    fptan_rotate(&sine, &cosine, signed_n);
    *numerator = sine;
    *denominator = cosine;
}

/* h260 four-coefficient table quotient pair. */
static void fptan_table_values(
    wv_t residual, int residual_sign, int64_t signed_n, wv_t *numerator, wv_t *denominator)
{
    int b;
    {
        /* Round 66: exact top-3-bit lane slice — the FPTAN twin of
         * the Round-62 trig fix.  The double-precision classifier
         * below misrounds the top ~2^-55 sliver under each interior
         * lane boundary (5/16, 3/8, 7/16, 1/2, 5/8, 3/4) into the
         * next lane (i7 hardware probes, 2026-08-15). */
        int rw = uint128_width(residual.sig);
        int rexp = residual.e2 + rw - 1;
        int lane = (int)(u128)(residual.sig >> (rw - 3)) - 4;
        if (rexp <= -2) {
            b = 18 + 4 * lane;
        } else {
            if (lane > 2)
                lane = 2;
            b = 36 + 8 * lane;
        }
    }
    int table_index = 0;
    while (P5TAB[table_index].b != b)
        table_index++;

    int shift = -6 - residual.e2;
    __int128 difference = (__int128)residual.sig - (__int128)((u128)b << shift);
    wv_t a = {(uint8_t)(difference < 0),
              residual.e2,
              difference < 0 ? (u128)(-difference) : (u128)difference,
              0};
    wv_t square = wide_mul(a, a, 67, P5_ROUND_CHOP);
    p5c_t p6s4_4 = P5S4_4;
    p6s4_4.sig -= (u128)1 << 60;
    sf_t p = tangent_horner4(&p6s4_4, &P5S4_3, &P5S4_2, &P5S4_1, &square);
    sf_t q = tangent_horner4(&P5C4_4, &P5C4_3, &P5C4_2, &P5C4_1, &square);
    wv_t p_state = {p.sign, p.exp - 63, (u128)p.sig, 0};
    wv_t q_state = {q.sign, q.exp - 63, (u128)q.sig, 0};
    wv_t p_square = wide_mul(p_state, square, 67, P5_ROUND_CHOP);
    wv_t sine_tail = wide_mul(p_square, a, 67, P5_ROUND_CHOP);
    wv_t sine_state = wide_add(a, sine_tail, 64, P5_ROUND_RN);
    wv_t cosine_tail = wide_mul(q_state, square, 64, P5_ROUND_RN);

    wv_t table_sine = {
        P5TAB[table_index].sinT.sign, P5TAB[table_index].sinT.exp2, P5TAB[table_index].sinT.sig, 0};
    wv_t table_cosine = {
        P5TAB[table_index].cosT.sign, P5TAB[table_index].cosT.exp2, P5TAB[table_index].cosT.sig, 0};
    wv_t negative_sine = sine_state;
    wv_t negative_table_sine = table_sine;
    negative_sine.sign ^= 1;
    negative_table_sine.sign ^= 1;

    wv_t denominator_partial =
        fptan_sub_chop67(wide_mul(negative_table_sine, negative_sine, 67, P5_ROUND_CHOP),
                         wide_mul(table_cosine, cosine_tail, 67, P5_ROUND_CHOP));
    wv_t cosine = fptan_sub_chop67(table_cosine, denominator_partial);
    wv_t numerator_partial =
        fptan_sub_chop67(wide_mul(table_cosine, negative_sine, 67, P5_ROUND_CHOP),
                         wide_mul(table_sine, cosine_tail, 67, P5_ROUND_CHOP));
    wv_t sine = fptan_sub_chop67(table_sine, numerator_partial);
    sine.sign ^= residual_sign ? 1 : 0;
    fptan_rotate(&sine, &cosine, signed_n);
    *numerator = sine;
    *denominator = cosine;
}

/* exact final quotient with architectural RC. */
static sf_t fptan_final_divide(wv_t numerator, wv_t denominator, sf_rc_t rc)
{
    int sign = numerator.sign ^ denominator.sign;
    if (!numerator.sig)
        return sf_zero(sign);
    if (!denominator.sig)
        return (sf_t){SF_INF, (uint8_t)sign, 0, 0};

    int numerator_width = uint128_width(numerator.sig);
    int denominator_width = uint128_width(denominator.sig);
    int ratio_exponent = numerator_width - denominator_width;
    if (ratio_exponent >= 0) {
        if (numerator.sig < (denominator.sig << ratio_exponent))
            ratio_exponent--;
    } else if ((numerator.sig << -ratio_exponent) < denominator.sig) {
        ratio_exponent--;
    }

    u128 normalized_numerator = numerator.sig;
    u128 normalized_denominator = denominator.sig;
    if (ratio_exponent >= 0)
        normalized_denominator <<= ratio_exponent;
    else
        normalized_numerator <<= -ratio_exponent;
    u128 remainder = normalized_numerator - normalized_denominator;
    u128 significand = (u128)1 << 63;
    for (int bit = 62; bit >= 0; bit--) {
        remainder <<= 1;
        if (remainder >= normalized_denominator) {
            remainder -= normalized_denominator;
            significand |= (u128)1 << bit;
        }
    }

    int increment = 0;
    if (rc == SF_RN) {
        u128 doubled = remainder << 1;
        increment = doubled > normalized_denominator ||
                    (doubled == normalized_denominator && (significand & 1));
    } else if (rc == SF_RD) {
        increment = sign && remainder;
    } else if (rc == SF_RU) {
        increment = !sign && remainder;
    }
    int32_t exponent = ratio_exponent + numerator.e2 - denominator.e2;
    if (increment) {
        significand++;
        if (significand == ((u128)1 << 64)) {
            significand >>= 1;
            exponent++;
        }
    }
    return (sf_t){SF_FIN, (uint8_t)sign, exponent, (uint64_t)significand};
}

/* complete finite/special FPTAN path selection. */
fsincos_status_t fptan_core(sf_t x, sf_rc_t rc, sf_t *out)
{
    if (x.cls == SF_NAN) {
        *out = x;
        out->sig |= 0x4000000000000000ull;
        return FSINCOS_OK;
    }
    if (x.cls == SF_INF) {
        *out = sf_qnan();
        return FSINCOS_OK;
    }
    if (sf_is_zero(&x)) {
        *out = x;
        return FSINCOS_OK;
    }
    if (x.exp >= 63)
        return FSINCOS_C2;

    sf_t r, c;
    int64_t signed_n;
    sf_t magnitude = sf_abs(&x);
    if (sf_lt(&magnitude, &PI_BY_4)) {
        if (x.exp < -68) {
            *out = x;
            return FSINCOS_OK;
        }
        r = x;
        c = ZERO;
        signed_n = 0;
    } else {
        /* h403: the same literal exact division as the FSIN/FCOS
         * operation-class reduction.  The reciprocal seed diverges from it
         * only on the 18 known large-argument residual inputs (zero
         * divergence over the sweep/dense corpora), and the exact quotient
         * removes all 25 of their result differences. */
        uint64_t n_magnitude = reduce_quotient(x.sig, x.exp);
        signed_n = x.sign ? -(int64_t)n_magnitude : (int64_t)n_magnitude;
        reduce_remainder(&x, n_magnitude, &r, &c);
        if (r.cls != SF_FIN)
            return FSINCOS_C2;
    }

    wv_t residual = reduced_to_wide(&r, &c);
    int residual_sign = residual.sign;
    residual.sign = 0;
    wv_t numerator, denominator;
    int residual_exponent = residual.sig ? residual.e2 + uint128_width(residual.sig) - 1 : -16383;
    if (residual_exponent <= -3) {
        fptan_polynomial_values(residual, residual_sign, signed_n, &numerator, &denominator);
    } else {
        fptan_table_values(residual, residual_sign, signed_n, &numerator, &denominator);
    }
    *out = fptan_final_divide(numerator, denominator, rc);
    return FSINCOS_OK;
}

x87t_error
x87t_fptan(const x87t_context *context, x87t_raw80 x, const x87t_control *control, x87t_result *out)
{
    x87t_error error = validate_call(context, control, out);
    if (error)
        return error;
    /* The historical decoder loses unsupported encodings. Preserve the
     * original bits and reject this unimplemented operand class explicitly. */
    if (raw80_classify(x) == RAW_UNSUPPORTED)
        return X87T_OUTSIDE_SCOPE;
    x87t_result result;
    result_begin(&result, X87T_REPLACE_ST0_PUSH);
    sf_t input = sf_from_parts(x.se >> 15, x.se & 0x7fff, x.sig), value;
    if (fptan_core(input, (sf_rc_t)control->rounding, &value) == FSINCOS_C2) {
        result_range(&result);
    } else {
        sf_to_x87(&value, &result.primary.se, &result.primary.sig);
        /* NaN/indefinite results push a second copy of the result
         * rather than exact one. */
        result.pushed = (result.primary.se & 0x7fff) == 0x7fff
                            ? result.primary
                            : (x87t_raw80){0x3fff, UINT64_C(0x8000000000000000)};
        result.values |= X87T_PUSHED;
        result.cc_known = X87T_C2;
    }
    *out = result;
    return X87T_OK;
}
