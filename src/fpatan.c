/* FPATAN computes atan2(y, x) in radians, where y is ST(1) and x is ST(0).
 * Zeros, infinities, NaNs and unsupported encodings are handled separately.
 * All other raw80 inputs, including subnormals and pseudo-denormals, enter
 * the finite calculation below.
 *
 * First set r = min(|y|,|x|)/max(|y|,|x|). For small r, approximate atan(r)
 * with r itself or an odd polynomial. For larger r, choose a table center c
 * and use atan(r) = atan(c) + atan((r-c)/(1+c*r)). Use pi/2 or pi to restore
 * the quadrant, apply y's sign, and round the final sum to raw80 using the
 * guest rounding mode (RC).
 *
 * The calculation truncates some operations to 67 significant bits and
 * rounds others to 64 bits, nearest-even. Guest precision control (PC) does
 * not change these widths. Changing them or the order of operations can
 * change the result and C1, even if it improves accuracy against atan2.
 *
 * The arithmetic helpers store integers with power-of-two scales. The GMP
 * notes below describe an earlier version of those helpers.
 */
/* Skylake FPATAN reconstruction: the fixed V7 numerical program (D0027).
 * D0023/D0024/D0026 provide 624,312 prospective observations with no misses.
 * Explicit finite integer arithmetic; no operand ledger, native FPATAN or algorithm flags.
 * The retained filename is historical. The entry handles masked results and
 * unmasked writeback; the finite kernel retains the V7 operation schedule.
 * The following V4 notes are historical, not the current validation status.
 */
/* Historical V4: Analysis-only C FPATAN candidate, NOT promoted or claimed complete.
 * Exact rational arithmetic uses GMP; no host atan, FPATAN, float or double.
 * Public P5 ROM constants are from Ken Shirriff's physical decode (2025).
 * Finite graph_v4.PROGRAM passed the fresh D0004 campaign. Architectural
 * values/C1 passed D0005/6; DE for pseudo-denormals passed D0006. Tininess
 * before final rounding is D0006's discovery correction for exception flags.
 * Broad fresh adversarial verification and final delivery are still pending.
 * Build: cc -O2 -std=c11 -Wall -Wextra -Werror fpatan_candidate.c -lgmp
 * Input uses the local public two-operand protocol. Output fields are
 * id, result_se, result_significand, C1, exception_flags, pre_load_flags.
 * PC is accepted as metadata, not an internal precision selection switch.
 */
#include "internal/binary.h"
#include "constants/atan.h"
#include <stdlib.h>

/* Each ROM row stores (-1)^sign * integer(sig,16) * 2^scale, where sig is
 * a hexadecimal integer. fhex reads every bit without rounding. Row numbers
 * preserve the P5 ROM indices, including gaps between coefficient groups.
 */
void x87t_internal_atan_constants_init(atan_constants *ctx)
{
    *ctx = (atan_constants){0};
    for (size_t i = 0; i < sizeof(constants) / sizeof(constants[0]); i++) {
        int k = constants[i].index;
        ctx->rom[k] = x87t_internal_fhex(constants[i].sig, constants[i].scale, constants[i].sign);
    }
}

/* fv stores an integer times a power of two. fmul returns the exact product
 * of two magnitudes of at most 128 bits each. mul67 then truncates that
 * product to 67 significant bits, toward zero. add67 truncates the sum the
 * same way; add64 rounds the sum to 64 bits, nearest-even. None of these
 * helpers limits the exponent to the raw80 range.
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

/* A single global numerical graph, no operand ledger or fitted exceptions.
 * Nonzero finite normal/subnormal values only until the specials campaign.
 */
/* The caller passes only finite nonzero operands. A stored exponent of zero
 * uses effective biased exponent E=1 for subnormals and pseudo-denormals.
 * The caller handles the denormal exception (DE) before this function.
 */
