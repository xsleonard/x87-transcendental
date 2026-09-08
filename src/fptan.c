/* FPTAN evaluates its own quotient pair before final division. */
/*
 * Compute tan(x). For finite |x| >= 2^63, set C2 and leave the stack unchanged.
 * Handle zeros, NaNs, infinities and unsupported encodings before the main
 * calculation. Denormals and pseudo-denormals can be evaluated too. The
 * emulator checks for stack faults and handles pending exceptions.
 *
 * Reduce x = n*M + u, where M is the stored 66-bit approximation to pi/2.
 * Keep the remainder u exactly as r+c. For |u| < 1/4, use sine and cosine
 * polynomials. Otherwise choose a table angle t and set a=|u|-t. Then
 * sin(t+a)=sin(t)cos(a)+cos(t)sin(a),
 * cos(t+a)=cos(t)cos(a)-sin(t)sin(a), and tan(x)=sin(x)/cos(x).
 * The quadrant n mod 4 determines the signs and whether to swap sine and
 * cosine. The code rounds the polynomial and table calculations at each
 * step shown below. Using a more precise pi/2 would also change the result.
 *
 * Keep the internal sine and cosine values for the final division. Dividing
 * the separately rounded FSIN and FCOS outputs would lose needed bits.
 * Round the exact ratio once to 64 bits using guest RC. Set C1 if rounding
 * increases its magnitude. Guest PC does not change the internal widths.
 * The public function sets exception flags and normally pushes exact +1.
 * Tests distinguish products and subtractions chopped to 67 bits (CHOP67)
 * from additions rounded to 64 bits, nearest with ties to even (RN64).
 * The sine value must also be rounded to RN64 before table reconstruction.
 */
#include "internal/numeric.h"

/* The FIRC discussion below describes an older reconstruction method.
 * fptan_table_values now uses a sequence of rounded subtractions to build
 * its numerator and denominator. tangent_horner4 evaluates the polynomials. */
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
    /* For v=square, evaluate c1 + v*(c2 + v*(c3 + v*c4)). Round each
     * coefficient to 67 bits, nearest with ties to even. Chop each product
     * to 67 bits and round each sum to RN64. The final conversion to sf_t
     * also uses RN64 and is implemented with integer arithmetic. */
    wv_t value = x87t_internal_constant_round(c4, 67, P5_ROUND_RN);
    value = x87t_internal_wide_mul(value, *square, 67, P5_ROUND_CHOP);
    value = x87t_internal_wide_add_constant(value, c3, 67, P5_ROUND_RN, 64, P5_ROUND_RN);
    value = x87t_internal_wide_mul(value, *square, 67, P5_ROUND_CHOP);
    value = x87t_internal_wide_add_constant(value, c2, 67, P5_ROUND_RN, 64, P5_ROUND_RN);
    value = x87t_internal_wide_mul(value, *square, 67, P5_ROUND_CHOP);
    value = x87t_internal_wide_add_constant(value, c1, 67, P5_ROUND_RN, 64, P5_ROUND_RN);
    return x87t_internal_wv_rn64(value);
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
        value = x87t_internal_wide_mul(value, square, 67, P5_ROUND_CHOP);
        wv_t constant = {
            coefficients[index]->sign, coefficients[index]->exp2, coefficients[index]->sig, 0};
        value = x87t_internal_wide_add(value, constant, 64, P5_ROUND_RN);
    }
    return value;
}

/* h260 shared reconstructed subtract class. */
static wv_t fptan_sub_chop67(wv_t left, wv_t right)
{
    right.sign ^= 1;
    return x87t_internal_wide_add(left, right, 67, P5_ROUND_CHOP);
}

/* quadrant rotation for the FPTAN quotient pair. */
/* For n mod 4 = 0,1,2,3, (S,C) becomes (S,C),(C,-S),(-S,-C),(-C,S).
 * Swapping values and changing their signs preserves all significand bits. */
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
/* magnitude is |u| < 1/4. Compute sine and cosine for this nonnegative value,
 * then apply residual_sign and rotate into the original quadrant.
 * With v=|u|^2, use sin(|u|) ~= |u| + |u|^3*p and cos(|u|) ~= 1 + v*q.
 * Both p and q have six coefficients in ascending powers of v.
 * The code chops square to 67 bits. p_square uses RN64(square*p), while
 * q_square and both completed sine and cosine values use CHOP67. */
