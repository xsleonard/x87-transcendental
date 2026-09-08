/* Skylake FPATAN reconstruction: the fixed V7 numerical program (D0027).
 * D0023/D0024/D0026 provide 624,312 prospective observations with no misses.
 * Explicit finite integer arithmetic; no operand ledger, native FPATAN or algorithm flags.
 * The retained filename is historical. See ALGORITHM.md and ACCEPTANCE.md
 * for the masked numerical contract, delivery checks and evidence limits.
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

void x87t_internal_atan_constants_init(atan_constants *ctx)
{
    *ctx = (atan_constants){0};
    for (size_t i = 0; i < sizeof(constants) / sizeof(constants[0]); i++) {
        int k = constants[i].index;
        ctx->rom[k] = x87t_internal_fhex(constants[i].sig, constants[i].scale, constants[i].sign);
    }
}

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
    int swap = x87t_internal_fcmp(y, x) > 0;
    if (swap) {
        t = y;
        y = x;
        x = t;
    }
    int n = 0;
    /* Tiny-ratio bypass, direct polynomial, or table-assisted reduction. */
    if (x87t_internal_fratio_exp(y, x) < -40) {
        angle_left = x87t_internal_fdiv(y, x, 67, CHOP);
    } else {
        fv y64 = x87t_internal_fscale(y, 6);
        if (x87t_internal_fcmp(y64, x87t_internal_fmul(x, x87t_internal_fuint(3))) <= 0) {
            z = x87t_internal_fdiv(y, x, 67, CHOP);
        } else {
            /* Historical V4: nearest table index; ties upwards, using the exact ratio.
             * V7 replaces it with nearest/lower ties: ceil(32*r - 1/2).
             */
            for (n = 1; n <= 32; ++n)
                if (x87t_internal_fcmp(y64,
                        x87t_internal_fmul(x, x87t_internal_fuint(2 * n + 1))) <= 0)
                    break;
            if (n > 32)
                abort();
            c = x87t_internal_fscale(x87t_internal_fuint(n), -5);
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
        t = x87t_internal_fround(z, 64, CHOP);
        square = x87t_internal_fround(x87t_internal_fmul(z, t), 64, RN);
        v = mul67(square, square);
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
        angle_left = z;
        angle_right = tail;
        /* The table kernel is intermediate, not the final architectural add. */
        if (n) {
            angle_left = add67(angle_left, angle_right);
            angle_right = ctx->rom[124 + n];
        }
    }
    /* Restore the quadrant before applying the caller's architectural RC.
     * Internal RN64/CHOP67 operations above do not depend on that RC.
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
    *out = x87t_internal_fencode_sum(angle_left, angle_right, rc, masks, c1, tiny);
    return 0;
}

/* Masked instruction contract: valid two-deep stack, all exception latches
 * clear before loading the two raw80 operands. FLD80 does not quiet or reject
 * them; FPATAN handles unsupported encodings and signals denormal assistance.
 * This models numerical values and defined arithmetic flags, not hidden FPU
 * pointers, arbitrary restore histories, or undefined condition bits.
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
    if (ky == RAW_UNSUPPORTED || kx == RAW_UNSUPPORTED) {
        *out = (raw80){0xffff, UINT64_C(0xc000000000000000)};
        *exceptions = 1;
        return 0;
    }
    int ny = ky == RAW_QNAN || ky == RAW_SNAN, nx = kx == RAW_QNAN || kx == RAW_SNAN;
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
        *exceptions |= 32;
        if (tiny)
            *exceptions |= 16;
        return 0;
    }
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
