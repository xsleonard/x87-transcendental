/* Compute y*log2(x) for FYL2X or y*log2(1+x) for FYL2XP1, including C1
 * and exception flags. FYL2X requires positive finite x for its numerical
 * calculation; FYL2XP1 limits finite x to |x| <= 1-sqrt(1/2). The raw80
 * dispatcher handles special encodings and zeros before calling logarithm.
 * The caller supplies two valid stack entries and handles pending exceptions.
 *
 * When the logarithm is close to zero, approximate it directly through
 * atanh. Otherwise, normalize the input, select one of 32 table midpoints,
 * and approximate the difference from that midpoint's logarithm. Add the
 * two parts of the table logarithm and the input's binary exponent. Finally,
 * multiply the computed logarithm by y exactly and round to raw80 using
 * guest RC.
 *
 * Let L = 1/ln(2). For positive a and b and binary exponent E,
 *     log2(a*2^E) = E + log2(a)
 *     log2(a/b) = 2*L*atanh((a-b)/(a+b)).
 * These are real-number identities. The code uses stored approximations
 * to L and rounds each result in mul67, add64 and add67; rearranging those
 * operations can change the result. Their widths and rounding modes are
 * independent of guest PC and RC. The final product is kept exact until
 * raw80 rounding, which determines the result bits and C1. The wrapper
 * then applies exception masks and reports whether to write ST(1) and pop.
 */
/* Source-guided Skylake FYL2X/FYL2XP1 numerical reconstruction.
 * Explicit finite integer arithmetic: no native logarithms, host floats or operand ledger.
 * Ken Shirriff's public P5 ROM supplies literal coefficients and split tables;
 * four transcription corrections are independently derived from log2 anchors
 * and corroborated by the public Goldmont ROM's upper-64-bit projections.
 * Rounding and operation order transfer from the public Goldmont listing,
 * tested against frozen Skylake captures. The arithmetic classes, table
 * reconstruction and exception rules are described at their use sites below.
 * The exact arithmetic helpers originate in this repository's FPATAN model.
 */
#include "internal/binary.h"
#include "constants/log.h"
#include <stdlib.h>

void x87t_internal_log_constants_init(log_constants *ctx)
{
    /* Each record stores the exact value (-1)^sign * integer(sig) * 2^scale.
     * k is its row in the published ROM, so rows need not be consecutive.
     * For midpoint a_i = (65+2*i)/64, 0 <= i <= 31, the table stores
     * H_i = rom[206+i] and L_i = rom[238+i]. H_i is log2(a_i) rounded to
     * 40 bits, nearest-even. L_i is the remaining difference rounded to
     * 67 bits, nearest-even, and can have either sign.
     *
     * The four corrected words were derived from these midpoint logarithms
     * and split widths. Their upper 64 bits also match the second public
     * ROM; the corrections were not fitted to instruction result samples.
     */
    *ctx = (log_constants){0};
    for (size_t i = 0; i < sizeof(constants) / sizeof(constants[0]); i++) {
        int k = constants[i].index;
        ctx->rom[k] = x87t_internal_fhex(constants[i].sig, constants[i].scale, constants[i].sign);
    }
}

/* The raw operation classes are distinct in the public operation listing.
 * M: 0x6e1 product, A: 0x649 add, W: 0x6c9 wide add.
 */
/* mul67 implements M by computing the exact product, then truncating it
 * toward zero to 67 significant bits. add64 implements A with 64-bit
 * nearest-even rounding; add67 implements W with 67-bit truncation.
 * The four-word fv type stores these results without further rounding;
 * its capacity does not determine the precision of an operation.
 * Below, Tn means truncation to n bits, Nn means nearest-even rounding
 * to n bits, and Cj denotes the stored constant ctx->rom[j].
 *
 * Saved-data tests distinguish these choices: using nearest-even products,
 * 67-bit truncated ordinary sums, or 67-bit truncated table division changes
 * results for both instructions. Tests also rejected squaring with equally
 * precise operands. Preserve the individual rounding steps below.
 */
