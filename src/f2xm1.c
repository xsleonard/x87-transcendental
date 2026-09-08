/* F2XM1: tiny, interleaved polynomial and table evaluation. */
#include "internal/numeric.h"
#include "constants/f2xm1.h"

/* expose a constant as an exact wide carrier. */
static wv_t f2xm1_constant(const p5c_t *constant)
{
    return (wv_t){constant->sign, constant->exp2, constant->sig, 0};
}

/* h254/h258 ordinary-multiply class. */
static wv_t f2xm1_mul_chop67(wv_t left, wv_t right)
{
    return x87t_internal_wide_mul(left, right, 67, P5_ROUND_CHOP);
}

/* h254/h258 multiply-class materialization. */
static wv_t f2xm1_mul_rn64(wv_t left, wv_t right)
{
    return x87t_internal_wide_mul(left, right, 64, P5_ROUND_RN);
}

/* h254/h258 ordinary-add class. */
static wv_t f2xm1_add_rn64(wv_t left, wv_t right)
{
    return x87t_internal_wide_add(left, right, 64, P5_ROUND_RN);
}

/* exact constant input followed by ordinary FADD. */
static wv_t f2xm1_add_constant_rn64(wv_t value, const p5c_t *constant)
{
    return f2xm1_add_rn64(value, f2xm1_constant(constant));
}

/* final add with architectural rounding control. */
static sf_t f2xm1_final_add(wv_t left, wv_t right, sf_rc_t rc, int *c1)
{
    int32_t scale = left.e2 < right.e2 ? left.e2 : right.e2;
    u256 accumulator = {0, 0};
    x87t_internal_acc_add_product(&accumulator, left.sign, left.sig, 1, left.e2, scale);
    x87t_internal_acc_add_product(&accumulator, right.sign, right.sig, 1, right.e2, scale);
    return x87t_internal_acc_round64_meta(accumulator, scale, 0, rc, c1);
}

/* final multiply with architectural rounding. */
static sf_t f2xm1_final_multiply(wv_t value, const p5c_t *constant, sf_rc_t rc, int *c1)
{
    int32_t scale = value.e2 + constant->exp2;
    u256 accumulator = {0, 0};
    x87t_internal_acc_add_product(
        &accumulator, value.sign ^ constant->sign, value.sig, constant->sig, scale, scale);
    return x87t_internal_acc_round64_meta(accumulator, scale, 0, rc, c1);
}

/* Round the exact tiny-path product once at the raw80 spacing.
 * In the lowest input binade and below, that spacing is 2^-16445.
 * Applying significand rounding before a truncating store loses this
 * rounding decision for native subnormal results. Direct rounding at
 * the destination spacing also makes the subsequent store exact. */
static sf_t f2xm1_tiny_raw80(sf_t x, sf_rc_t rc, int *c1)
{
    int32_t scale = x.exp - 63 + F2_LN2.exp2;
    int shift = -16445 - scale;
    u256 magnitude = {0, 0};
    x87t_internal_acc_add_product(&magnitude, 0, x.sig, F2_LN2.sig, scale, scale);
    uint64_t kept;
    int guard, sticky;
    if (shift >= 128) {
        kept = (uint64_t)(magnitude.hi >> (shift - 128));
        if (shift == 128) {
            guard = (int)((magnitude.lo >> 127) & 1);
            sticky = !!(magnitude.lo & (((u128)1 << 127) - 1));
        } else {
            guard = (int)((magnitude.hi >> (shift - 129)) & 1);
            sticky = !!magnitude.lo || !!(magnitude.hi & (((u128)1 << (shift - 129)) - 1));
        }
    } else {
        kept = (uint64_t)((magnitude.hi << (128 - shift)) | (magnitude.lo >> shift));
        guard = (int)((magnitude.lo >> (shift - 1)) & 1);
        sticky = !!(magnitude.lo & (((u128)1 << (shift - 1)) - 1));
    }
    int increment =
        rc == SF_RN ? guard && (sticky || (kept & 1))
                    : ((rc == SF_RU && !x.sign) || (rc == SF_RD && x.sign)) && (guard || sticky);
    *c1 = increment;
    kept += increment;
    return x87t_internal_sf_from_parts(x.sign, kept >= (1ull << 63) ? 1 : 0, kept);
}

