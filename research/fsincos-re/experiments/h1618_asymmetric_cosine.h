/* H1618 analysis-only fixed cosine candidate. Included into an in-memory
 * copy of the canonical translation unit by the experiment builder; the
 * installed emulator source is not edited. No operand ledger or selector.
 */
#ifndef G_H1618_ASYMMETRIC_COSINE
#define G_H1618_ASYMMETRIC_COSINE 0
#endif

static int h1618_cosine_scope(wv_t magnitude)
{
    if (!magnitude.sig || magnitude.sign) return 0;
    int width = u128_width(magnitude.sig);
    if (magnitude.e2 + width - 1 != -3) return 0;
    /* H1617's proved equivalence assumes a numerical 64-bit input, not
     * necessarily a 64-bit container. Exact reduced aliases may be padded. */
    u128 odd = magnitude.sig;
    while (!(odd & 1)) odd >>= 1;
    return u128_width(odd) <= 64;
}

static wv_t h1618_literal(const p5c_t *constant)
{
    return (wv_t){ constant->sign, constant->exp2, constant->sig, 0 };
}

static wv_t h1618_add(wv_t left, wv_t right, int bits, p5_round_t mode)
{
    /* Use the plain accumulator operation directly: none of the incumbent
     * conditional FADD-history patches is part of the fixed candidate. */
    int32_t scale = left.e2 < right.e2 ? left.e2 : right.e2;
    u256 accumulator = { 0, 0 };
    acc_add_product(&accumulator, left.sign, left.sig, 1, left.e2, scale);
    acc_add_product(&accumulator, right.sign, right.sig, 1, right.e2, scale);
    return acc_round_bits_mode(accumulator, scale, bits, mode);
}

static void h1618_trace_value(const char *name, wv_t value)
{
    fprintf(stderr, " %s=" DIWF, name, DIW(value));
}

static sf_t h1618_cosine(wv_t magnitude, int neg_out, sf_rc_t rc)
{
    wv_t square = p5_wv_mul_round(magnitude, magnitude, 67, P5_ROUND_CHOP);
    wv_t square64 = p5_wv_mul_round(
        square, (wv_t){ 0, 0, 1, 0 }, 64, P5_ROUND_CHOP);
    wv_t fourth = p5_wv_mul_round(square, square64, 67, P5_ROUND_CHOP);

    wv_t negative_mul1 = p5_wv_mul_round(
        fourth, h1618_literal(&P5C6_5), 67, P5_ROUND_CHOP);
    wv_t negative_add1 = h1618_add(
        h1618_literal(&P5C6_3), negative_mul1, 64, P5_ROUND_RN);
    wv_t negative_mul2 = p5_wv_mul_round(
        fourth, negative_add1, 67, P5_ROUND_CHOP);
    wv_t negative_factor = h1618_add(
        h1618_literal(&P5C6_1), negative_mul2, 64, P5_ROUND_RN);

    wv_t positive_mul1 = p5_wv_mul_round(
        fourth, h1618_literal(&P5C6_6), 67, P5_ROUND_CHOP);
    wv_t positive_add1 = h1618_add(
        h1618_literal(&P5C6_4), positive_mul1, 64, P5_ROUND_RN);
    wv_t positive_mul2 = p5_wv_mul_round(
        fourth, positive_add1, 67, P5_ROUND_CHOP);
    wv_t positive_factor = h1618_add(
        h1618_literal(&P5C6_2), positive_mul2, 64, P5_ROUND_RN);

    wv_t left = p5_wv_mul_round(square, negative_factor, 67, P5_ROUND_CHOP);
    wv_t right = p5_wv_mul_round(fourth, positive_factor, 67, P5_ROUND_CHOP);
    wv_t correction = h1618_add(left, right, 67, P5_ROUND_CHOP);
    int32_t scale = correction.e2 < 0 ? correction.e2 : 0;
    u256 final = { 0, 0 };
    acc_add_product(&final, 0, 1, 1, 0, scale);
    acc_add_product(&final, correction.sign, correction.sig, 1, correction.e2, scale);
    sf_t output = acc_round64_rc(final, scale, neg_out, rc);
    if (g_dump_internals) {
        fprintf(stderr, "DI_H1618 neg=%d rc=%d", neg_out, (int)rc);
        h1618_trace_value("magnitude", magnitude);
        h1618_trace_value("square", square);
        h1618_trace_value("fourth", fourth);
        h1618_trace_value("negative_mul1", negative_mul1);
        h1618_trace_value("negative_add1", negative_add1);
        h1618_trace_value("negative_mul2", negative_mul2);
        h1618_trace_value("negative_factor", negative_factor);
        h1618_trace_value("positive_mul1", positive_mul1);
        h1618_trace_value("positive_add1", positive_add1);
        h1618_trace_value("positive_mul2", positive_mul2);
        h1618_trace_value("positive_factor", positive_factor);
        h1618_trace_value("left", left);
        h1618_trace_value("right", right);
        h1618_trace_value("correction", correction);
        fprintf(stderr, "\n");
    }
    return output;
}