static void fptan_polynomial_values(
    wv_t magnitude, int residual_sign, int64_t signed_n, wv_t *numerator, wv_t *denominator)
{
    wv_t square = x87t_internal_wide_mul(magnitude, magnitude, 67, P5_ROUND_CHOP);
    wv_t p = fptan_horner6(&x87t_internal_P5S6_6, &x87t_internal_P5S6_5, &x87t_internal_P5S6_4, &x87t_internal_P5S6_3, &x87t_internal_P5S6_2, &x87t_internal_P5S6_1, square);
    wv_t q = fptan_horner6(&x87t_internal_P5C6_6, &x87t_internal_P5C6_5, &x87t_internal_P5C6_4, &x87t_internal_P5C6_3, &x87t_internal_P5C6_2, &x87t_internal_P5C6_1, square);
    wv_t p_square = x87t_internal_wide_mul(square, p, 64, P5_ROUND_RN);
    wv_t q_square = x87t_internal_wide_mul(square, q, 67, P5_ROUND_CHOP);
    wv_t sine_tail = x87t_internal_wide_mul(magnitude, p_square, 67, P5_ROUND_CHOP);
    wv_t sine = x87t_internal_wide_add(magnitude, sine_tail, 67, P5_ROUND_CHOP);
    wv_t one = {0, -63, (u128)1 << 63, 0};
    wv_t cosine = x87t_internal_wide_add(one, q_square, 67, P5_ROUND_CHOP);
    sine.sign ^= residual_sign ? 1 : 0;
    fptan_rotate(&sine, &cosine, signed_n);
    *numerator = sine;
    *denominator = cosine;
}

/* h260 four-coefficient table quotient pair. */
/* residual is |u| in [1/4,M/2). Set t=b/64 and a=|u|-t exactly.
 * The lower binade has [1/4,5/16),[5/16,3/8),[3/8,7/16),[7/16,1/2),
 * with b=18,22,26,30. The upper has [1/2,5/8),[5/8,3/4),[3/4,M/2),
 * with b=36,44,52. Find that b in P5TAB to get table_index; the rows are
 * stored in a different order from the cells. At a boundary, use the higher
 * cell. shift puts b/64 at the same binary scale as residual.sig. The
 * remainder's width and scale allow this shift and subtraction to be exact. */
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
        /* The "classifier below" mentioned above has been replaced by this
         * integer calculation. Converting the input to binary64 would lose
         * bits needed to choose the cell near a boundary. */
        int rw = x87t_internal_uint128_width(residual.sig);
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
    while (x87t_internal_P5TAB[table_index].b != b)
        table_index++;

    int shift = -6 - residual.e2;
    __int128 difference = (__int128)residual.sig - (__int128)((u128)b << shift);
    wv_t a = {(uint8_t)(difference < 0),
              residual.e2,
              difference < 0 ? (u128)(-difference) : (u128)difference,
              0};
    wv_t square = x87t_internal_wide_mul(a, a, 67, P5_ROUND_CHOP);
    p5c_t p6s4_4 = x87t_internal_P5S4_4;
    p6s4_4.sig -= (u128)1 << 60;
    sf_t p = tangent_horner4(&p6s4_4, &x87t_internal_P5S4_3, &x87t_internal_P5S4_2, &x87t_internal_P5S4_1, &square);
    sf_t q = tangent_horner4(&x87t_internal_P5C4_4, &x87t_internal_P5C4_3, &x87t_internal_P5C4_2, &x87t_internal_P5C4_1, &square);
    wv_t p_state = {p.sign, p.exp - 63, (u128)p.sig, 0};
    wv_t q_state = {q.sign, q.exp - 63, (u128)q.sig, 0};
    wv_t p_square = x87t_internal_wide_mul(p_state, square, 67, P5_ROUND_CHOP);
    wv_t sine_tail = x87t_internal_wide_mul(p_square, a, 67, P5_ROUND_CHOP);
    wv_t sine_state = x87t_internal_wide_add(a, sine_tail, 64, P5_ROUND_RN);
    wv_t cosine_tail = x87t_internal_wide_mul(q_state, square, 64, P5_ROUND_RN);

    /* sine_state approximates sin(a), and cosine_tail approximates cos(a)-1.
     * Both have been rounded to RN64. With S=table_sine and C=table_cosine,
     * the reconstruction formula is
     *     denominator = C + C*cosine_tail - S*sine_state,
     *     numerator   = S + S*cosine_tail + C*sine_state.
     * The negative temporaries let us compute each line with two subtractions.
     * Chop every product and subtraction to 67 bits. Combining them into one
     * fused sum would keep different bits and could change the quotient. */
    wv_t table_sine = {
        x87t_internal_P5TAB[table_index].sinT.sign, x87t_internal_P5TAB[table_index].sinT.exp2, x87t_internal_P5TAB[table_index].sinT.sig, 0};
    wv_t table_cosine = {
        x87t_internal_P5TAB[table_index].cosT.sign, x87t_internal_P5TAB[table_index].cosT.exp2, x87t_internal_P5TAB[table_index].cosT.sig, 0};
    wv_t negative_sine = sine_state;
    wv_t negative_table_sine = table_sine;
    negative_sine.sign ^= 1;
    negative_table_sine.sign ^= 1;

    wv_t denominator_partial =
        fptan_sub_chop67(x87t_internal_wide_mul(negative_table_sine, negative_sine, 67, P5_ROUND_CHOP),
                         x87t_internal_wide_mul(table_cosine, cosine_tail, 67, P5_ROUND_CHOP));
    wv_t cosine = fptan_sub_chop67(table_cosine, denominator_partial);
    wv_t numerator_partial =
        fptan_sub_chop67(x87t_internal_wide_mul(table_cosine, negative_sine, 67, P5_ROUND_CHOP),
                         x87t_internal_wide_mul(table_sine, cosine_tail, 67, P5_ROUND_CHOP));
    wv_t sine = fptan_sub_chop67(table_sine, numerator_partial);
    sine.sign ^= residual_sign ? 1 : 0;
    fptan_rotate(&sine, &cosine, signed_n);
    *numerator = sine;
    *denominator = cosine;
}