static fv mul67(fv a, fv b)
{
    return x87t_internal_fround(x87t_internal_fmul(a, b), 67, CHOP);
}
static fv add64(fv a, fv b)
{
    return x87t_internal_fadd(a, b, 64, RN);
}
static fv add67(fv a, fv b)
{
    return x87t_internal_fadd(a, b, 67, CHOP);
}

/* x is an exact finite raw80 value; op=0 is FYL2X, op=1 is FYL2XP1.
 * The caller handles exceptional classes and zero-logarithm cases.
 */
/* input must be positive for op=0, or nonzero and within FYL2XP1's supported
 * interval for op=1. All denominators below are positive. The returned
 * logarithm has at most 67 significant bits. Its exponent is not limited
 * to the raw80 range; this function neither sets exception flags nor uses
 * the guest rounding mode.
 */
static fv logarithm(const log_constants *ctx, int op, fv input)
{
    fv x = input, z, u, v, odd, even, t, den, anchor, result;
    t = x87t_internal_fscale(x87t_internal_fuint(1), -3);
    z = x87t_internal_fabs(x);
    /* For FYL2XP1 with |input| > 1/8, add 1 to input and truncate the sum
     * to 67 bits. Then approximate log2 of that rounded sum through the
     * FYL2X path. At |input| = 1/8, keep the direct calculation below.
     * Using a 64-bit sum here changes the input to the subsequent steps.
     * This 67-bit addition and the four table corrections fixed the L0001
     * mismatches; the corrected calculation also matched the L0002 tests.
     */
    if (op && x87t_internal_fcmp(z, t) > 0) {
        t = x87t_internal_fuint(1);
        x = add67(x, t);
        op = 0;
    }
    /* Use the direct calculation for FYL2X when 7/8 <= x <= 9/8; rows
     * 194 and 193 store these exact bounds. Let q = (x-1)/(x+1) for FYL2X
     * or q = x/(x+2) for FYL2XP1. In either case the logarithm is
     * 2*L*atanh(q). z will approximate 2*L*q using C196, the stored
     * approximation to 2*L.
     */
    if (op || (x87t_internal_fcmp(x, ctx->rom[194]) >= 0 && x87t_internal_fcmp(x, ctx->rom[193]) <= 0)) {
        /* fexp returns floor(log2(|x|)), so this branch covers
         * 0 < |x| < 2^-69. Use the linear approximation C195*x, truncated
         * to 67 bits, where C195 approximates L. There is no division or
         * addition of 1 to x on this path.
         */
        if (op && x87t_internal_fexp(x) <= -70) {
            result = mul67(ctx->rom[195], x);
            goto done;
        }
        t = x87t_internal_fuint(1);
        if (op)
            z = x;
        else {
            t = x87t_internal_fneg(t);
            z = add64(x, t);
            t = x87t_internal_fneg(t);
        }
        if (op)
            t = x87t_internal_fuint(2);
        den = add67(x, t);
        /* For FYL2X, z holds N64(x-1); for FYL2XP1 it holds x. Multiply
         * by C196 and truncate to 67 bits, then divide by den and truncate
         * again to 67 bits. fdiv uses the exact quotient remainder, so it
         * introduces no separate reciprocal rounding.
         */
        z = mul67(z, ctx->rom[196]);
        z = x87t_internal_fdiv(z, den, 67, CHOP);
        /* Distinct 0x661 square: one input port is truncated to 64 bits. */
        /* Compute u = N64(T64(z)*z): truncate one copy of z to 64 bits,
         * multiply it by the unchanged z, then round the product to 64 bits,
         * nearest-even. Keeping 67 bits in both factors or truncating the
         * product changes saved test results. The port description above
         * comes from the source listing.
         */
        u = x87t_internal_fround(z, 64, CHOP);
        u = x87t_internal_fmul(u, z);
        u = x87t_internal_fround(u, 64, RN);
        v = mul67(u, u);
        /* Before accounting for rounding, u = z^2 and v = z^4. odd and
         * even evaluate alternate coefficients of
         *     z + z^3*(C200+C201*z^2+...+C205*z^10).
         * Their separate chains put rounding at specific intermediate
         * results. Rewriting the polynomial as a single Horner chain
         * changes those results.
         */
        odd = mul67(ctx->rom[205], v);
        odd = add64(odd, ctx->rom[203]);
        odd = mul67(odd, v);
        odd = add64(odd, ctx->rom[201]);
        even = mul67(ctx->rom[204], v);
        even = add64(even, ctx->rom[202]);
        even = mul67(even, v);
        even = add64(even, ctx->rom[200]);
        odd = mul67(odd, v);
        even = mul67(even, u);
        t = add64(odd, even);
        t = mul67(t, z);
        result = add67(t, z);
    } else {
        /* Write X = m*2^e, where X is the FYL2X input or FYL2XP1's 67-bit
         * truncated sum 1+input. Scaling by 2^-e is exact and leaves
         * x = m in [1,2). Table bin i covers [1+i/32, 1+(i+1)/32), with
         * midpoint a_i = (65+2*i)/64; an exact boundary starts a new bin.
         */
        int e = x87t_internal_fexp(x);
        x = x87t_internal_fscale(x, -e);
        /* x is in [1,2); floor(32*(x-1)) = floor(32*x)-32 exactly. */
        int i = (int)x87t_internal_ffloor(x87t_internal_fscale(x, 5)) - 32;
        if (i < 0 || i > 31)
            abort();
        anchor = x87t_internal_fscale(x87t_internal_fuint(65 + 2 * i), -6);
        /* With a = anchor and m = x,
         *     log2(m/a) = 2*L*atanh((m-a)/(m+a)).
         * Compute z as an approximation to 2*(m-a)/(m+a). Round m-a,
         * its doubling, m+a, and the division separately to 64 bits,
         * nearest-even. even starts with C195*z truncated to 67 bits,
         * which approximates the linear term L*z of the residual.
         */
        t = x87t_internal_fneg(anchor);
        z = add64(x, t);
        z = add64(z, z);
        den = add64(x, anchor);
        z = x87t_internal_fdiv(z, den, 64, RN);
        even = mul67(ctx->rom[195], z);
        u = mul67(z, z);
        /* The polynomial adds z^3*(C197+C198*z^2+C199*z^4) to the linear
         * term. The code approximates this expression by truncating each
         * product to 67 bits and rounding each sum to 64 bits, nearest-even.
         */
        t = mul67(ctx->rom[199], u);
        t = add64(t, ctx->rom[198]);
        t = mul67(t, u);
        t = add64(t, ctx->rom[197]);
        t = mul67(t, u);
        t = mul67(t, z);
        t = add64(t, even);
        /* Reconstruct log2(X) = e + log2(a) + log2(m/a), using the two
         * stored parts H_i and L_i of log2(a). Add L_i to the residual t
         * and truncate to 67 bits. Separately add H_i to e and round to
         * 64 bits, nearest-even. Add those results and truncate to 67 bits.
         * Combining the table parts first would change the rounded sums.
         */
        t = add67(t, ctx->rom[238 + i]);
        anchor = x87t_internal_fuint(e < 0 ? -e : e);
        if (e < 0)
            anchor = x87t_internal_fneg(anchor);
        anchor = add64(anchor, ctx->rom[206 + i]);
        result = add67(t, anchor);
    }
done:
    return result;
}

