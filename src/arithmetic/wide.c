/* Exact integer products, signed accumulators and explicit precision cuts. */
#include "internal/numeric.h"

/* exact host-integer support for the experimentally
 * selected 66/68/69-bit Round-16 candidate. */
int uint128_width(u128 v)
{
    int width = 0;
    while (v) {
        width++;
        v >>= 1;
    }
    return width;
}

/* full unsigned 128x128 multiply.  Round-16 call
 * sites use at most 68-bit operands, but the full helper keeps the carrier
 * honest for the 65-bit reduced-argument path. */
u256 u128_mul_full(u128 a, u128 b)
{
    uint64_t a0 = (uint64_t)a, a1 = (uint64_t)(a >> 64);
    uint64_t b0 = (uint64_t)b, b1 = (uint64_t)(b >> 64);
    u128 p00 = (u128)a0 * b0;
    u128 p01 = (u128)a0 * b1;
    u128 p10 = (u128)a1 * b0;
    u128 p11 = (u128)a1 * b1;
    u128 lo = p00, hi = p11, old;
    old = lo;
    lo += p01 << 64;
    hi += (p01 >> 64) + (lo < old);
    old = lo;
    lo += p10 << 64;
    hi += (p10 >> 64) + (lo < old);
    return (u256){hi, lo};
}

sf_t wv_rn64(wv_t v)
{
    sf_t r;
    if (v.sig == 0)
        return sf_zero(v.sign);
    int b = 127;
    while (!((v.sig >> b) & 1))
        b--;
    int sh = b - 63;
    uint64_t top;
    int32_t e2 = v.e2;
    if (sh <= 0) {
        top = (uint64_t)(v.sig << (-sh));
        e2 -= (-sh);
    } else {
        top = (uint64_t)(v.sig >> sh);
        u128 rem = v.sig & (((u128)1 << sh) - 1);
        u128 half = (u128)1 << (sh - 1);
        if (rem > half || (rem == half && (top & 1))) {
            top++;
            if (top == 0) {
                top = 0x8000000000000000ull;
                e2 += 1;
            }
        }
        e2 += sh;
    }
    r.cls = SF_FIN;
    r.sign = v.sign;
    r.sig = top;
    r.exp = e2 + 63;
    return r;
}

/* fused combine: one rounding of  T1*(1+t) +/- T2*S  (all inputs exact).
 * T1,T2 are ROM-width entries; t,S are 64-bit values.  Accumulate exactly
 * in 256-bit fixed point. */
void acc_add(u256 *acc, int neg, u128 mag_hi, u128 mag_lo)
{
    if (!neg) {
        u128 lo = acc->lo + mag_lo;
        acc->hi += mag_hi + (lo < acc->lo ? 1 : 0);
        acc->lo = lo;
    } else {
        u128 borrow = acc->lo < mag_lo ? 1 : 0;
        acc->lo -= mag_lo;
        acc->hi -= mag_hi + borrow;
    }
}

/* add an exact small-wide product at a fixed-point
 * accumulator scale.  Current callers fit in at most 134 product bits. */
void acc_add_product(u256 *acc, int neg, u128 a, u128 b, int32_t e2, int scale)
{
    if (a == 0 || b == 0)
        return;
    u256 product = u128_mul_full(a, b);
    int sh = e2 - scale;
    u128 hi, lo;
    if (sh == 0) {
        hi = product.hi;
        lo = product.lo;
    } else if (sh < 0) {
        int rsh = -sh;
        if (rsh < 128) {
            hi = product.hi >> rsh;
            lo = (product.lo >> rsh) | (product.hi << (128 - rsh));
        } else {
            hi = 0;
            lo = product.hi >> (rsh - 128);
        }
    } else if (sh < 128) {
        hi = (product.hi << sh) | (product.lo >> (128 - sh));
        lo = product.lo << sh;
    } else {
        hi = product.lo << (sh - 128);
        lo = 0;
    }
    acc_add(acc, neg, hi, lo);
}

/*
 * generalized internal-width materialization for
 * the standalone-FSIN hypothesis.  It operates on the same exact signed
 * accumulator as acc_rn_bits and makes non-RN representatives explicit;
 * P5_ROUND_AWAY means magnitude away from zero, P5_ROUND_ODD retains
 * discarded information in the low stored bit, and UP/DOWN are signed
 * directed modes.
 */