/* reconstructed six-coefficient table polynomial. */
static sf_t f2xm1_table_path(sf_t x, sf_rc_t rc, int *c1)
{
    wv_t input = {x.sign, x.exp - 63, x.sig, 0};
    unsigned lane = (unsigned)((x.sig - (1ull << 63)) >> 59);
    unsigned index = (x.sign ? 32u : 0u) + (x.exp == -2 ? 16u : 0u) + lane;
    unsigned numerator = x.exp == -2 ? 33u + 2u * lane : 66u + 4u * lane;
    wv_t negative_anchor = {(uint8_t)(x.sign ^ 1), -7, numerator, 0};
    wv_t residual = f2xm1_add_rn64(input, negative_anchor);
    wv_t z = f2xm1_mul_rn64(f2xm1_constant(&F2_LN2), residual);
    wv_t z2 = f2xm1_mul_chop67(z, z);

    wv_t even =
        f2xm1_add_constant_rn64(f2xm1_mul_chop67(z2, f2xm1_constant(&F2_SHORT[4])), &F2_SHORT[2]);
    even = f2xm1_add_constant_rn64(f2xm1_mul_chop67(z2, even), &F2_SHORT[0]);
    even = f2xm1_add_rn64(z, f2xm1_mul_chop67(z2, even));

    wv_t odd =
        f2xm1_add_constant_rn64(f2xm1_mul_chop67(z2, f2xm1_constant(&F2_SHORT[5])), &F2_SHORT[3]);
    odd = f2xm1_add_constant_rn64(f2xm1_mul_chop67(z2, odd), &F2_SHORT[1]);
    odd = f2xm1_mul_chop67(z, f2xm1_mul_chop67(z2, odd));

    wv_t polynomial = f2xm1_add_rn64(even, odd);
    wv_t lookup = f2xm1_constant(&F2_TABLE[index]);
    wv_t one_plus_lookup = f2xm1_add_rn64(lookup, (wv_t){0, 0, 1, 0});
    wv_t scaled = f2xm1_mul_chop67(one_plus_lookup, polynomial);
    return f2xm1_final_add(lookup, scaled, rc, c1);
}

/* reconstructed eleven-coefficient long path. */
static sf_t f2xm1_long_path(sf_t x, sf_rc_t rc, int *c1)
{
    wv_t input = {x.sign, x.exp - 63, x.sig, 0};
    wv_t ln2 = f2xm1_constant(&F2_LN2);
    wv_t tmp1 = f2xm1_mul_chop67(ln2, input);
    wv_t tmp2 = f2xm1_mul_rn64(ln2, input);
    tmp2 = f2xm1_mul_chop67(tmp1, tmp2);

    wv_t tmp5 = f2xm1_mul_chop67(tmp2, f2xm1_constant(&F2_LONG[9]));
    wv_t tmp6 = f2xm1_mul_chop67(tmp2, f2xm1_constant(&F2_LONG[10]));
    tmp5 = f2xm1_add_constant_rn64(tmp5, &F2_LONG[7]);
    tmp6 = f2xm1_add_constant_rn64(tmp6, &F2_LONG[8]);
    tmp5 = f2xm1_mul_chop67(tmp2, tmp5);
    tmp6 = f2xm1_mul_chop67(tmp2, tmp6);
    tmp5 = f2xm1_add_constant_rn64(tmp5, &F2_LONG[5]);
    tmp6 = f2xm1_add_constant_rn64(tmp6, &F2_LONG[6]);
    tmp5 = f2xm1_mul_chop67(tmp2, tmp5);
    tmp6 = f2xm1_mul_chop67(tmp2, tmp6);
    tmp5 = f2xm1_add_constant_rn64(tmp5, &F2_LONG[3]);
    tmp6 = f2xm1_add_constant_rn64(tmp6, &F2_LONG[4]);
    tmp5 = f2xm1_mul_chop67(tmp2, tmp5);
    tmp6 = f2xm1_mul_chop67(tmp2, tmp6);
    tmp5 = f2xm1_add_constant_rn64(tmp5, &F2_LONG[1]);
    tmp6 = f2xm1_add_constant_rn64(tmp6, &F2_LONG[2]);
    tmp5 = f2xm1_mul_rn64(tmp2, tmp5);
    tmp6 = f2xm1_mul_rn64(tmp2, tmp6);
    tmp5 = f2xm1_mul_chop67(tmp1, tmp5);
    tmp6 = f2xm1_mul_chop67(tmp2, tmp6);
    wv_t tmp3 = f2xm1_mul_chop67(tmp2, f2xm1_constant(&F2_LONG[0]));
    tmp6 = f2xm1_add_rn64(tmp5, tmp6);
    tmp3 = f2xm1_add_rn64(tmp3, tmp6);
    return f2xm1_final_add(tmp1, tmp3, rc, c1);
}

