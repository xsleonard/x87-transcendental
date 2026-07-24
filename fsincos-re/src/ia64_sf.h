/*
 * ia64_sf.h — soft model of the IA-64 FP arithmetic used by Intel's
 * sincosl.s (FSIN/FCOS/FSINCOS algorithm, Harrison FMCAD 2000).
 *
 * Models exactly what the algorithm's op sequence needs (see
 * ../notes/op-sequence.md):
 *   - register values: sign / unbiased exponent / 64-bit significand with
 *     explicit integer bit (wide exponent range = wre; range is far wider
 *     than the algorithm ever produces, so int32 exponent is exact),
 *   - fma/fms/fnma with ONE rounding to 64-bit significand
 *     (sf1 = round-to-nearest-even; sf0 = selectable user mode),
 *   - frcpa via the exact architectural RECIP_TABLE,
 *   - fcvt.fx (round FP -> int64, nearest-even) and exact int64 -> FP.
 *
 * Host-FP-independent: only integer arithmetic (uses unsigned __int128).
 */
#ifndef IA64_SF_H
#define IA64_SF_H

#include <stdint.h>
#include <string.h>

typedef unsigned __int128 u128;

/* Rounding modes (final s0 op honors the user mode; s1 is always RN). */
typedef enum { SF_RN = 0, SF_RD = 1, SF_RU = 2, SF_RZ = 3 } sf_rc_t;

/* One FP register value.
 * value = (-1)^sign * sig * 2^(exp-63);  normal: sig bit63 set.
 * sig == 0 encodes zero (exp ignored).  cls distinguishes specials. */
typedef enum { SF_FIN = 0, SF_INF = 1, SF_NAN = 2 } sf_cls_t;
typedef struct {
    uint8_t  cls;    /* sf_cls_t */
    uint8_t  sign;   /* 0/1 */
    int32_t  exp;    /* unbiased exponent of the leading bit */
    uint64_t sig;    /* significand, integer bit = bit 63 */
} sf_t;

static inline sf_t sf_zero(int sign)
{ sf_t z; z.cls = SF_FIN; z.sign = (uint8_t)sign; z.exp = 0; z.sig = 0; return z; }

static inline sf_t sf_qnan(void)
{ sf_t n; n.cls = SF_NAN; n.sign = 1; n.exp = 0; n.sig = 0xC000000000000000ull; return n; }

static inline int sf_is_zero(const sf_t *a) { return a->cls == SF_FIN && a->sig == 0; }

/* Construct from x87/IA-64 memory format pieces: 15-bit biased exponent
 * field (bias 0x3FFF... note: EXTENDED format bias 16383) + 64-bit
 * significand with explicit integer bit.  Used for table constants and I/O.
 * A biased field of 0 with nonzero sig = pseudo-denormal/denormal input:
 * normalize (fnorm semantics; wre absorbs the range). */
static inline sf_t sf_from_parts(int sign, uint32_t expfield, uint64_t sig)
{
    sf_t r; r.cls = SF_FIN; r.sign = (uint8_t)sign;
    if (sig == 0) return sf_zero(sign);
    if (expfield == 0x7FFF) {
        if (sig == 0x8000000000000000ull) { r.cls = SF_INF; r.exp = 0; r.sig = sig; return r; }
        r.cls = SF_NAN; r.exp = 0; r.sig = sig; return r;
    }
    r.exp = (int32_t)expfield - 16383;
    if (expfield == 0) r.exp = 1 - 16383;      /* denormal: exp field 0 means 2^-16382 */
    r.sig = sig;
    while (!(r.sig & 0x8000000000000000ull)) { r.sig <<= 1; r.exp--; }  /* fnorm */
    return r;
}

/* Emit to x87 80-bit memory format (sign:1, expfield:15, sig:64).
 * Values out of double-extended range would need denormalization; the
 * algorithm's outputs are in [-1-ulp, 1+ulp] or sin(x)~x for normal x, so
 * only denormal-range results (sin of denormal x) need the shift path. */