wv_t acc_round_wide(u256 acc, int32_t scale, int bits, p5_round_t mode)
{
    int neg = (int)(acc.hi >> 127);
    if (neg) {
        acc.lo = ~acc.lo + 1;
        acc.hi = ~acc.hi + (acc.lo == 0);
    }
    if (acc.hi == 0 && acc.lo == 0)
        return (wv_t){(uint8_t)neg, 0, 0, 0};
    int msb;
    if (acc.hi) {
        msb = 127;
        while (!((acc.hi >> msb) & 1))
            msb--;
        msb += 128;
    } else {
        msb = 127;
        while (!((acc.lo >> msb) & 1))
            msb--;
    }
    int sh = msb - (bits - 1);
    u128 top;
    int guard = 0;
    u128 below = 0;
    if (sh <= 0) {
        top = acc.lo << -sh;
    } else if (sh < 128) {
        top = (acc.hi << (128 - sh)) | (acc.lo >> sh);
        guard = (int)((acc.lo >> (sh - 1)) & 1);
        below = sh > 1 ? acc.lo & (((u128)1 << (sh - 1)) - 1) : 0;
    } else {
        int hsh = sh - 128;
        top = acc.hi >> hsh;
        if (hsh == 0) {
            guard = (int)(acc.lo >> 127);
            below = acc.lo & (((u128)1 << 127) - 1);
        } else {
            guard = (int)((acc.hi >> (hsh - 1)) & 1);
            below = (hsh > 1 ? acc.hi & (((u128)1 << (hsh - 1)) - 1) : 0) | (acc.lo != 0);
        }
    }
    int discarded = guard || below;
    int increment = 0;
    if (mode == P5_ROUND_ODD) {
        increment = discarded && !(top & 1);
        if (discarded)
            top |= 1;
    } else {
        increment = mode == P5_ROUND_AWAY ? discarded
                    : mode == P5_ROUND_UP ? (!neg && discarded)
                    : mode == P5_ROUND_DOWN
                        ? (neg && discarded)
                        : (mode == P5_ROUND_RN && guard && (below || (top & 1)));
        if (increment) {
            top++;
            if (top == ((u128)1 << bits)) {
                top >>= 1;
                sh++;
            }
        }
    }
    int rh = discarded ? (increment ? 1 : -1) : 0;
    if (neg)
        rh = -rh;
    return (wv_t){(uint8_t)neg, scale + sh, top, (int8_t)rh};
}

/* exact wide multiply followed by an explicitly
 * selected standalone-FSIN internal materialization. */
wv_t wide_mul(wv_t a, wv_t b, int bits, p5_round_t mode)
{
    int32_t scale = a.e2 + b.e2;
    u256 acc = {0, 0};
    acc_add_product(&acc, a.sign ^ b.sign, a.sig, b.sig, scale, scale);
    return acc_round_wide(acc, scale, bits, mode);
}

/* materialize a native P5 ROM constant at an
 * internal width. */
wv_t constant_round(const p5c_t *constant, int bits, p5_round_t mode)
{
    u256 acc = {0, 0};
    acc_add_product(&acc, constant->sign, constant->sig, 1, constant->exp2, constant->exp2);
    return acc_round_wide(acc, constant->exp2, bits, mode);
}

/* exact add of a materialized carrier and P5 ROM
 * constant, followed by the standalone-FSIN internal-width rule. */
wv_t wide_add_constant(wv_t value,
                       const p5c_t *constant,
                       int constant_bits,
                       p5_round_t constant_mode,
                       int bits,
                       p5_round_t mode)
{
    wv_t stored = constant_round(constant, constant_bits, constant_mode);
    int32_t scale = value.e2 < stored.e2 ? value.e2 : stored.e2;
    u256 acc = {0, 0};
    acc_add_product(&acc, value.sign, value.sig, 1, value.e2, scale);
    acc_add_product(&acc, stored.sign, stored.sig, 1, stored.e2, scale);
    return acc_round_wide(acc, scale, bits, mode);
}

