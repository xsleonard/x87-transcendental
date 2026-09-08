/* Skylake FPATAN reconstruction: the fixed V7 numerical program (D0027).
 * D0023/D0024/D0026 provide 624,312 prospective observations with no misses.
 * Exact GMP arithmetic, no operand ledger, native FPATAN or algorithm flags.
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

static raw80 encode(const mpq_t in, enum mode mode, int *c1)
{
    raw80 out = {0, 0};
    int sign = mpq_sgn(in) < 0;
    mpq_t q, a, b;
    mpq_inits(q, a, b, NULL);
    int e = mpq_sgn(in) ? x87t_internal_qexp(in) : -16382;
    if (e < -16382)
        e = -16382;
    x87t_internal_at_step(q, in, e - 63, mode);
    mpq_abs(a, q);
    mpq_abs(b, in);
    *c1 = mpq_cmp(a, b) > 0;
    if (mpq_sgn(q)) {
        e = x87t_internal_qexp(q);
        if (e < -16382)
            e = -16382;
        x87t_internal_scale2(a, a, 63 - e);
        if (mpz_cmp_ui(mpq_denref(a), 1))
            abort();
        if (mpz_sizeinbase(mpq_numref(a), 2) > 64)
            abort();
        size_t count = 0;
        mpz_export(&out.sig, &count, 1, sizeof(out.sig), 0, 0, mpq_numref(a));
        if (count > 1)
            abort();
    }
    out.se = (uint16_t)((sign << 15) | (out.sig < (UINT64_C(1) << 63) ? 0 : e + 16383));
    mpq_clears(q, a, b, NULL);
    return out;
}

void x87t_internal_atan_constants_init(atan_constants *ctx)
{
    for (int i = 0; i < 157; i++)
        mpq_init(ctx->rom[i]);
    for (size_t i = 0; i < sizeof(constants) / sizeof(constants[0]); i++) {
        int k = constants[i].index;
        if (mpz_set_str(mpq_numref(ctx->rom[k]), constants[i].sig, 16))
            abort();
        if (constants[i].sign)
            mpq_neg(ctx->rom[k], ctx->rom[k]);
        x87t_internal_scale2(ctx->rom[k], ctx->rom[k], constants[i].scale);
    }
}

void x87t_internal_atan_constants_clear(atan_constants *ctx)
{
    for (int i = 0; i < 157; i++)
        mpq_clear(ctx->rom[i]);
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
    mpq_t y, x, r, z, square, h, tail, angle, t, u, c, v, odd, even;
    mpq_inits(y, x, r, z, square, h, tail, angle, t, u, c, v, odd, even, NULL);

    /* Normalize magnitudes into the first octant; retain the swap for later.
     * r is the exact ratio, z the reduced argument, and square/v are z^2/z^4
     * after their specified cuts. t and u are reusable arithmetic temporaries.
     */
    x87t_internal_decode(y, iy);
    x87t_internal_decode(x, ix);
    mpq_abs(y, y);
    mpq_abs(x, x);
    int swap = mpq_cmp(y, x) > 0;
    if (swap)
        mpq_swap(y, x);
    mpq_div(r, y, x);
    int n = 0;
    /* Tiny-ratio bypass, direct polynomial, or table-assisted reduction. */
    if (x87t_internal_qexp(r) < -40) {
        x87t_internal_rounded(angle, r, 67, CHOP);
    } else {
        if (mpq_cmp_ui(r, 3, 64) <= 0) {
            x87t_internal_rounded(z, r, 67, CHOP);
        } else {
            /* Historical V4: nearest table index; ties upwards, using the exact ratio.
             * V7 replaces it with nearest/lower ties: ceil(32*r - 1/2).
             */
            mpq_mul_2exp(t, r, 5);
            mpq_set_ui(u, 1, 2);
            mpq_sub(t, t, u);
            mpz_t index;
            mpz_init(index);
            mpz_cdiv_q(index, mpq_numref(t), mpq_denref(t));
            n = (int)mpz_get_ui(index);
            mpz_clear(index);
            if (n < 1 || n > 32)
                abort();
            mpq_set_ui(c, (unsigned)n, 32);
            mpq_canonicalize(c);
            /* These small-integer products are COMPLETE before subtraction. */
            mpq_mul(t, c, x);
            mpq_sub(t, y, t);
            x87t_internal_rounded(t, t, 67, CHOP);
            mpq_mul(u, c, y);
            mpq_add(u, x, u);
            x87t_internal_rounded(u, u, 67, CHOP);
            mpq_div(z, t, u);
            x87t_internal_rounded(z, z, 67, CHOP);
        }
        /* Source-guided interleaved operation roles (D0021).
         * Square uses X67/Y64 and RN64; ordinary products use CHOP67.
         * RN64 and CHOP67 sums are distinct operation classes. Numerical
         * transfer is verified on Skylake; Goldmont opcode meanings are
         * not claimed as a physical decode of the Skylake implementation.
         */
        x87t_internal_rounded(t, z, 64, CHOP);
        mpq_mul(square, z, t);
        x87t_internal_rounded(square, square, 64, RN);
        mpq_mul(v, square, square);
        x87t_internal_rounded(v, v, 67, CHOP);
        if (n) {
            /* Short kernel, with separate even/odd coefficient chains. */
            mpq_mul(t, v, ctx->rom[116]);
            x87t_internal_rounded(t, t, 67, CHOP);
            mpq_add(even, ctx->rom[114], t);
            x87t_internal_rounded(even, even, 67, CHOP);
            mpq_mul(t, v, ctx->rom[117]);
            x87t_internal_rounded(t, t, 67, CHOP);
            mpq_add(odd, ctx->rom[115], t);
            x87t_internal_rounded(odd, odd, 64, RN);
        } else {
            /* Long kernel, with the same interleaved evaluation structure. */
            mpq_mul(t, v, ctx->rom[123]);
            x87t_internal_rounded(t, t, 67, CHOP);
            mpq_add(odd, ctx->rom[121], t);
            x87t_internal_rounded(odd, odd, 64, RN);
            mpq_mul(t, v, ctx->rom[122]);
            x87t_internal_rounded(t, t, 67, CHOP);
            mpq_add(even, ctx->rom[120], t);
            x87t_internal_rounded(even, even, 64, RN);
            mpq_mul(t, v, odd);
            x87t_internal_rounded(t, t, 67, CHOP);
            mpq_add(odd, ctx->rom[119], t);
            x87t_internal_rounded(odd, odd, 67, CHOP);
            mpq_mul(t, v, even);
            x87t_internal_rounded(t, t, 67, CHOP);
            mpq_add(even, ctx->rom[118], t);
            x87t_internal_rounded(even, even, 67, CHOP);
        }
        mpq_mul(t, square, odd);
        x87t_internal_rounded(t, t, 67, CHOP);
        mpq_add(h, t, even);
        x87t_internal_rounded(h, h, 64, RN);
        mpq_mul(t, z, square);
        x87t_internal_rounded(t, t, 67, CHOP);
        mpq_mul(tail, t, h);
        x87t_internal_rounded(tail, tail, 67, CHOP);
        mpq_add(angle, z, tail);
        /* The table kernel is intermediate, not the final architectural add. */
        if (n) {
            x87t_internal_rounded(angle, angle, 67, CHOP);
            mpq_add(angle, angle, ctx->rom[124 + n]);
        }
    }
    /* Restore the quadrant before applying the caller's architectural RC.
     * Internal RN64/CHOP67 operations above do not depend on that RC.
     */
    if (swap || (ix.se & 0x8000))
        x87t_internal_rounded(angle, angle, 67, CHOP);
    if (swap) {
        if (ix.se & 0x8000)
            mpq_add(angle, ctx->rom[20], angle);
        else
            mpq_sub(angle, ctx->rom[20], angle);
    } else if (ix.se & 0x8000)
        mpq_sub(angle, ctx->rom[19], angle);
    if (iy.se & 0x8000)
        mpq_neg(angle, angle);
    *tiny = mpq_sgn(angle) && x87t_internal_qexp(angle) < -16382;
    if (*tiny && !(masks & X87T_UE))
        x87t_internal_scale2(angle, angle, 24576);
    *out = encode(angle, rc, c1);
    mpq_clears(y, x, r, z, square, h, tail, angle, t, u, c, v, odd, even, NULL);
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
    mpq_t angle;
    mpq_init(angle);
    int sx = (x.se >> 15), sy = (y.se >> 15);
    if (ky == RAW_ZERO || kx == RAW_INFINITY) {
        if (ky == RAW_INFINITY) {
            mpq_div_2exp(angle, ctx->rom[20], 1);
            if (sx) {
                mpq_t three;
                mpq_init(three);
                mpq_set_ui(three, 3, 1);
                mpq_mul(angle, angle, three);
                mpq_clear(three);
            }
        } else if (sx)
            mpq_set(angle, ctx->rom[19]);
    } else
        mpq_set(angle, ctx->rom[20]);
    if (mpq_sgn(angle)) {
        if (sy)
            mpq_neg(angle, angle);
        *out = encode(angle, rc, c1);
        *exceptions |= 32;
    } else
        *out = (raw80){(uint16_t)(sy << 15), 0};
    mpq_clear(angle);
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