/* complete finite-value F2XM1 path selection. */
sf_t x87t_internal_f2xm1_core(sf_t x, sf_rc_t rc, int *c1)
{
    *c1 = 0;
    if (x.cls == SF_NAN) { /* hardware quiets signaling NaNs */
        x.sig |= 0x4000000000000000ull;
        return x;
    }
    if (x.cls != SF_FIN || x87t_internal_sf_is_zero(&x))
        return x;
    if (x.exp > 0 || (x.exp == 0 && x.sig > (1ull << 63)))
        return x;
    if (x.exp == 0) {
        if (!x.sign)
            return x87t_internal_ONE;
        return (sf_t){SF_FIN, 1, -1, 1ull << 63};
    }
    if (x.exp >= -2)
        return f2xm1_table_path(x, rc, c1);
    if (x.exp >= -68)
        return f2xm1_long_path(x, rc, c1);
    if (x.exp <= -16382)
        return f2xm1_tiny_raw80(x, rc, c1);
    return f2xm1_final_multiply((wv_t){x.sign, x.exp - 63, x.sig, 0}, &F2_LN2, rc, c1);
}

x87t_error
x87t_f2xm1(const x87t_context *context, x87t_raw80 x, const x87t_control *control, x87t_result *out)
{
    x87t_error error = x87t_internal_validate_call(context, control, out);
    if (error)
        return error;
    raw_class kind = x87t_internal_raw80_classify(x);
    /* Infinity is outside the instruction's defined numerical domain. Keep
     * that policy explicit instead of inventing flags for a historical bypass. */
    if (kind == RAW_INFINITY)
        return X87T_OUTSIDE_SCOPE;
    x87t_result result;
    x87t_internal_result_begin(&result, X87T_REPLACE_ST0);
    result.cc_known = X87T_C1;
    if (kind == RAW_UNSUPPORTED) {
        result.primary = x87t_internal_X87_INDEFINITE;
        result.exceptions = X87T_IE;
    } else {
        sf_t input = x87t_internal_sf_from_parts(x.se >> 15, x.se & 0x7fff, x.sig);
        int c1;
        sf_t value = x87t_internal_f2xm1_core(input, (sf_rc_t)control->rounding, &c1);
        x87t_internal_sf_to_x87(&value, &result.primary.se, &result.primary.sig);
        result.cc = c1 ? X87T_C1 : 0;
        if (kind == RAW_SNAN)
            result.exceptions = X87T_IE;
        else if (kind != RAW_QNAN && kind != RAW_ZERO) {
            result.exceptions = X87T_PE;
            if (kind == RAW_DENORMAL || kind == RAW_PSEUDO)
                result.exceptions |= X87T_DE;
            /* Test the retained tiny product before raw80 rounding. A result
             * rounded up to minimum normal can still have UE (F0001/F0002). */
            if (input.exp <= -16382) {
                u256 product = x87t_internal_u128_mul_full(input.sig, F2_LN2.sig);
                int width = product.hi ? 128 + x87t_internal_uint128_width(product.hi)
                                       : x87t_internal_uint128_width(product.lo);
                if (input.exp - 63 + F2_LN2.exp2 + width - 1 < -16382)
                    result.exceptions |= X87T_UE;
            }
            if ((result.exceptions & X87T_UE) && !(control->exception_masks & X87T_UE)) {
                /* Adjust the exact product before final rounding. Subnormal
                 * masked storage may have discarded all significant bits. */
                value = f2xm1_final_multiply(
                    (wv_t){input.sign, input.exp - 63 + 24576, input.sig, 0},
                    &F2_LN2, (sf_rc_t)control->rounding, &c1);
                x87t_internal_sf_to_x87(&value, &result.primary.se, &result.primary.sig);
                result.cc = c1 ? X87T_C1 : 0;
            }
        }
    }
    x87t_internal_result_finish(&result, control);
    *out = result;
    return X87T_OK;
}
