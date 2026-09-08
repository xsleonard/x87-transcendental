/*
 * fsincos_itanium.c — bit-exact portable reimplementation of Intel's
 * double-extended sinl/cosl (= the Itanium IA-32-compat FSIN/FCOS/FSINCOS
 * algorithm, Harrison FMCAD 2000).
 *
 * ============================ FROZEN 2026-07-15 ============================
 * This is the FROZEN Itanium reference.  Do not edit except to fix a
 * demonstrated transcription error against data/glibc-ia64-fpu/s_cosl.S.
 * Verification status:
 *   - 1:1 transcription of Intel's shipped ia64 assembly (glibc-2.38
 *     sysdeps/ia64/fpu/s_cosl.S); op extraction in notes/op-sequence.md.
 *   - Arithmetic engine (ia64_sf.h) verified against exact rational
 *     arithmetic: 11,000-vector fused-ma oracle, 0 mismatches.
 *   - End-to-end within the FMCAD00-proven error bound on all sampled paths.
 *   - Corroborated by Intel Skylake silicon: bit-identical wherever the two
 *     implementations provably coincide (entire |x| < 2^-3 path 4004/4004;
 *     C2 boundary).
 *   - NOT verified against physical Itanium hardware (none available).
 *     Possible future validation: run glibc-2.38 ia64 under the Ski
 *     simulator.
 * Experiment scaffolding lives in fsincos_skylake.c, not here.
 * ===========================================================================
 *
 * Transcribed 1:1 from the op sequence of glibc-2.38
 * sysdeps/ia64/fpu/s_cosl.S (see ../notes/op-sequence.md).  Every arithmetic
 * step is a soft IA-64 fma with a single rounding to 64-bit significand
 * (sf1 = round-to-nearest); the one final op per path runs in the user
 * rounding mode (sf0).  cosl(x) = sinl-machinery with N_inc = 1.
 *
 * |x| >= 2^63: x87 FSIN/FCOS/FSINCOS set C2 and leave the operand; we return
 * FSINCOS_C2.  (The libm variant would call the Payne-Hanek reducer instead;
 * not implemented.)
 *
 * CLI:
 *   fsincos_itanium <se_hex4> <sig_hex16> -> "S <se> <sig>" / "C <se> <sig>"
 *   fsincos_itanium --batch               -> bulk mode, diffable format
 *   fsincos_itanium --fma-test            -> engine test server on stdin
 *   fsincos_itanium --selftest            -> internal invariants
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "ia64_sf.h"

/* exact architectural frcpa table (transcribed from IA-64 SDM vol 3) */
#include "../data/frcpa-recip-table.h"

int g_sf_split = 0;   /* engine knob (ia64_sf.h); FROZEN at 0 = true fused IA-64 semantics */

sf_t sf_frcpa(const sf_t *den)
{
    sf_t r; r.cls = SF_FIN; r.sign = den->sign;
    unsigned idx = (unsigned)((den->sig >> 55) & 0xFF);
    r.sig = 0x8000000000000000ull | ((uint64_t)FRCPA_RECIP_TABLE[idx] << 53);
    r.exp = -1 - den->exp;          /* biased: 0x1FFFF - 2 - e */
    return r;
}

/* ---------------- constants (decoded from the .S data tables) ---------- */
#define SFC(sgn, field, sighex) { SF_FIN, (sgn), (int32_t)(field) - 16383, (sighex) }

static const sf_t ONE        = { SF_FIN, 0, 0,  0x8000000000000000ull };
static const sf_t ZERO       = { SF_FIN, 0, 0,  0 };

static const sf_t INV_PI_BY_2 = SFC(0, 0x3FFE, 0xA2F9836E4E44152Aull);
static const sf_t P_0        = SFC(0, 0x4016, 0xC84D32B0CE81B9F1ull);
static const sf_t P_1        = SFC(0, 0x3FFF, 0xC90FDAA22168C235ull);
static const sf_t P_2        = SFC(1, 0x3FBD, 0xECE675D1FC8F8CBBull);
static const sf_t P_3        = SFC(1, 0x3F7C, 0xB7ED8FBBACC19C60ull);
static const sf_t D_1        = SFC(1, 0x3FBF, 0x8D848E89DBD171A1ull);
static const sf_t D_2        = SFC(1, 0x3F7C, 0xD5394C3618A66F8Eull);
static const sf_t PI_BY_4    = SFC(0, 0x3FFE, 0xC90FDAA22168C234ull);
static const sf_t INV_P_0    = SFC(0, 0x3FE7, 0xA397E5046EC6B45Aull);