static inline void sf_to_x87(const sf_t *a, uint16_t *se, uint64_t *sig)
{
    if (a->cls == SF_NAN) { *se = (uint16_t)(0x7FFF | (a->sign << 15)); *sig = a->sig; return; }
    if (a->cls == SF_INF) { *se = (uint16_t)(0x7FFF | (a->sign << 15)); *sig = 0x8000000000000000ull; return; }
    if (a->sig == 0) { *se = (uint16_t)(a->sign << 15); *sig = 0; return; }
    int32_t ef = a->exp + 16383;
    uint64_t s = a->sig;
    if (ef <= 0) {                              /* denormal on store */
        int32_t sh = 1 - ef;
        s = (sh >= 64) ? 0 : s >> sh;           /* truncation; fine for I/O of tiny sin results */
        ef = 0;
    }
    *se = (uint16_t)(((uint32_t)a->sign << 15) | (uint32_t)ef);
    *sig = s;
}

/* ---------------- core rounding helper ----------------
 * Round a positive 128-bit significand "acc" with leading bit at position
 * "msb" (so value = acc * 2^(e128)) down to 64 significand bits.
 * sticky = bits already lost below acc.  Returns rounded sf_t. */
static inline sf_t sf_round_from128(int sign, int32_t exp_of_msb, u128 acc,
                                    int sticky, sf_rc_t rc)
{
    sf_t r; r.cls = SF_FIN; r.sign = (uint8_t)sign;
    if (acc == 0) {                 /* exact zero sum */
        if (sticky == 0) return sf_zero(rc == SF_RD ? sign : 0);
        /* nonzero but all below: treat as tiny; not reachable in this
         * algorithm (operands are wildly separated only via sticky paths
         * where acc keeps the large operand) */
        return sf_zero(sign);
    }
    /* normalize so leading bit is at position 127 */
    int lead = 127;
    while (!((acc >> lead) & 1)) lead--;
    exp_of_msb -= (127 - lead);
    acc <<= (127 - lead);
    uint64_t hi = (uint64_t)(acc >> 64);
    uint64_t lo = (uint64_t)acc;
    int guard = (int)(lo >> 63) & 1;
    int stk   = sticky || ((lo << 1) != 0);
    uint64_t sig = hi;
    int inc = 0;
    switch (rc) {
    case SF_RN: inc = guard && (stk || (sig & 1)); break;
    case SF_RZ: inc = 0; break;
    case SF_RU: inc = (!sign) && (guard || stk); break;
    case SF_RD: inc = sign && (guard || stk); break;
    }
    if (inc) {
        sig++;
        if (sig == 0) { sig = 0x8000000000000000ull; exp_of_msb++; }
    }
    r.exp = exp_of_msb; r.sig = sig;
    return r;
}

/* ---------------- fused multiply-add ----------------
 * res = a*b + c with ONE rounding (to 64-bit significand, mode rc).
 * Finite operands only on the paths we use; NaN/Inf propagate simply. */