static int fpatan_candidate(
    const atan_constants *ctx, raw80 iy, raw80 ix, enum mode rc, raw80 *out, int *c1, int *tiny,
    unsigned masks)
{
    if (!iy.sig || !ix.sig || (iy.se & 0x7fff) == 0x7fff || (ix.se & 0x7fff) == 0x7fff ||
        ((iy.se & 0x7fff) && !(iy.sig >> 63)) || ((ix.se & 0x7fff) && !(ix.sig >> 63)))
        return 2;
    fv y = x87t_internal_fabs(x87t_internal_fdecode(iy));
    fv x = x87t_internal_fabs(x87t_internal_fdecode(ix));
    fv z, square, h, tail, t, u, c, v, odd, even;
    /* Keep the terminal addition unevaluated until its specified cut. */
    fv angle_left, angle_right = x87t_internal_fuint(0);

    /* Normalize magnitudes into the first octant; retain the swap for later.
     * r = y/x is compared exactly, z is the reduced argument, and square/v are z^2/z^4
     * after their specified cuts. t and u are reusable arithmetic temporaries.
     */
    /* After this step x >= y > 0, so r is in (0,1]. Equal magnitudes stay
     * in their original order. ix and iy keep the signs for restoring the
     * quadrant later.
     */
    int swap = x87t_internal_fcmp(y, x) > 0;
    if (swap) {
        t = y;
        y = x;
        x = t;
    }
    int n = 0;
    /* Tiny-ratio bypass, direct polynomial, or table-assisted reduction. */
    /* For r < 2^-40, use C67(r) without the polynomial correction. C67
     * means truncation to 67 significant bits, toward zero. fratio_exp
     * computes floor(log2(y/x)) by exact comparison, so rounding a quotient
     * cannot move an input across this boundary.
     */
    if (x87t_internal_fratio_exp(y, x) < -40) {
        angle_left = x87t_internal_fdiv(y, x, 67, CHOP);
    } else {
        /* y64 is exactly 64*y. Compare it with 3*x to select the direct
         * polynomial for 2^-40 <= r <= 3/64, including both endpoints.
         */
        fv y64 = x87t_internal_fscale(y, 6);
        if (x87t_internal_fcmp(y64, x87t_internal_fmul(x, x87t_internal_fuint(3))) <= 0) {
            z = x87t_internal_fdiv(y, x, 67, CHOP);
        } else {
            /* Historical V4: nearest table index; ties upwards, using the exact ratio.
             * V7 replaces it with nearest/lower ties: ceil(32*r - 1/2).
             */
            /* Choose c = n/32 such that (2*n-1)/64 < r <= (2*n+1)/64.
             * This path has 3/64 < r <= 1, so 2 <= n <= 32. Comparing exact
             * products avoids rounding the ratio before choosing a row.
             *
             * At the midpoint r = 19/64, choosing the upper row gave wrong
             * result bits and C1; choosing the lower row matched. Always
             * choosing the odd row at a tie gives the same final results as
             * this lower-row rule. D0022 and D0024-D0025 compared the rules
             * and proved that equivalence for this calculation.
             */
            for (n = 1; n <= 32; ++n)
                if (x87t_internal_fcmp(y64,
                        x87t_internal_fmul(x, x87t_internal_fuint(2 * n + 1))) <= 0)
                    break;
            if (n > 32)
                abort();
            c = x87t_internal_fscale(x87t_internal_fuint(n), -5);
            /* Set z0 = (r-c)/(1+c*r). Then atan(r) = atan(c) + atan(z0).
             * Compute the reduced argument as t=C67(y-c*x), u=C67(x+c*y),
             * then z=C67(t/u). The denominator is positive; z is negative
             * when r<c. fdiv rounds the quotient once, without first
             * rounding a reciprocal. These cuts make z an approximation
             * to z0, so the identity alone does not allow rearrangement.
             */
            /* These small-integer products are COMPLETE before subtraction. */
            t = add67(y, x87t_internal_fneg(x87t_internal_fmul(c, x)));
            u = add67(x, x87t_internal_fmul(c, y));
            z = x87t_internal_fdiv(t, u, 67, CHOP);
        }
        /* Source-guided interleaved operation roles (D0021).
         * Square uses X67/Y64 and RN64; ordinary products use CHOP67.
         * RN64 and CHOP67 sums are distinct operation classes. Numerical
         * transfer is verified on Skylake; Goldmont opcode meanings are
         * not claimed as a physical decode of the Skylake implementation.
         */
        /* Let C64 truncate to 64 bits and N64 round to 64 bits, nearest-even.
         * square=N64(z*C64(z)): truncate only the second factor before the
         * product, then round the product. v=C67(square*square) approximates
         * z^4. The operation listing examined in D0021 separates these
         * multiply and add steps. D0026-D0027 checked the widths and order
         * used here against captured result bits and C1.
         */
        t = x87t_internal_fround(z, 64, CHOP);
        square = x87t_internal_fround(x87t_internal_fmul(z, t), 64, RN);
        v = mul67(square, square);
        /* Before accounting for rounding, both polynomials have the form
         * z + z^3*(even(z^4) + z^2*odd(z^4)). ROM[114..117] holds the
         * coefficients of z^3,z^5,z^7,z^9 for the table path; ROM[118..123]
         * holds those of z^3,z^5,...,z^13 for the direct path. even and odd
         * collect alternating coefficients; the full polynomial is odd.
         */
        if (n) {
            /* Short kernel, with separate even/odd coefficient chains. */
            t = mul67(v, ctx->rom[116]);
            even = add67(ctx->rom[114], t);
            t = mul67(v, ctx->rom[117]);
            odd = add64(ctx->rom[115], t);
        } else {
            /* Long kernel, with the same interleaved evaluation structure. */
            t = mul67(v, ctx->rom[123]);
            odd = add64(ctx->rom[121], t);
            t = mul67(v, ctx->rom[122]);
            even = add64(ctx->rom[120], t);
            t = mul67(v, odd);
            odd = add67(ctx->rom[119], t);
            t = mul67(v, even);
            even = add67(ctx->rom[118], t);
        }
        t = mul67(square, odd);
        h = add64(t, even);
        t = mul67(z, square);
        tail = mul67(t, h);
        /* tail is the correction to z, starting at z^3. Keep the two terms
         * separate so that, on the direct path with no quadrant adjustment,
         * z+tail is rounded only once, to raw80.
         */
        angle_left = z;
        angle_right = tail;
        /* The table kernel is intermediate, not the final architectural add. */
        if (n) {
            /* ROM[124+n] stores the approximation to atan(n/32). Truncate
             * z+tail to 67 bits here, before adding the table value. Keep
             * this next sum as two terms until quadrant or final rounding.
             */
            angle_left = add67(angle_left, angle_right);
            angle_right = ctx->rom[124 + n];
        }
    }
    /* Restore the quadrant before applying the caller's architectural RC.
     * Internal RN64/CHOP67 operations above do not depend on that RC.
     */
    /* When a quadrant adjustment is needed, first truncate the angle to
     * 67 bits; call it a. If the magnitudes were swapped, use pi/2-a for
     * positive original x or pi/2+a for negative original x. Otherwise,
     * negative x needs pi-a. ROM[20] and ROM[19] store the 67-bit values
     * used for pi/2 and pi.
     */
    if (swap || (ix.se & 0x8000)) {
        angle_right = add67(angle_left, angle_right);
        angle_left = ctx->rom[swap ? 20 : 19];
        if (!swap || !(ix.se & 0x8000))
            angle_right = x87t_internal_fneg(angle_right);
    }
    if (iy.se & 0x8000) {
        angle_left = x87t_internal_fneg(angle_left);
        angle_right = x87t_internal_fneg(angle_right);
    }
    /* Round the sum to raw80 using guest RC: 64 significant bits for a
     * normal result, or multiples of 2^-16445 for a subnormal. The helper
     * tracks even a very small subtracted term, since pi minus a tiny angle
     * can round differently from pi alone. C1 is set if rounding increases
     * the magnitude. Test for a nonzero magnitude below 2^-16382 before
     * rounding. If it is tiny and UE is unmasked, scale it by 2^24576
     * before rounding. The caller uses tiny to set the exception flags.
     */
    *out = x87t_internal_fencode_sum(angle_left, angle_right, rc, masks, c1, tiny);
    return 0;
}