static const sf_t PP_8       = SFC(0, 0x3FCE, 0xCC8ABEBCA21C0BC9ull);
static const sf_t PP_7       = SFC(1, 0x3FD6, 0xD7468A05720221DAull);
static const sf_t PP_6       = SFC(0, 0x3FDE, 0xB092382F640AD517ull);
static const sf_t PP_5       = SFC(1, 0x3FE5, 0xD7322B47D1EB75A4ull);
static const sf_t PP_4       = SFC(0, 0x3FEC, 0xB8EF1D2ABAF69EEAull);
static const sf_t PP_3       = SFC(1, 0x3FF2, 0xD00D00D00D03BB69ull);
static const sf_t PP_2       = SFC(0, 0x3FF8, 0x8888888888888962ull);
static const sf_t PP_1_HI    = SFC(1, 0x3FFC, 0xAAAA000000000000ull);
static const sf_t PP_1_LO    = SFC(1, 0x3FEC, 0xAAAAAAAAAAAB0000ull);

static const sf_t QQ_8       = SFC(0, 0x3FD2, 0xD56232EFC2B0FE52ull);
static const sf_t QQ_7       = SFC(1, 0x3FDA, 0xC9C99ABA2B48DCA6ull);
static const sf_t QQ_6       = SFC(0, 0x3FE2, 0x8F76C6509C716658ull);
static const sf_t QQ_5       = SFC(1, 0x3FE9, 0x93F27DBAFDA8D0FCull);
static const sf_t QQ_4       = SFC(0, 0x3FEF, 0xD00D00D00C6E5041ull);
static const sf_t QQ_3       = SFC(1, 0x3FF5, 0xB60B60B60B607F60ull);
static const sf_t QQ_2       = SFC(0, 0x3FFA, 0xAAAAAAAAAAAAAA9Bull);
static const sf_t QQ_1       = SFC(1, 0x3FFE, 0x8000000000000000ull);

static const sf_t S_1        = SFC(1, 0x3FFC, 0xAAAAAAAAAAAAAAAAull);
static const sf_t S_2        = SFC(0, 0x3FF8, 0x88888888888868DBull);
static const sf_t S_3        = SFC(1, 0x3FF2, 0xD00D00D0055EFD4Bull);
static const sf_t S_4        = SFC(0, 0x3FEC, 0xB8EF1C5D839730B9ull);
static const sf_t S_5        = SFC(1, 0x3FE5, 0xD71EA3A4E5B3F492ull);

static const sf_t C_1        = SFC(1, 0x3FFD, 0xFFFFFFFFFFFFFFFEull);
static const sf_t C_2        = SFC(0, 0x3FFA, 0xAAAAAAAAAAAA719Full);
static const sf_t C_3        = SFC(1, 0x3FF5, 0xB60B60B60356F994ull);
static const sf_t C_4        = SFC(0, 0x3FEF, 0xD00CFFD5B2385EA9ull);
static const sf_t C_5        = SFC(1, 0x3FE9, 0x93E4BD18292A14CDull);

/* N-computation constants (moderate path "right shift" trick) */
static const sf_t INVPI_2TO63 = { SF_FIN, 0, 63,  0xA2F9836E4E44152Aull }; /* (2/pi)*2^64 as integer */
static const sf_t RSHF_2TO64  = { SF_FIN, 0, 127, 0xC000000000000000ull }; /* 1.5*2^127 */

/* thresholds (compared with fcmp; exact powers of two, and -2^-67) */
static const sf_t TWO_M3   = { SF_FIN, 0, -3,  0x8000000000000000ull };
static const sf_t NTWO_M3  = { SF_FIN, 1, -3,  0x8000000000000000ull };
static const sf_t TWO_M14  = { SF_FIN, 0, -14, 0x8000000000000000ull };
static const sf_t NTWO_M14 = { SF_FIN, 1, -14, 0x8000000000000000ull };
static const sf_t TWO_M33  = { SF_FIN, 0, -33, 0x8000000000000000ull };
static const sf_t NTWO_M33 = { SF_FIN, 1, -33, 0x8000000000000000ull };
static const sf_t NTWO_M67 = { SF_FIN, 1, -67, 0x8000000000000000ull };