static inline sf_t sf_fma_rc(const sf_t *a, const sf_t *b, const sf_t *c, sf_rc_t rc)
{
    if (a->cls == SF_NAN || b->cls == SF_NAN || c->cls == SF_NAN) return sf_qnan();
    if (a->cls == SF_INF || b->cls == SF_INF) {
        if (sf_is_zero(a) || sf_is_zero(b)) return sf_qnan();
        int ps = a->sign ^ b->sign;
        if (c->cls == SF_INF && c->sign != ps) return sf_qnan();
        sf_t r; r.cls = SF_INF; r.sign = (uint8_t)ps; r.exp = 0; r.sig = 0x8000000000000000ull;
        return r;
    }
    if (c->cls == SF_INF) return *c;

    int   psign = a->sign ^ b->sign;
    if (sf_is_zero(a) || sf_is_zero(b)) {
        if (sf_is_zero(c)) {
            /* 0+0: IEEE sign rules */
            if (psign == c->sign) return sf_zero(psign);
            return sf_zero(rc == SF_RD ? 1 : 0);
        }
        return *c;   /* c representable: rounding is identity */
    }

    /* exact product: 128-bit significand, leading bit at 127 or 126 */
    u128 prod = (u128)a->sig * (u128)b->sig;
    int32_t pexp = a->exp + b->exp;            /* exponent if leading bit at 126 */
    /* express product as prod * 2^(pexp-126); msb position: */
    int pmsb = ((prod >> 127) & 1) ? 127 : 126;
    int32_t pexp_of_msb = pexp + (pmsb - 126);

    if (sf_is_zero(c))
        return sf_round_from128(psign, pexp_of_msb, prod << (127 - pmsb), 0, rc);

    /* addend as 128-bit fixed point, leading bit at 127 */
    u128 csig = ((u128)c->sig) << 64;
    int32_t cexp_of_msb = c->exp;

    /* align: bring both to the frame of the larger exponent */
    u128 big, small; int32_t eres; int bsign, ssign;
    u128 pn = prod << (127 - pmsb);
    if (pexp_of_msb > cexp_of_msb ||
        (pexp_of_msb == cexp_of_msb && pn >= csig)) {
        big = pn;  bsign = psign;  small = csig; ssign = c->sign;
        eres = pexp_of_msb;
        cexp_of_msb = pexp_of_msb - cexp_of_msb;   /* reuse as shift */
    } else {
        big = csig; bsign = c->sign; small = pn; ssign = psign;
        eres = cexp_of_msb;
        cexp_of_msb = cexp_of_msb - pexp_of_msb;   /* shift */
    }
    int shift = (int)cexp_of_msb;
    int sticky = 0;
    if (shift >= 128) { sticky = (small != 0); small = 0; }
    else if (shift > 0) {
        sticky = ((small << (128 - shift)) != 0);
        small >>= shift;
    }

    if (bsign == ssign) {
        /* addition; may carry one bit beyond 127 */
        u128 sum = big + small;
        int carry = (sum < big);
        if (carry) {
            sticky |= (int)(sum & 1);
            sum = (sum >> 1) | ((u128)1 << 127);
            eres += 1;
        }
        return sf_round_from128(bsign, eres, sum, sticky, rc);
    } else {
        /* subtraction: big - small (big >= small in this frame unless equal
         * magnitudes with sticky... big==small && sticky -> tiny negative of
         * ssign side; cannot happen with sticky!=0 because sticky implies
         * shift>0 implies big had strictly larger exponent) */
        if (big == small && !sticky) return sf_zero(rc == SF_RD ? 1 : 0);
        u128 diff = big - small;
        if (sticky) {
            /* borrow from the sticky bits: diff -= ulp, sticky inverts.
             * Correct treatment: value = big - (small + eps), eps in (0,1ulp).
             * diff_exact = (big - small) - eps -> represent as (diff-1) with
             * inverted sticky (the classic two's complement trick). */
            diff -= 1;
            sticky = 1;  /* remaining fractional part is (1 - eps): nonzero */
        }
        return sf_round_from128(bsign, eres, diff, sticky, rc);
    }
}

/* s1 ops: round-to-nearest always.
 *
 * g_sf_split = 0: true IA-64 fused semantics (ONE rounding).
 * g_sf_split = 1: model a non-fused x87-style datapath — the multiply rounds
 * to 64 bits (FMUL), then the add rounds (FADD): TWO roundings per site.
 * Sites where b == +/-1 (pure adds) or c == 0 (pure muls) are identical in
 * both models. */
extern int g_sf_split;

static inline int sf_is_one_mag(const sf_t *b)
{ return b->cls == SF_FIN && b->sig == 0x8000000000000000ull && b->exp == 0; }