/* Masked instruction contract: valid two-deep stack, all exception latches
 * clear before loading the two raw80 operands. FLD80 does not quiet or reject
 * them; FPATAN handles unsupported encodings and signals denormal assistance.
 * This models numerical values and defined arithmetic flags, not hidden FPU
 * pointers, arbitrary restore histories, or undefined condition bits.
 */
/* The API also handles unmasked exceptions. result_finish suppresses the
 * result and stack pop for unmasked IE or DE. For unmasked UE or PE, it
 * allows the result to be written and the stack to be popped.
 */
int x87t_internal_fpatan_raw80(const atan_constants *ctx,
                 raw80 y,
                 raw80 x,
                 enum mode rc,
                 raw80 *out,
                 int *c1,
                 unsigned *exceptions, unsigned masks)
{
    raw_class ky = x87t_internal_raw80_classify(y), kx = x87t_internal_raw80_classify(x);
    *c1 = 0;
    *exceptions = 0;
    /* Check unsupported encodings before NaNs or denormals. Return the
     * negative indefinite quiet NaN and raise IE.
     */
    if (ky == RAW_UNSUPPORTED || kx == RAW_UNSUPPORTED) {
        *out = (raw80){0xffff, UINT64_C(0xc000000000000000)};
        *exceptions = 1;
        return 0;
    }
    int ny = ky == RAW_QNAN || ky == RAW_SNAN, nx = kx == RAW_QNAN || kx == RAW_SNAN;
    /* Prefer a quiet NaN to a signaling NaN. If both have the same class,
     * choose the larger significand; break a tie with the smaller se word.
     * Keep the chosen sign and payload, and set its quiet bit. Either
     * signaling NaN raises IE. Return without DE even if the other operand
     * is denormal.
     */
    if (ny || nx) {
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
        *exceptions = (ky == RAW_SNAN || kx == RAW_SNAN);
        return 0;
    }
    /* Both exponent-zero nonzero classes request the denormal assist.
     * A pseudo-denormal's numerical value still uses effective exponent 1.
     */
    if (ky == RAW_DENORMAL || ky == RAW_PSEUDO || kx == RAW_DENORMAL || kx == RAW_PSEUDO)
        *exceptions = 2;
    int special = ky == RAW_ZERO || kx == RAW_ZERO || ky == RAW_INFINITY || kx == RAW_INFINITY;
    if (!special) {
        int tiny = 0, status = fpatan_candidate(ctx, y, x, rc, out, c1, &tiny, masks);
        if (status)
            return status;
        /* Tininess is detected on the retained angle before final rounding,
         * even when directed rounding produces the minimum normal result.
         */
        /* Every finite nonzero calculation reports PE, regardless of its
         * error against atan2(y,x). Add UE when the angle was tiny before
         * rounding.
         */
        *exceptions |= 32;
        if (tiny)
            *exceptions |= 16;
        return 0;
    }
    /* Handle zero and infinite operands without division. Before applying
     * y's sign, y=0 or finite y with infinite x gives 0 for positive x and
     * pi for negative x. Two infinities give pi/4 or 3*pi/4, according to
     * x's sign. The remaining cases give pi/2. These sign tests include -0.
     *
     * Form nonzero angles from the stored pi constants with exact scaling
     * and multiplication, then round using guest RC and report PE. A zero
     * result keeps y's sign and clears C1 and PE. Any earlier DE remains set.
     */
    fv angle = x87t_internal_fuint(0);
    int sx = (x.se >> 15), sy = (y.se >> 15);
    if (ky == RAW_ZERO || kx == RAW_INFINITY) {
        if (ky == RAW_INFINITY) {
            angle = x87t_internal_fscale(ctx->rom[20], -1);
            if (sx)
                angle = x87t_internal_fmul(angle, x87t_internal_fuint(3));
        } else if (sx)
            angle = ctx->rom[19];
    } else
        angle = ctx->rom[20];
    if (x87t_internal_fsign(angle)) {
        if (sy)
            angle = x87t_internal_fneg(angle);
        *out = x87t_internal_fencode(angle, rc, c1);
        *exceptions |= 32;
    } else
        *out = (raw80){(uint16_t)(sy << 15), 0};
    return 0;
}