/* ---------------- kernels ---------------- */
/* i1 = bit0 of N_Inc (0: sine kernel, 1: cosine kernel);
   i0 = bit1 of N_Inc (result sign).  rc = user rounding mode (final op). */

static sf_t small_r(sf_t r, sf_t c, int i1, int i0, sf_rc_t rc)
{
    sf_t rsq = sf_fma(&r, &r, &ZERO);
    sf_t Z   = sf_fma(&rsq, &rsq, &ZERO);
    sf_t corr, lead;
    if (i1) { corr = sf_fnma(&c, &r, &ZERO); lead = ONE; }
    else    { corr = c;                      lead = r;   }
    if (!i1) Z = sf_fma(&Z, &r, &ZERO);
    Z = sf_fma(&Z, &rsq, &ZERO);
    sf_t pl = i1 ? sf_fma(&rsq, &C_5, &C_4) : sf_fma(&rsq, &S_5, &S_4);
    sf_t ph = i1 ? sf_fma(&rsq, &C_2, &C_1) : sf_fma(&rsq, &S_2, &S_1);
    pl = sf_fma(&rsq, &pl, i1 ? &C_3 : &S_3);
    ph = sf_fma(&ph, &rsq, &ZERO);
    sf_t poly = sf_fma(&Z, &pl, &corr);
    if (!i1) ph = sf_fma(&r, &ph, &ZERO);
    if (i0)  lead = sf_fms(&ZERO, &ONE, &lead);      /* lead = -lead */
    poly = sf_fma(&poly, &ONE, &ph);
    return i0 ? sf_fms_s0(&lead, &ONE, &poly, rc)
              : sf_fma_s0(&lead, &ONE, &poly, rc);
}

static sf_t normal_r(sf_t r, sf_t c, int i1, int i0, sf_rc_t rc)
{
    sf_t rsq  = sf_fma(&r, &r, &ZERO);
    sf_t h1   = sf_frcpa(&r);
    sf_t poly = i1 ? sf_fma(&rsq, &QQ_8, &QQ_7) : sf_fma(&rsq, &PP_8, &PP_7);
    sf_t rcube = sf_fma(&r, &rsq, &ZERO);
    sf_t r_hi = sf_frcpa(&h1);                       /* frcpa(frcpa(r)) */
    poly = sf_fma(&rsq, &poly, i1 ? &QQ_6 : &PP_6);
    sf_t corr = i1 ? sf_fma(&S_1, &rcube, &r) : sf_fma(&C_1, &rsq, &ZERO);
    sf_t r_hi_sq = sf_fma(&r_hi, &r_hi, &ZERO);
    sf_t r_lo = sf_fms(&r, &ONE, &r_hi);
    poly = sf_fma(&rsq, &poly, i1 ? &QQ_5 : &PP_5);
    corr = i1 ? sf_fnma(&corr, &c, &ZERO) : sf_fma(&corr, &c, &c);
    sf_t U_lo = i1 ? sf_fma(&r_hi, &ONE, &r) : sf_fma(&r, &r_hi, &r_hi_sq);
    sf_t U_hi = i1 ? sf_fma(&QQ_1, &r_hi_sq, &ONE) : sf_fma(&r_hi, &r_hi_sq, &ZERO);
    poly = sf_fma(&rsq, &poly, i1 ? &QQ_4 : &PP_4);
    if (!i1) {
        U_lo = sf_fma(&r, &r, &U_lo);
        U_hi = sf_fma(&PP_1_HI, &U_hi, &ZERO);
    }
    poly = sf_fma(&rsq, &poly, i1 ? &QQ_3 : &PP_3);
    U_lo = sf_fma(&r_lo, &U_lo, &ZERO);
    if (i1) U_lo = sf_fma(&QQ_1, &U_lo, &ZERO);
    else    U_hi = sf_fma(&r, &ONE, &U_hi);          /* r + PP_1_hi*r_hi^3 (exact) */
    poly = sf_fma(&rsq, &poly, i1 ? &QQ_2 : &PP_2);
    if (!i1) U_lo = sf_fma(&PP_1_HI, &U_lo, &ZERO);
    poly = i1 ? sf_fma(&rsq, &poly, &ZERO) : sf_fma(&rsq, &poly, &PP_1_LO);
    sf_t V = sf_fma(&U_lo, &ONE, &corr);
    poly = i1 ? sf_fma(&rsq, &poly, &ZERO) : sf_fma(&rcube, &poly, &ZERO);
    sf_t tmp = ONE; if (i0) tmp.sign = 1;            /* +/-1 via fma/fms of f0,f1,f1 */
    V = sf_fma(&poly, &ONE, &V);
    return i0 ? sf_fms_s0(&tmp, &U_hi, &V, rc)
              : sf_fma_s0(&tmp, &U_hi, &V, rc);
}