/* Masked numerical contract: two valid stack entries, all exception latches
 * clear before FLD80 of y and x. PC is metadata; the kernel retains its own
 * fixed precisions. Undefined condition bits and arbitrary restore histories
 * are not modeled. FYL2XP1's guaranteed finite domain is Intel's stated range.
 */
/* The masked contract above describes the original implementation. This
 * function now also handles unmasked overflow and underflow. If either
 * occurs and its bit is clear in masks, adjust the exponent before returning.
 * The wrapper's result_finish then selects the first unmasked exception.
 * IE, DE or ZE prevents the ST(1) write and pop, discards later exception
 * flags, and clears C1. OE, UE or PE allows the write and pop while reporting
 * a pending exception. The caller merges sticky flags, updates the registers,
 * and delivers exceptions, including any that were already pending.
 */
int x87t_internal_log_raw80(const log_constants *ctx,
              int op,
              raw80 y,
              raw80 x,
              enum mode rc,
              raw80 *out,
              int *c1,
              unsigned *exceptions, unsigned masks)
{
    raw_class ky = x87t_internal_raw80_classify(y), kx = x87t_internal_raw80_classify(x);
    raw80 invalid = {0xffff, UINT64_C(0xc000000000000000)};
    *c1 = 0;
    *exceptions = 0;
    if (ky == RAW_UNSUPPORTED || kx == RAW_UNSUPPORTED)
        goto invalid;
    int ny = ky == RAW_QNAN || ky == RAW_SNAN, nx = kx == RAW_QNAN || kx == RAW_SNAN;
    if (ny || nx) {
        /* If only one operand is NaN, return it. If both are NaNs, prefer
         * a quiet NaN over a signaling NaN; otherwise choose the larger
         * significand, with the smaller se word breaking ties. Quiet the
         * chosen NaN and raise IE if either operand was signaling.
         * Unsupported encodings take priority and have already returned.
         */
        raw80 pick;
        if (!ny)
            pick = x;
        else if (!nx)
            pick = y;
        else if (ky == RAW_QNAN && kx == RAW_SNAN)
            pick = y;
        else if (kx == RAW_QNAN && ky == RAW_SNAN)
            pick = x;
        else
            pick = y.sig > x.sig || (y.sig == x.sig && y.se < x.se) ? y : x;
        pick.sig |= UINT64_C(1) << 62;
        *out = pick;
        *exceptions = ky == RAW_SNAN || kx == RAW_SNAN;
        return 0;
    }
    /* Intel's guaranteed FYL2XP1 finite range is |x| <= 1-sqrt(1/2).
     * Its largest raw80 member is 0x3ffd:95f619980c4336f7. The bound is
     * checked by an exact integer inequality in the validation tooling.
     * Out-of-range finite/inf behavior is architecturally undefined.
     */
    /* Masking the sign from se compares magnitudes, so both signed
     * endpoints are accepted. Reject inputs outside the range before
     * recording DE. The wrapper turns return 1 into OUTSIDE_SCOPE and
     * leaves the caller's output unchanged.
     */
    if (op && ((x.se & 0x7fff) > 0x3ffd ||
               ((x.se & 0x7fff) == 0x3ffd && x.sig > UINT64_C(0x95f619980c4336f7))))
        return 1;
    if (ky == RAW_DENORMAL || ky == RAW_PSEUDO || kx == RAW_DENORMAL || kx == RAW_PSEUDO)
        *exceptions = 2;
    int sy = y.se >> 15, sx = x.se >> 15, logsign, logzero;
    /* logsign and logzero describe the logarithm before multiplying by y.
     * For FYL2X, negative nonzero x is invalid. When x=0, the logarithm is
     * -infinity and raises ZE, unless y=0 makes the product invalid instead.
     * For supported FYL2XP1 inputs, log2(1+x) has the same sign as x and
     * is zero exactly when x is zero. Build signed zeros directly as raw80
     * values below, because fv cannot distinguish +0 from -0.
     */
    if (!op) {
        if (sx && kx != RAW_ZERO)
            goto invalid;
        if (kx == RAW_ZERO) {
            if (ky == RAW_ZERO)
                goto invalid;
            *out = (raw80){(uint16_t)(((sy ^ 1) << 15) | 0x7fff), UINT64_C(1) << 63};
            *exceptions = 4;
            return 0;
        }
        if (kx == RAW_INFINITY) {
            if (ky == RAW_ZERO)
                goto invalid;
            *out = (raw80){(uint16_t)((sy << 15) | 0x7fff), UINT64_C(1) << 63};
            return 0;
        }
        logzero = x.se == 0x3fff && x.sig == (UINT64_C(1) << 63);
        logsign = x.se < 0x3fff;
    } else {
        if (kx == RAW_INFINITY)
            return 1;
        logzero = kx == RAW_ZERO;
        logsign = sx;
    }
    int sign = sy ^ logsign;
    if (logzero) {
        if (ky == RAW_INFINITY)
            goto invalid;
        *out = (raw80){(uint16_t)(sign << 15), 0};
        return 0;
    }
    if (ky == RAW_INFINITY) {
        *out = (raw80){(uint16_t)((sign << 15) | 0x7fff), UINT64_C(1) << 63};
        return 0;
    }
    if (ky == RAW_ZERO) {
        *out = (raw80){(uint16_t)(sign << 15), 0};
        return 0;
    }
    fv qx = x87t_internal_fdecode(x), qy = x87t_internal_fdecode(y);
    /* The FYL2XP1 range check above already ensures 1+qx > 0. Keep this
     * guard at the call to logarithm so its argument stays in the domain.
     */
    if (op && x87t_internal_fcmp(qx, x87t_internal_fneg(x87t_internal_fuint(1))) <= 0)
        return 1;
    fv v = x87t_internal_fmul(logarithm(ctx, op, qx), qy);
    /* The logarithm has at most 67 significant bits and y has at most 64,
     * so their exact product fits in 131 bits. fmul keeps all of them until
     * fencode rounds using guest rc: to a 64-bit significand for normal
     * results, or multiples of 2^-16445 for subnormals. C1 is set when
     * this rounding increases the magnitude. On overflow, fencode instead
     * sets C1 if it chooses infinity and clears it if it chooses max finite.
     * Rounding the logarithm or product to 64 bits earlier can change both
     * the final bits and C1. This path always reports PE, even when the
     * final multiplication and rounding are exact.
     */
    *out = x87t_internal_fencode(v, rc, c1);
    *exceptions |= 32;
    /* The final architectural multiply tests the 64-bit rounded value with
     * unbounded exponent, before the final raw80 denormalization. A stored
     * minimum normal can therefore still signal underflow (Intel SDM 8.5.5).
     * The logarithm kernel marks the result inexact even when this final
     * product is exact, so every tiny unbounded rounded result signals UE.
     */
    qx = x87t_internal_fround(v, 64, rc);
    if (x87t_internal_fexp(qx) < -16382)
        *exceptions |= 16;
    /* Check overflow using the exact product's leading exponent and the
     * rounded result. Either can overflow before the exponent is adjusted
     * for an unmasked exception below.
     */
    if (x87t_internal_fexp(v) > 16383 || (out->se & 0x7fff) == 0x7fff)
        *exceptions |= 8;
    if ((*exceptions & X87T_UE) && !(masks & X87T_UE)) {
        /* Scale the exact product by 2^24576, then round again. Scaling the
         * already rounded zero or subnormal would lose bits needed for this
         * result. The new rounding also determines C1 for the unmasked case.
         */
        v = x87t_internal_fscale(v, 24576);
        *out = x87t_internal_fencode(v, rc, c1);
    } else if ((*exceptions & X87T_OE) && !(masks & X87T_OE)) {
        v = x87t_internal_fscale(v, -24576);
        *out = x87t_internal_fencode(v, rc, c1);
    }
    return 0;
invalid:
    *out = invalid;
    *exceptions = 1;
    return 0;
}