static inline sf_t sf_fma(const sf_t *a, const sf_t *b, const sf_t *c)   /* a*b + c */
{
    if (g_sf_split && !sf_is_one_mag(a) && !sf_is_one_mag(b) && !sf_is_zero(c)) {
        sf_t z = sf_zero(0);
        sf_t p = sf_fma_rc(a, b, &z, SF_RN);         /* FMUL: round product */
        sf_t one = { SF_FIN, 0, 0, 0x8000000000000000ull };
        return sf_fma_rc(&p, &one, c, SF_RN);        /* FADD: round sum */
    }
    return sf_fma_rc(a, b, c, SF_RN);
}
static inline sf_t sf_fms(const sf_t *a, const sf_t *b, const sf_t *c)   /* a*b - c */
{ sf_t nc = *c; nc.sign ^= 1; return sf_fma(a, b, &nc); }
static inline sf_t sf_fnma(const sf_t *a, const sf_t *b, const sf_t *c)  /* c - a*b */
{ sf_t na = *a; na.sign ^= 1; return sf_fma(&na, b, c); }
/* s0 ops (user rounding mode) */
static inline sf_t sf_fma_s0(const sf_t *a, const sf_t *b, const sf_t *c, sf_rc_t rc)
{ return sf_fma_rc(a, b, c, rc); }
static inline sf_t sf_fms_s0(const sf_t *a, const sf_t *b, const sf_t *c, sf_rc_t rc)
{ sf_t nc = *c; nc.sign ^= 1; return sf_fma_rc(a, b, &nc, rc); }

/* negate / abs (fmerge idioms) */
static inline sf_t sf_neg(const sf_t *a) { sf_t r = *a; r.sign ^= 1; return r; }
static inline sf_t sf_abs(const sf_t *a) { sf_t r = *a; r.sign = 0; return r; }

/* magnitude compare of finite values: |a| < |b| */
static inline int sf_lt_abs(const sf_t *a, const sf_t *b)
{
    if (sf_is_zero(a)) return !sf_is_zero(b);
    if (sf_is_zero(b)) return 0;
    if (a->exp != b->exp) return a->exp < b->exp;
    return a->sig < b->sig;
}
/* signed compare a < b (finite) */
static inline int sf_lt(const sf_t *a, const sf_t *b)
{
    int az = sf_is_zero(a), bz = sf_is_zero(b);
    if (az && bz) return 0;
    if (az) return !b->sign;
    if (bz) return a->sign;
    if (a->sign != b->sign) return a->sign;
    int lt = sf_lt_abs(a, b);
    return a->sign ? sf_lt_abs(b, a) : lt;
}

/* ---------------- frcpa ----------------
 * Exact architectural table lookup (fp_ieee_recip).  Finite nonzero normal
 * input assumed (the algorithm only applies it to r and to frcpa's output).
 * Defined in fsincos_ref.c, next to the transcribed RECIP_TABLE. */
sf_t sf_frcpa(const sf_t *den);

/* ---------------- conversions ---------------- */
/* fcvt.fx.s1: round to nearest-even signed 64-bit integer. */
static inline int64_t sf_cvt_fx_rn(const sf_t *a)
{
    if (sf_is_zero(a)) return 0;
    int32_t e = a->exp;             /* value = sig * 2^(e-63) */
    uint64_t mag;
    if (e < -1) return 0;
    if (e == -1) {                  /* value in [0.5, 1): ties-to-even at 0.5 */
        mag = (a->sig > 0x8000000000000000ull) ? 1 : 0; /* exactly .5 -> 0 (even) */
    } else if (e >= 63) {
        mag = a->sig;               /* already integer scale (e==63); larger: out of our use */
        if (e > 63) mag = 0;        /* not used by the algorithm */
    } else {
        int sh = 63 - e;            /* fractional bits */
        uint64_t ipart = a->sig >> sh;
        uint64_t frac  = a->sig << (64 - sh);
        uint64_t half  = 0x8000000000000000ull;
        if (frac > half || (frac == half && (ipart & 1))) ipart++;
        mag = ipart;
    }
    return a->sign ? -(int64_t)mag : (int64_t)mag;
}
/* fcvt.xf: exact int64 -> fp */
static inline sf_t sf_from_i64(int64_t v)
{
    if (v == 0) return sf_zero(0);
    sf_t r; r.cls = SF_FIN; r.sign = (uint8_t)(v < 0);
    uint64_t m = (v < 0) ? (uint64_t)(-(v + 1)) + 1 : (uint64_t)v;
    r.exp = 63;
    r.sig = m;
    while (!(r.sig & 0x8000000000000000ull)) { r.sig <<= 1; r.exp--; }
    return r;
}

#endif /* IA64_SF_H */