/* ---------------- top level (sinl machinery; cos: n_inc = 1) ---------- */

typedef enum { FSINCOS_OK = 0, FSINCOS_C2 = 1 } fsincos_status_t;

static fsincos_status_t sincos_core(sf_t x, int n_inc, sf_rc_t rc, sf_t *out)
{
    if (x.cls == SF_NAN) {                    /* fmpy.s0(x, f0): quiet the NaN */
        *out = x; out->sig |= 0x4000000000000000ull;
        return FSINCOS_OK;
    }
    if (x.cls == SF_INF) { *out = sf_qnan(); return FSINCOS_OK; }  /* indefinite */
    if (sf_is_zero(&x)) {                     /* sinl(+-0)=+-0; cosl(0)=1 */
        *out = n_inc ? ONE : x;
        return FSINCOS_OK;
    }
    /* x is fnorm-normalized by sf_from_parts (denormals included). */
    if (x.exp >= 63) return FSINCOS_C2;       /* |x| >= 2^63: x87 sets C2 */

    if (x.exp >= 24) {
        /* ---- LARGER_ARG: 2^24 <= |x| < 2^63 (Step 8 pre-reduction) ---- */
        sf_t N0f = sf_fma(&x, &INV_P_0, &ZERO);
        int64_t N0i = sf_cvt_fx_rn(&N0f);
        sf_t N0 = sf_from_i64(N0i);
        sf_t xp = sf_fnma(&N0, &P_0, &x);              /* Arg' = x - N0*P_0 */
        sf_t w  = sf_fma(&N0, &D_1, &ZERO);
        sf_t Nf = sf_fma(&xp, &INV_PI_BY_2, &ZERO);
        int64_t Ni = sf_cvt_fx_rn(&Nf);
        sf_t N  = sf_from_i64(Ni);
        int N_Inc = (int)((Ni + n_inc) & 3);
        sf_t s = sf_fnma(&N, &P_1, &xp);
        w = sf_fnma(&N, &P_2, &w);                     /* w = w - N*P_2 */
        int tiny14 = sf_lt(&s, &TWO_M14) && sf_lt(&NTWO_M14, &s);
        if (!tiny14) {
            sf_t r = sf_fma(&s, &ONE, &w);
            sf_t c = sf_fms(&s, &ONE, &r);
            c = sf_fma(&c, &ONE, &w);
            int i1 = N_Inc & 1, i0 = (N_Inc >> 1) & 1;
            int small = sf_lt(&r, &TWO_M3) && sf_lt(&NTWO_M3, &r);
            *out = small ? small_r(r, c, i1, i0, rc) : normal_r(r, c, i1, i0, rc);
            return FSINCOS_OK;
        }
        /* ---- Case 4: |s| < 2^-14 ---- */
        int i1 = N_Inc & 1, i0 = (N_Inc >> 1) & 1;
        sf_t V_hi = sf_fma(&N, &P_2, &ZERO);           /* sign-flipped vs write-up */
        sf_t U_hi = sf_fma(&N0, &D_1, &ZERO);
        sf_t w2 = sf_fma(&N, &P_3, &ZERO);
        sf_t A  = sf_fms(&U_hi, &ONE, &V_hi);
        sf_t V_lo = sf_fnma(&N, &P_2, &V_hi);          /* exact residual */
        sf_t U_lo = sf_fms(&N0, &D_1, &U_hi);          /* exact residual */
        sf_t Uabs = sf_abs(&U_hi), Vabs = sf_abs(&V_hi);
        w2 = sf_fms(&N0, &D_2, &w2);                   /* w = N0*d_2 - w2 */
        sf_t t = sf_fma(&U_lo, &ONE, &V_lo);
        sf_t a;
        if (!sf_lt(&Uabs, &Vabs)) {                    /* |U_hi| >= |V_hi| */
            a = sf_fms(&U_hi, &ONE, &A);
            a = sf_fms(&a, &ONE, &V_hi);
        } else {
            a = sf_fma(&V_hi, &ONE, &A);
            a = sf_fms(&U_hi, &ONE, &a);
        }
        sf_t C_hi = sf_fma(&s, &ONE, &A);
        t = sf_fma(&t, &ONE, &w2);
        sf_t C_lo = sf_fms(&s, &ONE, &C_hi);
        C_lo = sf_fma(&C_lo, &ONE, &A);
        t = sf_fma(&t, &ONE, &a);
        C_lo = sf_fma(&C_lo, &ONE, &t);
        sf_t r = sf_fma(&C_hi, &ONE, &C_lo);
        sf_t rsq = sf_fma(&r, &r, &ZERO);
        sf_t c = sf_fms(&C_hi, &ONE, &r);
        c = sf_fma(&c, &ONE, &C_lo);
        sf_t tmp = i1 ? ONE : r;
        if (i0) tmp = sf_fms(&ZERO, &ONE, &tmp);
        sf_t poly;
        if (!i1) {
            poly = sf_fma(&rsq, &S_2, &S_1);
            sf_t rcube = sf_fma(&rsq, &r, &ZERO);
            poly = sf_fma(&rcube, &poly, &c);
        } else {
            poly = sf_fma(&rsq, &C_2, &C_1);
            poly = sf_fma(&rsq, &poly, &ZERO);
        }
        *out = i0 ? sf_fms_s0(&tmp, &ONE, &poly, rc)
                  : sf_fma_s0(&tmp, &ONE, &poly, rc);
        return FSINCOS_OK;
    }

    /* ---- 0 < |x| < 2^24 ---- */
    sf_t absx = sf_abs(&x);
    if (sf_lt(&absx, &PI_BY_4)) {
        /* quick: r = x, c = 0 */
        int N_Inc = n_inc & 3;
        int i1 = N_Inc & 1, i0 = (N_Inc >> 1) & 1;
        sf_t c = ZERO;
        if (x.exp < -3) { *out = small_r(x, c, i1, i0, rc); return FSINCOS_OK; }
        *out = normal_r(x, c, i1, i0, rc);
        return FSINCOS_OK;
    }

    /* ---- moderate reduction: pi/4 <= |x| < 2^24 ---- */
    sf_t Nsig = sf_fma(&x, &INVPI_2TO63, &RSHF_2TO64);  /* rshf trick */
    int64_t Ni = (int64_t)(Nsig.sig - 0xC000000000000000ull);
    sf_t N = sf_from_i64(Ni);                           /* == fms(Nsig,2^-64,rshf) */
    int N_Inc = (int)((Ni + n_inc) & 3);
    int i1 = N_Inc & 1, i0 = (N_Inc >> 1) & 1;

    sf_t s = sf_fnma(&N, &P_1, &x);                     /* EXACT (paper thm) */
    sf_t w = sf_fma(&N, &P_2, &ZERO);
    sf_t r = sf_fms(&s, &ONE, &w);
    int tiny33 = sf_lt(&s, &TWO_M33) && sf_lt(&NTWO_M33, &s);
    if (!tiny33) {
        sf_t c = sf_fms(&s, &ONE, &r);
        c = sf_fms(&c, &ONE, &w);
        int small = sf_lt(&r, &TWO_M3) && sf_lt(&NTWO_M3, &r);
        *out = small ? small_r(r, c, i1, i0, rc) : normal_r(r, c, i1, i0, rc);
        return FSINCOS_OK;
    }
    /* ---- Case 2: |s| < 2^-33 ---- */
    sf_t w2  = sf_fma(&N, &P_3, &ZERO);
    sf_t U_1 = sf_fma(&N, &P_2, &w2);
    r = sf_fms(&s, &ONE, &U_1);
    sf_t U_2 = sf_fms(&N, &P_2, &U_1);                  /* exact residual */
    sf_t s2  = sf_fms(&s, &ONE, &r);
    sf_t rsq = sf_fma(&r, &r, &ZERO);
    U_2 = sf_fma(&U_2, &ONE, &w2);
    sf_t c = sf_fms(&s2, &ONE, &U_1);
    sf_t tmp = i1 ? ONE : r;
    if (i0) tmp = sf_fnma(&tmp, &ONE, &ZERO);           /* tmp = -tmp */
    sf_t t1 = sf_fma(&S_1, &r, &ZERO);
    c = sf_fms(&c, &ONE, &U_2);
    sf_t poly = i1 ? NTWO_M67 : sf_fma(&t1, &rsq, &c);
    *out = i0 ? sf_fms_s0(&tmp, &ONE, &poly, rc)
              : sf_fma_s0(&tmp, &ONE, &poly, rc);
    return FSINCOS_OK;
}