x87t_error x87t_internal_evaluate_log(const x87t_context *context,
                        int instruction,
                        x87t_raw80 y,
                        x87t_raw80 x,
                        const x87t_control *control,
                        x87t_result *out)
{
    /* Leave out unchanged if an argument is invalid or outside the domain.
     * Otherwise ask the emulator to write ST(1) and pop, unless an unmasked
     * exception prevents it. Only C1 is known among the condition bits.
     * result_finish selects the first unmasked exception: IE, DE or ZE
     * prevents the write and pop and suppresses later flags; OE, UE or PE
     * allows the stack changes and reports a pending exception. The result
     * has already been rounded.
     */
    x87t_error error = x87t_internal_validate_call(context, control, out);
    if (error)
        return error;
    x87t_result result;
    x87t_internal_result_begin(&result, X87T_REPLACE_ST1_POP);
    int c1;
    unsigned exceptions;
    if (x87t_internal_log_raw80(&context->log,
                  instruction,
                  y,
                  x,
                  (enum mode)control->rounding,
                  &result.primary,
                  &c1,
                  &exceptions, control->exception_masks))
        return X87T_OUTSIDE_SCOPE;
    result.cc = c1 ? X87T_C1 : 0;
    result.cc_known = X87T_C1;
    result.exceptions = (uint8_t)exceptions;
    result.exceptions_known = 0x3f;
    x87t_internal_result_finish(&result, control);
    *out = result;
    return X87T_OK;
}