/* exact final quotient with architectural RC. */
/* Both inputs have at most 67 significand bits, so the shifts and doubled
 * remainders fit u128. Normalize their significand ratio to [1,2). Its first
 * bit is 1; long division then produces the next 63 bits and an exact remainder.
 * Compare twice that remainder with the denominator to round to nearest,
 * breaking ties toward an even low bit. Directed rounding also uses the sign.
 * Only the final quotient is rounded. The core has already set c1=0 for
 * the early returns when either input is zero. The public function sets flags. */
static sf_t fptan_final_divide(wv_t numerator, wv_t denominator, sf_rc_t rc, int *c1)
{
    int sign = numerator.sign ^ denominator.sign;
    if (!numerator.sig)
        return x87t_internal_sf_zero(sign);
    if (!denominator.sig)
        return (sf_t){SF_INF, (uint8_t)sign, 0, 0};

    int numerator_width = x87t_internal_uint128_width(numerator.sig);
    int denominator_width = x87t_internal_uint128_width(denominator.sig);
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
    *c1 = increment;
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
trig_status_t x87t_internal_fptan_core(sf_t x, sf_rc_t rc, sf_t *out, int *c1)
{
    *c1 = 0;
    if (x.cls == SF_NAN) {
        *out = x;
        out->sig |= 0x4000000000000000ull;
        return TRIG_OK;
    }
    if (x.cls == SF_INF) {
        *out = x87t_internal_sf_qnan();
        return TRIG_OK;
    }
    if (x87t_internal_sf_is_zero(&x)) {
        *out = x;
        return TRIG_OK;
    }
    if (x.exp >= 63)
        return TRIG_RANGE;

    sf_t r, c;
    int64_t signed_n;
    sf_t magnitude = x87t_internal_sf_abs(&x);
    if (x87t_internal_sf_lt(&magnitude, &x87t_internal_PI_BY_4)) {
        /* Compare with the stored PI_BY_4 value. For a direct input with
         * |x| < 2^-68, return x with C1=0. Exactly 2^-68 uses the polynomial.
         * Reduced arguments do not use this bypass. */
        if (x.exp < -68) {
            *out = x;
            return TRIG_OK;
        }
        r = x;
        c = x87t_internal_ZERO;
        signed_n = 0;
    } else {
        /* h403: the same literal exact division as the FSIN/FCOS
         * operation-class reduction.  The reciprocal seed diverges from it
         * only on the 18 known large-argument residual inputs (zero
         * divergence over the sweep/dense corpora), and the exact quotient
         * removes all 25 of their result differences. */
        uint64_t n_magnitude = x87t_internal_reduce_quotient(x.sig, x.exp);
        signed_n = x.sign ? -(int64_t)n_magnitude : (int64_t)n_magnitude;
        x87t_internal_reduce_remainder(&x, n_magnitude, &r, &c);
        if (r.cls != SF_FIN)
            return TRIG_RANGE;
    }

    wv_t residual = x87t_internal_reduced_to_wide(&r, &c);
    int residual_sign = residual.sign;
    residual.sign = 0;
    wv_t numerator, denominator;
    int residual_exponent = residual.sig ? residual.e2 + x87t_internal_uint128_width(residual.sig) - 1 : -16383;
    /* exponent <= -3 means |u| < 1/4; exactly 1/4 takes the table.
     * Zero takes the polynomial and gives sine=0 before quadrant rotation. */
    if (residual_exponent <= -3) {
        fptan_polynomial_values(residual, residual_sign, signed_n, &numerator, &denominator);
    } else {
        fptan_table_values(residual, residual_sign, signed_n, &numerator, &denominator);
    }
    *out = fptan_final_divide(numerator, denominator, rc, c1);
    return TRIG_OK;
}

x87t_error
x87t_fptan(const x87t_context *context, x87t_raw80 x, const x87t_control *control, x87t_result *out)
{
    x87t_error error = x87t_internal_validate_call(context, control, out);
    if (error)
        return error;
    x87t_result result;
    x87t_internal_result_begin(&result, X87T_REPLACE_ST0_PUSH);
    /* Unsupported encodings must be rejected by the instruction before the
     * numerical decoder can normalize away their original class. */
    if (x87t_internal_raw80_classify(x) == RAW_UNSUPPORTED) {
        result.primary = result.pushed = x87t_internal_X87_INDEFINITE;
        result.values |= X87T_PUSHED;
        result.exceptions = X87T_IE;
        result.cc_known = X87T_C1 | X87T_C2;
        x87t_internal_result_finish(&result, control);
        *out = result;
        return X87T_OK;
    }
    sf_t input = x87t_internal_sf_from_parts(x.se >> 15, x.se & 0x7fff, x.sig), value;
    int c1;
    if (x87t_internal_fptan_core(input, (sf_rc_t)control->rounding, &value, &c1) == TRIG_RANGE) {
        x87t_internal_result_range(&result);
    } else {
        x87t_internal_sf_to_x87(&value, &result.primary.se, &result.primary.sig);
        /* NaN/indefinite results push a second copy of the result
         * rather than exact one. */
        result.pushed = (result.primary.se & 0x7fff) == 0x7fff
                            ? result.primary
                            : (x87t_raw80){0x3fff, UINT64_C(0x8000000000000000)};
        result.values |= X87T_PUSHED;
        result.cc_known = X87T_C1 | X87T_C2;
        result.cc = c1 ? X87T_C1 : 0;
    }
    result.exceptions = x87t_internal_trig_flags(x, result.completion == X87T_RANGE_RETURN, 1);
    /* Set PE for completed finite nonzero inputs. Denormals and
     * pseudo-denormals also set DE; only true denormals set UE. These flags
     * depend on the original input encoding, separately from quotient C1.
     * For unmasked UE, scale the tiny input before writing the result.
     * result_finish cancels the write and push for unmasked IE or DE, but
     * allows them for unmasked UE or PE. A C2 return leaves the stack alone. */
    x87t_internal_wrap_trig_underflow(x, &result, control);
    x87t_internal_result_finish(&result, control);
    *out = result;
    return X87T_OK;
}