/* public: x87-format in/out */
typedef struct { uint16_t se; uint64_t sig; } x80_t;

static fsincos_status_t fsincos_ref(x80_t in, x80_t *sin_out, x80_t *cos_out, sf_rc_t rc)
{
    sf_t x = sf_from_parts((in.se >> 15) & 1, in.se & 0x7FFF, in.sig);
    sf_t s, c;
    fsincos_status_t st = sincos_core(x, 0, rc, &s);
    if (st != FSINCOS_OK) return st;
    (void)sincos_core(x, 1, rc, &c);
    sf_to_x87(&s, &sin_out->se, &sin_out->sig);
    sf_to_x87(&c, &cos_out->se, &cos_out->sig);
    return FSINCOS_OK;
}

/* ---------------- CLI ---------------- */

static int hex_se(const char *s, uint16_t *v)
{ unsigned long t = strtoul(s, NULL, 16); if (t > 0xFFFF) return 0; *v = (uint16_t)t; return 1; }

static int run_fma_test(void)
{
    /* lines: a_se a_sig b_se b_sig c_se c_sig op rc
       op: 0 fma, 1 fms, 2 fnma; rc: 0..3.  Output: se sig */
    unsigned as, bs, cs; unsigned long long am, bm, cm; int op, rc;
    while (scanf("%x %llx %x %llx %x %llx %d %d", &as, &am, &bs, &bm, &cs, &cm, &op, &rc) == 8) {
        sf_t a = sf_from_parts((as >> 15) & 1, as & 0x7FFF, am);
        sf_t b = sf_from_parts((bs >> 15) & 1, bs & 0x7FFF, bm);
        sf_t c = sf_from_parts((cs >> 15) & 1, cs & 0x7FFF, cm);
        sf_t r;
        if (op == 1) { sf_t nc = c; nc.sign ^= 1; r = sf_fma_rc(&a, &b, &nc, (sf_rc_t)rc); }
        else if (op == 2) { sf_t na = a; na.sign ^= 1; r = sf_fma_rc(&na, &b, &c, (sf_rc_t)rc); }
        else r = sf_fma_rc(&a, &b, &c, (sf_rc_t)rc);
        uint16_t se; uint64_t sig; sf_to_x87(&r, &se, &sig);
        printf("%04x %016llx\n", se, (unsigned long long)sig);
    }
    return 0;
}