/* Request replacement of ST(1), followed by one stack pop. PC24, PC53 and
 * PC64 are accepted; the calculation uses only guest RC and exception masks.
 * result_finish cancels the write and pop, and suppresses later exception
 * flags, for unmasked IE or DE. Unmasked UE or PE allows the write and pop.
 * Return C1 and all six arithmetic flags; other condition bits are unknown.
 * The emulator applies the stack change, merges sticky flags and delivers
 * any pending exception.
 */
x87t_error x87t_fpatan(const x87t_context *context,
                       x87t_raw80 y,
                       x87t_raw80 x,
                       const x87t_control *control,
                       x87t_result *out)
{
    x87t_error error = x87t_internal_validate_call(context, control, out);
    if (error)
        return error;
    x87t_result result;
    x87t_internal_result_begin(&result, X87T_REPLACE_ST1_POP);
    int c1;
    unsigned exceptions;
    if (x87t_internal_fpatan_raw80(
            &context->atan, y, x, (enum mode)control->rounding, &result.primary, &c1, &exceptions,
            control->exception_masks))
        return X87T_OUTSIDE_SCOPE;
    result.cc = c1 ? X87T_C1 : 0;
    result.cc_known = X87T_C1;
    result.exceptions = (uint8_t)exceptions;
    result.exceptions_known = 0x3f;
    x87t_internal_result_finish(&result, control);
    *out = result;
    return X87T_OK;
}