/* exact addition of two explicit internal
 * carriers followed by a selected materialization.  Round 36 uses this to
 * replay the validated three-FADD reconstruction without host floating
 * point. */
wv_t wide_add(wv_t left, wv_t right, int bits, p5_round_t mode)
{
    int32_t scale = left.e2 < right.e2 ? left.e2 : right.e2;
    u256 acc = {0, 0};
    if (left.sig) {
        acc_add_product(&acc, left.sign, left.sig, 1, left.e2, scale);
    }
    if (right.sig) {
        acc_add_product(&acc, right.sign, right.sig, 1, right.e2, scale);
    }
    return acc_round_wide(acc, scale, bits, mode);
}

/* architectural RC rounding of a signed
 * fixed-point accumulator, shared by the baseline and Round-24 combines. */
sf_t acc_round64_rc(u256 acc, int32_t scale, int neg_out, sf_rc_t rc)
{
    int neg = (acc.hi >> 127) & 1;
    if (neg) {
        acc.lo = ~acc.lo + 1;
        acc.hi = ~acc.hi + (acc.lo == 0 ? 1 : 0);
    }
    neg ^= neg_out;
    if (acc.hi == 0 && acc.lo == 0)
        return sf_zero(neg);
    int b;
    if (acc.hi) {
        b = 127;
        while (!((acc.hi >> b) & 1))
            b--;
        b += 128;
    } else {
        b = 127;
        while (!((acc.lo >> b) & 1))
            b--;
    }
    int sh = b - 63;
    uint64_t top;
    if (sh <= 0) {
        top = (uint64_t)(acc.lo << (-sh));
    } else if (sh >= 128) {
        top = (uint64_t)(acc.hi >> (sh - 128));
        int guard;
        u128 below;
        if (sh - 128 >= 1) {
            guard = (int)((acc.hi >> (sh - 128 - 1)) & 1);
            below = (sh - 128 - 1 > 0 ? acc.hi & (((u128)1 << (sh - 128 - 1)) - 1) : 0) |
                    (acc.lo ? 1 : 0);
        } else {
            guard = (int)(acc.lo >> 127) & 1;
            below = acc.lo & (((u128)1 << 127) - 1);
        }
        int inc = 0;
        if (rc == SF_RN)
            inc = guard && (below || (top & 1));
        else if (rc == SF_RU)
            inc = !neg && (guard || below);
        else if (rc == SF_RD)
            inc = neg && (guard || below);
        if (inc) {
            top++;
            if (!top) {
                top = 1ull << 63;
                sh++;
            }
        }
    } else {
        top = (uint64_t)((acc.hi << (128 - sh)) | (acc.lo >> sh));
        int guard = (int)((acc.lo >> (sh - 1)) & 1);
        u128 below = sh > 1 ? acc.lo & (((u128)1 << (sh - 1)) - 1) : 0;
        if (rc == SF_RN) {
            if (guard && (below || (top & 1))) {
                top++;
                if (!top) {
                    top = 1ull << 63;
                    sh++;
                }
            }
        } else if (rc == SF_RU) {
            if (!neg && (guard || below)) {
                top++;
                if (!top) {
                    top = 1ull << 63;
                    sh++;
                }
            }
        } else if (rc == SF_RD) {
            if (neg && (guard || below)) {
                top++;
                if (!top) {
                    top = 1ull << 63;
                    sh++;
                }
            }
        }
    }
    return (sf_t){
        SF_FIN,
        (uint8_t)neg,
        scale + sh + 63,
        top,
    };
}

/* Rebuild the exact wide reduced argument |r+c| from (r, c).
 * By construction of the M66 reducer, c != 0 only when |r| >= 0.5 (the
 * 65th significand bit), and then c is exactly +-1 unit of 2^-65. */
wv_t reduced_to_wide(const sf_t *r, const sf_t *c)
{
    wv_t w = {0};
    w.sign = r->sign;
    if (c->sig == 0) {
        w.sig = (u128)r->sig;
        w.e2 = r->exp - 63;
        return w;
    }
    u128 m = ((u128)r->sig) << 1; /* r.exp == -1 here; scale 2^-65 */
    if (c->sign == r->sign)
        m += 1;
    else
        m -= 1;
    w.sig = m;
    w.e2 = -65;
    return w;
}