static int selftest(void)
{
    int fail = 0;
    /* frcpa(1.0) = 0.998046875-ish: table[0]=0x3fc at bits 62:53, exp -1 */
    sf_t one = ONE, fr = sf_frcpa(&one);
    if (!(fr.exp == -1 && fr.sig == (0x8000000000000000ull | (0x3fcull << 53)))) {
        printf("FAIL frcpa(1)\n"); fail++;
    }
    /* frcpa(frcpa(1.0)) should approximate 1.0 to ~8 bits */
    sf_t fr2 = sf_frcpa(&fr);
    if (!(fr2.exp == 0)) { printf("FAIL frcpa^2(1) exp\n"); fail++; }
    /* engine: (1.5 * 2 - 3) == 0 exactly */
    sf_t th = { SF_FIN, 0, 0, 0xC000000000000000ull };
    sf_t two = { SF_FIN, 0, 1, 0x8000000000000000ull };
    sf_t three = { SF_FIN, 0, 1, 0xC000000000000000ull };
    sf_t z = sf_fms(&th, &two, &three);
    if (!sf_is_zero(&z)) { printf("FAIL 1.5*2-3\n"); fail++; }
    /* rshf trick: x = 100.0 -> N = round(100 * 2/pi) = round(63.66) = 64 */
    sf_t hundred = { SF_FIN, 0, 6, 0xC800000000000000ull }; /* 100 = 1.5625*64 */
    sf_t nsig = sf_fma(&hundred, &INVPI_2TO63, &RSHF_2TO64);
    int64_t n = (int64_t)(nsig.sig - 0xC000000000000000ull);
    if (n != 64) { printf("FAIL rshf N(100) = %lld\n", (long long)n); fail++; }
    /* negative: x = -100 -> N = -64 */
    sf_t mh = hundred; mh.sign = 1;
    nsig = sf_fma(&mh, &INVPI_2TO63, &RSHF_2TO64);
    n = (int64_t)(nsig.sig - 0xC000000000000000ull);
    if (n != -64) { printf("FAIL rshf N(-100) = %lld\n", (long long)n); fail++; }
    /* sin(+0)=+0, sin(-0)=-0, cos(0)=1 */
    x80_t xin = { 0x0000, 0 }, so, co;
    fsincos_ref(xin, &so, &co, SF_RN);
    if (so.se != 0 || so.sig != 0) { printf("FAIL sin(+0)\n"); fail++; }
    if (co.se != 0x3FFF || co.sig != 0x8000000000000000ull) { printf("FAIL cos(0)\n"); fail++; }
    xin.se = 0x8000;
    fsincos_ref(xin, &so, &co, SF_RN);
    if (so.se != 0x8000 || so.sig != 0) { printf("FAIL sin(-0)\n"); fail++; }
    /* C2 for |x| >= 2^63 */
    x80_t big = { 0x403E, 0x8000000000000000ull };  /* 2^63 */
    if (fsincos_ref(big, &so, &co, SF_RN) != FSINCOS_C2) { printf("FAIL C2\n"); fail++; }
    printf(fail ? "SELFTEST: %d FAILURES\n" : "SELFTEST: ok\n", fail);
    return fail ? 1 : 0;
}

/* batch mode: "se_hex sig_hex" per line ->
 * "OK <sin_se> <sin_sig> <cos_se> <cos_sig>" or "C2".
 * Same output format as the x87 capture harness => directly diffable. */
static int run_batch(void)
{
    unsigned se; unsigned long long sig;
    while (scanf("%x %llx", &se, &sig) == 2) {
        x80_t in = { (uint16_t)se, (uint64_t)sig }, s, c;
        if (fsincos_ref(in, &s, &c, SF_RN) == FSINCOS_C2) { puts("C2"); continue; }
        printf("OK %04x %016llx %04x %016llx\n",
               s.se, (unsigned long long)s.sig, c.se, (unsigned long long)c.sig);
    }
    return 0;
}

int main(int argc, char **argv)
{
    if (argc >= 2 && !strcmp(argv[1], "--fma-test")) return run_fma_test();
    if (argc >= 2 && !strcmp(argv[1], "--selftest")) return selftest();
    if (argc >= 2 && !strcmp(argv[1], "--batch"))    return run_batch();
    if (argc == 3) {
        x80_t in, s, c;
        uint16_t se;
        if (!hex_se(argv[1], &se)) { fprintf(stderr, "bad se\n"); return 2; }
        in.se = se;
        in.sig = strtoull(argv[2], NULL, 16);
        fsincos_status_t st = fsincos_ref(in, &s, &c, SF_RN);
        if (st == FSINCOS_C2) { printf("C2\n"); return 0; }
        printf("S %04x %016llx\n", s.se, (unsigned long long)s.sig);
        printf("C %04x %016llx\n", c.se, (unsigned long long)c.sig);
        return 0;
    }
    fprintf(stderr,
        "usage: %s <se_hex4> <sig_hex16> | --selftest | --fma-test\n", argv[0]);
    return 2;
}
