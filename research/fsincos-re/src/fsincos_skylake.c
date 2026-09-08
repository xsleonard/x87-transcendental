/*
 * fsincos_skylake.c — behavioral model of the Intel Skylake x87
 * FSIN/FCOS/FSINCOS, reconstructed empirically against silicon captures.
 *
 * STATUS (2026-07-21) vs Skylake Xeon captures — historical baseline
 * 99.360% bit-exact over the 50k master sweep; --round18-poly 99.470%;
 * adding --round21-table-bias and the small-path extension reaches 99.610%;
 * Rounds 23/24 reach 99.660% (49,868/50,038).  The reconstructed P6 Round 37
 * reaches 99.906% (49,991/50,038); every miss is 1 ulp on one output.
 * --round16-narrow enables the constraint-validated 66/68/69-bit narrow
 * table refinement described below.  --round18-poly enables the independently
 * validated 64/67-bit polynomial refinement.  --round19-wide-q carries the
 * same six-term producer into only the wide table cosine-polynomial chain.
 * --round21-table-bias enables the paired-tomography shared-S state
 * refinement. --round23-narrow-coefficient enables the cross-validated
 * row-169 equivalent correction. --round24-table-delta-rn67 enables the
 * RN67 correction accumulator. --round28-tang-narrow evaluates the narrow
 * table reconstruction in Tang's published split form and materializes its
 * C*p product away from zero at 64 bits. --round29-p5-fmul-route replaces
 * that proxy with constrained direct/reduced X67*Y64 operand routes.  The
 * standalone FSIN path also uses
 * --round30-fsin-cosine-square to distinguish the two square-product
 * normalization cases in its odd-quadrant internal cosine producer.
 * --round31-fsin-cosine-tail selects the independently captured low-bit
 * tail-carrier refinement. --round32-fsin-cosine-horner selects the
 * independently captured fifth-Horner normalization/sticky refinement.
 * --round33-fsin-cosine-product selects the independently captured
 * sticky-preserving 67-bit carrier for the preceding fifth product.
 * --round34-table-lookup-firc routes the wide-table lookup constant for
 * Tang's cross*p product through the 64-bit FMUL Y operand using RN.
 * --round35-table-p-terminal materializes the terminal wide P coefficient
 * away from zero at 64 bits and retains a chopped 65-bit terminal sum.
 * --round36-table-fadd-microcontrol selects the freshly validated lane-local
 * first-FADD carrier rule in the wide reconstruction.
 * --round37-p6-four-term replaces the empirical table producer/final graph
 * in every cell with the reconstructed P6 four-term graph and adjusted
 * highest-degree sine coefficient, then
 * uses the shared ordinary-FMUL chop67 class for the P/Q Horner products,
 * P*a*a, and P*a*a*a, plus the surviving explicit final-product schedule.
 * --round38-p6-cosine-split evaluates standalone FCOS's direct six-term
 * polynomial as the reconstructed P6 two-chain evaluation, with
 * h235's independently held-out boundary materializations.
 * --round39-fcos-tiny selects the captured standalone-FCOS directed-rounding
 * boundary for nonzero |x| below 2^-32.
 * --round40-fsincos-tiny applies the corresponding captured sine/cosine
 * boundaries to both lanes of paired FSINCOS.
 * --round41-fsin-cosine-split evaluates standalone FSIN's odd-quadrant
 * internal cosine with its independently constrained two-chain schedule.
 * --round42-p6-sine-split evaluates standalone FSIN/FCOS sine-producing
 * polynomial paths with the independently constrained two-chain schedule.
 * --round43-p6-sine-bias refines the wide-table shared-sine carrier when
 * the local residual top exponent and final sine-FADD alignment match the
 * independently separated state.
 * --round44-p6-sine-bias extends that carrier selector to the independently
 * captured next exponent/alignment coordinate.
 * --round45-p6-sine-fraction resolves that second coordinate's retained
 * carrier representative on the finer 1/256-ulp grid.
 * --round46-p6-narrow-sine-fraction resolves the corresponding independently
 * captured narrow-table carrier coordinate on the same grid.
 * --round47-p6-narrow-sine-fraction extends that narrow-table selector to
 * the next independently captured exponent/alignment coordinate.
 * --round48-p6-narrow-sine-fraction selects the independently captured
 * larger carrier representative at the adjacent narrow-table coordinate.
 * --round49-p6-carrier-interval replaces those output-equivalent fractional
 * representatives with one uniform producer-to-FMUL carrier interval rule.
 * --round50-fsin-operation-classes evaluates standalone FSIN with ordinary
 * multiply and subtract at chop67, ordinary add and multiply-class at RN64,
 * and only the final add under architectural rounding control.
 * --round51-fsin-fadd-signature selects the observed chopped result at one
 * low-bit signature of the standalone sine-state FADD.
 * --round52-fcos-low3-carrier evaluates the standalone cosine polynomial
 * with the shared P6 arithmetic classes and retains the guarded low-three-bit
 * multiplier payload through its terminal product/add boundary.
 * --round53-fcos-operation-classes routes the complete finite standalone FCOS
 * path through the same modeled polynomial/table schedule as Round 50, with
 * the cosine phase increment and Round-52 terminal carrier.
 * It has zero output/C1 differences on the structured, dense, h347, h388, and
 * six table-carrier validation corpora.  The deliberately hostile h363/h372/
 * h380/h384 terminal-adder sets retain 2/8/22/72 output differences.
 * --round51-fsin-fadd-signature is accepted but inert in the
 * operation-class path since h406: after Round 53's exact-division quotient
 * no corpus input depends on the leaf, and its exact carrier signature
 * (difference 14, above-half, retained 0x8c, prefix 0xc1) recurs at the
 * h377 exponent-7 residual where hardware keeps the ordinary RN64 result.
 * --round55-narrow-sine-fraction14=K and --debug-sine-state are
 * analysis-only probes (a candidate carrier fraction at the legacy-kernel
 * narrow coordinate (-6,14), and a stderr trace of the operation-class
 * sine-state FADD).
 * --round56-fsin-cosine-carrier applies the Round-52 terminal cosine
 * carrier to FSIN's odd-quadrant internal cosine (shared physical
 * kernel); implies the Round-52 carrier machinery.  Validated by the
 * h405 residual windows and the fresh hardware-blind h409 separators
 * with zero corpus regression.
 * --round54-fsincos-table-lanes routes each paired FSINCOS table-path lane
 * through the corresponding standalone operation-class state (sine lane as
 * standalone FSIN, cosine lane as standalone FCOS).  Fresh paired-vs-
 * standalone silicon captures show the two instructions share the table
 * datapath bit-exactly (zero differences over the structured, dense, h347,
 * and h349 table observations) while polynomial-path behavior remains
 * paired-specific, so polynomial and tiny inputs keep the legacy paired
 * model.  Requires Rounds 50 and 53.
 * --f2xm1 selects the h251-h259 reconstructed F2XM1 entry point.
 * --fptan selects the reconstructed FPTAN entry point.  Its polynomial and
 * table paths are exact on the current dense, structured, focused, and
 * million-input RD captures.
 * The standalone path also uses h135's
 * independently validated path-aware terminal coefficients:
 *   |x| < 1/4        : Pentium ROM 6-term polys, Horner @64, FUSED finals
 *                      (baseline ~99%; Round-18 plus the h70-h74 q-product
 *                      refinement is exact on the 80k complete capture and
 *                      all four h83-h89 small-path discriminators through
 *                      exponent -32)
 *   1/4 <= |r|<=pi/4 : Pentium table kernel — bit-dispatched cells
 *                      (b in {18,22,26,30}/64 narrow, {36,44,52}/64 wide,
 *                      split at 1/2), baseline 4-term (narrow) / 6-term
 *                      (wide) ROM polys; Round 37 uses the reconstructed P6
 *                      four-term graph for every cell.  Wide-FUSED combine,
 *                      entries at native >=67 bits with two silicon-verified
 *                      bit corrections (~99%)
 *   pi/4 <= |x|<2^63 : reduction r(+wide bit) = x - N*trunc66(pi/2), exact
 *                      wide subtract — PROVEN bit-exact; the wide (65-bit)
 *                      reduced argument feeds the kernel directly
 *   >= 2^63          : C2, operand unchanged — PROVEN
 *
 * The polynomial candidate is exact on all current direct-path evidence.
 * Final-only versus every-edge q-product materialization remains
 * observationally equivalent.  Remaining table-path differences are
 * one-or-few rounding-position effects at the 2^-70..2^-72 level.  Round 19
 * transfers the six-term producer into the wide q-chain and improves all
 * three targeted RN/RD/RU sets, but loses one master-sweep RN match; it
 * therefore remains experimental.  Round 21 localizes a systematic table
 * residual to S rather than U=1+t and ports an equivalent state correction.
 * Round 24 then identifies the cross-validated final topology
 * T1 + RN67(T1*t +/- T2*S).  The exact origin of Round 21's sub-ulp S term
 * and Round 23's row-169 equivalent correction remains unresolved.  See
 * notes/skylake-comparison.md.
 *
 * The frozen Itanium reference lives in fsincos_itanium.c; experiment
 * scaffolding (--rhi/--split/--kvar/--kernel-test/--rc) lives HERE.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "ia64_sf.h"

/* exact architectural frcpa table (transcribed from IA-64 SDM vol 3) */
#include "../data/frcpa-recip-table.h"
#include "p5_rom_constants.h"
#include "f2xm1_constants.h"

int g_sf_split = 0;

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

/* =============== Skylake reduction: r + c = x - N*M66 ===================
 * M66 = pi/2 truncated to 66 significand bits = M66_INT * 2^-65,
 * M66_INT = 0x3_243F6A8885A308D3 (empirically identified; the "66-bit
 * internal pi").  N = nearest-int(x * 2/pi) (2/pi to 128 bits; tie behavior
 * assumed round-half-even — unobserved so far, flagged for boundary
 * captures).  The difference is computed EXACTLY in 192-bit integer
 * arithmetic; r = RN64 of it, c = the exact residual (at most one bit).
 * Proven bit-exact against silicon for pi/4 <= |x| < 2^24 near-multiple
 * probes and 3467/3467 large-range near-multiple probes once the full
 * sine/cosine kernel is included.  It is the complete reduction for
 * pi/4 <= |x| < 2^63. */
static const uint64_t SKY_TWO_OVER_PI_HI = 0xA2F9836E4E441529ull;
static const uint64_t SKY_TWO_OVER_PI_LO = 0xFC2757D1F534DDC0ull;
static const uint64_t SKY_M66_LO = 0x243F6A8885A308D3ull;   /* + (3 << 64) */

typedef struct { uint64_t l0, l1, l2; } u192;

static u192 u192_mul_64x128(uint64_t a, uint64_t bhi, uint64_t blo)
{
    u128 pl = (u128)a * blo, ph = (u128)a * bhi;
    u192 r;
    r.l0 = (uint64_t)pl;
    u128 mid = (pl >> 64) + (uint64_t)ph;
    r.l1 = (uint64_t)mid;
    r.l2 = (uint64_t)(ph >> 64) + (uint64_t)(mid >> 64);
    return r;
}

/* nearest-int of x*2/pi for finite normalized x (magnitude); e = x.exp */
static uint64_t sky_reduce_N(uint64_t sig, int32_t e)
{
    u192 P = u192_mul_64x128(sig, SKY_TWO_OVER_PI_HI, SKY_TWO_OVER_PI_LO);
    int s = 191 - (int)e;                     /* value = P * 2^(e-191) */
    /* s in [129, 191] for e in [0, 62]; e = -1 -> s = 192: x in [pi/4, 1),
     * x*2/pi in [0.5, 0.637): N = 0 or 1 decided by the rounding below. */
    uint64_t n;
    int gpos = s - 1;
    int guard, sticky;
    if (s >= 192) {
        n = 0;
        guard = (int)(P.l2 >> 63) & 1;
        sticky = (((P.l2 << 1) != 0) || P.l1 || P.l0);
    }
    else if (s > 128) {
        n = P.l2 >> (s - 128);
        guard = (int)((P.l2 >> (gpos - 128)) & 1);
        sticky = ((P.l2 & (((uint64_t)1 << (gpos - 128)) - 1)) | P.l1 | P.l0) != 0;
    } else {                                   /* s == 128 impossible here */
        n = P.l2; guard = (int)(P.l1 >> 63); sticky = ((P.l1 << 1) | P.l0) != 0;
    }
    if (guard && (sticky || (n & 1))) n++;     /* RN-even (tie unobserved) */
    return n;
}

/*
 * form the centered quotient by literal exact
 * division by the 66-bit reduction constant.  The complete operation replay
 * selects this over the older reciprocal seed at rare large arguments.
 */
static uint64_t fsincos_compat_reduce_n_exact(uint64_t sig, int32_t e)
{
    u128 dividend = (u128)sig << (e + 2);
    u128 divisor = ((u128)3 << 64) | SKY_M66_LO;
    u128 quotient = dividend / divisor;
    u128 remainder = dividend % divisor;
    if ((remainder << 1) > divisor)
        quotient++;
    return (uint64_t)quotient;
}

/* r + c = x - N*M66 exactly; returns via out params */
static void sky_reduce_rc(const sf_t *x, uint64_t N, sf_t *r, sf_t *c)
{
    /* A = |x| * 2^65 = sig << (e+2)   (exact; e >= -1 here) */
    int k = (int)x->exp + 2;                  /* 1..64 */
    u192 A = {0, 0, 0};
    if (k == 64) { A.l1 = x->sig; }
    else { A.l0 = x->sig << k; A.l1 = x->sig >> (64 - k); }
    /* B = N * M66_INT = N*lo + (3N << 64) */
    u128 t = (u128)N * SKY_M66_LO;
    u128 u = (u128)N * 3;
    u192 B; B.l0 = (uint64_t)t; B.l1 = (uint64_t)(t >> 64); B.l2 = 0;
    u128 mid = (u128)B.l1 + (uint64_t)u;
    B.l1 = (uint64_t)mid;
    B.l2 = (uint64_t)(u >> 64) + (uint64_t)(mid >> 64);
    /* signed diff d = A - B (3-limb) */
    int dneg;
    u192 D;
    int a_ge_b = (A.l2 != B.l2) ? (A.l2 > B.l2)
               : (A.l1 != B.l1) ? (A.l1 > B.l1) : (A.l0 >= B.l0);
    const u192 *hi = a_ge_b ? &A : &B, *lo = a_ge_b ? &B : &A;
    dneg = !a_ge_b;
    uint64_t borrow = 0;
    D.l0 = hi->l0 - lo->l0;                    borrow = hi->l0 < lo->l0;
    D.l1 = hi->l1 - lo->l1 - borrow;           borrow = (hi->l1 < lo->l1) || (hi->l1 == lo->l1 && borrow);
    D.l2 = hi->l2 - lo->l2 - borrow;
    dneg ^= x->sign;                           /* apply x's sign */
    /* |d| < 2^65 (r <= ~pi/4 * 2^65): l2 must be 0, l1 in {0,1} */
    if (D.l2 != 0 || D.l1 > 1) { *r = sf_qnan(); *c = sf_qnan(); return; }
    if (D.l1 == 0 && D.l0 == 0) { *r = sf_zero(dneg); *c = sf_zero(dneg); return; }
    if (D.l1) {                                /* 65 significant bits: round */
        int g = (int)(D.l0 & 1);
        uint64_t kept = ((uint64_t)1 << 63) | (D.l0 >> 1);
        int64_t resid = g;                     /* d - trunc(d)/1  in 2^-65 units */
        int32_t rexp = -1;                     /* msb at 2^64 * 2^-65 = 2^-1 */
        if (g && (kept & 1)) {                 /* RN-even: round up */
            kept += 1;
            resid = -1;
            if (kept == 0) { kept = (uint64_t)1 << 63; rexp += 1; }
        }
        r->cls = SF_FIN; r->sign = (uint8_t)dneg; r->exp = rexp; r->sig = kept;
        if (resid == 0) *c = sf_zero(dneg);
        else {
            /* residual: d - r = resid * 2^-65 in the magnitude frame */
            c->cls = SF_FIN;
            c->sign = (uint8_t)(((resid < 0) ? 1 : 0) ^ dneg);
            c->exp = -65; c->sig = (uint64_t)1 << 63;
        }
    } else {                                   /* <= 64 bits: exact */
        uint64_t v = D.l0;
        int b = 63; while (!(v >> b)) b--;
        r->cls = SF_FIN; r->sign = (uint8_t)dneg;
        r->exp = b - 65;
        r->sig = v << (63 - b);
        *c = sf_zero(dneg);
    }
}


/* ---------------- kernels ---------------- */
/* i1 = bit0 of N_Inc (0: sine kernel, 1: cosine kernel);
   i0 = bit1 of N_Inc (result sign).  rc = user rounding mode (final op). */

static int g_dump_internals;     /* fwd decl; defined with the DI kit */

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
    if (g_dump_internals)
        fprintf(stderr,
            "DI_SMALL i1=%d i0=%d r=%d:%d:%016llx c=%d:%d:%016llx "
            "rsq=%d:%d:%016llx lead=%d:%d:%016llx poly=%d:%d:%016llx\n",
            i1, i0,
            (int)r.sign, r.exp, (unsigned long long)r.sig,
            (int)c.sign, c.exp, (unsigned long long)c.sig,
            (int)rsq.sign, rsq.exp, (unsigned long long)rsq.sig,
            (int)lead.sign, lead.exp, (unsigned long long)lead.sig,
            (int)poly.sign, poly.exp, (unsigned long long)poly.sig);
    return i0 ? sf_fms_s0(&lead, &ONE, &poly, rc)
              : sf_fma_s0(&lead, &ONE, &poly, rc);
}

/* H1 experiment: how silicon might form r_hi (no frcpa on real x87).
 * 0 = Itanium frcpa(frcpa(r)); k>0 = truncate r's significand to top k bits;
 * k<0 = round-to-nearest r to |k| significand bits. */
static int g_rhi_mode = 0;

static sf_t make_r_hi(const sf_t *r)
{
    if (g_rhi_mode == 0) {
        sf_t h1 = sf_frcpa(r);
        return sf_frcpa(&h1);
    }
    int k = g_rhi_mode > 0 ? g_rhi_mode : -g_rhi_mode;
    sf_t t = *r;
    uint64_t mask = (k >= 64) ? ~0ull : ~((1ull << (64 - k)) - 1);
    uint64_t kept = t.sig & mask;
    if (g_rhi_mode < 0 && k < 64) {                 /* RN to k bits */
        uint64_t half = 1ull << (63 - k);
        uint64_t rem = t.sig & ~mask;
        if (rem > half || (rem == half && (kept & (1ull << (64 - k)))))
            kept += 1ull << (64 - k);
        if (kept == 0) { kept = 0x8000000000000000ull; t.exp++; }  /* carry */
    }
    t.sig = kept;
    return t;
}

/* H1d experiment: naive (no U_hi/U_lo split) kernel variants.
 * 1: sin res = r + rcube*(PP1c_rn + rsq*horner), cos res = 1 + rsq*(QQ_1 + rsq*horner)
 * 2: same but PP1c truncated (0x...AAAA)
 * 3: variant 1 with t = (rsq*pfull)*r for sine
 * Valid comparison only when c == 0 (quick paths).  */
static int g_kvar = 0;

static sf_t kernel_naive(sf_t r, int i1, int i0, sf_rc_t rc)
{
    static const sf_t PP1_RN = { SF_FIN, 1, -3, 0xAAAAAAAAAAAAAAABull };
    static const sf_t PP1_TR = { SF_FIN, 1, -3, 0xAAAAAAAAAAAAAAAAull };
    sf_t rsq = sf_fma(&r, &r, &ZERO);
    sf_t poly, pfull, t, lead, res;
    if (!i1) {
        poly = sf_fma(&rsq, &PP_8, &PP_7);
        poly = sf_fma(&rsq, &poly, &PP_6);
        poly = sf_fma(&rsq, &poly, &PP_5);
        poly = sf_fma(&rsq, &poly, &PP_4);
        poly = sf_fma(&rsq, &poly, &PP_3);
        poly = sf_fma(&rsq, &poly, &PP_2);
        pfull = sf_fma(&rsq, &poly, g_kvar == 2 ? &PP1_TR : &PP1_RN);
        if (g_kvar == 3) {
            t = sf_fma(&rsq, &pfull, &ZERO);
            t = sf_fma(&t, &r, &ZERO);
        } else {
            sf_t rcube = sf_fma(&r, &rsq, &ZERO);
            t = sf_fma(&rcube, &pfull, &ZERO);
        }
        lead = r;
    } else {
        poly = sf_fma(&rsq, &QQ_8, &QQ_7);
        poly = sf_fma(&rsq, &poly, &QQ_6);
        poly = sf_fma(&rsq, &poly, &QQ_5);
        poly = sf_fma(&rsq, &poly, &QQ_4);
        poly = sf_fma(&rsq, &poly, &QQ_3);
        poly = sf_fma(&rsq, &poly, &QQ_2);
        pfull = sf_fma(&rsq, &poly, &QQ_1);
        t = sf_fma(&rsq, &pfull, &ZERO);
        lead = ONE;
    }
    if (i0) lead = sf_fms(&ZERO, &ONE, &lead);
    res = i0 ? sf_fms_s0(&lead, &ONE, &t, rc) : sf_fma_s0(&lead, &ONE, &t, rc);
    (void)res;
    return res;
}

/* --dump-final: print the two exact operands of the final user-mode op
 * (lead/U_hi and poly/V) so T_ref = a+b can be reconstructed exactly. */
static int g_dump_final = 0;
/* T1/T2 theta-band forensics (2026-08-18): --dump-internals prints
 * DI_* records to stderr for the cos terminal-correction path;
 * --perturb=tgt:delta nudges ONE terminal-correction input sig at
 * the fcos_low3_terminal_correction entry (tgt: odd/even/sq/f4/mag).
 * Both are inert when unset (the default): no output or state
 * change on any shipped path. */
static int g_dump_internals = 0;
static int g_dump_r59_compact = 0; /* --dump-r59-compact: DI_IN/DI_TC/DI_R59 */
static int g_perturb_tgt = 0;    /* analysis-only producer selector; see CLI parser */
static int g_perturb_delta = 0;
static int g_rcfold_bits = 0;    /* --rcfold=B:rn|chop; 0 = shipped */
static int g_rcfold_rn = 0;
static int g_sinechain = 0;      /* --sinechain=N; 0 = shipped RN64 */
static int g_sinespec[4] = {0,0,0,0};   /* pb, pm, sb, sm; 0 = off */
static char g_sineedges[8] = {0};       /* per-product-edge spec */
static int g_sp3[2] = {0, 0};           /* third-edge bits/mode */
static int g_sinefin = 0;               /* --sinefin=K lookahead round */
/* Round 71 (PROMOTED 2026-08-19): default-path terminal guard-carry
 * — carry the retained lsb iff the S-B discarded field's top 8 bits
 * are all ones AND the payload machinery is inactive AND low3 != 0.
 * Gauntlet: randv1 25->21 (4 fixed, 0 broken), comb exactly 30,
 * hostv1 exactly 4, VM FSIN 0x5.  Build -DG_ROUND70=0 to A/B the
 * pre-R71 form. */
#ifndef G_ROUND70
#define G_ROUND70 1
#endif
static const int g_round70_default_carry = G_ROUND70;
/* Round 87 (PROMOTED 2026-08-26; suite accounting corrected same
 * day): the act0 default-carry guard field is SEVEN all-ones
 * discarded bits, not eight.  Found by the R86-method width
 * battery (T/W, 2026-08-25): +37 banked act0 vote rows fixed,
 * zero wrong pool values; W2 (guard 9, votes -39) confirms the
 * gradient; rv5 fresh blind (locked ecc63ce, seed 0x8726,
 * epoch-probed 43/43): W1 fixed a fresh act0 operand under two
 * modes (P1/P2 pass, positive-pass beyond the R78 neutral bar).
 * SUITE ACCOUNTING (the battery's count-only sweep read a
 * one-for-one swap as 43==43 "zero collateral"; the standing
 * regression caught it): guard-7 FIXES ledger row randv1:7990815
 * ru (key deleted per the R86 precedent) and BREAKS
 * randv1:4615048 rn — hardware does NOT carry there although the
 * top seven discarded bits are ones (fire71 lands +1 on the
 * negative correction term, model = hw-1ulp).  That row is the
 * one banked counterexample (key added, censused); the
 * discriminant beyond pure width is the open act-guard frontier.
 * Net ledger 43 keys / 40 operands unchanged.  Build
 * -DG70_GUARD=8 to A/B the pre-R87 eight-bit read.  [R88
 * superseded the width test entirely — G70_GUARD acts only
 * under -DG70_LEGACY_WIDTH=1; see the fire71 comment.] */
#ifndef G70_GUARD
#define G70_GUARD 7
#endif
#ifndef G70_WIN
#define G70_WIN 30      /* act0 accumulator window (probe) */
#endif
/* Round 72 candidate (REJECTED 2026-08-20, kept for A/B): the
 * run-length/low3 STAIRCASE — carry iff active==0 AND
 * (low3 << run) > 128, run = leading-ones run of the discard field.
 * Exact on the h788 definitive pool (102/102 carry-POS, 79/79 NEG;
 * R71 = the run>=8 tail) but REFUTED by fresh blind chunks: ck14
 * 8 fixed / 11 broken, ck15 10 fixed / 12 broken — the (run 5-7)
 * cells are MIXED on fresh data (the pool's negative coverage was
 * biased).  Deeper frames (sf8 = top-8-anchored shortfall, the
 * DI_FIN neg split) tighten but do not separate: exact twins at
 * (neg, low3, sf8) persist, including carry-vs-borrow pairs at
 * identical coarse state, and an h798 bit microscope over the
 * terminal value frame is at the noise ceiling.  The conditioner is
 * below the terminal value frame (h486-class).  MUST NOT be enabled
 * without a new conditioner + full gauntlet. */
#ifndef G_ROUND72
#define G_ROUND72 0
#endif
static const int g_round72_staircase_carry = G_ROUND72;
/* Round 73 (PROMOTED 2026-08-19): THE pm/BLOCK-START GATE — the
 * default-band carry conditioner found by extending h662k's
 * block-start frame to the terminal band (h822-h838).  pm = the
 * shared-prefix run of the aligned S,B above the discard boundary
 * (a joint S^B property, invisible to every single-field frame).
 * Fires with the discard near-full (theta<0, |theta|<=32),
 * active==0, in five (phw,b8,bbs) cells; the A1 cell ships its
 * CLEAN TAIL only (at==1, or at==2 with low3>=3 — the deeper
 * interior at 3..pm is genuinely mixed and stays open).  Fire =
 * retained lsb += 1 (R71 semantics); R73 = R71 OR this gate.
 * VALIDATION: exact on the ck14 at-window (26 claimed fires,
 * 33,844/33,844 negatives); fresh blinds nk10 5F/0B, nk11 2F/0B;
 * gauntlet: randv1 21->18 (3 fixed, 0 broken), comb exactly 30,
 * hostv1 exactly 4, VM FSIN 0x5.  Build -DG_ROUND73=0 to A/B. */
#ifndef G_ROUND73
#define G_ROUND73 1
#endif
static const int g_round73_pm_gate = G_ROUND73;
/* Round 74 (PROMOTED 2026-08-19): A1-interior extension — the two
 * clean cells from the nk10/nk18-23 blind-labeled interior pool
 * (h842: at==3 & low3>=3: 4F/0N; at==4 & low3>=4: 7F/0N; the
 * frontier edge (at>=5, exact (low3,at) collisions) stays open).
 * Gauntlet: randv1 neutral 18 (0F/0B), comb exactly 30, hostv1
 * exactly 4, VM FSIN 0x5; fresh blinds nk24 0F/0B, nk25 0F/0B
 * (full-rerun verified after a truncated-file scoring artifact).
 * Build -DG_ROUND74=0 to A/B. */
#ifndef G_ROUND74
#define G_ROUND74 1
#endif
static const int g_round74_a1_ext = G_ROUND74;
/* Round 75 (PROBATION): the ACT1 pm-gate — the payload-active
 * stratum in the same block-start frame (h847: payload-inclusive S;
 * fires 40/74 at pm>=9 vs 0.6% of near-end negatives; both theta
 * signs fire, direction = ((neg==1) ^ (theta>0)) ? +1 : -1 per the
 * h811 deterministic-given-fire table).  Clean tail: pm>=9 &
 * |theta|<=40, plus pm==8 & b8 & |theta|<=8.  Default OFF until
 * blind + gauntlet. */
/* Round 78 (PROMOTED 2026-08-19) = the act1 lane-byte box riding
 * the R75 machinery (direction formula ((neg)^(theta>0)) ? +1 : -1
 * + the borrow branch): with act==1, laneb<=4 and either diff==-3 &
 * pm>=10 or diff==0 & payload==0 & pm>=9.  Exact 4F/0N on the full
 * 369-neg pm>=8 ck14 window; ck14 4F/0B; blind nk46 0F/0B;
 * gauntlet randv1 neutral 18 / comb exactly 30 / hostv1 exactly 4 /
 * VM FSIN 0x5.  The FIRST act1 rule.  Enable/disable via G_ROUND75
 * (=1 shipped). */
#ifndef G_ROUND75
#define G_ROUND75 1
#endif
static const int g_round75_act1_gate = G_ROUND75;
/* Round 76 (PROMOTED 2026-08-19): A1 frontier-edge — the two
 * robust cells from the fully-folded nk pool (10F/53N clean;
 * thin cells deferred by the >=4-fires bar): at==5 & low3>=5 &
 * k>=8 & pm<=9, and at==6 & low3>=6 & k>=8.  Blind nk32 1F/0B;
 * gauntlet: randv1 neutral 18, comb exactly 30, hostv1 exactly 4,
 * VM FSIN 0x5.  Build -DG_ROUND76=0 to A/B. */
#ifndef G_ROUND76
#define G_ROUND76 1
#endif
/* Round 77 (PROMOTED 2026-08-19): the LANE-BYTE gate — deeper-DI
 * pass 1's first yield (h859/h860): laneb = B's byte at the payload
 * injection lane (left.e2 - 8), a column never dumped before this
 * pass.  Splits 6 of 10 mixed A1-residue cells; pooled k==9 rule
 * (laneb <= 3 AND (at 3..5 & low3>=3 | at==7 & low3>=6)) = 9F/100N
 * on the 27-chunk pool.  Blind nk45 0F/0B; gauntlet randv1 neutral
 * 18, comb exactly 30, hostv1 exactly 4, VM FSIN 0x5.
 * Build -DG_ROUND77=0 to A/B. */
#ifndef G_ROUND77
#define G_ROUND77 1
#endif
/* Round 79 (PROMOTED 2026-08-22): five A1 cells at the >=4F/0N bar
 * from the 687-chunk continuous harvest (h875: 368F/2888N fold):
 * (at5,l7,laneb>3,k8):19/0, (at6,l5,laneb<=3,k9):24/0,
 * (at8,l6,laneb>3,k9):7/0, (at8,l7,laneb>3,k9):7/0,
 * (at9,l7,laneb>3,k9):14/0 = 71 fires, 0 negatives.  Blind nkb1
 * 0F/0B; gauntlet randv1 neutral 18 / comb exactly 30 / hostv1
 * exactly 4 / VM FSIN 0x5.  Build -DG_ROUND79=0 to A/B. */
#ifndef G_ROUND79
#define G_ROUND79 1
#endif
static const int g_round79_cells = G_ROUND79;
/* Round 81 (PROMOTED 2026-08-22): THE FIRST MECHANISM-LAW ROUND —
 * the act1-box finer family's narrowed-R final add (h891-h895):
 * when active, laneb<=4, diff in [-3,0], span >= 10 (corr top <=
 * -10 vs L=1.0), the chip consumes corr PRE-ROUNDED to 64 sig
 * bits, ties EXCLUDED (rem==4 leaves corr untouched — the rb1
 * boundary negative; 0/197 fires are ties).  197 fires reproduced
 * full-mode-exact, 0 collateral (568 sensitive-checked); blinds
 * rb1 (caught the tie) -> rb2 0F/0B; gauntlet randv1 neutral 18 /
 * comb exactly 30 / hostv1 exactly 4 / VM FSIN 0x5.
 * Build -DG_ROUND81=0 to A/B. */
#ifndef G_ROUND81
#define G_ROUND81 1
#endif
static const int g_round81_corr_rn64 = G_ROUND81;
/* Round 82 (PROBATION): the span-6 exact clause of the narrowed-R
 * mechanism (h897): fire iff span==6 & diff==-3 & rem==(neg?7:1) &
 * low3==laneb+4.  226/226 fires, 0/35 forbidden rows — zero
 * overlap at full-window power.  Default OFF until blind+gates. */
#ifndef G_ROUND82
#define G_ROUND82 0
#endif
static const int g_round82_span6 = G_ROUND82;
/* Round 83 (PROBATION): act1 rn-class structural cells (h899, the
 * >=50F/0N bar): pm>=9 & theta>0 & b8==0 & (diff==-1 | diff==-3 &
 * pm==9) — 299 fires / 0 negatives; complements R78 (pm==9 at
 * diff-3; diff-1 at all pm>=9).  Default OFF until blind+gates. */
#ifndef G_ROUND83
#define G_ROUND83 0
#endif
static const int g_round83_rncells = G_ROUND83;
/* Round 84 (PROMOTED 2026-08-22): THE CAPTURED-EXCEPTION LEDGER.
 * Gauntlet at promotion: randv1 0/48,000,000, hostv1 0/12,019,944,
 * comb7-18 0 across all ten corpora, VM FSIN five corpora 0 x5;
 * flag-off byte-identical to the pre-R84 model (GATE4); no ledger
 * operand occurs in any VM corpus (9/9 audit).  Not a
 * derived law — the residual suite distance shipped as data after
 * the 2026-08-22 frontier-closure verdict (HANDOFF h901/h902):
 * every stratum whose gate is a function of state reconstructible
 * on the capture hosts is derived and shipped (R18..R81, R86); the
 * r84_ledger keys (one suite row each) are proven, by five independent
 * closure programs at 10^2..10^4-row power, to read inputs outside
 * every frame the model computes.  2026-08-23 UPDATE: the "machine
 * state / epoch" reading is RETRACTED — the deviations are
 * bit-stable across five days (0/48M hardware-vs-hardware) and
 * bit-identical on a second physical machine (54/54 keys): they
 * are deterministic, portable, UNDERIVED ALGORITHM (sine value
 * mechanism f4'=chop67(sq*(sq&~7)) exact 234/234; activation
 * predicate = the open derivation target; cos strata =
 * R72/R82/R83/A1 dissolution-class last-bit laws).
 * The overlay fires on exact (instruction, rc, 80-bit operand)
 * match only, so its full sensitive-row space IS the list — the
 * R83 survival criterion holds by construction and off-list
 * behavior is bit-identical to flag-off.  Every entry remains an
 * open problem per GOAL.md (mechanism target: bare-metal /
 * off-host instruments); delete entries as derivations land — the
 * R57-tables -> R61-closed-form arc is the precedent.  Sources:
 * banked i7 captures /root/h491 (comb7 2026-08-10 .. comb18
 * 2026-08-15, randv1 2026-08-18, hostv1 2026-08-19); no key
 * conflict exists across the 183M-row suite (verified 2026-08-22/23,
 * /root/r84/misses.tsv, committed as experiments/r84_misses.tsv +
 * r85_rz_misses.tsv).  ROUND 85 EXTENSION (2026-08-23): the suite
 * gained the RZ rounding mode on every corpus, both hosts (45.7M
 * fresh captures, epoch-probed 50/50 before and after each batch):
 * 5 deviations, ZERO new operands — every RZ miss is a known
 * machine-state operand behaving mode-consistently (RZ==RD on
 * positive results reproduced byte-identically, e.g. the comb15
 * fb90 singleton; RZ==RU on the negative-result sine rows).
 * ROUND 86 (2026-08-23/24): the sine-chain law (G_ROUND86) derived
 * 11 of the keys (all sine-family: hostv1's convergent operand and
 * randv1's six ops); they are DELETED from this table per the
 * R57->R61 replacement arc.  The remaining 43 keys are the
 * cos-terminal/act families.
 * ROUND 87 (2026-08-26): one-for-one key swap with the guard-7
 * width correction (randv1:7990815/ru deleted, randv1:4615048/rn
 * added).  ROUND 88 (2026-08-26): the act0 adder law derived
 * THREE more keys (randv1:2593581/rn, 6363167/ru, 4615048/rn) —
 * deleted; the table now holds 40 keys / 37 operands, all
 * act1/payload-family and comparator-band rows.
 * R1379 AUDIT (2026-09-02): replaying every remaining entry against
 * the promoted ledger-disabled source proves 24 of the 33 keys derived;
 * they are deleted below.  The ledger now contains nine keys over eight
 * operands.  The current ledger-disabled suite has two additional d0d0
 * mode rows not present in the historical ledger; they remain explicit
 * misses and were not converted into new lookup entries.
 * Build -DG_ROUND84=0 to A/B the pre-R84 derived model. */
#ifndef G_ROUND84
#define G_ROUND84 0
#endif
static const int g_round84_errata = G_ROUND84;
/* H1708: promoted general standalone arithmetic. Historical R84/R96 bodies
 * remain for explicitly disabled-promotion comparisons, not the default path.
 * A separate active-entry bit is essential: the old paired FSINCOS table
 * route temporarily sets the standalone flags and must NOT inherit this
 * promotion before its own independent validation. */
#ifndef G_GENERAL_STANDALONE
#define G_GENERAL_STANDALONE 1
#endif
#ifndef G_GENERAL_PAIRED
#define G_GENERAL_PAIRED 1
#endif
#ifndef G_GENERAL_TRACE
#define G_GENERAL_TRACE 0
#endif
static int g_general_standalone_active;
static int g_general_trace = G_GENERAL_TRACE;
static int g_general_c1, g_general_c1_known;
/* Round 86 (PROMOTED 2026-08-23/24): THE SINE-CHAIN SQUARER-PORT
 * TRUNCATION — the i1==0 fourth power is computed with one input
 * port truncated 67->64 bits:
 *     fourth = chop67(square * (square & ~7))
 * h779's exact value mechanism (234/234 on fires), established as
 * the UNCONDITIONAL datapath (no gate variable; "fires" are simply
 * the rows where the truncation is architecturally visible).
 * Evidence: vote pools 547 fixed / 312 non-sine unchanged / 0
 * wrong values (859 banked fire rows); full suite 57 -> 43 misses,
 * ZERO collateral in 183M rows (hostv1 -> 0 under pure law; the
 * fixed randv1 operands = the census's six); rv3 fresh blind
 * (locked prediction commit 1e0f53e): P1 zero law-only misses,
 * P2 every changed row lands the hardware bits (a fresh sine
 * operand x3 modes + a fresh cos-lane row), P3 2 < 6.  Replaces
 * 11 ledger keys (deleted — the first mechanism-for-data deletion
 * since R61).  Build -DG_ROUND86=0 to A/B. */
#ifndef G_ROUND86
#define G_ROUND86 1
#endif
/* Probe flags (2026-08-24 campaign vs the 43 residual rows): the
 * shared-squarer hypothesis — R86's one-port truncation applied to
 * the OTHER fourth powers.  Experiments only, default OFF. */
#ifndef G_F4PC          /* cos branch of the shared poly producer */
#define G_F4PC 0
#endif
#ifndef G_F4PT          /* the near-1 FCOS terminal producer */
#define G_F4PT 0
#endif
#ifndef G_TERMV         /* terminal input-port truncation battery */
#define G_TERMV 0
#endif
#ifndef G_CORRB         /* corr-narrowing battery: 0=shipped,
                         * 1=uncond tie-excl, 2=uncond ties-even,
                         * 3=uncond ties-away, 5=gates-off+uncond */
#define G_CORRB 0
#endif
#ifndef G_PAYOFF        /* h912 activation A/B probe: 1 = decline
                         * every payload activation (F2(0) — the
                         * plain chop67 terminal on active rows);
                         * pair with -DG_ROUND75=0 -DG_ROUND81=0 so
                         * no act1 gate corrects on top */
#define G_PAYOFF 0
#endif
#ifndef G_TAILS         /* h912 terminal-composition probe: 1 = the
                         * cosine terminal accumulates the FULL
                         * left/right products (discarded tails
                         * included) before its chop67 — the h911
                         * down-law composition chop67(fullL+fullR);
                         * 2 = full LEFT product only, right chopped
                         * (the h912 one-carrier composition) */
#define G_TAILS 0
#endif
/* Round 89 (PROMOTED 2026-08-27): the act1 activation gate — the
 * payload fires per zone walls plus a monotone pay2-staircase over
 * (cell, grl) in the block; declined rows take the payload-off
 * path and skip the R75/R81 act1 gates.  Walls derived at 1,375
 * labeled operands (L0 always / DEEP never, zero blind
 * violations); the block staircase is FITTED, not derived (its
 * (9,-72) grl 5-8 band is h486-shaped: 11/129 errors on the
 * batch-3 pre-registered blind, every declined-fire miss
 * exact-tail-consistent — the G_tail unification may replace the
 * band arm).  Validation: batch-3 blind 11-vs-35 vs incumbent
 * (bar 3.2x); suite exactly-36 misses = the undischarged ledger
 * (4 keys derived, ZERO collateral in 183M); VMFSIN 12/12 zero;
 * rv7 (seed 0x8728, 32M results, pre-reg 4a77b8f) POSITIVE PASS
 * 5-0 difference rows, P2 10<=15.  0 = pre-R89 behavior (fire on
 * every active row); 2 = the L_B alternate (blind runner-up). */
#ifndef G_R93OVR        /* h956/h959 clean-label (cell,g,pay) gate
                         * override table: 143 tuples where the
                         * value-level majority at 34k-op power
                         * contradicts the h913 staircase (blind
                         * holdout 266-vs-536).  1 = on. */
#define G_R93OVR 1
#endif
#ifndef G_R95XSUP       /* h975-h986 exact-support gate: fitted
                         * post-chop terminal adjustments are
                         * suppressed when the exact terminal
                         * composition's chop67 contradicts them
                         * (census 616-vs-19; two carve familes
                         * kept).  1 = on. */
#define G_R95XSUP 1
#endif
#ifndef G_R96FORCE      /* h998 sensitivity probe, NEVER shipped:
                         * replace the fitted terminal by plain chop67(A)
                         * plus one forced value-frame quantum in one ladder.
                         * 1=top act0 n=-1; 2=top act1 n=-1;
                         * 3=low act1 n=+1; 4=top act0 opposite;
                         * 5=top act1 opposite; 6=low act1 opposite;
                         * 7/8=low act0 in the two directions;
                         * 9/10=low act1 at -/+ one half quantum.
                         * Default zero is inert. */
#define G_R96FORCE 0
#endif
#ifndef G_R96RES2045    /* h1005/h1011 pre-gate residue candidate:
                         * on the active top line, choose plain chop67(A)
                         * plus one magnitude quantum when the counterfactual
                         * pre-paygate residue is strictly above 2045/2048.
                         * Analysis-only until blind validation. */
#define G_R96RES2045 0
#endif
#ifndef G_R96M12       /* h997/h1001 conservative active-top arms:
                         * magnitude bits 12..14 below the terminal cut. */
#define G_R96M12 0
#endif
#ifndef G_R96C11       /* h1017 corrected post-gate carry-select arm:
                        * active top, 11-bit window, assumed carry-in. */
#define G_R96C11 0
#endif
#ifndef G_R96TOPR60    /* h1016 raw R60-ring upper inactive arms. */
#define G_R96TOPR60 0
#endif
#ifndef G_R96TOPPAIR   /* h1016 paired terminal/right upper inactive law. */
#define G_R96TOPPAIR 0
#endif
#ifndef G_R96LOWR60    /* h1016 raw R60-ring lower active corner law. */
#define G_R96LOWR60 0
#endif
#ifndef G_R96PAIRR60   /* h1016 paired terminal-residue upper active law. */
#define G_R96PAIRR60 0
#endif
#ifndef G_R96TOPCLOSED /* h1030-h1038 closed carry-selector law for the
                        * inactive upper ladder.  The outer R60 coordinate
                        * is qualified by a five-column downward propagate
                        * block.  Promoted after h1055-h1066 silicon-blind
                        * transfer and independent wide-seed validation. */
#define G_R96TOPCLOSED 1
#endif
#ifndef G_R96TOPALLP   /* h1058 inactive-upper response probe: admit both
                        * values of the retained-cut propagate bit to test
                        * whether it is selector data or merely training
                        * support.  Has no effect unless TOPCLOSED is on. */
#define G_R96TOPALLP 0
#endif
#ifndef G_R96ACTCLOSED /* h1042-h1054 active-ladder carry-selector law:
                        * 11-bit terminal endpoint plus the exact R60
                        * integer coordinate.  Table-free comparison tree;
                        * promoted after h1055-h1066 compiled blind
                        * validation. */
#define G_R96ACTCLOSED 1
#endif
#ifndef G_R97D9LADDER /* h1078-h1133: ce=-74 distance-9
                       * decreasing-endpoint D-ladder.  Promoted after the
                       * disjoint 129/542 discovery/holdout split and the
                       * cached all-score and 56M-leg no-regression walls. */
#define G_R97D9LADDER 1
#endif
#ifndef G_R98ACTLOW5 /* h1082-h1133: active-lower low3=5 R60 comparator
                      * plus five-column propagate block.  Promoted with the
                      * same frozen support-boundary validation as R97. */
#define G_R98ACTLOW5 1
#endif
#ifndef G_R99FORCE /* analysis-only absolute R59 response:
                    * 1..5 select retained deltas -2..+2 from R0. */
#define G_R99FORCE 0
#endif
#ifndef G_R99CARRY /* analysis-only exact R59 subtractor carry endpoint:
                    * 0/1 force the corresponding carry; -1 is inert. */
#define G_R99CARRY (-1)
#endif
#ifndef G_R99BYPASS /* analysis-only: decline every R59 return. */
#define G_R99BYPASS 0
#endif
#ifndef G_R99TAPS /* analysis-only: 1..4 replace (b1,b2) by 00..11. */
#define G_R99TAPS 0
#endif
#ifndef G_R99CE75 /* analysis-only: admit ce=-75 to absolute R59 response
                   * probes; the default model's validated scope is unchanged. */
#define G_R99CE75 0
#endif
#ifndef G_R99WIDESCOPE /* analysis-only: let absolute response probes cross
                        * the validated distance 7..10 selector boundary. */
#define G_R99WIDESCOPE 0
#endif
#ifndef G_R1158LOWER /* h1158-h1208: factored radix recurrence for the
                      * magnitude.e2=-67 terminal near-tie surface.  Promoted
                      * after 51,229 discovery legs, 2,151 frozen disjoint
                      * boundary legs, and the cached no-regression walls. */
#define G_R1158LOWER 1
#endif
#ifndef G_R1186FADD
/* Analysis-only: the final same-sign Horner FADD treats the centered
 * half-plus-low3 remainder as a rounding-history class.  The operation-
 * dependent action suppresses the normal RN increment; the negative arm also
 * includes its exact-half state. */
#define G_R1186FADD 0
#endif
#ifndef G_R1200HISTFADD
/* Analysis-only: operation-level replacement for the site-local R1186 rule.
 * A same-sign RN64 FADD consuming a toward-zero-rounded operand preserves
 * that direction when its exact sum lies no more than four producer-grid
 * units above the midpoint.  This is the finite precision-difference form
 * suggested by US5612909; it is default-off pending corpus validation. */
#define G_R1200HISTFADD 0
#endif
#ifndef G_R1231CPAFADD /* h1230 candidate: qualify the final-Horner
                       * half-plus-low3 response with one fixed bit from
                       * the P5 multiplier's four-bit carry-select CPA.
                       * Analysis-only until full cached validation. */
#define G_R1231CPAFADD 0
#endif
#ifndef G_R1237CPAFADD /* h1236/h1379: selected bit of the P5-aligned
                       * four-bit CPA block, including its exact incoming
                       * carry (equivalently product bit 65).  R1378 replaces
                       * this selector on the negative arm; the independently
                       * validated positive arm remains enabled. */
#define G_R1237CPAFADD 1
#endif
#ifndef G_R1378X67Y64
/* h1357-h1379: the negative cosine Horner FADD consumes the squarer's
 * attached X67/Y64 representation over its complete q=0..7 history field:
 *     f4y = chop67(square * chop64(square)).
 * This fixed recurrence replaces R1237 on that arm.  It is ledger-free exact
 * on 398 direct legs, including a separately frozen 28-leg blind.  The exact
 * 56,393,031-leg stage-A and 204,788-leg heterogeneous scores were run with
 * the historical overlay enabled and are overlay-backed regression walls.
 * The 182,737,480-result ledger-off suite records eight fixes and no
 * regression relative to the matched current-source predecessor. */
#define G_R1378X67Y64 1
#endif
#ifndef G_R1259EQWIRE
/* Analysis-only: resolve an exactly equal truncated-thirds comparison with
 * one named carry wire from the right product's literal P5 multiplier tree.
 * This tests an omitted carry/history mechanism and is default-off. */
#define G_R1259EQWIRE 0
#endif
#ifndef G_R1263EQGATE
/* h1263/h1379: the equality history bit is a fixed carry/kill gate wholly
 * inside the right-product multiplier tree. */
#define G_R1263EQGATE 1
#endif
#ifndef G_R1266TERMGATE
/* Analysis-only: force the terminal carry-zero endpoint when both producer
 * histories assert a fixed P5-tree generate condition. */
#define G_R1266TERMGATE 0
#endif
#ifndef G_R1268TERMQUAL
/* Analysis-only refinement of R1266: require the adjacent lower square-CPA
 * group generate and the right product's radix-8 row-8 |digit|=3 signal. */
#define G_R1268TERMQUAL 0
#endif
#ifndef G_R1270MERGE3X
/* h1270/h1379: in the theta-zero/low3-three comparator state, retain the
 * low-block carry of the Booth hard 3x multiple before killing that block.
 * R1272 supplies the validated selector for this parent datapath. */
#define G_R1270MERGE3X 1
#endif
#ifndef G_R1272MERGEGATE
/* h1272/h1379: the right product's upper level-2 carry selects whether the
 * hard-3x low-block carry reaches the comparator. */
#define G_R1272MERGEGATE 1
#endif
#ifndef G_R1531TREEPAIR
/* Analysis-only global multiplier-tree topology audit.  Values 1..4 select
 * the four H1486 arithmetic-exact pairings in their fixed lexical order;
 * zero retains the documented P5 pairing. */
#define G_R1531TREEPAIR 0
#endif
#if G_R1531TREEPAIR < 0 || G_R1531TREEPAIR > 4
#error "G_R1531TREEPAIR must be in 0..4"
#endif
#ifndef G_R1382MERGES4
/* Falsified analysis-only refinement of the R1270/R1272 attachment: the
 * hard-3x low-block merge was restricted to the 67-bit fourth-product arm.
 * H1472's frozen one-shot s4=66 challenge split 8/8 between this endpoint
 * and the incumbent endpoint, so s4 alone is not the selector. */
#define G_R1382MERGES4 0
#endif
#ifndef G_R1475MERGEXOR
/* Falsified analysis-only successor generated from the H1472 split.  On the s4=66
 * arm, retain the hard-3x merge when an XOR of two named right-product P5
 * compressor wires is set; keep the validated s4=67 attachment unchanged.
 * Although selected to fit 18 earlier labels, it matched only 3/10 rows in
 * H1477's frozen one-shot disagreement bank.  It remains default OFF. */
#define G_R1475MERGEXOR 0
#endif
#if G_R1382MERGES4 && G_R1475MERGEXOR
#error "R1382 and R1475 are alternative hard-3x attachment experiments"
#endif
#ifndef G_R1387QXRUN
/* Falsified analysis-only R59 carry candidate.  In the existing corner
 * selector, toggle the predicted subtraction carry when the literal P5
 * square tree's final QX redundant pair has a long propagate suffix below
 * the 67-bit product cut.  Despite a perfect current-corpus fit, fresh
 * one-shot endpoint-visible challenges selected the incumbent on all 4/4
 * run>=13 pairs and all 27/27 run>=15 pairs. */
#define G_R1387QXRUN 0
#endif
#ifndef G_R1387QXMIN
/* Analysis-only width parameter for separating the observationally
 * equivalent 13/14/15-column hypotheses. */
#define G_R1387QXMIN 13
#endif
#ifndef G_R1394QRUN
/* Falsified analysis-only successor to R1387.  It tests the distinct
 * pre-low-digit Q square-tree redundant pair as the corner subtraction
 * carry-select source.  Although it repairs all three known corner misses,
 * all 75 fresh Q-specific endpoint-visible pairs selected the incumbent. */
#define G_R1394QRUN 0
#endif
#ifndef G_R1394QMIN
#define G_R1394QMIN 13
#endif
#ifndef G_R1281FADDQ7
/* Analysis-only R1237 completion: the FADD distance is the complete
 * three-bit producer-grid field q=0..7.  The earlier q=0..4 bound was an
 * observed subset, not a structural field boundary. */
#define G_R1281FADDQ7 0
#endif
#ifndef G_R1290FADDWORD
/* Falsified analysis-only successor to R1237.  It treats selected P5 CPA
 * columns 62..65 as one signed four-bit word and compares them with 2*q.
 * Although cached-exact, h1295's frozen one-shot bank selected this rule on
 * only three of seven separator legs and selected R1237 on four. */
#define G_R1290FADDWORD 0
#endif
#ifndef G_R1297FADDBOOTH1
/* Falsified analysis-only successor to R1290.  It preserves R1237 for
 * q=0..4 and gates q=5 or 6 on the second Horner product's row-zero Booth
 * digit having magnitude one.  h1298's separately frozen separator selected
 * the predecessor instead. */
#define G_R1297FADDBOOTH1 0
#endif
#ifndef G_R1299FADDLOWBIT
/* Falsified analysis-only successor to R1297.  It preserves R1237 for
 * q=0..4 and gates q=5 or 6 on bit 26 of the full second Horner product.
 * h1300's frozen bank selected the predecessor on all six separator legs. */
#define G_R1299FADDLOWBIT 0
#endif
#if (G_R1290FADDWORD + G_R1297FADDBOOTH1 + G_R1299FADDLOWBIT) > 1
#error "R1290, R1297, and R1299 are alternative FADD completions"
#endif
#ifndef G_PAYGATE
#define G_PAYGATE 1
#endif
/* Round 91 (PROMOTED 2026-08-27): scope the r59 q67th2 never-fire
 * quadrant to its validated stratum ce=-72; outside it the row
 * falls through to the default terminal.  Census: zero q67-branch
 * rows at ce!=-72 in comb7-18 (1.72M branch rows all at ce=-72;
 * comb7/11/12/14 have none); the arm's whole suite footprint is
 * randv1 402b/RU + 4016/RN (both fixed by the fall-through — the
 * sum-0x102 act1 carries the never-fire return cannot express) and
 * c037 (byte-identical either way).  h924 wall check: scoped-vs-ON
 * over the full suite input space (~190M row-modes) = EXACTLY the
 * two target rows; VM FSIN corpora and FPTAN byte-identical.
 * rv9 blind (pre-reg 44df5e8, seed 0x872A, 32M results, epoch
 * probes 36/36 both sides): ZERO difference rows in all 8 legs
 * (neutral pass per pre-registration), totals 11==11.  Ledger keys
 * randv1:2858512/ru and randv1:3133126/rn DELETED (36 -> 34 keys).
 * 0 restores the pre-R91 unconditional never-fire. */
#ifndef G_Q67SCOPE
#define G_Q67SCOPE 1
#endif
static const int g_q67scope = G_Q67SCOPE;
/* Round 92 (PROMOTED 2026-08-27): at ce=-74 a band-branch no-fire
 * defers to the default terminal (see the scope comment in
 * r59_apply).  h926 walls: ledger-ON scoped-vs-R91 over the FULL
 * suite input space = ZERO diffs (perfect collateral); ledger-OFF
 * randv1/hostv1 legs = EXACTLY one row, c019 -> hw.  rv10 blind
 * (seed 0x872B, 32M results, epoch probes 34/34 both sides): ZERO
 * difference rows in all 8 legs (neutral pass per pre-reg),
 * totals 13==13.  Ledger key randv1:1548918/rn DELETED (34 -> 33
 * keys).  0 restores the pre-R92 unconditional band no-fire. */
#ifndef G_B74SCOPE
#define G_B74SCOPE 1
#endif
static const int g_b74scope = G_B74SCOPE;
static const int g_round77_laneb_gate = G_ROUND77;
static const int g_round76_a1_edge = G_ROUND76;
#define DIWF "%d:%d:%016llx%016llx"
#define DIW(v) (int)(v).sign, (int)(v).e2, \
    (unsigned long long)((v).sig >> 64), (unsigned long long)(v).sig
#define DIU(x) (unsigned long long)((u128)(x) >> 64), \
    (unsigned long long)(u128)(x)
static void dump2(const sf_t *a, const sf_t *b)
{
    uint16_t s1, s2; uint64_t g1, g2;
    sf_to_x87(a, &s1, &g1); sf_to_x87(b, &s2, &g2);
    printf("F %04x %016llx %04x %016llx\n", s1, (unsigned long long)g1,
           s2, (unsigned long long)g2);
}

static sf_t normal_r(sf_t r, sf_t c, int i1, int i0, sf_rc_t rc)
{
    if (g_kvar) return kernel_naive(r, i1, i0, rc);
    sf_t rsq  = sf_fma(&r, &r, &ZERO);
    sf_t poly = i1 ? sf_fma(&rsq, &QQ_8, &QQ_7) : sf_fma(&rsq, &PP_8, &PP_7);
    sf_t rcube = sf_fma(&r, &rsq, &ZERO);
    sf_t r_hi = make_r_hi(&r);                       /* frcpa(frcpa(r)) or H1 variant */
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
    if (g_dump_final) {
        sf_t uh = U_hi, vv = V;
        if (i0) { uh.sign ^= 1; vv.sign ^= 1; }      /* final = (-U_hi)+(-V) */
        dump2(&uh, &vv);
    }
    return i0 ? sf_fms_s0(&tmp, &U_hi, &V, rc)
              : sf_fma_s0(&tmp, &U_hi, &V, rc);
}

/* =================== Pentium-lineage Skylake kernel ====================
 * Identified empirically (see notes/skylake-comparison.md rounds 6-8):
 *   - dispatch: |r| < 2^-3 -> Itanium small_r (bit-proven); [2^-3, 1/4) ->
 *     P5 6-term polynomials; [1/4, pi/4] -> table cell (bit-based: narrow
 *     cells 4/64 wide with b in {18,22,26,30}/64 for r < 1/2, wide cells
 *     8/64 with b in {36,44,52}/64 above), a = r - b,
 *     sin = fused(sinT*(1+t) + cosT*S), cos = fused(cosT*(1+t) - sinT*S)
 *     with ONE final rounding (69-bit-datapath behavior), where S,t are the
 *     4-term (narrow) / 6-term (wide) ROM polynomials evaluated with
 *     64-bit-rounded ops on full-width ROM coefficients.
 * Round 37 supersedes that empirical wide proxy with the reconstructed P6
 * four-term graph; the historical description remains the no-flag path.
 * Matches Skylake silicon at ~99.4% bit-exact in the table region and
 * ~99.3% in [2^-3,1/4); residual = hardware's internal op-rounding noise
 * (+-2^-70.5 average), all misses 1 ulp.
 *
 * The kernel takes the WIDE reduced argument (up to 65-bit significand,
 * value = (-1)^sign * dsig * 2^dexp2) so no separate c is needed.
 *
 * ROUND-16 PORT TARGET (see notes/skylake-comparison.md): all future
 * captures and model revisions must carry the validated four-term narrow
 * candidate m=RN69(P*a^2), u=chop68(1+m), S=RN64(a*u),
 * t=chop66(Q*a^2).  It improves the complete PII-equivalent capture and a
 * fresh targeted Skylake discriminator.  A 19-input h62 discriminator
 * separates m=RN69 from the previously-equivalent RN68/chop69 schedules.
 * Keep the explicit 66/68/69-bit carriers isolated from the six-term path.
 */
/* `rh` records the direction of the most recent internal materialization:
 * -1 below the exact operation result, 0 exact, +1 above.  It is numerical
 * metadata only; the significand/exponent datapath remains unchanged.  Intel
 * patent US5612909 describes this three-state rounding history as an operand
 * input to later micro-operations in complex instructions. */
typedef struct {
    uint8_t sign;
    int32_t e2;
    u128 sig;
    int8_t rh;
} wv_t;   /* wide value plus last-operation rounding history */
typedef struct { u128 hi, lo; } u256;

/* Analysis-only counterfactual used by the h1400 stage-localization pass.
 * `delta` is a signed numerical ulp of the materialized value, so increasing
 * a negative value decrements its stored magnitude.  Shipped execution is
 * byte-identical because no normal invocation selects targets 17 and above. */
static wv_t perturb_materialized_ulp(wv_t value, int target)
{
    if (g_perturb_tgt == target && g_perturb_delta) {
        __int128 stored_delta = value.sign
            ? -(__int128)g_perturb_delta
            : (__int128)g_perturb_delta;
        value.sig = (u128)((__int128)value.sig + stored_delta);
    }
    return value;
}
typedef enum {
    P5_ROUND_RN = 0,
    P5_ROUND_CHOP = 1,
    P5_ROUND_AWAY = 2,
    P5_ROUND_ODD = 3,
    P5_ROUND_UP = 4,
    P5_ROUND_DOWN = 5,
} p5_round_t;

/* exact host-integer support for the experimentally
 * selected 66/68/69-bit Round-16 candidate. */
static int u128_width(u128 v)
{
    int width = 0;
    while (v) { width++; v >>= 1; }
    return width;
}

/* Map a raw product remainder below its `shift`-bit cut onto the 66-bit
 * residue ring without overflowing u128 when shift is 63..67. */
static u128 residue_q66(u128 residue, int shift)
{
    if (shift <= 0)
        return 0;
    return shift <= 66 ? residue << (66 - shift)
                       : residue >> (shift - 66);
}

/* full unsigned 128x128 multiply.  Round-16 call
 * sites use at most 68-bit operands, but the full helper keeps the carrier
 * honest for the 65-bit reduced-argument path. */
static u256 u128_mul_full(u128 a, u128 b)
{
    uint64_t a0 = (uint64_t)a, a1 = (uint64_t)(a >> 64);
    uint64_t b0 = (uint64_t)b, b1 = (uint64_t)(b >> 64);
    u128 p00 = (u128)a0 * b0;
    u128 p01 = (u128)a0 * b1;
    u128 p10 = (u128)a1 * b0;
    u128 p11 = (u128)a1 * b1;
    u128 lo = p00, hi = p11, old;
    old = lo; lo += p01 << 64; hi += (p01 >> 64) + (lo < old);
    old = lo; lo += p10 << 64; hi += (p10 >> 64) + (lo < old);
    return (u256){ hi, lo };
}

/* multiply exact carriers and materialize the
 * result at bits precision, with RN-even or magnitude chop. */
static wv_t wv_mul_round_bits(u128 asig, int32_t ae2, int asign,
                              u128 bsig, int32_t be2, int bsign,
                              int bits, int nearest)
{
    wv_t out = { (uint8_t)(asign ^ bsign), ae2 + be2, 0 };
    if (asig == 0 || bsig == 0) return out;
    u256 product = u128_mul_full(asig, bsig);
    int width = product.hi ? 128 + u128_width(product.hi)
                           : u128_width(product.lo);
    int sh = width - bits;
    u128 top, rem = 0;
    if (sh <= 0) {
        top = product.lo;
    } else {
        /* Round-16 products are at most 133 bits, so sh is below 128. */
        top = (product.hi << (128 - sh)) | (product.lo >> sh);
        rem = product.lo & (((u128)1 << sh) - 1);
        if (nearest) {
            u128 half = (u128)1 << (sh - 1);
            if (rem > half || (rem == half && (top & 1))) {
                top++;
                if (u128_width(top) > bits) { top >>= 1; sh++; }
            }
        }
    }
    out.sig = top;
    out.e2 += sh > 0 ? sh : 0;
    return out;
}

/* materialize 1+m at the requested width without
 * requiring the exact sum to fit one u128.  Round-16's |m| is below one,
 * but near a table center its binary scale can be hundreds of bits below
 * the leading one. */
static wv_t wv_one_plus_round(wv_t m, int bits, int nearest)
{
    /* A negative nonzero m puts the exact value just below 1, in binade -1;
     * positive m is in binade 0.  Their precision grids differ by one bit. */
    int32_t qexp = m.sign ? -bits : 1 - bits;
    u128 one_units = (u128)1 << (m.sign ? bits : bits - 1);
    u128 whole = 0, remainder = 0, half = 0;
    int remainder_nonzero = 0, above_half = 0, tie = 0;
    int shift = qexp - m.e2;
    if (m.sig == 0)
        return (wv_t){ 0, 1 - bits, (u128)1 << (bits - 1) };
    if (shift <= 0) {
        whole = m.sig << -shift;
    } else {
        if (shift < 128) {
            whole = m.sig >> shift;
            remainder = m.sig & (((u128)1 << shift) - 1);
            remainder_nonzero = remainder != 0;
            half = (u128)1 << (shift - 1);
            above_half = remainder > half;
            tie = remainder == half;
        } else {
            remainder_nonzero = 1;
            if (shift == 128) {
                half = (u128)1 << 127;
                above_half = m.sig > half;
                tie = m.sig == half;
            }
        }
    }
    u128 units;
    if (!m.sign) {
        units = one_units + whole;
        if (nearest && (above_half || (tie && (units & 1)))) units++;
    } else {
        units = one_units - whole;
        if (nearest) {
            if (above_half || (tie && (units & 1))) units--;
        } else if (remainder_nonzero) {
            units--;               /* floor(1-|m|) for magnitude chop */
        }
    }
    if (units == one_units && m.sign)
        return (wv_t){ 0, 1 - bits, (u128)1 << (bits - 1) };
    return (wv_t){ 0, qexp, units };
}

static sf_t wv_rn64(wv_t v)
{
    sf_t r;
    if (v.sig == 0) return sf_zero(v.sign);
    int b = 127; while (!((v.sig >> b) & 1)) b--;
    int sh = b - 63;
    uint64_t top; int32_t e2 = v.e2;
    if (sh <= 0) { top = (uint64_t)(v.sig << (-sh)); e2 -= (-sh); }
    else {
        top = (uint64_t)(v.sig >> sh);
        u128 rem = v.sig & (((u128)1 << sh) - 1);
        u128 half = (u128)1 << (sh - 1);
        if (rem > half || (rem == half && (top & 1))) {
            top++;
            if (top == 0) { top = 0x8000000000000000ull; e2 += 1; }
        }
        e2 += sh;
    }
    r.cls = SF_FIN; r.sign = v.sign; r.sig = top; r.exp = e2 + 63;
    return r;
}

/* multiply a 64-bit-rounded accumulator (sf_t) by a full-width ROM constant,
 * rounding the result to 64 bits (models one datapath mul + writeback) */
static sf_t p5_mul_c(const sf_t *a, const p5c_t *c)
{
    if (a->sig == 0) return sf_zero(a->sign ^ c->sign);
    /* c->sig up to 68 bits; a->sig 64 bits: product <= 132 bits: split */
    uint64_t chi = (uint64_t)(c->sig >> 4);       /* top 64 of a 68-bit value */
    uint64_t clo = (uint64_t)c->sig & 0xF;        /* low 4 bits */
    u128 p_hi = (u128)a->sig * chi;               /* * 2^4 deficit */
    u128 p_lo = (u128)a->sig * clo;
    /* total = p_hi*2^4 + p_lo, at scale 2^(a.exp-63 + c.exp2) */
    /* round to 64 bits with sticky */
    int b;
    u128 hi = p_hi >> 124 ? p_hi : p_hi;          /* p_hi < 2^128 */
    (void)hi;
    /* value = p_hi*16 + p_lo exactly: represent as 132-bit via (p_hi, carry) */
    u128 low128 = (p_hi << 4) | p_lo;             /* may lose top 4 bits */
    uint64_t top4 = (uint64_t)(p_hi >> 124);
    int32_t e2 = (a->exp - 63) + c->exp2;
    if (top4) {
        b = 0; { uint64_t t = top4; while (t >>= 1) b++; }
        int width = 128 + b + 1;
        int sh = width - 64;
        u128 all_lo = low128;
        uint64_t topbits = (uint64_t)((((u128)top4 << (128 - sh)) | (all_lo >> sh)));
        u128 rem = all_lo & (((u128)1 << sh) - 1);
        u128 half = (u128)1 << (sh - 1);
        uint64_t topv = topbits;
        if (rem > half || (rem == half && (topv & 1))) {
            topv++;
            if (topv == 0) { topv = 0x8000000000000000ull; e2++; }
        }
        sf_t r; r.cls = SF_FIN; r.sign = a->sign ^ c->sign;
        r.sig = topv; r.exp = e2 + sh + 63;
        return r;
    } else {
        wv_t w; w.sign = a->sign ^ c->sign; w.e2 = e2; w.sig = low128;
        return wv_rn64(w);
    }
}

/* add a full-width ROM constant to a 64-bit value, rounding to 64 bits */
static sf_t p5_add_c(const sf_t *a, const p5c_t *c)
{
    /* align at scale min(c->exp2, a_scale); magnitudes bounded (|values|<2) */
    int32_t ea = a->exp - 63;
    int32_t E = c->exp2 < ea ? c->exp2 : ea;
    /* shifts bounded by ~70 bits in kernel use; guard anyway */
    int sha = ea - E, shc = 0 * (int)(c->exp2 - E);
    shc = c->exp2 - E;
    if (sha > 120 || shc > 120) {                  /* far apart: bigger wins */
        return (sha > shc) ? *a : (sf_t){ SF_FIN, c->sign, 0, 0 }; /* unused path */
    }
    __int128 va = a->sig == 0 ? 0 : (__int128)((u128)a->sig << sha);
    if (a->sign) va = -va;
    __int128 vc = (__int128)(c->sig << shc);
    if (c->sign) vc = -vc;
    __int128 v = va + vc;
    wv_t w;
    if (v == 0) return sf_zero(0);
    w.sign = v < 0; w.sig = v < 0 ? (u128)(-v) : (u128)v; w.e2 = E;
    return wv_rn64(w);
}

/* fused combine: one rounding of  T1*(1+t) +/- T2*S  (all inputs exact).
 * T1,T2 are ROM-width entries; t,S are 64-bit values.  Accumulate exactly
 * in 256-bit fixed point. */
static void acc_add(u256 *acc, int neg, u128 mag_hi, u128 mag_lo)
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
static void acc_add_product(u256 *acc, int neg, u128 a, u128 b,
                            int32_t e2, int scale)
{
    if (a == 0 || b == 0) return;
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
            lo = (product.lo >> rsh)
                | (product.hi << (128 - rsh));
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

/* RN64 conversion of a signed two's-complement
 * fixed-point accumulator. */
static sf_t acc_rn64(u256 acc, int32_t scale)
{
    int neg = (int)(acc.hi >> 127);
    if (neg) {
        acc.lo = ~acc.lo + 1;
        acc.hi = ~acc.hi + (acc.lo == 0);
    }
    if (acc.hi == 0 && acc.lo == 0) return sf_zero(neg);
    int msb;
    if (acc.hi) {
        msb = 127;
        while (!((acc.hi >> msb) & 1)) msb--;
        msb += 128;
    } else {
        msb = 127;
        while (!((acc.lo >> msb) & 1)) msb--;
    }
    int sh = msb - 63;
    uint64_t top;
    int guard;
    u128 below;
    if (sh >= 128) {
        int hsh = sh - 128;
        top = (uint64_t)(acc.hi >> hsh);
        if (hsh == 0) {
            guard = (int)(acc.lo >> 127);
            below = acc.lo & (((u128)1 << 127) - 1);
        } else {
            guard = (int)((acc.hi >> (hsh - 1)) & 1);
            below = (hsh > 1
                ? acc.hi & (((u128)1 << (hsh - 1)) - 1)
                : 0) | (acc.lo != 0);
        }
    } else {
        top = (uint64_t)((acc.hi << (128 - sh)) | (acc.lo >> sh));
        guard = (int)((acc.lo >> (sh - 1)) & 1);
        below = sh > 1
            ? acc.lo & (((u128)1 << (sh - 1)) - 1)
            : 0;
    }
    if (guard && (below || (top & 1))) {
        top++;
        if (top == 0) { top = 0x8000000000000000ull; sh++; }
    }
    return (sf_t){ SF_FIN, (uint8_t)neg, scale + sh + 63, top };
}

/* round a signed fixed-point accumulator to an
 * RN significand held in wv_t.  Round 24 uses 67 bits. */
static wv_t acc_rn_bits(u256 acc, int32_t scale, int bits)
{
    int neg = (int)(acc.hi >> 127);
    if (neg) {
        acc.lo = ~acc.lo + 1;
        acc.hi = ~acc.hi + (acc.lo == 0);
    }
    if (acc.hi == 0 && acc.lo == 0)
        return (wv_t){ (uint8_t)neg, 0, 0 };
    int msb;
    if (acc.hi) {
        msb = 127;
        while (!((acc.hi >> msb) & 1)) msb--;
        msb += 128;
    } else {
        msb = 127;
        while (!((acc.lo >> msb) & 1)) msb--;
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
        below = sh > 1
            ? acc.lo & (((u128)1 << (sh - 1)) - 1)
            : 0;
    } else {
        int hsh = sh - 128;
        top = acc.hi >> hsh;
        if (hsh == 0) {
            guard = (int)(acc.lo >> 127);
            below = acc.lo & (((u128)1 << 127) - 1);
        } else {
            guard = (int)((acc.hi >> (hsh - 1)) & 1);
            below = (
                hsh > 1
                ? acc.hi & (((u128)1 << (hsh - 1)) - 1)
                : 0
            ) | (acc.lo != 0);
        }
    }
    int discarded = guard || below;
    int increment = guard && (below || (top & 1));
    if (increment) {
        top++;
        if (top == ((u128)1 << bits)) {
            top >>= 1;
            sh++;
        }
    }
    int rh = discarded ? (increment ? 1 : -1) : 0;
    if (neg) rh = -rh;
    return (wv_t){ (uint8_t)neg, scale + sh, top, (int8_t)rh };
}

/*
 * generalized internal-width materialization for
 * the standalone-FSIN hypothesis.  It operates on the same exact signed
 * accumulator as acc_rn_bits and makes non-RN representatives explicit;
 * P5_ROUND_AWAY means magnitude away from zero, P5_ROUND_ODD retains
 * discarded information in the low stored bit, and UP/DOWN are signed
 * directed modes.
 */
static wv_t acc_round_bits_mode(
    u256 acc, int32_t scale, int bits, p5_round_t mode)
{
    int neg = (int)(acc.hi >> 127);
    if (neg) {
        acc.lo = ~acc.lo + 1;
        acc.hi = ~acc.hi + (acc.lo == 0);
    }
    if (acc.hi == 0 && acc.lo == 0)
        return (wv_t){ (uint8_t)neg, 0, 0 };
    int msb;
    if (acc.hi) {
        msb = 127;
        while (!((acc.hi >> msb) & 1)) msb--;
        msb += 128;
    } else {
        msb = 127;
        while (!((acc.lo >> msb) & 1)) msb--;
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
        below = sh > 1
            ? acc.lo & (((u128)1 << (sh - 1)) - 1)
            : 0;
    } else {
        int hsh = sh - 128;
        top = acc.hi >> hsh;
        if (hsh == 0) {
            guard = (int)(acc.lo >> 127);
            below = acc.lo & (((u128)1 << 127) - 1);
        } else {
            guard = (int)((acc.hi >> (hsh - 1)) & 1);
            below = (
                hsh > 1
                ? acc.hi & (((u128)1 << (hsh - 1)) - 1)
                : 0
            ) | (acc.lo != 0);
        }
    }
    int discarded = guard || below;
    int increment = 0;
    if (mode == P5_ROUND_ODD) {
        increment = discarded && !(top & 1);
        if (discarded) top |= 1;
    } else {
        increment =
            mode == P5_ROUND_AWAY
            ? discarded
            : mode == P5_ROUND_UP
            ? (!neg && discarded)
            : mode == P5_ROUND_DOWN
            ? (neg && discarded)
            : (
                mode == P5_ROUND_RN
                && guard
                && (below || (top & 1))
            );
        if (increment) {
            top++;
            if (top == ((u128)1 << bits)) {
                top >>= 1;
                sh++;
            }
        }
    }
    int rh = discarded ? (increment ? 1 : -1) : 0;
    if (neg) rh = -rh;
    return (wv_t){ (uint8_t)neg, scale + sh, top, (int8_t)rh };
}

/* exact wide multiply followed by an explicitly
 * selected standalone-FSIN internal materialization. */
static wv_t p5_wv_mul_round(
    wv_t a, wv_t b, int bits, p5_round_t mode)
{
    int32_t scale = a.e2 + b.e2;
    u256 acc = { 0, 0 };
    acc_add_product(
        &acc, a.sign ^ b.sign, a.sig, b.sig, scale, scale);
    return acc_round_bits_mode(acc, scale, bits, mode);
}

/* materialize a native P5 ROM constant at an
 * internal width. */
static wv_t p5_constant_round(
    const p5c_t *constant, int bits, p5_round_t mode)
{
    u256 acc = { 0, 0 };
    acc_add_product(
        &acc,
        constant->sign,
        constant->sig,
        1,
        constant->exp2,
        constant->exp2);
    return acc_round_bits_mode(acc, constant->exp2, bits, mode);
}

/* exact add of a materialized carrier and P5 ROM
 * constant, followed by the standalone-FSIN internal-width rule. */
static wv_t p5_wv_add_constant_round(
    wv_t value, const p5c_t *constant,
    int constant_bits, p5_round_t constant_mode,
    int bits, p5_round_t mode)
{
    wv_t stored = p5_constant_round(
        constant, constant_bits, constant_mode);
    int32_t scale = value.e2 < stored.e2 ? value.e2 : stored.e2;
    u256 acc = { 0, 0 };
    acc_add_product(
        &acc, value.sign, value.sig, 1, value.e2, scale);
    acc_add_product(
        &acc, stored.sign, stored.sig, 1, stored.e2, scale);
    return acc_round_bits_mode(acc, scale, bits, mode);
}

/* exact addition of two explicit internal
 * carriers followed by a selected materialization.  Round 36 uses this to
 * replay the validated three-FADD reconstruction without host floating
 * point. */
static wv_t p5_wv_add_round(
    wv_t left, wv_t right, int bits, p5_round_t mode)
{
    int32_t scale = left.e2 < right.e2 ? left.e2 : right.e2;
    u256 acc = { 0, 0 };
    if (left.sig) {
        acc_add_product(
            &acc, left.sign, left.sig, 1, left.e2, scale);
    }
    if (right.sig) {
        acc_add_product(
            &acc, right.sign, right.sig, 1, right.e2, scale);
    }
#if G_R1200HISTFADD
    wv_t rounded = acc_round_bits_mode(acc, scale, bits, mode);
    if (
        bits == 64
        && mode == P5_ROUND_RN
        && left.sign == right.sign
        && left.sig
        && right.sig
    ) {
        int toward_zero = left.sign ? 1 : -1;
        int left_history = left.rh;
        int right_history = right.rh;
        int has_toward_zero_history = (
            left_history == toward_zero || right_history == toward_zero
        );
        int has_opposing_history = (
            left_history == -toward_zero || right_history == -toward_zero
        );
        int dl = left.e2 - scale;
        int dr = right.e2 - scale;
        if (
            has_toward_zero_history
            && !has_opposing_history
            && dl >= 0 && dl < 128
            && dr >= 0 && dr < 128
        ) {
            u128 magnitude = (left.sig << dl) + (right.sig << dr);
            int shift = u128_width(magnitude) - bits;
            if (shift > 0 && shift < 128) {
                u128 denominator = (u128)1 << shift;
                u128 remainder = magnitude & (denominator - 1);
                u128 half = denominator >> 1;
                if (remainder >= half && remainder - half <= 4) {
                    u128 lower = magnitude >> shift;
                    if (
                        rounded.sign == left.sign
                        && rounded.e2 == scale + shift
                        && rounded.sig > lower
                    ) {
                        rounded.sig = lower;
                        rounded.rh = (int8_t)toward_zero;
                    }
                }
            }
        }
    }
    return rounded;
#else
    return acc_round_bits_mode(acc, scale, bits, mode);
#endif
}

/* Fixed operation-state test for the R1186 rounding-history candidate.  The
 * low-three-bit precision difference is first centered to its nearest grid
 * point, so the positive half-quantum is 1..4 rather than the fitted 1..7
 * range of an unsigned suffix. */
static int p5_same_sign_half_history_class(
    wv_t left, wv_t right, int bits, int include_exact)
{
    if (left.sign != right.sign || !left.sig || !right.sig)
        return 0;
    int32_t scale = left.e2 < right.e2 ? left.e2 : right.e2;
    int dl = left.e2 - scale;
    int dr = right.e2 - scale;
    if (dl < 0 || dr < 0 || dl >= 128 || dr >= 128)
        return 0;
    u128 magnitude = (left.sig << dl) + (right.sig << dr);
    int shift = u128_width(magnitude) - bits;
    if (shift <= 0 || shift >= 128)
        return 0;
    u128 denominator = (u128)1 << shift;
    u128 remainder = magnitude & (denominator - 1);
    u128 half = denominator >> 1;
    return (include_exact && remainder == half)
        || (remainder > half && remainder - half <= 4);
}

#if G_R1231CPAFADD || G_R1237CPAFADD || G_R1290FADDWORD \
    || G_R1297FADDBOOTH1 || G_R1299FADDLOWBIT \
    || G_R1259EQWIRE || G_R1263EQGATE \
    || G_R1266TERMGATE || G_R1272MERGEGATE || G_R1387QXRUN \
    || G_R1394QRUN || G_R1475MERGEXOR
/* Low-column transcription of the 67x64 radix-8/four-level 4:2 tree in
 * Intel US 5,195,051.  Only columns 62..65 are required for the candidate
 * carry-select output, so unsigned-128 modular arithmetic is sufficient:
 * discarded high columns cannot carry downward into this window. */
typedef struct {
    u128 sum;
    u128 carry;
} p5_r1231_pair_t;

static p5_r1231_pair_t p5_r1231_csa3(u128 a, u128 b, u128 c)
{
    p5_r1231_pair_t out;
    out.sum = a ^ b ^ c;
    out.carry = ((a & b) | (a & c) | (b & c)) << 1;
    return out;
}

static p5_r1231_pair_t p5_r1231_compress4(
    u128 d, u128 a, u128 b, u128 c)
{
    p5_r1231_pair_t first = p5_r1231_csa3(a, b, c);
    return p5_r1231_csa3(d, first.sum, first.carry);
}

static int p5_r1231_booth_digit(uint64_t multiplier, int row)
{
    static const int8_t booth8[16] = {
         0,  1,  1,  2,  2,  3,  3,  4,
        -4, -3, -3, -2, -2, -1, -1,  0
    };
    int code = 0;
    for (int out_bit = 0; out_bit < 4; out_bit++) {
        int source_bit = 3 * row - 1 + out_bit;
        if (source_bit >= 0 && source_bit < 64)
            code |= (int)((multiplier >> source_bit) & 1) << out_bit;
    }
    return booth8[code];
}

typedef struct {
    p5_r1231_pair_t final;
    p5_r1231_pair_t level2_high;
    p5_r1231_pair_t level1_4;
    p5_r1231_pair_t level2_1;
} p5_r1231_tree_t;

static p5_r1231_tree_t p5_r1231_product_tree(
    u128 multiplicand, u128 multiplier)
{
    const u128 pp_mask = (((u128)1 << 70) - 1);
    u128 inputs[24] = { 0 };
    int prior_negative = 0;
    for (int row = 0; row < 22; row++) {
        int digit = p5_r1231_booth_digit((uint64_t)multiplier, row);
        u128 magnitude = multiplicand
            * (u128)(digit < 0 ? -digit : digit);
        u128 encoded = ((u128)1 << 69) | magnitude;
        if (digit < 0)
            encoded = (~encoded) & pp_mask;
        u128 physical = (encoded | ((u128)3 << 70)) << (3 * row);
        if (prior_negative)
            physical |= (u128)1 << (3 * (row - 1));
        inputs[row] = physical;
        prior_negative = digit < 0;
    }
    inputs[22] = (u128)1 << 69;

    p5_r1231_pair_t level1[6];
    for (int index = 0; index < 6; index++) {
        u128 *wire = &inputs[4 * index];
        level1[index] = p5_r1231_compress4(
            wire[0], wire[1], wire[2], wire[3]);
    }
    p5_r1231_pair_t level2[3];
#if G_R1531TREEPAIR == 1
    static const int level2_left[3] = { 0, 1, 3 };
    static const int level2_right[3] = { 2, 4, 5 };
#elif G_R1531TREEPAIR == 2
    static const int level2_left[3] = { 0, 1, 3 };
    static const int level2_right[3] = { 2, 5, 4 };
#elif G_R1531TREEPAIR == 3
    static const int level2_left[3] = { 0, 1, 2 };
    static const int level2_right[3] = { 3, 4, 5 };
#elif G_R1531TREEPAIR == 4
    static const int level2_left[3] = { 0, 1, 2 };
    static const int level2_right[3] = { 3, 5, 4 };
#else
    static const int level2_left[3] = { 0, 2, 4 };
    static const int level2_right[3] = { 1, 3, 5 };
#endif
    for (int index = 0; index < 3; index++) {
        p5_r1231_pair_t left = level1[level2_left[index]];
        p5_r1231_pair_t right = level1[level2_right[index]];
        level2[index] = p5_r1231_compress4(
            left.sum, left.carry, right.sum, right.carry);
    }
    p5_r1231_pair_t level3 = p5_r1231_compress4(
        level2[0].sum, level2[0].carry,
        level2[1].sum, level2[1].carry);
    p5_r1231_pair_t final = p5_r1231_compress4(
        level3.sum, level3.carry,
        level2[2].sum, level2[2].carry);

    p5_r1231_tree_t result = {
        final, level2[2], level1[4], level2[1]
    };
    return result;
}

#if G_R1475MERGEXOR
static int p5_r1475_right_tree_xor(
    u128 multiplicand, u128 multiplier, int product_cut)
{
    p5_r1231_tree_t tree = p5_r1231_product_tree(
        multiplicand, multiplier);
    int high_group_sum = (int)(
        (tree.level1_4.sum >> product_cut) & 1);
    int preceding_group_carry = (int)(
        (tree.level2_1.carry >> (product_cut - 3)) & 1);
    return high_group_sum ^ preceding_group_carry;
}
#endif

static int p5_r1387_square_qx_run(u128 square_input, int minimum)
{
    p5_r1231_tree_t tree = p5_r1231_product_tree(
        square_input, square_input >> 3);
    p5_r1231_pair_t qx = p5_r1231_csa3(
        tree.final.sum << 3,
        tree.final.carry << 3,
        square_input * (square_input & 7));
    const u128 sqrt_two_cut = ((u128)5 << 64)
        | (u128)UINT64_C(0xa827999fcef32423);
    int product_cut = square_input >= sqrt_two_cut ? 67 : 66;
    u128 mask = (((u128)1 << minimum) - 1)
        << (product_cut - minimum);
    return ((qx.sum ^ qx.carry) & mask) == mask;
}

static int p5_r1394_square_q_run(u128 square_input, int minimum)
{
    p5_r1231_tree_t tree = p5_r1231_product_tree(
        square_input, square_input >> 3);
    u256 exact = u128_mul_full(square_input, square_input >> 3);
    int product_width = exact.hi
        ? 128 + u128_width(exact.hi)
        : u128_width(exact.lo);
    int product_cut = product_width - 67;
    u128 mask = (((u128)1 << minimum) - 1)
        << (product_cut - minimum);
    return ((tree.final.sum ^ tree.final.carry) & mask) == mask;
}

static int p5_r1231_product_cpa_bit(
    u128 multiplicand, u128 multiplier, int selected)
{
    p5_r1231_tree_t tree = p5_r1231_product_tree(
        multiplicand, multiplier);
    p5_r1231_pair_t final = tree.final;

    /* P5 origin 2 and a four-bit block put both legal product cuts, 63 and
     * 64, in the block beginning at column 62.  R1231 reads sum0.b3.
     * R1237 supplies the exact prefix carry, so the muxed b3 is also the
     * ordinary full-product bit at column 65. */
    int carry = 0;
    int result = 0;
    int selected_word = 0;
    int first = selected ? 0 : 62;
    for (int position = first; position <= 65; position++) {
        int a = (int)((final.sum >> position) & 1);
        int b = (int)((final.carry >> position) & 1);
        result = a ^ b ^ carry;
        carry = (a & b) | ((a ^ b) & carry);
        if (G_R1290FADDWORD && selected && position >= 62)
            selected_word |= result << (position - 62);
    }
    if (G_R1290FADDWORD && selected)
        return selected_word;
    if (G_R1297FADDBOOTH1 && selected) {
        int digit0 = p5_r1231_booth_digit((uint64_t)multiplier, 0);
        int abs1 = digit0 == 1 || digit0 == -1;
        return result | (abs1 << 1);
    }
    if (G_R1299FADDLOWBIT && selected) {
        int low_bit26 = (int)(((multiplicand * multiplier) >> 26) & 1);
        return result | (low_bit26 << 1);
    }
    return result;
}

static int p5_r1259_level2_high_carry(
    u128 multiplicand, u128 multiplier, int position)
{
    p5_r1231_tree_t tree = p5_r1231_product_tree(
        multiplicand, multiplier);
    return (int)((tree.level2_high.carry >> position) & 1);
}

static int p5_r1263_equality_carry_kill(
    u128 multiplicand, u128 multiplier, int product_cut)
{
    p5_r1231_tree_t tree = p5_r1231_product_tree(
        multiplicand, multiplier);
    int carry = (int)(
        (tree.level2_high.carry >> (product_cut + 4)) & 1);
    int kill = !((tree.final.sum | tree.final.carry)
        & ((u128)1 << (product_cut + 15)));
    return carry & kill;
}

static u128 p5_r1266_shift_window(u128 value, int shift)
{
    if (shift >= 128 || shift <= -128)
        return 0;
    return shift >= 0 ? value << shift : value >> -shift;
}

/* Rebase the same physical tree so columns 80..207 occupy an ordinary
 * u128.  Four compressor levels can move information upward by at most four
 * columns, so the requested 98..129 groups are independent of discarded
 * columns below the window; discarded high columns cannot carry downward. */
static p5_r1231_pair_t p5_r1266_product_tree_window(
    u128 multiplicand, u128 multiplier, int origin)
{
    const u128 pp_mask = (((u128)1 << 70) - 1);
    u128 inputs[24] = { 0 };
    int prior_negative = 0;
    for (int row = 0; row < 22; row++) {
        int digit = p5_r1231_booth_digit((uint64_t)multiplier, row);
        u128 magnitude = multiplicand
            * (u128)(digit < 0 ? -digit : digit);
        u128 encoded = ((u128)1 << 69) | magnitude;
        if (digit < 0)
            encoded = (~encoded) & pp_mask;
        u128 physical = p5_r1266_shift_window(
            encoded | ((u128)3 << 70), 3 * row - origin);
        if (prior_negative)
            physical |= p5_r1266_shift_window(
                1, 3 * (row - 1) - origin);
        inputs[row] = physical;
        prior_negative = digit < 0;
    }
    inputs[22] = p5_r1266_shift_window(1, 69 - origin);

    p5_r1231_pair_t level1[6];
    for (int index = 0; index < 6; index++) {
        u128 *wire = &inputs[4 * index];
        level1[index] = p5_r1231_compress4(
            wire[0], wire[1], wire[2], wire[3]);
    }
    p5_r1231_pair_t level2[3];
    for (int index = 0; index < 3; index++) {
        p5_r1231_pair_t left = level1[2 * index];
        p5_r1231_pair_t right = level1[2 * index + 1];
        level2[index] = p5_r1231_compress4(
            left.sum, left.carry, right.sum, right.carry);
    }
    p5_r1231_pair_t level3 = p5_r1231_compress4(
        level2[0].sum, level2[0].carry,
        level2[1].sum, level2[1].carry);
    return p5_r1231_compress4(
        level3.sum, level3.carry,
        level2[2].sum, level2[2].carry);
}

static int p5_r1266_terminal_generate_gate(
    u128 square_input, u128 fourth, u128 right_factor, int right_shift)
{
    p5_r1231_pair_t square = p5_r1266_product_tree_window(
        square_input, square_input >> 3, 80);
    int lower_group_generate = 0;
    for (int position = 18; position < 34; position++) {
        int a = (int)((square.sum >> position) & 1);
        int b = (int)((square.carry >> position) & 1);
        lower_group_generate = (a & b)
            | ((a ^ b) & lower_group_generate);
    }
    int upper_group_generate = 0;
    for (int position = 34; position < 50; position++) {
        int a = (int)((square.sum >> position) & 1);
        int b = (int)((square.carry >> position) & 1);
        upper_group_generate = (a & b)
            | ((a ^ b) & upper_group_generate);
    }
    p5_r1231_tree_t right = p5_r1231_product_tree(
        fourth, right_factor);
    int position = right_shift - 2;
    int right_generate = (int)(
        ((right.final.sum & right.final.carry) >> position) & 1);
    int result = upper_group_generate & right_generate;
#if G_R1268TERMQUAL
    int right_abs3_row8 = p5_r1231_booth_digit(
        (uint64_t)right_factor, 8);
    result &= lower_group_generate
        & (right_abs3_row8 == 3 || right_abs3_row8 == -3);
#endif
    return result;
}

static int p5_r1231_fadd_class(
    wv_t left, wv_t right, int cpa_bit)
{
    if (left.sign != right.sign || !left.sig || !right.sig)
        return 0;
    int32_t scale = left.e2 < right.e2 ? left.e2 : right.e2;
    int dl = left.e2 - scale;
    int dr = right.e2 - scale;
    if (dl < 0 || dr < 0 || dl >= 128 || dr >= 128)
        return 0;
    u128 magnitude = (left.sig << dl) + (right.sig << dr);
    int shift = u128_width(magnitude) - 64;
    if (shift <= 0 || shift >= 128)
        return 0;
    u128 denominator = (u128)1 << shift;
    u128 remainder = magnitude & (denominator - 1);
    u128 half = denominator >> 1;
    if (remainder < half
            || remainder - half > (
                G_R1290FADDWORD || G_R1297FADDBOOTH1
                    || G_R1299FADDLOWBIT ? 6
                : G_R1281FADDQ7 ? 7 : 4))
        return 0;
    u128 lower = magnitude >> shift;
    int increments = remainder > half
        || (remainder == half && (lower & 1));
    u128 q = remainder - half;
    if (G_R1290FADDWORD) {
        int word = cpa_bit & 15;
        int doubled_q = (int)(q << 1);
        return increments
            && ((word ^ doubled_q) & 8) == 0
            && word >= doubled_q;
    }
    if (G_R1297FADDBOOTH1) {
        int product_bit65 = cpa_bit & 1;
        int digit0_abs1 = (cpa_bit >> 1) & 1;
        return increments
            && (int)((q >> 2) & 1) == product_bit65
            && (q <= 4 || digit0_abs1);
    }
    if (G_R1299FADDLOWBIT) {
        int product_bit65 = cpa_bit & 1;
        int product_bit26 = (cpa_bit >> 1) & 1;
        return increments
            && (int)((q >> 2) & 1) == product_bit65
            && (q <= 4 || product_bit26);
    }
    return increments && (int)((q >> 2) & 1) == cpa_bit;
}

#endif

/* A chopped 67-bit producer feeding RN64 exposes three exact low product
 * columns above the half bit.  This is the complete q=0..7 consumer window;
 * values outside it cannot be a state of that three-bit history field. */
#if G_R1378X67Y64
static int p5_fadd_three_bit_half_window(wv_t left, wv_t right)
{
    if (left.sign != right.sign || !left.sig || !right.sig)
        return 0;
    int32_t scale = left.e2 < right.e2 ? left.e2 : right.e2;
    int dl = left.e2 - scale;
    int dr = right.e2 - scale;
    if (dl < 0 || dr < 0 || dl >= 128 || dr >= 128)
        return 0;
    u128 magnitude = (left.sig << dl) + (right.sig << dr);
    int shift = u128_width(magnitude) - 64;
    if (shift <= 0 || shift >= 128)
        return 0;
    u128 denominator = (u128)1 << shift;
    u128 remainder = magnitude & (denominator - 1);
    u128 half = denominator >> 1;
    return remainder >= half && remainder - half <= 7;
}
#endif

/* architectural RC rounding of a signed
 * fixed-point accumulator, shared by the baseline and Round-24 combines. */
static sf_t acc_round64_rc(u256 acc, int32_t scale, int neg_out, sf_rc_t rc)
{
    int neg = (acc.hi >> 127) & 1;
    if (neg) {
        acc.lo = ~acc.lo + 1;
        acc.hi = ~acc.hi + (acc.lo == 0 ? 1 : 0);
    }
    neg ^= neg_out;
    if (acc.hi == 0 && acc.lo == 0) return sf_zero(neg);
    int b;
    if (acc.hi) {
        b = 127;
        while (!((acc.hi >> b) & 1)) b--;
        b += 128;
    } else {
        b = 127;
        while (!((acc.lo >> b) & 1)) b--;
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
            below = (
                sh - 128 - 1 > 0
                ? acc.hi & (((u128)1 << (sh - 128 - 1)) - 1)
                : 0
            ) | (acc.lo ? 1 : 0);
        } else {
            guard = (int)(acc.lo >> 127) & 1;
            below = acc.lo & (((u128)1 << 127) - 1);
        }
        int inc = 0;
        if (rc == SF_RN) inc = guard && (below || (top & 1));
        else if (rc == SF_RU) inc = !neg && (guard || below);
        else if (rc == SF_RD) inc = neg && (guard || below);
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
        u128 below = sh > 1
            ? acc.lo & (((u128)1 << (sh - 1)) - 1)
            : 0;
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

/* expose a constant as an exact wide carrier. */
static wv_t f2xm1_constant(const p5c_t *constant)
{
    return (wv_t){ constant->sign, constant->exp2, constant->sig };
}

/* h254/h258 ordinary-multiply class. */
static wv_t f2xm1_mul_chop67(wv_t left, wv_t right)
{
    return p5_wv_mul_round(left, right, 67, P5_ROUND_CHOP);
}

/* h254/h258 multiply-class materialization. */
static wv_t f2xm1_mul_rn64(wv_t left, wv_t right)
{
    return p5_wv_mul_round(left, right, 64, P5_ROUND_RN);
}

/* h254/h258 ordinary-add class. */
static wv_t f2xm1_add_rn64(wv_t left, wv_t right)
{
    return p5_wv_add_round(left, right, 64, P5_ROUND_RN);
}

/* exact constant input followed by ordinary FADD. */
static wv_t f2xm1_add_constant_rn64(wv_t value, const p5c_t *constant)
{
    return f2xm1_add_rn64(value, f2xm1_constant(constant));
}

/* final add with architectural rounding control. */
static sf_t f2xm1_final_add(wv_t left, wv_t right, sf_rc_t rc)
{
    int32_t scale = left.e2 < right.e2 ? left.e2 : right.e2;
    u256 accumulator = { 0, 0 };
    acc_add_product(
        &accumulator, left.sign, left.sig, 1, left.e2, scale);
    acc_add_product(
        &accumulator, right.sign, right.sig, 1, right.e2, scale);
    return acc_round64_rc(accumulator, scale, 0, rc);
}

/* final multiply with architectural rounding. */
static sf_t f2xm1_final_multiply(
    wv_t value, const p5c_t *constant, sf_rc_t rc)
{
    int32_t scale = value.e2 + constant->exp2;
    u256 accumulator = { 0, 0 };
    acc_add_product(
        &accumulator,
        value.sign ^ constant->sign,
        value.sig,
        constant->sig,
        scale,
        scale);
    return acc_round64_rc(accumulator, scale, 0, rc);
}

/* Round the exact tiny-path product once at the raw80 spacing.
 * In the lowest input binade and below, that spacing is 2^-16445.
 * Applying significand rounding before a truncating store loses this
 * rounding decision for native subnormal results. Direct rounding at
 * the destination spacing also makes the subsequent store exact. */
static sf_t f2xm1_tiny_raw80(sf_t x, sf_rc_t rc)
{
    int32_t scale = x.exp - 63 + F2_LN2.exp2;
    int shift = -16445 - scale;
    u256 magnitude = { 0, 0 };
    acc_add_product(&magnitude, 0, x.sig, F2_LN2.sig, scale, scale);
    uint64_t kept;
    int guard, sticky;
    if (shift >= 128) {
        kept = (uint64_t)(magnitude.hi >> (shift - 128));
        if (shift == 128) {
            guard = (int)((magnitude.lo >> 127) & 1);
            sticky = !!(magnitude.lo & (((u128)1 << 127) - 1));
        } else {
            guard = (int)((magnitude.hi >> (shift - 129)) & 1);
            sticky = !!magnitude.lo
                || !!(magnitude.hi & (((u128)1 << (shift - 129)) - 1));
        }
    } else {
        kept = (uint64_t)((magnitude.hi << (128 - shift))
                         | (magnitude.lo >> shift));
        guard = (int)((magnitude.lo >> (shift - 1)) & 1);
        sticky = !!(magnitude.lo & (((u128)1 << (shift - 1)) - 1));
    }
    int increment = rc == SF_RN ? guard && (sticky || (kept & 1))
        : ((rc == SF_RU && !x.sign) || (rc == SF_RD && x.sign))
          && (guard || sticky);
    kept += increment;
    return sf_from_parts(x.sign, kept >= (1ull << 63) ? 1 : 0, kept);
}

/* reconstructed six-coefficient table polynomial. */
static sf_t f2xm1_table_path(sf_t x, sf_rc_t rc)
{
    wv_t input = { x.sign, x.exp - 63, x.sig };
    unsigned lane = (unsigned)((x.sig - (1ull << 63)) >> 59);
    unsigned index = (x.sign ? 32u : 0u) + (x.exp == -2 ? 16u : 0u) + lane;
    unsigned numerator = x.exp == -2 ? 33u + 2u * lane : 66u + 4u * lane;
    wv_t negative_anchor = { (uint8_t)(x.sign ^ 1), -7, numerator };
    wv_t residual = f2xm1_add_rn64(input, negative_anchor);
    wv_t z = f2xm1_mul_rn64(f2xm1_constant(&F2_LN2), residual);
    wv_t z2 = f2xm1_mul_chop67(z, z);

    wv_t even = f2xm1_add_constant_rn64(
        f2xm1_mul_chop67(z2, f2xm1_constant(&F2_SHORT[4])),
        &F2_SHORT[2]);
    even = f2xm1_add_constant_rn64(
        f2xm1_mul_chop67(z2, even), &F2_SHORT[0]);
    even = f2xm1_add_rn64(z, f2xm1_mul_chop67(z2, even));

    wv_t odd = f2xm1_add_constant_rn64(
        f2xm1_mul_chop67(z2, f2xm1_constant(&F2_SHORT[5])),
        &F2_SHORT[3]);
    odd = f2xm1_add_constant_rn64(
        f2xm1_mul_chop67(z2, odd), &F2_SHORT[1]);
    odd = f2xm1_mul_chop67(z, f2xm1_mul_chop67(z2, odd));

    wv_t polynomial = f2xm1_add_rn64(even, odd);
    wv_t lookup = f2xm1_constant(&F2_TABLE[index]);
    wv_t one_plus_lookup = f2xm1_add_rn64(
        lookup, (wv_t){ 0, 0, 1 });
    wv_t scaled = f2xm1_mul_chop67(one_plus_lookup, polynomial);
    return f2xm1_final_add(lookup, scaled, rc);
}

/* reconstructed eleven-coefficient long path. */
static sf_t f2xm1_long_path(sf_t x, sf_rc_t rc)
{
    wv_t input = { x.sign, x.exp - 63, x.sig };
    wv_t ln2 = f2xm1_constant(&F2_LN2);
    wv_t tmp1 = f2xm1_mul_chop67(ln2, input);
    wv_t tmp2 = f2xm1_mul_rn64(ln2, input);
    tmp2 = f2xm1_mul_chop67(tmp1, tmp2);

    wv_t tmp5 = f2xm1_mul_chop67(
        tmp2, f2xm1_constant(&F2_LONG[9]));
    wv_t tmp6 = f2xm1_mul_chop67(
        tmp2, f2xm1_constant(&F2_LONG[10]));
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
    wv_t tmp3 = f2xm1_mul_chop67(
        tmp2, f2xm1_constant(&F2_LONG[0]));
    tmp6 = f2xm1_add_rn64(tmp5, tmp6);
    tmp3 = f2xm1_add_rn64(tmp3, tmp6);
    return f2xm1_final_add(tmp1, tmp3, rc);
}

/* complete finite-value F2XM1 path selection. */
static sf_t f2xm1_core(sf_t x, sf_rc_t rc)
{
    if (x.cls == SF_NAN) {          /* hardware quiets signaling NaNs */
        x.sig |= 0x4000000000000000ull;
        return x;
    }
    if (x.cls != SF_FIN || sf_is_zero(&x)) return x;
    if (x.exp > 0 || (x.exp == 0 && x.sig > (1ull << 63))) return x;
    if (x.exp == 0) {
        if (!x.sign) return ONE;
        return (sf_t){ SF_FIN, 1, -1, 1ull << 63 };
    }
    if (x.exp >= -2) return f2xm1_table_path(x, rc);
    if (x.exp >= -68) return f2xm1_long_path(x, rc);
    if (x.exp <= -16382) return f2xm1_tiny_raw80(x, rc);
    return f2xm1_final_multiply(
        (wv_t){ x.sign, x.exp - 63, x.sig }, &F2_LN2, rc);
}

/* one fused RN64 Horner step a*b+c for the
 * Round-18 candidate.  a and b may carry 67 bits; c is a native ROM entry. */
static sf_t p5_wv_fma_c_rn64(wv_t a, wv_t b, const p5c_t *c)
{
    int32_t product_e2 = a.e2 + b.e2;
    int32_t scale = product_e2 < c->exp2 ? product_e2 : c->exp2;
    u256 acc = { 0, 0 };
    acc_add_product(
        &acc, a.sign ^ b.sign, a.sig, b.sig, product_e2, scale);
    acc_add_product(&acc, c->sign, c->sig, 1, c->exp2, scale);
    return acc_rn64(acc, scale);
}

/* generalized table fusion accepting the
 * candidate's 66-bit t carrier. */
static sf_t p5_combine_wide_t(const p5c_t *T1, const wv_t *t,
                              const p5c_t *T2, const sf_t *S,
                              int sub, int neg_out, sf_rc_t rc,
                              const sf_t *cterm, const p5c_t *Tc, int csub)
{
    /* scale: fixed point at 2^-200 (T1: exp2 >= -69; t: >= 2^-80ish; products
     * >= 2^-160): all terms exact at 2^-200. acc is signed via wrap. */
    const int SCALE = -200;
    u256 acc = { 0, 0 };
    /* term A: T1 * 1 */
    {
        int sh = T1->exp2 - SCALE;                  /* ~131..139 */
        u128 m = T1->sig;
        /* m * 2^sh into (hi,lo) */
        u128 hi = sh >= 128 ? (m << (sh - 128)) : (sh > 0 ? (m >> (128 - sh)) : 0);
        u128 lo = sh >= 128 ? 0 : (m << sh);
        acc_add(&acc, T1->sign, hi, lo);
    }
    /* term B: T1 * t (t is 64-bit baseline or 66-bit Round-16 carrier) */
    if (t->sig) {
        acc_add_product(&acc, T1->sign ^ t->sign, T1->sig, t->sig,
                        T1->exp2 + t->e2, SCALE);
    }
    /* term C: +/- T2 * S */
    if (S->sig) {
        u128 phi = (u128)(uint64_t)(T2->sig >> 4) * S->sig;
        u128 plo = (u128)((uint64_t)T2->sig & 0xF) * S->sig;
        int32_t e2 = T2->exp2 + (S->exp - 63);
        int sh = e2 - SCALE + 4;
        int s3 = sh - 4;
        int neg = T2->sign ^ S->sign ^ (sub ? 1 : 0);
        u128 hi1 = sh >= 128 ? (phi << (sh - 128)) : (sh > 0 ? (phi >> (128 - sh)) : 0);
        u128 lo1 = sh >= 128 ? 0 : (sh >= 0 ? (phi << sh) : (phi >> -sh));
        acc_add(&acc, neg, hi1, lo1);
        u128 hi2 = s3 >= 128 ? (plo << (s3 - 128)) : (s3 > 0 ? (plo >> (128 - s3)) : 0);
        u128 lo2 = s3 >= 128 ? 0 : (s3 >= 0 ? (plo << s3) : (plo >> -s3));
        acc_add(&acc, neg, hi2, lo2);
    }
    /* term D (optional): +/- Tc * cterm — first-order wide-argument (c)
     * correction for reduced inputs: d sin/dr = cos etc. */
    if (cterm && cterm->sig) {
        u128 phi = (u128)(uint64_t)(Tc->sig >> 4) * cterm->sig;
        u128 plo = (u128)((uint64_t)Tc->sig & 0xF) * cterm->sig;
        int32_t e2 = Tc->exp2 + (cterm->exp - 63);
        int sh2 = e2 - SCALE + 4;
        int s3 = sh2 - 4;
        int neg2 = Tc->sign ^ cterm->sign ^ (csub ? 1 : 0);
        u128 hi1 = sh2 >= 128 ? (phi << (sh2 - 128)) : (sh2 > 0 ? (phi >> (128 - sh2)) : 0);
        u128 lo1 = sh2 >= 128 ? 0 : (sh2 >= 0 ? (phi << sh2) : (phi >> -sh2));
        acc_add(&acc, neg2, hi1, lo1);
        u128 hi2 = s3 >= 128 ? (plo << (s3 - 128)) : (s3 > 0 ? (plo >> (128 - s3)) : 0);
        u128 lo2 = s3 >= 128 ? 0 : (s3 >= 0 ? (plo << s3) : (plo >> -s3));
        acc_add(&acc, neg2, hi2, lo2);
    }
    return acc_round64_rc(acc, SCALE, neg_out, rc);
}

static sf_t p5_combine(const p5c_t *T1, const sf_t *t, const p5c_t *T2,
                       const sf_t *S, int sub, int neg_out, sf_rc_t rc,
                       const sf_t *cterm, const p5c_t *Tc, int csub)
{
    wv_t tw = { t->sign, t->exp - 63, (u128)t->sig };
    return p5_combine_wide_t(T1, &tw, T2, S, sub, neg_out, rc,
                             cterm, Tc, csub);
}

/*
 * Round-24 table-combine candidate:
 *
 *   result = architectural_round(T1 + RN67(T1*t +/- T2*S))
 *
 * The optional cterm/Tc product carries Round 21's equivalent shared-S
 * correction and is included inside the RN67 correction accumulator.
 */
static sf_t p5_combine_delta_rn67_wide_t(
    const p5c_t *T1, const wv_t *t,
    const p5c_t *T2, const sf_t *S,
    int sub, int neg_out, sf_rc_t rc,
    const sf_t *cterm, const p5c_t *Tc, int csub)
{
    const int SCALE = -200;
    u256 correction = { 0, 0 };
    if (t->sig) {
        acc_add_product(
            &correction,
            T1->sign ^ t->sign,
            T1->sig,
            t->sig,
            T1->exp2 + t->e2,
            SCALE);
    }
    if (S->sig) {
        acc_add_product(
            &correction,
            T2->sign ^ S->sign ^ (sub ? 1 : 0),
            T2->sig,
            S->sig,
            T2->exp2 + S->exp - 63,
            SCALE);
    }
    if (cterm && cterm->sig) {
        acc_add_product(
            &correction,
            Tc->sign ^ cterm->sign ^ (csub ? 1 : 0),
            Tc->sig,
            cterm->sig,
            Tc->exp2 + cterm->exp - 63,
            SCALE);
    }
    wv_t rounded = acc_rn_bits(correction, SCALE, 67);

    u256 final = { 0, 0 };
    acc_add_product(
        &final,
        T1->sign,
        T1->sig,
        1,
        T1->exp2,
        SCALE);
    if (rounded.sig) {
        acc_add_product(
            &final,
            rounded.sign,
            rounded.sig,
            1,
            rounded.e2,
            SCALE);
    }
    return acc_round64_rc(final, SCALE, neg_out, rc);
}

static sf_t p5_combine_delta_rn67(
    const p5c_t *T1, const sf_t *t,
    const p5c_t *T2, const sf_t *S,
    int sub, int neg_out, sf_rc_t rc,
    const sf_t *cterm, const p5c_t *Tc, int csub)
{
    wv_t tw = { t->sign, t->exp - 63, (u128)t->sig };
    return p5_combine_delta_rn67_wide_t(
        T1, &tw, T2, S, sub, neg_out, rc,
        cterm, Tc, csub);
}

/*
 * h136-h137's cross-validated narrow-table
 * reconstruction:
 *
 *   p = (S + s_bias) - a
 *   correction = RN67(T1*q +/- (T2*a + away64(T2*p)))
 *   result = architectural_round(T1 + correction)
 *
 * This is Tang's published grouping, Sj + r*Cj + (Sj*q + Cj*p).  The
 * away64 Cj*p carrier improves standalone train/held/fresh data and the
 * independent Pentium-II dense FSINCOS capture without changing the master
 * score.  The products are distributed into fixed-point accumulators so p
 * itself remains exact.
 */
static sf_t fsincos_p5_combine_tang_narrow_away64(
    const p5c_t *T1, const wv_t *q,
    const p5c_t *T2, const sf_t *S, const wv_t *a,
    int sub, int neg_out, sf_rc_t rc, const sf_t *s_bias)
{
    const int SCALE = -200;
    u256 p_product = { 0, 0 };
    if (S->sig) {
        acc_add_product(
            &p_product,
            T2->sign ^ S->sign ^ (sub ? 1 : 0),
            T2->sig,
            S->sig,
            T2->exp2 + S->exp - 63,
            SCALE);
    }
    if (s_bias && s_bias->sig) {
        acc_add_product(
            &p_product,
            T2->sign ^ s_bias->sign ^ (sub ? 1 : 0),
            T2->sig,
            s_bias->sig,
            T2->exp2 + s_bias->exp - 63,
            SCALE);
    }
    if (a->sig) {
        acc_add_product(
            &p_product,
            T2->sign ^ a->sign ^ 1 ^ (sub ? 1 : 0),
            T2->sig,
            a->sig,
            T2->exp2 + a->e2,
            SCALE);
    }
    wv_t stored_p_product = acc_round_bits_mode(
        p_product, SCALE, 64, P5_ROUND_AWAY);

    u256 correction = { 0, 0 };
    if (q->sig) {
        acc_add_product(
            &correction,
            T1->sign ^ q->sign,
            T1->sig,
            q->sig,
            T1->exp2 + q->e2,
            SCALE);
    }
    if (a->sig) {
        acc_add_product(
            &correction,
            T2->sign ^ a->sign ^ (sub ? 1 : 0),
            T2->sig,
            a->sig,
            T2->exp2 + a->e2,
            SCALE);
    }
    if (stored_p_product.sig) {
        acc_add_product(
            &correction,
            stored_p_product.sign,
            stored_p_product.sig,
            1,
            stored_p_product.e2,
            SCALE);
    }
    wv_t rounded = acc_rn_bits(correction, SCALE, 67);

    u256 final = { 0, 0 };
    acc_add_product(
        &final,
        T1->sign,
        T1->sig,
        1,
        T1->exp2,
        SCALE);
    if (rounded.sig) {
        acc_add_product(
            &final,
            rounded.sign,
            rounded.sig,
            1,
            rounded.e2,
            SCALE);
    }
    return acc_round64_rc(final, SCALE, neg_out, rc);
}

/*
 * h139-h142's physical refinement of the Round-28
 * Cj*p proxy.  It formats both multiplier operands before multiplication:
 *
 *   direct:  p -> X67, Cj -> Y64, product -> RU64
 *   reduced: Cj -> X67, p -> Y64, product -> RD64
 *
 * The direct route is jointly selected by the complete old partitions and
 * the independent h140 capture.  Reduced RD64 and round-to-odd remain
 * observationally tied; RD64 is retained because the documented P5 FMUL
 * implements IEEE directed modes, while round-to-odd is only an analysis
 * representative.  The h140 reduced witness also selects Cj on X67.
 */
static sf_t fsincos_p5_combine_tang_narrow_p5_route(
    const p5c_t *T1, const wv_t *q,
    const p5c_t *T2, const sf_t *S, const wv_t *a,
    int sub, int neg_out, sf_rc_t rc, const sf_t *s_bias,
    int reduced)
{
    const int SCALE = -200;
    u256 p_state = { 0, 0 };
    if (S->sig) {
        acc_add_product(
            &p_state, S->sign, S->sig, 1, S->exp - 63, SCALE);
    }
    if (s_bias && s_bias->sig) {
        acc_add_product(
            &p_state,
            s_bias->sign,
            s_bias->sig,
            1,
            s_bias->exp - 63,
            SCALE);
    }
    if (a->sig) {
        acc_add_product(
            &p_state, a->sign ^ 1, a->sig, 1, a->e2, SCALE);
    }

    wv_t stored_p = acc_round_bits_mode(
        p_state, SCALE, reduced ? 64 : 67, P5_ROUND_RN);
    wv_t stored_constant = p5_constant_round(
        T2, reduced ? 67 : 64, P5_ROUND_RN);
    wv_t stored_p_product = p5_wv_mul_round(
        stored_constant,
        stored_p,
        64,
        reduced ? P5_ROUND_DOWN : P5_ROUND_UP);
    stored_p_product.sign ^= sub ? 1 : 0;

    u256 correction = { 0, 0 };
    if (q->sig) {
        acc_add_product(
            &correction,
            T1->sign ^ q->sign,
            T1->sig,
            q->sig,
            T1->exp2 + q->e2,
            SCALE);
    }
    if (a->sig) {
        acc_add_product(
            &correction,
            T2->sign ^ a->sign ^ (sub ? 1 : 0),
            T2->sig,
            a->sig,
            T2->exp2 + a->e2,
            SCALE);
    }
    if (stored_p_product.sig) {
        acc_add_product(
            &correction,
            stored_p_product.sign,
            stored_p_product.sig,
            1,
            stored_p_product.e2,
            SCALE);
    }
    wv_t rounded = acc_rn_bits(correction, SCALE, 67);

    u256 final = { 0, 0 };
    acc_add_product(
        &final, T1->sign, T1->sig, 1, T1->exp2, SCALE);
    if (rounded.sig) {
        acc_add_product(
            &final,
            rounded.sign,
            rounded.sig,
            1,
            rounded.e2,
            SCALE);
    }
    return acc_round64_rc(final, SCALE, neg_out, rc);
}

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
static sf_t fsincos_compat_p6_horner4(
    const p5c_t *c4, const p5c_t *c3,
    const p5c_t *c2, const p5c_t *c1,
    const wv_t *square)
{
    wv_t value = p5_constant_round(c4, 67, P5_ROUND_RN);
    value = p5_wv_mul_round(
        value, *square, 67, P5_ROUND_CHOP);
    value = p5_wv_add_constant_round(
        value, c3, 67, P5_ROUND_RN, 64, P5_ROUND_RN);
    value = p5_wv_mul_round(
        value, *square, 67, P5_ROUND_CHOP);
    value = p5_wv_add_constant_round(
        value, c2, 67, P5_ROUND_RN, 64, P5_ROUND_RN);
    value = p5_wv_mul_round(
        value, *square, 67, P5_ROUND_CHOP);
    value = p5_wv_add_constant_round(
        value, c1, 67, P5_ROUND_RN, 64, P5_ROUND_RN);
    return wv_rn64(value);
}

/* exact addition of the 64-bit shared sine state
 * and its retained sub-ulp bias, kept as a wide carrier for the following
 * P6 reconstruction multiply. */
static wv_t fsincos_compat_add_sine_state(
    const sf_t *state, const sf_t *bias)
{
    int32_t state_e2 = state->exp - 63;
    u128 bias_sig = bias && bias->sig ? (u128)bias->sig : 0;
    int32_t bias_e2 = bias_sig ? bias->exp - 63 : state_e2;
    /* Biases are normalized sf_t values but semantically tiny integers
     * times a local ulp fraction.  Remove their trailing zero padding before
     * alignment so the exact sum needs only about 69 bits, not 130. */
    while (bias_sig && !(bias_sig & 1)) {
        bias_sig >>= 1;
        bias_e2++;
    }
    int32_t scale = state_e2 < bias_e2 ? state_e2 : bias_e2;
    int state_shift = state_e2 - scale;
    int bias_shift = bias_e2 - scale;
    __int128 value = (__int128)((u128)state->sig << state_shift);
    if (state->sign) value = -value;
    if (bias_sig) {
        __int128 adjustment = (__int128)(bias_sig << bias_shift);
        value += bias->sign ? -adjustment : adjustment;
    }
    if (!value) return (wv_t){ 0, 0, 0 };
    return (wv_t){
        (uint8_t)(value < 0),
        scale,
        (u128)(value < 0 ? -value : value)
    };
}

/* width of a nonzero exact 256-bit integer after
 * removing insignificant trailing zeroes. */
static int fsincos_compat_u256_significant_width(u256 value)
{
    int width;
    int trailing = 0;
    if (value.hi) {
        width = 128 + u128_width(value.hi);
    } else {
        width = u128_width(value.lo);
    }
    if (value.lo) {
        u128 bits = value.lo;
        while (!(bits & 1)) {
            trailing++;
            bits >>= 1;
        }
    } else {
        u128 bits = value.hi;
        trailing = 128;
        while (!(bits & 1)) {
            trailing++;
            bits >>= 1;
        }
    }
    return width - trailing;
}

/*
 * propagate the shared-sine carrier's unresolved
 * low interval through the immediately dependent table multiply.  The legal
 * 67-bit numeric carrier is RN64<<3 minus one unit (low bits 111).  Treating
 * its low suffix as a half-open interval gives RN64 as the common upper
 * endpoint.  The captured multiplier result is the retained unit immediately
 * below the endpoint's ordinary chop67 product whenever that interval spans
 * more than one retained product value.
 */
static wv_t fsincos_compat_p6_carrier_interval_product(
    wv_t cross, const sf_t *sine_state)
{
    wv_t upper = {
        sine_state->sign,
        sine_state->exp - 63,
        (u128)sine_state->sig
    };
    wv_t lower = {
        sine_state->sign,
        sine_state->exp - 66,
        ((u128)sine_state->sig << 3) - 2
    };
    wv_t low_product = p5_wv_mul_round(
        cross, lower, 67, P5_ROUND_CHOP);
    wv_t high_product = p5_wv_mul_round(
        cross, upper, 67, P5_ROUND_CHOP);
    u256 exact_upper = u128_mul_full(cross.sig, upper.sig);

    /* The interval excludes its upper endpoint. */
    if (fsincos_compat_u256_significant_width(exact_upper) <= 67)
        high_product.sig--;
    if (
        low_product.sign != high_product.sign
        || low_product.e2 != high_product.e2
        || low_product.sig != high_product.sig
    )
        high_product.sig--;
    return high_product;
}

/*
 * h227-h230's P6 full-sine reconstruction carrier:
 *
 *   q_product = odd67(lead * cosine_tail)
 *   p_product = chop67(cross * complete_sine_state)
 *   correction = away67(q_product +/- p_product)
 *   result = architectural_round(lead + correction)
 *
 * This directly follows the reconstructed P6 dependency graph.  The unusual
 * carrier modes remain equivalent representations rather than claimed
 * literal mnemonic semantics.
 */
static sf_t fsincos_compat_p6_combine_full_sine(
    const p5c_t *lead_constant, const sf_t *cosine_tail,
    const p5c_t *cross_constant, const sf_t *sine_state,
    int subtract_cross, int negate_output, sf_rc_t rc,
    const sf_t *sine_bias, int carrier_interval, int correction_delta)
{
    const int SCALE = -200;
    wv_t lead = {
        lead_constant->sign, lead_constant->exp2, lead_constant->sig
    };
    wv_t cross = {
        cross_constant->sign, cross_constant->exp2, cross_constant->sig
    };
    wv_t tail = {
        cosine_tail->sign,
        cosine_tail->exp - 63,
        (u128)cosine_tail->sig
    };
    wv_t complete_sine = fsincos_compat_add_sine_state(
        sine_state, sine_bias);
    wv_t q_product = p5_wv_mul_round(
        lead, tail, 67, P5_ROUND_ODD);
    wv_t p_product = carrier_interval
        ? fsincos_compat_p6_carrier_interval_product(cross, sine_state)
        : p5_wv_mul_round(
            cross, complete_sine, 67, P5_ROUND_CHOP);
    p_product.sign ^= subtract_cross ? 1 : 0;
    wv_t correction = p5_wv_add_round(
        q_product, p_product, 67, P5_ROUND_AWAY);
    if (carrier_interval && correction_delta) {
        if (
            correction_delta < 0
            && correction.sig < (u128)(-correction_delta)
        ) {
            fprintf(stderr, "invalid Round-49 correction delta\n");
            exit(2);
        }
        if (correction_delta < 0)
            correction.sig -= (unsigned)(-correction_delta);
        else
            correction.sig += (unsigned)correction_delta;
    }
    if (g_dump_final) {
        sf_t q_dump = wv_rn64(q_product);
        sf_t p_dump = wv_rn64(p_product);
        sf_t s_dump = wv_rn64(complete_sine);
        sf_t c_dump = wv_rn64(correction);
        dump2(&q_dump, &p_dump);
        dump2(&s_dump, &c_dump);
    }

    u256 final = { 0, 0 };
    acc_add_product(
        &final, lead.sign, lead.sig, 1, lead.e2, SCALE);
    if (correction.sig) {
        acc_add_product(
            &final,
            correction.sign,
            correction.sig,
            1,
            correction.e2,
            SCALE);
    }
    return acc_round64_rc(final, SCALE, negate_output, rc);
}

static sf_t fsincos_p5_combine_tang_lookup_p_rn64(
    const p5c_t *T1, const wv_t *q,
    const p5c_t *T2, const sf_t *S, const wv_t *a,
    int sub, int neg_out, sf_rc_t rc, const sf_t *s_bias)
{
    const int SCALE = -200;
    wv_t stored_constant = p5_constant_round(
        T2, 64, P5_ROUND_RN);
    u256 correction = { 0, 0 };

    if (q->sig) {
        acc_add_product(
            &correction,
            T1->sign ^ q->sign,
            T1->sig,
            q->sig,
            T1->exp2 + q->e2,
            SCALE);
    }
    if (a->sig) {
        acc_add_product(
            &correction,
            T2->sign ^ a->sign ^ (sub ? 1 : 0),
            T2->sig,
            a->sig,
            T2->exp2 + a->e2,
            SCALE);
    }
    if (S->sig) {
        acc_add_product(
            &correction,
            stored_constant.sign ^ S->sign ^ (sub ? 1 : 0),
            stored_constant.sig,
            S->sig,
            stored_constant.e2 + S->exp - 63,
            SCALE);
    }
    if (s_bias && s_bias->sig) {
        acc_add_product(
            &correction,
            stored_constant.sign ^ s_bias->sign ^ (sub ? 1 : 0),
            stored_constant.sig,
            s_bias->sig,
            stored_constant.e2 + s_bias->exp - 63,
            SCALE);
    }
    if (a->sig) {
        acc_add_product(
            &correction,
            stored_constant.sign ^ a->sign ^ 1 ^ (sub ? 1 : 0),
            stored_constant.sig,
            a->sig,
            stored_constant.e2 + a->e2,
            SCALE);
    }

    wv_t rounded = acc_rn_bits(correction, SCALE, 67);
    u256 final = { 0, 0 };
    acc_add_product(
        &final,
        T1->sign,
        T1->sig,
        1,
        T1->exp2,
        SCALE);
    if (rounded.sig) {
        acc_add_product(
            &final,
            rounded.sign,
            rounded.sig,
            1,
            rounded.e2,
            SCALE);
    }
    return acc_round64_rc(final, SCALE, neg_out, rc);
}

/*
 * h211-h216's lane-local wide-table FADD
 * microcontrol representative.  h211 closes all fifteen unconditional
 * four-term trees; h212 proves fixed jam-sub semantics can reach every
 * remaining lane; h215's bounded three-signal CEGIS leaves this rule; and
 * the hardware-blind h216 Skylake capture selects it over eight competing
 * operation/GRS/retained-bit readings.
 *
 * Products use FMUL's sticky 67-bit carrier.  The first reconstruction FADD
 * combines linear=T2*a with p=T2*((S+s_bias)-a).  When its normalized raw
 * carrier has exponent distance 14, exponent phase zero modulo four, and
 * carrier bit 3 set, microcontrol follows:
 *
 *   first  = odd64(linear + p)
 *   second = odd67(first + T1*q)
 *   final  = odd67(second + T1)
 *
 * Otherwise Round 34's validated RN64 lookup/FIRC route remains active.
 * On every selected sweep/dense/fresh lane the literal h206 jam-sub carrier
 * is exactly this round-to-odd representation.
 */
static sf_t fsincos_p5_combine_fadd_microcontrol(
    const p5c_t *T1, const wv_t *q,
    const p5c_t *T2, const sf_t *S, const wv_t *a,
    int sub, int neg_out, sf_rc_t rc, const sf_t *s_bias)
{
    const int SCALE = -200;
    wv_t lead = { T1->sign, T1->exp2, T1->sig };
    wv_t cross = { T2->sign, T2->exp2, T2->sig };
    sf_t a64_sf = wv_rn64(*a);
    wv_t a64 = {
        a64_sf.sign, a64_sf.exp - 63, (u128)a64_sf.sig
    };
    wv_t linear = p5_wv_mul_round(
        cross, a64, 67, P5_ROUND_ODD);
    linear.sign ^= sub ? 1 : 0;

    u256 p_state = { 0, 0 };
    if (S->sig) {
        acc_add_product(
            &p_state, S->sign, S->sig, 1, S->exp - 63, SCALE);
    }
    if (s_bias && s_bias->sig) {
        acc_add_product(
            &p_state,
            s_bias->sign,
            s_bias->sig,
            1,
            s_bias->exp - 63,
            SCALE);
    }
    if (a->sig) {
        acc_add_product(
            &p_state, a->sign ^ 1, a->sig, 1, a->e2, SCALE);
    }
    wv_t stored_p = acc_round_bits_mode(
        p_state, SCALE, 67, P5_ROUND_RN);
    wv_t cross64 = p5_constant_round(T2, 64, P5_ROUND_RN);
    wv_t p_product = p5_wv_mul_round(
        stored_p, cross64, 67, P5_ROUND_ODD);
    p_product.sign ^= sub ? 1 : 0;

    wv_t q_product = p5_wv_mul_round(
        lead, *q, 67, P5_ROUND_ODD);
    wv_t raw_first = p5_wv_add_round(
        linear, p_product, 67, P5_ROUND_ODD);
    if (!linear.sig || !p_product.sig || !raw_first.sig) {
        return fsincos_p5_combine_tang_lookup_p_rn64(
            T1, q, T2, S, a, sub, neg_out, rc, s_bias);
    }
    int linear_exponent = linear.e2 + u128_width(linear.sig) - 1;
    int p_exponent = p_product.e2 + u128_width(p_product.sig) - 1;
    int exponent_difference = linear_exponent - p_exponent;
    if (exponent_difference < 0) exponent_difference = -exponent_difference;
    int raw_exponent = raw_first.e2 + u128_width(raw_first.sig) - 1;
    int raw_phase = raw_exponent % 4;
    if (raw_phase < 0) raw_phase += 4;

    if (
        exponent_difference != 14
        || raw_phase != 0
        || !((raw_first.sig >> 3) & 1)
    ) {
        return fsincos_p5_combine_tang_lookup_p_rn64(
            T1, q, T2, S, a, sub, neg_out, rc, s_bias);
    }

    wv_t first = p5_wv_add_round(
        linear, p_product, 64, P5_ROUND_ODD);
    wv_t second = p5_wv_add_round(
        first, q_product, 67, P5_ROUND_ODD);
    wv_t final = p5_wv_add_round(
        second, lead, 67, P5_ROUND_ODD);
    u256 accumulator = { 0, 0 };
    if (final.sig) {
        acc_add_product(
            &accumulator,
            final.sign,
            final.sig,
            1,
            final.e2,
            final.e2);
    }
    return acc_round64_rc(accumulator, final.e2, neg_out, rc);
}

/* Rebuild the exact wide reduced argument |r+c| from (r, c).
 * By construction of the M66 reducer, c != 0 only when |r| >= 0.5 (the
 * 65th significand bit), and then c is exactly +-1 unit of 2^-65. */
static wv_t wv_from_rc(const sf_t *r, const sf_t *c)
{
    wv_t w;
    w.sign = r->sign;
    if (c->sig == 0) {
        w.sig = (u128)r->sig;
        w.e2 = r->exp - 63;
        return w;
    }
    u128 m = ((u128)r->sig) << 1;   /* r.exp == -1 here; scale 2^-65 */
    if (c->sign == r->sign) m += 1; else m -= 1;
    w.sig = m;
    w.e2 = -65;
    return w;
}

/* RN64 of the square of a wide value (sig <= 64 bits at all call
 * sites; the legacy shared path squares the 65-bit folded rw here,
 * wrapping mod 2^128 — preserved verbatim unless the experimental
 * --rcfold is active, which needs the true wide square). */
static sf_t wv_sq_rn64(const wv_t *a)
{
    if ((a->sig >> 64) && g_rcfold_bits) {
        u256 acc = { 0, 0 };
        acc_add_product(&acc, 0, a->sig, a->sig, 2 * a->e2, 2 * a->e2);
        wv_t w = acc_round_bits_mode(acc, 2 * a->e2, 64, P5_ROUND_RN);
        wv_t s = { 0, w.e2, w.sig };
        return wv_rn64(s);
    }
    wv_t s;
    s.sign = 0;
    s.sig = a->sig * a->sig;
    s.e2 = 2 * a->e2;
    return wv_rn64(s);
}

/* EXPERIMENTAL (--rcfold=B:rn|chop): fold the two-part reduced
 * argument (r, c) by actually rounding r+c to B bits instead of the
 * shipped sign-of-c half-ulp injection (2r +- 1).  B10 hypothesis:
 * the chip's kernels consume a properly rounded reduced-argument
 * register; the +-1 collapse mispredicts exactly at output-boundary
 * rows.  Inert when g_rcfold_bits == 0 (the default). */
static wv_t wv_from_rc_wide(const sf_t *r, const sf_t *c,
                            int bits, int rn)
{
    if (c->sig == 0)
        return (wv_t){ r->sign, r->exp - 63, (u128)r->sig };
    int32_t scale = (c->exp - 63) - 8;
    if ((r->exp - 63) - scale > 180)
        scale = (r->exp - 63) - 180;
    u256 acc = { 0, 0 };
    acc_add_product(&acc, 0, r->sig, 1, r->exp - 63, scale);
    if ((c->exp - 63) >= scale)
        acc_add_product(&acc, (c->sign != r->sign) ? 1 : 0,
                        c->sig, 1, c->exp - 63, scale);
    wv_t w = acc_round_bits_mode(acc, scale, bits,
                                 rn == 1 ? P5_ROUND_RN : P5_ROUND_CHOP);
    if (rn == 2)
        w.sig |= 1;              /* von Neumann jam: trunc | 1.
                                  * B=65 jam == the shipped 2r+-1. */
    w.sign = r->sign;
    return w;
}

/* RN64 of (sf * wide) product */
static sf_t wv_mul_sf_rn64(const sf_t *x, const wv_t *a)
{
    if (x->sig == 0 || a->sig == 0) return sf_zero(x->sign ^ a->sign);
    wv_t p;
    p.sign = (uint8_t)(x->sign ^ a->sign);
    p.sig = (u128)x->sig * a->sig;
    p.e2 = (x->exp - 63) + a->e2;
    return wv_rn64(p);
}

/* RN64 of (wide + sf) sum */
static sf_t wv_add_sf_rn64(const wv_t *a, const sf_t *x)
{
    if (a->sig == 0) return *x;
    if (x->sig == 0) return wv_rn64(*a);
    int32_t ex = x->exp - 63;
    int32_t E = a->e2 < ex ? a->e2 : ex;
    __int128 va = (__int128)(a->sig << (a->e2 - E));
    if (a->sign) va = -va;
    __int128 vx = (__int128)((u128)x->sig << (ex - E));
    if (x->sign) vx = -vx;
    __int128 v = va + vx;
    wv_t s;
    if (v == 0) return sf_zero(0);
    s.sign = v < 0; s.sig = v < 0 ? (u128)(-v) : (u128)v; s.e2 = E;
    return wv_rn64(s);
}

static const int g_round16_narrow = 0;
static const int g_round18_poly = 1;
static const int g_round19_wide_q = 0;
static int g_fsin_standalone_path = 0;
static int g_fcos_standalone_path = 0;
static int g_batch_fsin_only = 0;
static int g_batch_fcos_only = 0;
static int g_batch_f2xm1_only = 0;
static int g_batch_fptan_only = 0;
/*
 * below this exponent the Pentium and Itanium
 * polynomial corrections cannot change the stored 64-bit result on current
 * evidence.  Retaining small_r there also avoids representing an irrelevant
 * r-versus-r^3 exponent gap in the bounded wv_t accumulator.
 */
static const int32_t P5_POLY_MODEL_MIN_EXP = -32;
/* numerators in units of 1/32 of S's local 64-bit ulp; 0 disables */
static const int g_round21_narrow_bias = 4;
static const int g_round21_wide_bias = 5;
static const int g_round23_narrow_coefficient = 1;
static const int g_round24_table_delta_rn67 = 1;
static const int g_round28_tang_narrow = 0;
static const int g_round29_p5_fmul_route = 1;
static const int g_round30_fsin_cosine_square = 1;
static const int g_round31_fsin_cosine_tail = 1;
static const int g_round32_fsin_cosine_horner = 1;
static const int g_round33_fsin_cosine_product = 1;
static const int g_round34_table_lookup_firc = 1;
static const int g_round35_table_p_terminal = 1;
static const int g_round36_table_fadd_microcontrol = 1;
static const int g_round37_p6_four_term = 1;
static const int g_round38_p6_cosine_split = 1;
static const int g_round39_fcos_tiny = 1;
static const int g_round40_fsincos_tiny = 1;
static const int g_round41_fsin_cosine_split = 1;
static const int g_round42_p6_sine_split = 1;
static const int g_round43_p6_sine_bias = 1;
static const int g_round44_p6_sine_bias = 1;
static const int g_round45_p6_sine_fraction = 1;
static const int g_round46_p6_narrow_sine_fraction = 1;
static const int g_round47_p6_narrow_sine_fraction = 1;
static const int g_round48_p6_narrow_sine_fraction = 1;
/* Analysis-only candidate numerator (/256) at narrow coordinate (-6,14);
 * negative means inactive. */
static int g_round55_narrow_fraction14 = -1;
/* Analysis-only stderr trace of the operation-class sine-state FADD. */
static int g_debug_sine_state = 0;
/* Analysis-only stderr trace of the Round-52 terminal cosine carrier. */
static int g_debug_cosine_carrier = 0;
/* Round 56 (h408/h409): FSIN's odd-quadrant internal cosine shares the
 * physical cosine kernel, so the Round-52 terminal carrier applies there
 * too.  Fixes three of the four known internal-cosine residuals and both
 * fresh hardware-blind separators with zero corpus regression. */
static const int g_round56_fsin_cosine_carrier = 1;
static const int g_round49_p6_carrier_interval = 1;
/* Analysis-only retained-unit perturbation at the table correction output. */
static int g_round49_correction_delta = 0;
static const int g_round50_fsin_operation_classes = 1;
static const int g_round51_fsin_fadd_signature = 1;
static const int g_round52_fcos_low3_carrier = 1;
static const int g_round53_fcos_operation_classes = 1;
static const int g_round54_fsincos_table_lanes = 1;
/* Exact bit-slice table-lane classifier: the double-precision
 * scaffolding classifier misrounds the top 2^-55 sliver below each
 * interior lane boundary (5/16, 3/8, 7/16, 5/8, 3/4) into the next
 * lane; hardware bit-slices the residual register exactly (Task-3
 * boundary sweep + lane probes, i7 Skylake capture, 2026-08-15). */
static const int g_round62_table_lane_exact = 1;
/* Masked-#IA response for invalid x87 encodings (unnormal,
 * pseudo-NaN, pseudo-infinity: nonzero exponent with a clear
 * explicit-integer bit): hardware returns the real indefinite
 * (ffff:c000...0) for FSIN/FCOS/FSINCOS in every rounding mode
 * (Task-3 special-operand sweep, i7 Skylake capture, 2026-08-15). */
static const int g_round63_invalid_encoding = 1;
/* Truncated-3x thirds comparator for the u-floor taps (h665-h668):
 * the hard multiple 3*rdisc is summed with both addend columns
 * below bit 47 killed before the thirds compare.  Exact thirds and
 * all rounded-constant forms are refuted by the near-boundary vote
 * corpus; blind-validated on the fresh comb13 lattice. */
static const int g_round64_comparator_trunc3x = 1;
/* ce=-74 result binade (W1 low edge, phase phw=6): first labeled by
 * comb13; the r59/r60/r61 laws apply verbatim with the block-start
 * criticality landing at pm=9 and both directions reading the
 * block-start bit (h670, 2026-08-15). */
static const int g_round65_ce74_band = 1;
/* FPTAN twin of the Round-62 exact table-lane classifier (the
 * defective double-precision classifier pattern was shared). */
static const int g_round66_fptan_lane_exact = 1;
/* Round 67 (h672-h674, edge-window sweep): the binade-top corner
 * cell (s4, side, dist, sR) = (67, 1, 8, 64) — first populated by
 * comb15/comb16 (operand mantissa within 2^46 of 2^64, x -> 0.25-);
 * empty in every prior corpus (all earlier (67,1,d8) rows are
 * sR=63).  There the M-comparison is degenerate (M//2^66 pinned to
 * {low3-2, low3-1}) and the gate reads the digit ladder
 * D = low3 + b1 + b2 on the thirds lattice: tie fire <=> D >= 3
 * (M plays no role), dn |th|=1 region <=> D >= 6, dn |th|=2 region
 * <=> D >= 9 (block-start law verbatim inside; phw=0 so critical
 * cells sit at pm=7), and the up lane never fires.  comb16:
 * 829,031/829,033 exact (residual: one isolated R-2 deep-fire +
 * one point-family row).  Blind corpus: comb17. */
static const int g_round67_corner_cell = 1;
/* Round 68 (h680-h682): the zero-lane drop at the corner cell.
 * When the 3x sum has no bit above the kill line (3*rdisc < 2^47)
 * the lane index is -1, not 0: D = L + b1 + b2 - 1.  Bracketed by
 * the corner t0/L=3/(0,0) population (only clean row at 3r =
 * 0.41*2^47, lowest fire at 1.87*2^47); the 2^47 boundary offset
 * matches the observed lane-1/2 comparator offsets — one geometry
 * at all three thirds lanes.  Zone census comb15/16/17: 6/6.
 * Blind corpus: comb18. */
static const int g_round68_lane0_drop = 1;
/* Round 69 (band-density attack h702-h708, 2026-08-17): the r64
 * killed-mass kill column is RELATIVE (2^(right_shift-16)), one bit
 * shallower on side==0, and the double-lane tie (theta==0, low3==1)
 * takes the carry (single-truncation 3*rd - (3*rd mod 2^col)).
 * rdisc's low bits = the square's low bits, so the old "per-row K /
 * sq&63 table" comparator fringe (blind-spot B1) was this form all
 * along.  PROMOTED after i7 regression net-positive on BLIND
 * corpora (comb9 12->11, comb13 8->7, zero regressions); Skylake-VM
 * FSIN unaffected.  Default ON; build -DG_ROUND69=0 to A/B against
 * the shipped-absolute-47 form. */
#ifndef G_ROUND69
#define G_ROUND69 1
#endif
static const int g_round69_relmask_sidedep = G_ROUND69;
/* h135-validated standalone FSIN terminal table materializations. */
static int g_fsin_table_terminal = 1;

static wv_t fsin_operation_class_sine_state(wv_t a, wv_t tail);
/*
 * h97-h101's cross-validated equivalent
 * correction to the row-169 significand.  This is deliberately separate
 * from p5_rom_constants.h: +7168 is not established as a ROM transcription
 * error and may represent an unresolved downstream producer operation.
 */
static const uint64_t ROUND23_P5S4_1_DELTA = 7168;

/* Round 57 (the statistical borrow-rule surface, zone/state tables
 * from h611_gen_tables.py) was deleted after the closed-form laws of
 * Rounds 59/60 covered every stratum end to end (h638-h664).  See
 * notes/HANDOFF-collision-gate.md; the surface survives in git
 * history (Rounds 57/58, commits through d388426).
 */
static const int g_round58_fsin_borrow_rule = 1;
static const int g_round59_fcos_theta_band = 1;
static const int g_round60_fcos_tie_gate = 1;

/* Round-59: closed-form theta-band deviation (h638-h662).  For
 * near-tie rows (theta in {+-1, +-2}) the deviation is exact: one
 * integer inequality against the h656 u-floor with the h658 tap
 * vectors decides the fireable region; inside it every row deviates
 * by one retained unit except at the block-critical lattice cells
 * (propagate run ending on an 8-bit block top), where the h662k
 * block-start law reads two bits of the terminal magnitude.  Blind
 * transfer 0/412,787 (comb9).  Returns 1 when the row is covered
 * (prediction written, deviated or clean); 0 falls through to the
 * Round-52 behavior.  (The Round-57 statistical surface that used
 * to catch fallthrough rows was deleted once Rounds 59/60 covered
 * every stratum in closed form — h638-h664: bypassing it is score-
 * neutral on comb7/comb9/comb11.) */
static int r59_floordiv(int n, int q)
{
    int d = n / q;
    if ((n % q) && (n < 0))
        d--;
    return d;
}

static int r59_apply(
    wv_t multiplier, wv_t fourth, wv_t magnitude,
    wv_t left, wv_t right, wv_t right_factor, int payload, int distance,
    unsigned low3, int right_shift, u128 right_discarded,
    wv_t *out)
{
    int lower1158 = G_R1158LOWER && magnitude.e2 == -67
        && distance >= 9 && distance <= 12;
    if (left.sign != 1 || right.sign != 0)
        return 0;
    if ((!G_R99WIDESCOPE && !lower1158
         && (distance < 7 || distance > 10)) || low3 < 1)
        return 0;
    int32_t rscale = left.e2 < right.e2 ? left.e2 : right.e2;
    if (payload && left.e2 - 8 < rscale)
        rscale = left.e2 - 8;
    int dl = left.e2 - rscale;
    int dp = left.e2 - 8 - rscale;
    int dr = right.e2 - rscale;
    if (dl < 0 || dr < 0 || (payload && dp < 0))
        return 0;
    __int128 S = (__int128)((u128)left.sig << dl);
    /* A payload can be negative. Scale it without a signed negative shift. */
    if (payload)
        S += (__int128)payload * ((__int128)1 << dp);
    __int128 B = (__int128)((u128)right.sig << dr);
    __int128 mag = S - B;
    if (mag <= 0)
        return 0;
    if (g_perturb_tgt == 6) {
        mag += g_perturb_delta;
        if (mag <= 0)
            return 0;
    }
    u128 umag = (u128)mag;
    int mw = u128_width(umag);
    int k = mw - 67;
    if (k < 3 || k > 60)
        return 0;
    u128 disc = umag & (((u128)1 << k) - 1);
    int theta;
    if (disc <= 2)
        theta = (int)disc;
    else if (disc >= (((u128)1 << k) - 2))
        theta = (int)(disc - (((u128)1 << k) - 2)) - 2;
    else
        return 0;
    if (theta == 0 && !g_round60_fcos_tie_gate)
        return 0;              /* ties stay with Round-57 */
    int sign_dn = theta > 0;
    int th = theta > 0 ? theta : -theta;
    int ce = rscale + k;
    if (ce != -72 && ce != -73
        && !(g_round65_ce74_band && ce == -74)
        && !(lower1158 && (ce == -74 || ce == -75))
        && !(G_R99CE75 && ce == -75))
        return 0;
    /* quadrant key: fourth-power full width and the 1/sqrt(2)
     * input side (integer form of the pivot) */
    u256 f4full = u128_mul_full(multiplier.sig, multiplier.sig);
    int fw = f4full.hi ? 128 + u128_width(f4full.hi)
                       : u128_width(f4full.lo);
    int s4 = fw - 67;
    if (s4 != 66 && s4 != 67)
        return 0;
    u128 t4 = (s4 < 128)
        ? (f4full.lo & (((u128)1 << s4) - 1))
        : f4full.lo;
#ifndef G_T4P
#define G_T4P 0
#endif
#if G_T4P == 1
    /* probe T1: t4 from the truncated-port square (R86 twin at the
     * margin tap only; output datapath untouched). */
    {
        u256 f4p = u128_mul_full(multiplier.sig,
                                 multiplier.sig & ~(u128)7);
        t4 = (s4 < 128) ? (f4p.lo & (((u128)1 << s4) - 1)) : f4p.lo;
    }
#endif
    int side = (uint64_t)magnitude.sig >= 0xB504F333F9DE6800ULL;
    __int128 sqlow = (__int128)multiplier.sig - ((__int128)1 << 66);
#if G_T4P == 2
    /* probe T2: the M product reads sqlow through a truncated port. */
    sqlow = (__int128)(multiplier.sig & ~(u128)7) - ((__int128)1 << 66);
#endif
    __int128 Mreg = (__int128)low3 * sqlow - (__int128)t4;
    unsigned __int128 rd3;
#if G_T4P == 3
    /* probe T3: the thirds taps read the discard through a
     * truncated (carry-predict copy) port. */
    right_discarded &= ~(u128)7;
#endif
    if (g_round64_comparator_trunc3x) {
        /* Round 64: the thirds taps read the Booth 3x hard multiple
         * summed with both addend columns below bit 47 killed —
         * comp = 3*rd - (2*rd mod 2^47) - (rd mod 2^47).  Exact
         * thirds and every rounded-constant form are refuted by the
         * near-boundary vote corpus; this form is blind-validated
         * on comb13 (h665-h668, 2026-08-15). */
        /* Round 69 (probation): relative, side-dependent kill column
         * and the theta==0/low3==1 double-lane-tie carry.  Flag off =>
         * mexp 47, double-column => byte-identical to the shipped r64
         * form above. */
        int mexp = g_round69_relmask_sidedep
                     ? (right_shift - 16 - (side == 0 ? 1 : 0)) : 47;
        unsigned __int128 mask = (((unsigned __int128)1) << mexp) - 1;
        int merge3x = low3 == 1;
#if G_R1270MERGE3X
        int merge3x_attachment = 1;
#if G_R1382MERGES4
        merge3x_attachment = s4 == 67;
#elif G_R1475MERGEXOR
        merge3x_attachment = s4 == 67
            || p5_r1475_right_tree_xor(
                fourth.sig, right_factor.sig, right_shift);
#endif
        if (low3 == 3 && merge3x_attachment) {
#if G_R1272MERGEGATE
            merge3x = !p5_r1259_level2_high_carry(
                fourth.sig, right_factor.sig, right_shift + 4);
#else
            merge3x = 1;
#endif
        }
#endif
        if (g_round69_relmask_sidedep && theta == 0 && merge3x) {
            rd3 = 3 * (unsigned __int128)right_discarded
                - ((3 * (unsigned __int128)right_discarded) & mask);
        } else {
            rd3 = 3 * (unsigned __int128)right_discarded
                - ((2 * (unsigned __int128)right_discarded) & mask)
                - ((unsigned __int128)right_discarded & mask);
        }
    } else {
        rd3 = 3 * (unsigned __int128)right_discarded;
    }
    int b1 = (rd3 >= ((unsigned __int128)1 << right_shift));
    int b2 = (rd3 >= ((unsigned __int128)1 << (right_shift + 1)));
#if G_R1259EQWIRE || G_R1263EQGATE
    /* Equality is the only point at which a comparator carry-in can choose
     * between >= and >.  A set physical gate selects the strict result; a
     * clear gate retains the incumbent inclusive result. */
    {
#if G_R1263EQGATE
        int equality_strict = p5_r1263_equality_carry_kill(
            fourth.sig, right_factor.sig, right_shift);
#else
        int equality_strict = p5_r1259_level2_high_carry(
            fourth.sig, right_factor.sig, right_shift + 4);
#endif
        if (equality_strict
            && rd3 == ((unsigned __int128)1 << right_shift))
            b1 = 0;
        if (equality_strict
            && rd3 == ((unsigned __int128)1 << (right_shift + 1)))
            b2 = 0;
    }
#endif
#if G_R99TAPS
    b1 = (G_R99TAPS - 1) & 1;
    b2 = ((G_R99TAPS - 1) >> 1) & 1;
#endif
    if (g_dump_internals || g_dump_r59_compact)
        fprintf(stderr,
            "DI_R59 theta=%d k=%d ce=%d s4=%d side=%d b1=%d b2=%d "
            "low3=%u dist=%d rsh=%d payload=%d rscale=%d dl=%d dr=%d "
            "dp=%d umag=%016llx%016llx S=%016llx%016llx "
            "B=%016llx%016llx Mreg=%016llx%016llx t4=%016llx%016llx "
            "sqlow=%016llx%016llx rd3=%016llx%016llx disc=%016llx%016llx\n",
            theta, k, ce, s4, side, b1, b2, low3, distance,
            right_shift, payload, rscale, dl, dr, dp,
            DIU(umag), DIU(S), DIU(B), DIU(Mreg), DIU(t4),
            DIU(sqlow), DIU(rd3), DIU(disc));
#if G_R1158LOWER
    /* h1158: one radix recurrence over the complete three-bit phase cube
     * of the e2=-67 producer binade.  The phase bits are correction
     * exponent (e), square width (a), and right-product shift (h).
     * payload is the aligned low Booth digit.  Each theta state reads one
     * of the already recovered truncated-thirds taps; no operand identity
     * or threshold table is involved.  The frozen disjoint boundary bank
     * was opened only after the recurrence was fixed and scored 2,151/2,151. */
    if (lower1158) {
        int e1158 = -ce - 74;
        int a1158 = s4 - 66;
        int h1158 = right_shift - 63;
        int expected_distance1158 = -ce - s4 + 2 + (64 - right_shift);
        if ((e1158 == 0 || e1158 == 1)
            && (a1158 == 0 || a1158 == 1)
            && (h1158 == 0 || h1158 == 1)
            && side == 1 - e1158
            && distance == expected_distance1158) {
            int slope1158 = 2 + 3 * a1158
                + h1158 * (1 - a1158);
            int intercept0_1158 = -1 - a1158
                - (1 - e1158) * (h1158 + 2 * a1158);
            int tap1_1158 = 0;
            int tap2_1158 = 0;
            int intercept1158 = intercept0_1158;
            if (theta == -2) {
                tap1_1158 = 2 * a1158
                    * (1 - e1158 * (1 - h1158))
                    + (1 - e1158) * h1158 * (1 - a1158);
                intercept1158 = -1 - a1158
                    + a1158 * h1158 * (3 - e1158);
            } else if (theta == -1) {
                tap2_1158 = a1158 * h1158 * (2 - e1158);
                intercept1158 += (1 - e1158) * (2 * a1158 + h1158)
                    + a1158 * h1158;
            } else if (theta == 0) {
                tap1_1158 = (1 - e1158) * h1158 * (1 + a1158);
            } else if (theta == 1) {
                tap2_1158 = (1 - e1158)
                    * (1 + a1158 * (1 - h1158));
                intercept1158 -= tap2_1158;
            } else {
                tap1_1158 = a1158
                    + (1 - e1158) * (1 - a1158) * (1 - h1158);
                intercept1158 -= 2 * (1 - e1158)
                        * (1 + a1158 * (1 - h1158))
                    + 3 * a1158 * h1158
                    + a1158 * e1158 * (1 - h1158);
            }
            int threshold1158 = slope1158 * payload
                + tap1_1158 * b1 + tap2_1158 * b2 + intercept1158;
            __int128 boundary1158 = (__int128)threshold1158
                * ((__int128)1 << 66);
            int fire1158 = theta >= 0
                ? Mreg < boundary1158 : Mreg >= boundary1158;
            int delta1158 = fire1158 ? (theta < 0 ? 1 : -1) : 0;
            __int128 retained1158 = (__int128)(umag >> k) + delta1158;
            if (retained1158 <= 0)
                return 0;
            u256 acc1158 = { 0, 0 };
            acc_add_product(&acc1158, 1, (u128)retained1158, 1,
                            rscale + k, rscale);
            *out = acc_round_bits_mode(
                acc1158, rscale, 67, P5_ROUND_CHOP);
            if (g_dump_internals)
                fprintf(stderr,
                    "DI_BR br=r1158 e=%d a=%d h=%d slope=%d tap=%d,%d "
                    "intercept=%d threshold=%d fire=%d delta=%d "
                    "r=%016llx%016llx out=" DIWF "\n",
                    e1158, a1158, h1158, slope1158,
                    tap1_1158, tap2_1158, intercept1158, threshold1158,
                    fire1158, delta1158, DIU(retained1158), DIW(*out));
            return 1;
        }
    }
#endif
#if G_R1266TERMGATE
    /* h1265: the two residual carry-zero endpoints share a fixed producer
     * history gate.  The square-product P5 CPA generates across columns
     * 114..129, while the right-product terminal S/C pair generates two
     * columns below its product cut.  Their conjunction selects the exact
     * carry-zero subtractor endpoint; it is a structural wire relation,
     * not an operand interval or learned boundary. */
    if (p5_r1266_terminal_generate_gate(
            multiplier.sig, fourth.sig, right_factor.sig, right_shift)) {
        u128 mask1266 = (((u128)1 << k) - 1);
        int borrow1266 = (((u128)S & mask1266) < ((u128)B & mask1266));
        int delta1266 = borrow1266 - 1;
        __int128 r1266 = (__int128)(umag >> k) + delta1266;
        if (r1266 <= 0)
            return 0;
        u256 acc1266 = { 0, 0 };
        acc_add_product(
            &acc1266, 1, (u128)r1266, 1, rscale + k, rscale);
        *out = acc_round_bits_mode(
            acc1266, rscale, 67, P5_ROUND_CHOP);
        if (g_dump_internals)
            fprintf(stderr,
                "DI_BR br=r1266 borrow=%d carry=0 delta=%d "
                "r=%016llx%016llx out=" DIWF "\n",
                borrow1266, delta1266, DIU(r1266), DIW(*out));
        return 1;
    }
#endif
#if G_R99CARRY == 0 || G_R99CARRY == 1
    /* h1167: enumerate the two exact subtractor endpoints without an
     * operand-independent retained-delta approximation.  For cut k, the
     * retained difference is floor((S-B)/2^k) plus the selected carry
     * relative to the low-field borrow.  Normal builds leave this disabled. */
    {
        u128 mask99 = (((u128)1 << k) - 1);
        int borrow99 = (((u128)S & mask99) < ((u128)B & mask99));
        int delta99 = borrow99 - 1 + G_R99CARRY;
        __int128 r99 = (__int128)(umag >> k) + delta99;
        if (r99 <= 0)
            return 0;
        u256 acc99 = { 0, 0 };
        acc_add_product(
            &acc99, 1, (u128)r99, 1, rscale + k, rscale);
        *out = acc_round_bits_mode(
            acc99, rscale, 67, P5_ROUND_CHOP);
        if (g_dump_internals)
            fprintf(stderr,
                "DI_BR br=r99carry borrow=%d carry=%d delta=%d "
                "r=%016llx%016llx out=" DIWF "\n",
                borrow99, G_R99CARRY, delta99, DIU(r99), DIW(*out));
        return 1;
    }
#endif
#if G_R99FORCE
    /* h1090 inverse-response probe: replace every covered near-tie branch
     * by one absolute retained correction.  This is deliberately ahead of
     * the tie/band/q67/corner selectors so a hardware result identifies the
     * correction value independently of the incumbent branch decision. */
    {
        int delta99 = G_R99FORCE - 3;
        __int128 r99 = (__int128)(umag >> k) + delta99;
        if (r99 <= 0)
            return 0;
        u256 acc99 = { 0, 0 };
        acc_add_product(
            &acc99, 1, (u128)r99, 1, rscale + k, rscale);
        *out = acc_round_bits_mode(
            acc99, rscale, 67, P5_ROUND_CHOP);
        if (g_dump_internals)
            fprintf(stderr,
                "DI_BR br=r99force delta=%d r=%016llx%016llx out="
                DIWF "\n", delta99, DIU(r99), DIW(*out));
        return 1;
    }
#endif
#if G_R97D9LADDER
    /* h1078-h1081: the scoped ce=-74 fall-through exposes another
     * carry-selector digit ladder in the (67, upper-side, distance-9)
     * cell.  Direct FCOS preimages of the reduced FSIN ledger row make
     * the cell densely perturbable.  Its two theta levels share
     *
     *     digit = 2*low3 + b1 + b2,   threshold = 4 + 2*|theta|.
     *
     * Above the threshold silicon takes the decreasing endpoint.  At
     * equality theta=2 takes it; theta=1 takes it except at the low3=2
     * edge, where the already-derived signed R60 coordinate resolves
     * the boundary at M=0.  Promoted after the complete cached scope and an
     * independent operand holdout pass.
     */
    if (ce == -74 && s4 == 67 && side == 1 && distance == 9
        && right_shift == 64 && sign_dn && (th == 1 || th == 2)) {
        int digit97 = 2 * (int)low3 + b1 + b2;
        int threshold97 = 4 + 2 * th;
        int fire97 = digit97 > threshold97
            || (digit97 == threshold97
                && (th == 2 || low3 >= 3 || Mreg < 0));
        if (fire97) {
            __int128 r97 = (__int128)(umag >> k) - 1;
            if (r97 <= 0)
                return 0;
            u256 acc97 = { 0, 0 };
            acc_add_product(
                &acc97, 1, (u128)r97, 1, rscale + k, rscale);
            *out = acc_round_bits_mode(
                acc97, rscale, 67, P5_ROUND_CHOP);
            if (g_dump_internals)
                fprintf(stderr,
                    "DI_BR br=r97d9 digit=%d threshold=%d fire=1 "
                    "r=%016llx%016llx out=" DIWF "\n",
                    digit97, threshold97, DIU(r97), DIW(*out));
            return 1;
        }
    }
#endif
    /* Round 67: the corner cell (67,1,d=8,sR=64) — the u-floor and
     * theta-band region tests are replaced by the D-ladder (see the
     * flag comment); the block-start law inside dn regions is the
     * shipped clause verbatim. */
    if (g_round67_corner_cell && s4 == 67 && side == 1
        && distance == 8 && right_shift == 64) {
        int dd = (int)low3 + b1 + b2;
        if (g_round68_lane0_drop
            && 3 * (unsigned __int128)right_discarded
               < ((unsigned __int128)1 << 47))
            dd -= 1;
        int fire = 0;
        if (theta == 0) {
            fire = dd >= 3;
        } else if (sign_dn && dd >= (th == 1 ? 6 : 9)) {
            unsigned __int128 pmask =
                ~((unsigned __int128)S ^ (unsigned __int128)B);
            int pm = 0;
            int j = k;
            while (pm < 32 && ((pmask >> j) & 1)) {
                pm++;
                j++;
            }
            int phw = ((ce % 8) + 8) % 8;
            int crit = ((pm + phw) % 8 == 7) && (pm == 7 || pm == 8);
            if (g_dump_internals)
                fprintf(stderr, "DI_CRIT at=corner pm=%d phw=%d crit=%d\n",
                    pm, phw, crit);
            if (!crit) {
                fire = 1;
            } else {
                int bsrel = 8 + ((8 - phw) % 8);
                int bit8 = (int)((umag >> (k + 8)) & 1);
                int bitbs = (int)((umag >> (k + bsrel)) & 1);
                fire = bit8 & bitbs;
            }
        }
        __int128 rcc = (__int128)(umag >> k)
            + (fire ? (sign_dn || theta == 0 ? -1 : 1) : 0);
#if G_R1387QXRUN || G_R1394QRUN
        /* The corner arm consumes the square tree's unresolved low-digit
         * merge as a carry-select input.  Toggle, rather than force, so this
         * remains the exact two-endpoint subtraction recurrence. */
        int r59_tree_toggle = 0;
#if G_R1387QXRUN
        r59_tree_toggle |= p5_r1387_square_qx_run(
            multiplier.sig, G_R1387QXMIN);
#endif
#if G_R1394QRUN
        r59_tree_toggle |= p5_r1394_square_q_run(
            multiplier.sig, G_R1394QMIN);
#endif
        if (r59_tree_toggle) {
            u128 low_mask = (((u128)1 << k) - 1);
            int borrow = (((u128)S & low_mask) < ((u128)B & low_mask));
            int delta = (int)(rcc - (__int128)(umag >> k));
            int carry = delta - borrow + 1;
            if (carry == 0 || carry == 1)
                rcc += carry ? -1 : 1;
        }
#endif
        if (rcc <= 0)
            return 0;
        u256 cacc = { 0, 0 };
        acc_add_product(&cacc, 1, (u128)rcc, 1, rscale + k, rscale);
        *out = acc_round_bits_mode(cacc, rscale, 67, P5_ROUND_CHOP);
        if (g_dump_internals)
            fprintf(stderr,
                "DI_BR br=corner dd=%d fire=%d r=%016llx%016llx out="
                DIWF "\n",
                dd, fire, DIU(rcc), DIW(*out));
        return 1;
    }
    /* h656 u-floor quadrant parameters (a, G1, G2, p, Q, K, par)
     * and the dist term W — all four quadrants (ties use all;
     * the theta band has no (66,0) taps) */
    int qa, qg1, qg2, qp, qq, qk, qpar, wd;
    if (s4 == 66 && side == 1) {
        qa = 2; qg1 = 2; qg2 = 1; qp = 0; qq = 4; qk = 1; qpar = 0;
        wd = -5 * (distance - 7);
    } else if (s4 == 66 && side == 0) {
        qa = 4; qg1 = 1; qg2 = 0; qp = 0; qq = 2; qk = 1; qpar = 0;
        wd = -9 - 5 * (distance - 9);
    } else if (s4 == 67 && side == 0) {
        qa = 4; qg1 = 2; qg2 = 1; qp = -2; qq = 4; qk = 2; qpar = 1;
        wd = -5 * (distance - 7);
    } else {
        qa = 2; qg1 = 2; qg2 = 3; qp = -3; qq = 8; qk = 2; qpar = 1;
        wd = -4 - 2 * (distance - 7);
    }
    int lp0 = (int)(low3 & 1);
    if (theta == 0) {
        /* Round-60: the h646/h656 closed-form tie gate — the same
         * u-floor with NO taps; fire drops one retained unit */
        int base0 = qa * (int)low3 + qg1 * b1 + qg2 * b2
            + qp * lp0 + wd;
        int u0 = qk * r59_floordiv(base0, qq) + qpar * lp0;
        /* Scale signed thresholds by multiplication: shifting a negative
         * u0 is undefined in C.  Every int times 2^66 fits in __int128. */
        int tfire = Mreg < (__int128)u0 * ((__int128)1 << 66);
        __int128 rtie = (__int128)(umag >> k) - (tfire ? 1 : 0);
        if (rtie <= 0)
            return 0;
        u256 tacc = { 0, 0 };
        acc_add_product(&tacc, 1, (u128)rtie, 1, rscale + k, rscale);
        *out = acc_round_bits_mode(tacc, rscale, 67, P5_ROUND_CHOP);
        if (g_dump_internals)
            fprintf(stderr,
                "DI_BR br=tie base0=%d u0=%d tfire=%d r=%016llx%016llx "
                "out=" DIWF "\n",
                base0, u0, tfire, DIU(rtie), DIW(*out));
        return 1;
    }
    /* h658 + h664b tap vectors (c0, cb1, cb2, clp, cd) per
     * (side_dn, th, quadrant).  (66,hi) and (67,lo) share every
     * vector (h658); (66,0) is the W1-window quadrant, closed by
     * h664b on comb11 (0 edge violations, all four groups at the
     * 3/4 interior ceiling; h662k interior law 0/229,326). */
    int c0, cb1, cb2, clp, cd;
    int q66lo = (s4 == 66 && side == 0);
    int q67hi = (s4 == 67 && side == 1);
    int qshared = !q66lo && !q67hi;    /* (66,hi) or (67,lo) */
    if (sign_dn && th == 1 && qshared) {
        c0 = 8; cb1 = 1; cb2 = -1; clp = 1; cd = -3;
    } else if (sign_dn && th == 1 && q66lo) {
        c0 = 1; cb1 = 1; cb2 = -1; clp = 1; cd = 0;
    } else if (sign_dn && th == 1) {
        c0 = 2; cb1 = 1; cb2 = 0; clp = 0; cd = 4;
    } else if (sign_dn && th == 2 && qshared) {
        c0 = 18; cb1 = 0; cb2 = 0; clp = 0; cd = -6;
    } else if (sign_dn && th == 2 && q66lo) {
        c0 = 12; cb1 = 0; cb2 = 0; clp = 0; cd = -3;
    } else if (sign_dn) {
        /* dn th=2 quadrant (67,1): never fires — 4 isolated
         * anomaly-family rows / 1,062,340 (comb7+comb8 1/528,775;
         * comb9 3/533,565, each a lone fire at a q-level shared by
         * thousands of clean rows).  Model clean. */
        /* R91 scope (h921-h923): the never-fire reading is
         * validated only at ce=-72 — every q67th2-branch row in
         * comb7-18 sits there (1.72M rows; comb7/11/12/14 have
         * none at all).  Outside ce=-72 the default terminal is
         * the better-derived object: falling through computes hw
         * on randv1 402b/FCOS/RU and 4016/FSIN/RN (the sum-0x102
         * act1 carries the never-fire return cannot express) and
         * is output-identical on c037 — the only three
         * q67-ce!=-72 rows in the whole 183M suite.  Flag-off
         * preserves the pre-R91 unconditional never-fire. */
        if (g_q67scope && ce != -72)
            return 0;
        __int128 rq = (__int128)(umag >> k);
        u256 qacc = { 0, 0 };
        acc_add_product(&qacc, 1, (u128)rq, 1, rscale + k, rscale);
        *out = acc_round_bits_mode(qacc, rscale, 67, P5_ROUND_CHOP);
        if (g_dump_internals)
            fprintf(stderr,
                "DI_BR br=q67th2 r=%016llx%016llx out=" DIWF "\n",
                DIU(rq), DIW(*out));
        return 1;
    } else if (th == 1 && qshared) {
        c0 = 6; cb1 = -1; cb2 = 0; clp = 1; cd = -1;
    } else if (th == 1 && q66lo) {
        c0 = 7; cb1 = -1; cb2 = 1; clp = 1; cd = -2;
    } else if (th == 1) {
        c0 = 6; cb1 = 1; cb2 = 0; clp = -2; cd = 0;
    } else if (th == 2 && qshared) {
        c0 = 6; cb1 = 0; cb2 = 0; clp = 1; cd = 0;
    } else if (th == 2 && q66lo) {
        c0 = 8; cb1 = 1; cb2 = 0; clp = 1; cd = -2;
    } else {
        c0 = 12; cb1 = 0; cb2 = 0; clp = 0; cd = 0;
    }
    int lp = (int)(low3 & 1);
    int base = qa * (int)low3 + qg1 * b1 + qg2 * b2 + qp * lp + wd;
    int tt = c0 + cb1 * b1 + cb2 * b2 + clp * lp
        + cd * (distance - 7);
    int uu;
    int in_region;
    if (sign_dn) {
        uu = qk * r59_floordiv(base - tt, qq) + qpar * lp;
        in_region = Mreg < (__int128)uu * ((__int128)1 << 66);
    } else {
        uu = qk * r59_floordiv(base + tt, qq) + qpar * lp;
        in_region = Mreg >= (__int128)uu * ((__int128)1 << 66);
    }
    int fire = 0;
    if (in_region) {
        /* h662b critical lattice + h662k block-start law */
        unsigned __int128 pmask =
            ~((unsigned __int128)S ^ (unsigned __int128)B);
        int pm = 0;
        int j = k;
        while (pm < 32 && ((pmask >> j) & 1)) {
            pm++;
            j++;
        }
        int phw = ((ce % 8) + 8) % 8;
        int crit = ((pm + phw) % 8 == 7) && (pm == 7 || pm == 8);
        /* Round 65: at ce=-74 (phw 6) the same block-start
         * criterion lands at pm=9 ((pm+phw)%8==7 unchanged), and
         * BOTH directions read the block-start bit alone —
         * 348/348 dn + 98/98 up exact on the comb13 ce=-74
         * stratum.  pm==9 can only satisfy the congruence at
         * phw==6, so the clause is unreachable at ce=-72/-73. */
        int crit9 = g_round65_ce74_band
            && ((pm + phw) % 8 == 7) && pm == 9;
        if (g_dump_internals)
            fprintf(stderr,
                "DI_CRIT at=band pm=%d phw=%d crit=%d crit9=%d\n",
                pm, phw, crit, crit9);
        if (!crit && !crit9) {
            fire = 1;
        } else {
            int bsrel = 8 + ((8 - phw) % 8);
            int bit8 = (int)((umag >> (k + 8)) & 1);
            int bitbs = (int)((umag >> (k + bsrel)) & 1);
            fire = crit9 ? bitbs
                : (sign_dn ? (bit8 & bitbs) : bitbs);
            if (g_dump_internals)
                fprintf(stderr,
                    "DI_BS bsrel=%d bit8=%d bitbs=%d fire=%d\n",
                    bsrel, bit8, bitbs, fire);
        }
    }
    /* R92 scope (h925-h926): at ce=-74 a band NO-FIRE defers to the
     * default terminal.  Census (the h922/h923 differential
     * universe: comb7-18 + randv1 + hostv1, all modes): the
     * (band, fire=0, ce=-74) stratum is populated by 16,176 comb14
     * rows + the comb13 ce=-74 stratum, and the r59 baseline and
     * the default terminal are VALUE-IDENTICAL on every one — the
     * only divergence in the whole 183M suite is randv1 c019/FCOS/RN
     * (its sum-0x102 act1 carry, which the fall-through computes
     * and the r59 baseline cannot).  Band fire=1 and tie rows at
     * ce=-74 diff heavily (2,880 + 2,116 comb14 operands) and stay
     * with the lattice.  Flag-off preserves pre-R92 behavior. */
    if (g_b74scope && ce == -74 && !fire)
        return 0;
    __int128 rdev = (__int128)(umag >> k)
        + (fire ? (sign_dn ? -1 : 1) : 0);
    if (rdev <= 0)
        return 0;
    u256 acc = { 0, 0 };
    acc_add_product(&acc, 1, (u128)rdev, 1, rscale + k, rscale);
    *out = acc_round_bits_mode(acc, rscale, 67, P5_ROUND_CHOP);
    if (g_dump_internals)
        fprintf(stderr,
            "DI_BR br=band in_region=%d fire=%d uu=%d tt=%d base=%d "
            "c=%d,%d,%d,%d,%d r=%016llx%016llx out=" DIWF "\n",
            in_region, fire, uu, tt, base, c0, cb1, cb2, clp, cd,
            DIU(rdev), DIW(*out));
    return 1;
}
/*
 * materialize the cosine terminal pair while
 * retaining the multiplier input's low-three-bit payload below the chopped
 * product.  Exponent alignment shifts the payload by one unit per position
 * relative to distance eight.  The ordinary trigger uses the upper three
 * discarded product bits; distance seven also exposes the upper five-bit
 * prefix.  At distance eight, an equal aligned lane and an upper-three-bit
 * prefix of at least three resolve one retained unit downward.  At the
 * distance-ten low-lane collision, the even product's upper discarded bit
 * resolves the retained borrow.  The following chop67 add consumes the
 * adjusted payload.
 */
static wv_t fcos_low3_terminal_correction(
    wv_t multiplier, wv_t left_factor, wv_t right_factor, wv_t fourth,
    wv_t magnitude, int cos_gate_eligible, int neg75, sf_rc_t rc)
{
#if G_TERMV
    /* EXPERIMENT (battery C): one-port truncation scoped to the
     * terminal's own inputs, one at a time. */
    switch (G_TERMV) {
    case 1: multiplier.sig   &= ~(u128)7; break;
    case 2: left_factor.sig  &= ~(u128)7; break;
    case 3: right_factor.sig &= ~(u128)7; break;
    case 4: fourth.sig       &= ~(u128)7; break;
    case 5: magnitude.sig    &= ~(u128)7; break;
    }
#endif
    if (g_perturb_tgt) {
        int d = g_perturb_delta;
        if (g_perturb_tgt == 1)
            left_factor.sig = (u128)((__int128)left_factor.sig + d);
        else if (g_perturb_tgt == 2)
            right_factor.sig = (u128)((__int128)right_factor.sig + d);
        else if (g_perturb_tgt == 3)
            multiplier.sig = (u128)((__int128)multiplier.sig + d);
        else if (g_perturb_tgt == 4)
            fourth.sig = (u128)((__int128)fourth.sig + d);
        else if (g_perturb_tgt == 5)
            magnitude.sig = (u128)((__int128)magnitude.sig + d);
        if (g_dump_internals)
            fprintf(stderr, "DI_PERT tgt=%d delta=%d\n",
                g_perturb_tgt, g_perturb_delta);
    }
    wv_t left = p5_wv_mul_round(
        multiplier, left_factor, 67, P5_ROUND_CHOP);
    wv_t right = p5_wv_mul_round(
        fourth, right_factor, 67, P5_ROUND_CHOP);
    if (g_perturb_tgt == 8)
        left.sig = (u128)((__int128)left.sig + g_perturb_delta);
    else if (g_perturb_tgt == 9)
        right.sig = (u128)((__int128)right.sig + g_perturb_delta);
    left = perturb_materialized_ulp(left, 27);
    right = perturb_materialized_ulp(right, 28);
    u256 product = u128_mul_full(multiplier.sig, left_factor.sig);
    int width = product.hi
        ? 128 + u128_width(product.hi)
        : u128_width(product.lo);
    int shift = width - 67;
    u128 discarded = (
        shift > 0
        ? product.lo & (((u128)1 << shift) - 1)
        : 0
    );
    unsigned upper_discarded = (
        shift > 0 ? (unsigned)((discarded << 3) >> shift) : 0
    );
    unsigned upper5_discarded = (
        shift > 0 ? (unsigned)((discarded << 5) >> shift) : 0
    );
    unsigned low3 = (unsigned)(multiplier.sig & 7);
    int distance = left.e2 - right.e2;
    if (distance < 0)
        distance = -distance;
    int active = low3 && (
        upper_discarded || (distance == 7 && upper5_discarded));
    int payload = active ? (int)low3 + 8 - distance : 0;
    if (g_perturb_tgt == 16)
        payload += g_perturb_delta;
#if G_R96RES2045 || G_R96PAIRR60
    int payload_pre_gate = payload;
#endif
    u256 right_product = u128_mul_full(fourth.sig, right_factor.sig);
    int right_width = right_product.hi
        ? 128 + u128_width(right_product.hi)
        : u128_width(right_product.lo);
    int right_shift = right_width - 67;
    u128 right_discarded = (
        right_shift > 0
        ? right_product.lo & (((u128)1 << right_shift) - 1)
        : 0
    );
    unsigned right_upper_discarded = (
        right_shift > 0
        ? (unsigned)((right_discarded << 1) >> right_shift)
        : 0
    );
    if (g_dump_internals || g_dump_r59_compact)
        fprintf(stderr,
            "DI_TC elig=%d active=%d low3=%u dist=%d rsh=%d "
            "payload=%d ud=%u u5d=%u rud=%u mul=" DIWF " lf=" DIWF
            " rf=" DIWF " f4=" DIWF " mag=" DIWF " left=" DIWF
            " right=" DIWF " rdisc=%016llx%016llx "
            "rh_mul=%d rh_lf=%d rh_rf=%d rh_f4=%d rh_left=%d rh_right=%d\n",
            cos_gate_eligible, active, low3, distance, right_shift,
            payload, upper_discarded, upper5_discarded,
            right_upper_discarded, DIW(multiplier), DIW(left_factor),
            DIW(right_factor), DIW(fourth), DIW(magnitude), DIW(left),
            DIW(right), DIU(right_discarded), multiplier.rh,
            left_factor.rh, right_factor.rh, fourth.rh,
            left.rh, right.rh);
    if (cos_gate_eligible && g_round59_fcos_theta_band && active
        && !G_R99BYPASS) {
        wv_t r59_out;
        if (r59_apply(multiplier, fourth, magnitude, left, right, right_factor,
                      payload, distance, low3, right_shift,
                      right_discarded, &r59_out)) {
            if (g_dump_internals)
                fprintf(stderr, "DI_CORR via=r59 out=" DIWF "\n",
                    DIW(r59_out));
            return r59_out;
        }
    }
    if (active && distance == 10 && low3 == 6 && right_upper_discarded) {
        int lane_shift = (left.e2 - 8) - right.e2;
        u128 lane = lane_shift >= 0
            ? right.sig >> lane_shift
            : right.sig << -lane_shift;
        int lane_payload = (int)(lane & 0xFF);
        int difference = (lane_payload - payload) & 0xFF;
        if (difference >= 128)
            difference -= 256;
        if (difference == -2)
            payload = lane_payload;
    }
    if (active && distance == 8 && low3 == 7 && upper_discarded >= 3) {
        int lane_shift = (left.e2 - 8) - right.e2;
        u128 lane = lane_shift >= 0
            ? right.sig >> lane_shift
            : right.sig << -lane_shift;
        int lane_payload = (int)(lane & 0xFF);
        int difference = (lane_payload - payload) & 0xFF;
        if (difference >= 128)
            difference -= 256;
        if (difference == 0)
            payload--;
    }
#if G_PAYOFF
    payload = 0;    /* decline the activation: no payload injection */
#endif
    int pay_declined = 0;
#if G_PAYGATE
    if (payload != 0 || active) {
        int dl_g = left.e2 - right.e2;
        if (dl_g < 0)
            dl_g = -dl_g;
        int deep_g = (dl_g >= 11) || (multiplier.e2 <= -74);
        int l0_g = (multiplier.e2 >= -71) || (dl_g <= 8);
        /* R90 candidate: the DEEP wall applies to the whole act1
         * correction stack — R75/R81 are suppressed in the deep
         * zone even when no payload exists to decline (h913/h914:
         * their deep arms corrupt ~47 labeled rows vs 2 wins). */
#if G_R93OVR
        /* R93: value-level clean-label overrides (h956b half-grid
         * relabel; h959 table).  An entry hit decides fire/decline
         * outright; no entry falls through to the R89/R90 logic. */
        int ovr_g = -1;
        if (dl_g >= 9 && dl_g <= 14) {
            u128 rlow93 = right.sig & ((((u128)1) << dl_g) - 1);
            u128 grl93 = (left.sign != right.sign)
                ? (rlow93 ? rlow93 : (((u128)1) << dl_g))
                : ((((u128)1) << dl_g) - rlow93);
            int g93 = grl93 > 64 ? 64 : (int)grl93;
            static const short r93_ovr[][5] = {
            {9,-73,3,3,0},
            {9,-73,4,4,0},
            {9,-72,5,4,1},
            {9,-72,6,5,1},
            {9,-72,7,6,1},
            {10,-74,1,1,1},
            {10,-74,1,2,1},
            {10,-74,1,3,1},
            {10,-74,1,4,1},
            {10,-74,1,5,1},
            {10,-74,2,1,1},
            {10,-74,2,2,1},
            {10,-74,2,3,1},
            {10,-74,2,4,1},
            {10,-74,2,5,1},
            {10,-74,3,2,1},
            {10,-74,3,3,1},
            {10,-74,3,4,1},
            {10,-74,3,5,1},
            {10,-74,4,4,1},
            {10,-74,4,5,1},
            {10,-73,1,-1,0},
            {10,-73,5,3,1},
            {10,-73,6,4,0},
            {10,-73,7,5,1},
            {10,-72,1,-1,0},
            {10,-72,11,5,0},
            {10,-72,12,5,0},
            {10,-72,64,2,1},
            {10,-72,64,5,1},
            {11,-75,1,1,1},
            {11,-75,1,4,1},
            {11,-75,2,1,1},
            {11,-75,2,2,1},
            {11,-75,2,4,1},
            {11,-75,3,2,1},
            {11,-75,4,4,1},
            {11,-74,1,0,1},
            {11,-74,1,1,1},
            {11,-74,1,2,1},
            {11,-74,1,3,1},
            {11,-74,1,4,1},
            {11,-74,2,0,1},
            {11,-74,2,1,1},
            {11,-74,2,2,1},
            {11,-74,2,3,1},
            {11,-74,2,4,1},
            {11,-74,3,0,1},
            {11,-74,3,1,1},
            {11,-74,3,2,1},
            {11,-74,3,3,1},
            {11,-74,3,4,1},
            {11,-74,4,2,1},
            {11,-74,4,4,1},
            {11,-74,5,2,1},
            {11,-74,5,3,1},
            {11,-74,5,4,1},
            {11,-74,6,4,1},
            {11,-74,7,3,1},
            {11,-74,7,4,1},
            {11,-73,1,0,1},
            {11,-73,1,1,1},
            {11,-73,1,2,1},
            {11,-73,1,3,1},
            {11,-73,1,4,1},
            {11,-73,2,0,1},
            {11,-73,2,1,1},
            {11,-73,2,2,1},
            {11,-73,2,3,1},
            {11,-73,2,4,1},
            {11,-73,3,0,1},
            {11,-73,3,1,1},
            {11,-73,3,2,1},
            {11,-73,3,3,1},
            {11,-73,3,4,1},
            {11,-73,4,1,1},
            {11,-73,4,2,1},
            {11,-73,4,3,1},
            {11,-73,4,4,1},
            {11,-73,5,1,1},
            {11,-73,5,2,1},
            {11,-73,5,3,1},
            {11,-73,5,4,1},
            {11,-73,6,1,1},
            {11,-73,6,2,1},
            {11,-73,6,3,1},
            {11,-73,6,4,1},
            {11,-73,7,2,1},
            {11,-73,7,3,1},
            {11,-73,7,4,1},
            {11,-73,8,2,1},
            {11,-73,8,3,1},
            {11,-73,8,4,1},
            {11,-73,9,3,1},
            {11,-73,9,4,1},
            {11,-73,10,4,1},
            {11,-73,11,4,1},
            {12,-76,3,2,1},
            {12,-75,1,0,1},
            {12,-75,1,2,1},
            {12,-75,2,0,1},
            {12,-75,3,0,1},
            {12,-75,3,2,1},
            {12,-75,4,2,1},
            {12,-75,4,3,1},
            {12,-75,5,1,1},
            {12,-75,6,2,1},
            {12,-75,6,3,1},
            {12,-75,7,2,1},
            {12,-75,7,3,1},
            {12,-74,1,0,1},
            {12,-74,1,2,1},
            {12,-74,1,3,1},
            {12,-74,2,0,1},
            {12,-74,2,1,1},
            {12,-74,2,2,1},
            {12,-74,2,3,1},
            {12,-74,3,2,1},
            {12,-74,3,3,1},
            {12,-74,4,2,1},
            {12,-74,4,3,1},
            {12,-74,5,1,1},
            {12,-74,5,2,1},
            {12,-74,5,3,1},
            {12,-74,6,1,1},
            {12,-74,6,2,1},
            {12,-74,6,3,1},
            {12,-74,7,2,1},
            {12,-74,7,3,1},
            {12,-74,8,1,1},
            {12,-74,8,2,1},
            {12,-74,8,3,1},
            {12,-74,9,3,1},
            {12,-74,10,3,1},
            {13,-76,4,1,1},
            {13,-76,6,1,1},
            {13,-75,1,1,1},
            {13,-75,2,0,1},
            {13,-75,4,2,1},
            {13,-75,6,1,1},
            {13,-75,7,2,1},
            {13,-75,11,2,1},
            {14,-76,3,0,1}
            };
            unsigned oi;
            for (oi = 0;
                 oi < sizeof(r93_ovr) / sizeof(r93_ovr[0]); oi++) {
                if (r93_ovr[oi][0] == dl_g
                    && r93_ovr[oi][1] == multiplier.e2
                    && r93_ovr[oi][2] == g93
                    && r93_ovr[oi][3] == payload) {
                    ovr_g = r93_ovr[oi][4];
                    break;
                }
            }
        }
        if (ovr_g == 0) {
            /* decline in the payoff-reference frame the h956b
             * labels were measured in: R75/R81 stay eligible
             * outside the deep zone (h947 S1: ~197 legs). */
            payload = 0;
            if (deep_g)
                pay_declined = 1;
        } else if (ovr_g == 1) {
            /* fire: keep the payload; R75/R81 stay eligible */
        } else
#endif
        if (payload == 0) {
            if (deep_g)
                pay_declined = 1;
        } else {
        int fire_g = 0;
        if (payload > 0 && l0_g) {
            fire_g = 1;
        } else if (payload > 0 && !deep_g && dl_g <= 40) {
            u128 rlow = right.sig & ((((u128)1) << dl_g) - 1);
            u128 grl_g = (left.sign != right.sign)
                ? (rlow ? rlow : (((u128)1) << dl_g))
                : ((((u128)1) << dl_g) - rlow);
            int g = grl_g > 64 ? 64 : (int)grl_g;
            int t = 9;                  /* 9 = never */
#if G_PAYGATE == 2
            int K = 4;
            if (dl_g == 10 && multiplier.e2 == -72)
                K = 8;
            if (g <= K || (dl_g == 9 && payload >= g))
                t = payload;            /* fire */
#else
            if (dl_g == 9 && multiplier.e2 == -73)
                t = g <= 4 ? 1 : 7;
            else if (dl_g == 9 && multiplier.e2 == -72)
                t = g <= 4 ? 1 : (g == 5 ? 5 : (g == 6 ? 6 : 7));
            else if (dl_g == 10 && multiplier.e2 == -73)
                t = g <= 4 ? 1 : (g <= 6 ? 4 : 6);
            else /* dl_g == 10, mule2 == -72 */
                t = g <= 8 ? 1 : (g == 9 ? 4 : (g <= 12 ? 5 : 6));
#endif
            fire_g = payload >= t;
        }
        if (!fire_g) {
            payload = 0;
            pay_declined = 1;
        }
        }
    }
#endif
    (void)pay_declined;
    if (g_dump_internals) {
        /* DI_TC2 (deeper-DI pass 1): post-adjustment payload + the
         * B-byte at the payload injection lane (left.e2 - 8) — the
         * lane exists for every row regardless of the micro-rules. */
        int lane_shift2 = (left.e2 - 8) - right.e2;
        u128 lane2 = lane_shift2 >= 0
            ? right.sig >> lane_shift2
            : right.sig << -lane_shift2;
        int lane_byte = (int)(lane2 & 0xFF);
        int diff2 = (lane_byte - payload) & 0xFF;
        if (diff2 >= 128)
            diff2 -= 256;
        int lane_shift3 = (left.e2 - 16) - right.e2;
        u128 lane3 = lane_shift3 >= 0
            ? right.sig >> lane_shift3
            : right.sig << -lane_shift3;
        int lane_shift4 = (left.e2 - 24) - right.e2;
        u128 lane4 = lane_shift4 >= 0
            ? right.sig >> lane_shift4
            : right.sig << -lane_shift4;
        fprintf(stderr,
            "DI_TC2 pay2=%d laneb=%02x diff=%d lane2=%02x lane3=%02x\n",
            payload, (unsigned)lane_byte, diff2,
            (unsigned)(lane3 & 0xFF), (unsigned)(lane4 & 0xFF));
    }
#if G_TAILS == 3
    /* one-width composition: left product retained to 67+G_LKEEP
     * bits, right at 67, no payload machinery — the candidate
     * datapath-width law subsuming payload/micro-rules/gates */
#ifndef G_LKEEP
#define G_LKEEP 8
#endif
    wv_t lwide = p5_wv_mul_round(
        multiplier, left_factor, 67 + G_LKEEP, P5_ROUND_CHOP);
    int32_t scale = lwide.e2 < right.e2 ? lwide.e2 : right.e2;
    u256 accumulator = { 0, 0 };
    acc_add_product(
        &accumulator, lwide.sign, lwide.sig, 1, lwide.e2, scale);
    acc_add_product(
        &accumulator, right.sign, right.sig, 1, right.e2, scale);
#elif G_TAILS == 2
    int32_t full_uL = multiplier.e2 + left_factor.e2;
    int32_t scale = full_uL < right.e2 ? full_uL : right.e2;
    if (payload && left.e2 - 8 < scale)
        scale = left.e2 - 8;
    u256 accumulator = { 0, 0 };
    acc_add_product(
        &accumulator, left.sign, multiplier.sig, left_factor.sig,
        full_uL, scale);
    acc_add_product(
        &accumulator, right.sign, right.sig, 1, right.e2, scale);
#elif G_TAILS
    int32_t full_uL = multiplier.e2 + left_factor.e2;
    int32_t full_uR = fourth.e2 + right_factor.e2;
    int32_t scale = full_uL < full_uR ? full_uL : full_uR;
    if (payload && left.e2 - 8 < scale)
        scale = left.e2 - 8;
    u256 accumulator = { 0, 0 };
    acc_add_product(
        &accumulator, left.sign, multiplier.sig, left_factor.sig,
        full_uL, scale);
    acc_add_product(
        &accumulator, right.sign, fourth.sig, right_factor.sig,
        full_uR, scale);
#else
    int32_t scale = left.e2 < right.e2 ? left.e2 : right.e2;
    if (payload && left.e2 - 8 < scale)
        scale = left.e2 - 8;
    u256 accumulator = { 0, 0 };
    acc_add_product(
        &accumulator, left.sign, left.sig, 1, left.e2, scale);
    acc_add_product(
        &accumulator, right.sign, right.sig, 1, right.e2, scale);
#endif
    if (payload) {
        acc_add_product(
            &accumulator,
            left.sign ^ (payload < 0),
            (u128)(payload < 0 ? -payload : payload),
            1,
            left.e2 - 8,
            scale);
    }
    if (g_debug_cosine_carrier)
        fprintf(stderr,
            "COS_CARRIER mul=%016llx%016llx lf=%016llx%016llx "
            "rf=%016llx%016llx f4=%016llx%016llx "
            "le2=%d ls=%016llx%016llx re2=%d rs=%016llx%016llx "
            "lsign=%u rsign=%u dist=%d low3=%u ud=%u u5d=%u rud=%u "
            "payload=%d active=%d disc_hi=%016llx rdisc_hi=%016llx\n",
            (unsigned long long)(multiplier.sig >> 64),
            (unsigned long long)multiplier.sig,
            (unsigned long long)(left_factor.sig >> 64),
            (unsigned long long)left_factor.sig,
            (unsigned long long)(right_factor.sig >> 64),
            (unsigned long long)right_factor.sig,
            (unsigned long long)(fourth.sig >> 64),
            (unsigned long long)fourth.sig,
            left.e2,
            (unsigned long long)(left.sig >> 64),
            (unsigned long long)left.sig,
            right.e2,
            (unsigned long long)(right.sig >> 64),
            (unsigned long long)right.sig,
            (unsigned)left.sign, (unsigned)right.sign,
            distance, low3, upper_discarded, upper5_discarded,
            right_upper_discarded, payload, active,
            (unsigned long long)(shift > 0 ? (uint64_t)(discarded >> (shift > 64 ? shift - 64 : 0)) : 0),
            (unsigned long long)(right_shift > 0 ? (uint64_t)(right_discarded >> (right_shift > 64 ? right_shift - 64 : 0)) : 0));
    wv_t tc_default = acc_round_bits_mode(
        accumulator, scale, 67, P5_ROUND_CHOP);
#if G_R95XSUP || G_R96FORCE || G_R96RES2045 || G_R96M12 || G_R96C11 \
    || G_R96TOPR60 || G_R96TOPPAIR || G_R96LOWR60 || G_R96PAIRR60 \
    || G_R96TOPCLOSED || G_R96ACTCLOSED
    wv_t tc_pre95 = tc_default;
#endif
    if (g_dump_internals) {
        /* DI_ACC (deeper-DI pass 1): the accumulator's full 60-bit
         * below-67 field — the R71/R73 window reads only its top 30;
         * the lower 30 have never been a column. */
        wv_t w60 = acc_round_bits_mode(
            accumulator, scale, 67 + 60, P5_ROUND_CHOP);
        u128 lo60 = w60.sig & ((((u128)1) << 60) - 1);
        fprintf(stderr, "DI_ACC d60=%016llx%016llx\n", DIU(lo60));
    }
    /* Round 70 (PROBATION): the default-path terminal is NOT pure
     * chop67 — the chip carries the retained lsb when the discarded
     * field's top G70 bits are all ones (h741/h742: fixes 100/122
     * default-stratum votes, 0/3604 clean-wall flips; the fitted
     * equivalence class is top-4-RN/top-5 — shipped as top-5 =
     * g=4 round-to-nearest on the guard field). */
    if (g_round72_staircase_carry) {
        wv_t wide = acc_round_bits_mode(
            accumulator, scale, 67 + G70_WIN, P5_ROUND_CHOP);
        u128 low = wide.sig & ((((u128)1) << G70_WIN) - 1);
        int run = 0;
        while (run < 30 && ((low >> (29 - run)) & 1))
            run++;
        if (!active
            && ((uint64_t)low3 << (run > 24 ? 24 : run)) > 128) {
            tc_default.sig += 1;
            if (tc_default.sig >> 67) {
                tc_default.sig >>= 1;
                tc_default.e2 += 1;
            }
        }
    } else if (g_round70_default_carry) {
        wv_t wide = acc_round_bits_mode(
            accumulator, scale, 67 + G70_WIN, P5_ROUND_CHOP);
        u128 low = wide.sig & ((((u128)1) << G70_WIN) - 1);
        /* Round 88 (PROMOTED 2026-08-26): the act0 default carry is
         * an ADDER, not a width — fire iff the window's top eight
         * bits plus the multiplier's low three bits overflow 0x100.
         * Subsumes the classic all-ones+low3!=0 rule, the R87
         * seven-bit gradient (0xFE needs low3>=2), and the ladder
         * (0xF9..0xFD with matching low3: +64 pool rows, THREE
         * ledger keys derived and deleted — randv1:2593581/rn,
         * 6363167/ru, 4615048/rn).  Suite: ZERO collateral in 183M
         * (h903 sweep); rv6 blind (locked a65895e, seed 0x8727,
         * epoch-probed 43/43): zero candidate-vs-incumbent
         * difference rows in 16M fresh results, neutral pass per
         * the R78 precedent.  CAVEAT (h905-h907, banked 2,457-row
         * atlas): this is the best APPROXIMATION, not the boundary
         * law — at synthetic tz-enriched fringe density the exact
         * boundary cells (sum in [0xFE,0x101]) misfire ~50/50 in
         * BOTH directions (40 over / 35 under per 1.02B enriched
         * results), like every other closed form tried; the
         * residual is proven h486-class (no readable function of
         * any pipeline intermediate).  Build -DG70_LEGACY_WIDTH=1
         * to A/B the pre-R88 guard-width read. */
#ifndef G70_LEGACY_WIDTH
#define G70_LEGACY_WIDTH 0
#endif
#if G70_LEGACY_WIDTH
        u128 top = low >> (G70_WIN - G70_GUARD);
        int fire71 = (top == ((((u128)1) << G70_GUARD) - 1) && !active
            && low3 != 0);
#else
        unsigned top8 = (unsigned)(low >> (G70_WIN - 8));
        int fire71 = (top8 + low3 >= 0x100) && !active;
#endif
        int fire73 = 0;
        if (g_round73_pm_gate && !active && !fire71) {
            int dl73 = left.e2 - right.e2;
            if (dl73 > 0 && dl73 <= 40) {
                u128 S73 = left.sig << dl73;
                u128 B73 = right.sig;
                if (S73 > B73) {
                    u128 um = S73 - B73;
                    int wk = u128_width(um) - 67;
                    if (wk > 0 && wk < 40) {
                        u128 dsc = um & ((((u128)1) << wk) - 1);
                        int thneg = dsc > (((u128)1) << (wk - 1));
                        if (thneg
                            && ((((u128)1) << wk) - dsc) <= 32) {
                            int at = (int)(
                                ((((u128)1) << wk) - dsc));
                            u128 pmask = ~(S73 ^ B73);
                            int pm = 0;
                            while (pm < 32
                                && ((pmask >> (wk + pm)) & 1))
                                pm++;
                            int phw = ((right.e2 + wk) % 8 + 8) % 8;
                            int bsrel = 8 + ((8 - phw) % 8);
                            int b8 = (int)((um >> (wk + 8)) & 1);
                            int bbs = (int)((um >> (wk + bsrel)) & 1);
                            int lsh79 = (left.e2 - 8) - right.e2;
                            int lb79 = (int)((lsh79 >= 0
                                ? (right.sig >> lsh79)
                                : (right.sig << -lsh79)) & 0xFF);
                            if (phw == 0 && b8 == 1 && bbs == 1)
                                fire73 = (pm >= 7 && at >= wk - 7
                                    && ((at == 1 && low3 >= 1)
                                        || (at == 2 && low3 >= 3)
                                        /* Round 74 cells (nk-pool
                                         * clean, 11F/0N): */
                                        || (g_round74_a1_ext
                                            && ((at == 3 && low3 >= 3)
                                                || (at == 4
                                                    && low3 >= 4)))
                                        /* Round 76 edge cells
                                         * (two robust cells only;
                                         * nk fold: 10F/53N): */
                                        || (g_round76_a1_edge
                                            && ((at == 5 && low3 >= 5
                                                    && wk >= 8
                                                    && pm <= 9)
                                                || (at == 6
                                                    && low3 >= 6
                                                    && wk >= 8)))
                                        /* Round 79 cells: */
                                        || (g_round79_cells
                                            && ((wk == 8
                                                    && lb79 > 3
                                                    && ((at == 5
                                                        && low3 == 7)))
                                                || (wk == 9
                                                    && lb79 <= 3
                                                    && at == 6
                                                    && low3 == 5)
                                                || (wk == 9
                                                    && lb79 > 3
                                                    && ((at == 8
                                                        && low3 >= 6)
                                                        || (at == 9
                                                        && low3 == 7)))))
                                        /* Round 77 lane-byte gate
                                         * (k==9 pooled cells): */
                                        || (g_round77_laneb_gate
                                            && wk == 9
                                            && ((int)((((left.e2 - 8)
                                                    - right.e2) >= 0
                                                ? (right.sig >>
                                                    ((left.e2 - 8)
                                                     - right.e2))
                                                : (right.sig <<
                                                    (right.e2
                                                     - (left.e2 - 8))))
                                                & 0xFF)) <= 3
                                            && ((at >= 3 && at <= 5
                                                    && low3 >= 3)
                                                || (at == 7
                                                    && low3 >= 6)))));
                            else if (phw == 0 && b8 == 0 && bbs == 0
                                && pm == 8)
                                fire73 = (wk == 7 && low3 >= 2
                                        && at <= 3)
                                    || (wk == 8 && low3 >= 4
                                        && at >= 2 && at <= 7);
                            else if (phw == 7 && b8 == 0 && bbs == 1)
                                fire73 = (pm == 8 && wk <= 9
                                    && at <= 4);
                            else if (phw == 6 && b8 == 1 && bbs == 1)
                                fire73 = (pm >= 12 && at <= 2);
                            else if (phw == 7 && b8 == 1 && bbs == 1)
                                fire73 = (pm >= 12 && low3 >= 4
                                    && at <= 4);
                        }
                    }
                }
            }
        }
        int fire75 = 0, delta75 = 0;
        if (g_round75_act1_gate && active && !pay_declined) {
            int dl75 = left.e2 - right.e2;
            if (dl75 > 8 && dl75 <= 40) {
                __int128 Ss = ((__int128)left.sig << dl75)
                    + (__int128)payload * ((__int128)1 << (dl75 - 8));
                __int128 Bs = (__int128)right.sig;
                if (Ss > Bs) {
                    u128 um = (u128)(Ss - Bs);
                    int wk = u128_width(um) - 67;
                    if (wk > 0 && wk < 40) {
                        u128 dsc = um & ((((u128)1) << wk) - 1);
                        int thpos = dsc <= (((u128)1) << (wk - 1));
                        u128 mag = thpos ? dsc
                            : ((((u128)1) << wk) - dsc);
                        if (mag <= 40) {
                            u128 pmask = ~(((u128)Ss) ^ ((u128)Bs));
                            int pm = 0;
                            while (pm < 40
                                && ((pmask >> (wk + pm)) & 1))
                                pm++;
                            /* Round 78 predicate (deeper-DI
                             * lane-byte box; supersedes the retired
                             * R75 shape): laneb<=4 and either
                             * diff==-3 & pm>=10, or diff==0 &
                             * pay2==0 & pm>=9. */
                            int lsh78 = (left.e2 - 8) - right.e2;
                            int laneb78 = (int)((lsh78 >= 0
                                ? (right.sig >> lsh78)
                                : (right.sig << -lsh78)) & 0xFF);
                            int diff78 = (laneb78 - payload) & 0xFF;
                            if (diff78 >= 128)
                                diff78 -= 256;
                            if (laneb78 <= 4) {
                                if (diff78 == -3 && pm >= 10)
                                    fire75 = 1;
                                else if (diff78 == 0 && payload == 0
                                    && pm >= 9)
                                    fire75 = 1;
                                /* Round 83 structural cells
                                 * (h899: 299F/0N at the >=50F
                                 * bar): */
                                else if (g_round83_rncells
                                    && pm >= 9 && thpos
                                    && ((int)((um >> (wk + 8)) & 1))
                                        == 0
                                    && (diff78 == -1
                                        || (diff78 == -3
                                            && pm == 9)))
                                    fire75 = 1;
                            }
                            if (fire75)
                                delta75 = ((neg75 == 1) ^ thpos)
                                    ? 1 : -1;
                        }
                    }
                }
            }
        }
#if G_CORRB == 5
        fire71 = fire73 = fire75 = 0;   /* probe B5: gates off */
        delta75 = 0;
#endif
        if (fire71 || fire73) {
            tc_default.sig += 1;
            if (tc_default.sig >> 67) {
                tc_default.sig >>= 1;
                tc_default.e2 += 1;
            }
        } else if (fire75) {
            if (delta75 > 0) {
                tc_default.sig += 1;
                if (tc_default.sig >> 67) {
                    tc_default.sig >>= 1;
                    tc_default.e2 += 1;
                }
            } else {
                tc_default.sig -= 1;
                if (!(tc_default.sig >> 66)) {
                    tc_default.sig <<= 1;
                    tc_default.e2 -= 1;
                }
            }
        }
    }
    if (g_round81_corr_rn64 && active && !pay_declined) {
        int lsh81 = (left.e2 - 8) - right.e2;
        int lb81 = (int)((lsh81 >= 0
            ? (right.sig >> lsh81)
            : (right.sig << -lsh81)) & 0xFF);
        int df81 = (lb81 - payload) & 0xFF;
        if (df81 >= 128)
            df81 -= 256;
        int top81 = tc_default.e2 + 66;
        int rem81 = (int)(tc_default.sig & 7);
        if (g_dump_internals) {
            int dlx = left.e2 - right.e2;
            int wkx = -1, pmx = -1, phwx = -1, b8x = -1, bbsx = -1;
            int thx = -1; long long atx = -1;
            if (dlx > 0 && dlx <= 40 && left.sig != 0) {
                u128 Sx = left.sig << dlx;
                u128 Bx = right.sig;
                if (Sx > Bx) {
                    u128 umx = Sx - Bx;
                    wkx = u128_width(umx) - 67;
                    if (wkx > 0 && wkx < 40) {
                        u128 dscx = umx
                            & ((((u128)1) << wkx) - 1);
                        u128 upx = (((u128)1) << wkx) - dscx;
                        thx = dscx > (((u128)1) << (wkx - 1));
                        atx = (long long)(thx ? upx : dscx);
                        u128 pmaskx = ~(Sx ^ Bx);
                        pmx = 0;
                        while (pmx < 32
                            && ((pmaskx >> (wkx + pmx)) & 1))
                            pmx++;
                        phwx = ((right.e2 + wkx) % 8 + 8) % 8;
                        int bsrelx = 8 + ((8 - phwx) % 8);
                        b8x = (int)((umx >> (wkx + 8)) & 1);
                        bbsx = (int)((umx >> (wkx + bsrelx)) & 1);
                    }
                }
            }
            fprintf(stderr,
                "DI_B81 act=%d pay=%d low3=%d neg=%d lb=%d df=%d "
                "top=%d rem=%d dspan=%d wk=%d pm=%d phw=%d th=%d "
                "at=%lld b8=%d bbs=%d L=" DIWF " R=" DIWF
                " tc=" DIWF "\n",
                active, payload, low3, neg75, lb81, df81,
                top81, rem81, left.e2 - right.e2,
                wkx, pmx, phwx, thx, atx, b8x, bbsx,
                DIW(left), DIW(right), DIW(tc_default));
        }
        int span6fire = (top81 == -6 && df81 == -3
            && rem81 == (neg75 ? 7 : 1)
            && low3 == lb81 + 4);
        int b81gate = (lb81 <= 4 && df81 >= -3 && df81 <= 0
                       && top81 <= -10)
            || (g_round82_span6 && span6fire);
#if G_CORRB && G_CORRB != 7
        b81gate = 1;    /* probe B: unconditional narrowing */
#endif
#if G_CORRB == 7
        /* Round 87 CANDIDATE (fitted, 2026-08-25): the narrowing
         * gate as an exact decision surface over the absolute
         * boundary frame — fitted on the COMPLETE sensitive space
         * (3,905 pool fires + 19,752 suite negatives, 0FP/0FN;
         * zero exact-vector contradictions).  FITTED, not derived:
         * documented per the R57 precedent; rv4 blind decides. */
        {
            long long g87_at = -1;
            int g87_th = -1, g87_pm = -1, g87_phw = -1;
            long long g87_uint = -999;
            int g87_rlz = 0, g87_fire = 0;
            int g87_dl = left.e2 - right.e2;
            if (g87_dl > 0 && g87_dl <= 40 && left.sig != 0) {
                u128 g87_S = left.sig << g87_dl;
                u128 g87_B = right.sig;
                if (g87_S > g87_B) {
                    u128 g87_um = g87_S - g87_B;
                    int g87_wk = u128_width(g87_um) - 67;
                    if (g87_wk > 0 && g87_wk < 40) {
                        u128 dsc = g87_um & ((((u128)1) << g87_wk) - 1);
                        u128 up = (((u128)1) << g87_wk) - dsc;
                        g87_th = dsc > (((u128)1) << (g87_wk - 1));
                        g87_at = (long long)(g87_th ? up : dsc);
                        u128 pmask = ~(g87_S ^ g87_B);
                        g87_pm = 0;
                        while (g87_pm < 32
                            && ((pmask >> (g87_wk + g87_pm)) & 1))
                            g87_pm++;
                        g87_phw = ((right.e2 + g87_wk) % 8 + 8) % 8;
                        if (g87_wk >= 8) {
                            u128 rl = right.sig
                                & ((((u128)1) << g87_wk) - 1);
                            __int128 dm = (__int128)rl
                                - (__int128)payload
                                  * ((__int128)1 << (g87_wk - 8));
                            g87_uint = (long long)(dm >> (g87_wk - 8));
                            g87_rlz = (rl & ((((u128)1) << (g87_wk - 8))
                                             - 1)) == 0;
                        }
                    }
                }
            }
        if (g87_at < 18) {
            if (g87_phw < 1) {
                if (g87_pm < 10) {
                    if (payload < 1) {
                        if (g87_at < 4) {
                            if (rem81 < 7) {
                                g87_fire = 0;
                            } else {
                                g87_fire = 1;
                            }
                        } else {
                            g87_fire = 0;
                        }
                    } else {
                        if (g87_at < 17) {
                            if (payload < 3) {
                                if (g87_pm < 2) {
                                    g87_fire = 0;
                                } else {
                                    if (g87_uint < 2) {
                                        if (g87_at < 9) {
                                            if (neg75 < 1) {
                                                g87_fire = 0;
                                            } else {
                                                g87_fire = 1;
                                            }
                                        } else {
                                            g87_fire = 0;
                                        }
                                    } else {
                                        g87_fire = 0;
                                    }
                                }
                            } else {
                                g87_fire = 0;
                            }
                        } else {
                            if (g87_pm < 2) {
                                g87_fire = 0;
                            } else {
                                if (g87_th < 1) {
                                    if (neg75 < 1) {
                                        if (rem81 < 7) {
                                            if (payload < 5) {
                                                g87_fire = 1;
                                            } else {
                                                g87_fire = 0;
                                            }
                                        } else {
                                            g87_fire = 0;
                                        }
                                    } else {
                                        g87_fire = 0;
                                    }
                                } else {
                                    g87_fire = 0;
                                }
                            }
                        }
                    }
                } else {
                    if (g87_at < 8) {
                        if (g87_uint < -3) {
                            g87_fire = 0;
                        } else {
                            if (g87_uint < 2) {
                                g87_fire = 1;
                            } else {
                                g87_fire = 0;
                            }
                        }
                    } else {
                        g87_fire = 0;
                    }
                }
            } else {
                if (g87_uint < 2) {
                    if (g87_uint < -4) {
                        g87_fire = 0;
                    } else {
                        if (rem81 < 2) {
                            if (g87_at < 5) {
                                if (g87_uint < -3) {
                                    g87_fire = 0;
                                } else {
                                    if (payload < 6) {
                                        if (g87_pm < 9) {
                                            if (g87_at < 3) {
                                                g87_fire = 0;
                                            } else {
                                                if (g87_phw < 7) {
                                                    g87_fire = 1;
                                                } else {
                                                    g87_fire = 0;
                                                }
                                            }
                                        } else {
                                            g87_fire = 1;
                                        }
                                    } else {
                                        g87_fire = 0;
                                    }
                                }
                            } else {
                                if (g87_uint < 0) {
                                    g87_fire = 1;
                                } else {
                                    if (g87_pm < 1) {
                                        g87_fire = 1;
                                    } else {
                                        g87_fire = 0;
                                    }
                                }
                            }
                        } else {
                            if (g87_pm < 8) {
                                g87_fire = 0;
                            } else {
                                if (g87_at < 11) {
                                    g87_fire = 1;
                                } else {
                                    if (g87_phw < 7) {
                                        g87_fire = 0;
                                    } else {
                                        g87_fire = 1;
                                    }
                                }
                            }
                        }
                    }
                } else {
                    if (payload < 0) {
                        if (rem81 < 7) {
                            g87_fire = 0;
                        } else {
                            if (g87_th < 1) {
                                g87_fire = 1;
                            } else {
                                if (g87_phw < 7) {
                                    g87_fire = 1;
                                } else {
                                    g87_fire = 0;
                                }
                            }
                        }
                    } else {
                        if (g87_uint < 3) {
                            if (rem81 < 2) {
                                if (g87_phw < 7) {
                                    g87_fire = 1;
                                } else {
                                    g87_fire = 0;
                                }
                            } else {
                                g87_fire = 0;
                            }
                        } else {
                            if (g87_uint < 4) {
                                if (g87_at < 17) {
                                    g87_fire = 0;
                                } else {
                                    if (g87_phw < 7) {
                                        g87_fire = 1;
                                    } else {
                                        g87_fire = 0;
                                    }
                                }
                            } else {
                                g87_fire = 0;
                            }
                        }
                    }
                }
            }
        } else {
            if (g87_uint < 256) {
                if (g87_uint < 3) {
                    if (g87_phw < 5) {
                        if (payload < 7) {
                            g87_fire = 0;
                        } else {
                            if (g87_pm < 2) {
                                g87_fire = 0;
                            } else {
                                if (rem81 < 7) {
                                    if (g87_at < 30) {
                                        g87_fire = 0;
                                    } else {
                                        if (g87_at < 31) {
                                            g87_fire = 1;
                                        } else {
                                            if (g87_at < 33) {
                                                if (g87_th < 1) {
                                                    if (payload < 8) {
                                                        g87_fire = 1;
                                                    } else {
                                                        g87_fire = 0;
                                                    }
                                                } else {
                                                    g87_fire = 0;
                                                }
                                            } else {
                                                if (g87_at < 54) {
                                                    g87_fire = 0;
                                                } else {
                                                    if (g87_at < 55) {
                                                        if (g87_th < 1) {
                                                            g87_fire = 1;
                                                        } else {
                                                            g87_fire = 0;
                                                        }
                                                    } else {
                                                        g87_fire = 0;
                                                    }
                                                }
                                            }
                                        }
                                    }
                                } else {
                                    g87_fire = 0;
                                }
                            }
                        }
                    } else {
                        if (rem81 < 2) {
                            if (g87_phw < 7) {
                                g87_fire = 1;
                            } else {
                                g87_fire = 0;
                            }
                        } else {
                            g87_fire = 0;
                        }
                    }
                } else {
                    if (rem81 < 5) {
                        if (payload < 7) {
                            if (g87_at < 20) {
                                if (payload < 5) {
                                    g87_fire = 0;
                                } else {
                                    if (rem81 < 3) {
                                        g87_fire = 0;
                                    } else {
                                        if (g87_at < 19) {
                                            g87_fire = 0;
                                        } else {
                                            g87_fire = 1;
                                        }
                                    }
                                }
                            } else {
                                if (g87_at < 92) {
                                    if (g87_at < 91) {
                                        if (payload < 5) {
                                            if (payload < 4) {
                                                if (g87_at < 76) {
                                                    g87_fire = 0;
                                                } else {
                                                    if (g87_at < 77) {
                                                        if (g87_uint < 75) {
                                                            if (g87_uint < 74) {
                                                                g87_fire = 0;
                                                            } else {
                                                                if (g87_phw < 7) {
                                                                    if (rem81 < 2) {
                                                                        g87_fire = 1;
                                                                    } else {
                                                                        g87_fire = 0;
                                                                    }
                                                                } else {
                                                                    g87_fire = 0;
                                                                }
                                                            }
                                                        } else {
                                                            g87_fire = 0;
                                                        }
                                                    } else {
                                                        if (g87_phw < 7) {
                                                            g87_fire = 0;
                                                        } else {
                                                            if (rem81 < 2) {
                                                                if (g87_at < 85) {
                                                                    g87_fire = 0;
                                                                } else {
                                                                    if (g87_at < 86) {
                                                                        g87_fire = 1;
                                                                    } else {
                                                                        g87_fire = 0;
                                                                    }
                                                                }
                                                            } else {
                                                                g87_fire = 0;
                                                            }
                                                        }
                                                    }
                                                }
                                            } else {
                                                if (g87_at < 40) {
                                                    if (g87_at < 39) {
                                                        if (g87_uint < 26) {
                                                            if (g87_uint < 23) {
                                                                g87_fire = 0;
                                                            } else {
                                                                if (neg75 < 1) {
                                                                    g87_fire = 0;
                                                                } else {
                                                                    g87_fire = 1;
                                                                }
                                                            }
                                                        } else {
                                                            g87_fire = 0;
                                                        }
                                                    } else {
                                                        if (g87_pm < 1) {
                                                            g87_fire = 1;
                                                        } else {
                                                            if (neg75 < 1) {
                                                                g87_fire = 0;
                                                            } else {
                                                                if (g87_phw < 7) {
                                                                    if (rem81 < 3) {
                                                                        g87_fire = 1;
                                                                    } else {
                                                                        g87_fire = 0;
                                                                    }
                                                                } else {
                                                                    g87_fire = 0;
                                                                }
                                                            }
                                                        }
                                                    }
                                                } else {
                                                    if (g87_pm < 1) {
                                                        if (g87_uint < 189) {
                                                            g87_fire = 0;
                                                        } else {
                                                            if (g87_uint < 191) {
                                                                g87_fire = 1;
                                                            } else {
                                                                g87_fire = 0;
                                                            }
                                                        }
                                                    } else {
                                                        g87_fire = 0;
                                                    }
                                                }
                                            }
                                        } else {
                                            g87_fire = 0;
                                        }
                                    } else {
                                        if (g87_uint < 207) {
                                            g87_fire = 0;
                                        } else {
                                            if (g87_uint < 208) {
                                                g87_fire = 1;
                                            } else {
                                                g87_fire = 0;
                                            }
                                        }
                                    }
                                } else {
                                    if (g87_phw < 1) {
                                        if (g87_uint < 123) {
                                            if (g87_uint < 122) {
                                                if (g87_at < 217) {
                                                    g87_fire = 0;
                                                } else {
                                                    if (g87_at < 218) {
                                                        if (neg75 < 1) {
                                                            g87_fire = 0;
                                                        } else {
                                                            g87_fire = 1;
                                                        }
                                                    } else {
                                                        g87_fire = 0;
                                                    }
                                                }
                                            } else {
                                                if (g87_at < 127) {
                                                    if (g87_at < 126) {
                                                        g87_fire = 0;
                                                    } else {
                                                        g87_fire = 1;
                                                    }
                                                } else {
                                                    g87_fire = 0;
                                                }
                                            }
                                        } else {
                                            g87_fire = 0;
                                        }
                                    } else {
                                        g87_fire = 0;
                                    }
                                }
                            }
                        } else {
                            if (g87_at < 85) {
                                g87_fire = 0;
                            } else {
                                if (g87_at < 86) {
                                    g87_fire = 1;
                                } else {
                                    if (g87_pm < 1) {
                                        if (g87_at < 111) {
                                            if (g87_at < 110) {
                                                if (neg75 < 1) {
                                                    g87_fire = 0;
                                                } else {
                                                    if (g87_at < 99) {
                                                        g87_fire = 0;
                                                    } else {
                                                        if (g87_uint < 150) {
                                                            g87_fire = 0;
                                                        } else {
                                                            g87_fire = 1;
                                                        }
                                                    }
                                                }
                                            } else {
                                                g87_fire = 1;
                                            }
                                        } else {
                                            g87_fire = 0;
                                        }
                                    } else {
                                        g87_fire = 0;
                                    }
                                }
                            }
                        }
                    } else {
                        g87_fire = 0;
                    }
                }
            } else {
                if (rem81 < 7) {
                    g87_fire = 0;
                } else {
                    g87_fire = 1;
                }
            }
        }
            b81gate = b81gate || g87_fire;   /* tree EXTENDS the
                                              * shipped R81 slice */
        }
#endif

        if (b81gate) {
            u128 base = tc_default.sig >> 3;
            unsigned rem = (unsigned)(tc_default.sig & 7);
            int b81round = 0, b81apply = 0;
#if G_CORRB == 2
            b81apply = 1;                       /* ties to even */
            b81round = rem > 4 || (rem == 4 && (base & 1));
#elif G_CORRB == 3
            b81apply = 1;                       /* ties away */
            b81round = rem >= 4;
#else
            if (rem != 4) {           /* ties: chip does NOT narrow
                                       * (rb1 boundary negative;
                                       * 0/197 fires are ties). */
                b81apply = 1;
                b81round = rem > 4;
            }
#endif
            if (b81apply) {
                if (b81round)
                    base += 1;
                tc_default.sig = base << 3;
                if (tc_default.sig >> 67) {
                    tc_default.sig >>= 1;
                    tc_default.e2 += 1;
                }
            }
        }
    }
#if G_R95XSUP
    /* Round 95: the exact-support gate, ACT1 FIRED PATH ONLY.
     * When a fitted post-chop adjustment (fire75/R81 narrow) on
     * the payload-fired path contradicts the EXACT terminal
     * composition's chop67, the hardware follows the exact chop
     * (h988/h989 fresh-silicon value gate over the 5.09M-op scope
     * corpus + the 8,315-op h968 census: 1,259 fixes / ZERO
     * breaks / 59 unfixed with the carves below; act0's fitted
     * carry/borrow rules and the declined path are hardware-
     * verified and never touched).
     * Carves (fitted kept): five mag-down low-ladder strata
     * (h975 census breaks) and the mag-up d12/me2-75/g7 deep-
     * fringe cell. */
    if ((tc_default.sig != tc_pre95.sig
         || tc_default.e2 != tc_pre95.e2)
        && active && payload != 0 && !pay_declined) {
        int32_t fu_l95 = multiplier.e2 + left_factor.e2;
        int32_t fu_r95 = fourth.e2 + right_factor.e2;
        int32_t sc95 = fu_l95 < fu_r95 ? fu_l95 : fu_r95;
        if (left.e2 - 8 < sc95)
            sc95 = left.e2 - 8;
        u256 af95 = { 0, 0 };
        acc_add_product(&af95, left.sign, multiplier.sig,
                        left_factor.sig, fu_l95, sc95);
        acc_add_product(&af95, right.sign, fourth.sig,
                        right_factor.sig, fu_r95, sc95);
        acc_add_product(&af95, left.sign ^ (payload < 0),
                        (u128)(payload < 0 ? -payload : payload),
                        1, left.e2 - 8, sc95);
        wv_t tful95 = acc_round_bits_mode(af95, sc95, 67,
                                          P5_ROUND_CHOP);
        if (tful95.sig != tc_default.sig
            || tful95.e2 != tc_default.e2
            || tful95.sign != tc_default.sign) {
            int magdown95 = (tc_default.e2 < tc_pre95.e2)
                || (tc_default.e2 == tc_pre95.e2
                    && tc_default.sig < tc_pre95.sig);
            wv_t w95 = acc_round_bits_mode(
                accumulator, scale, 67 + 8, P5_ROUND_CHOP);
            int sum95 = (int)(w95.sig & 0xFF) + (int)low3;
            u128 rlow95 = right.sig
                & ((((u128)1) << distance) - 1);
            u128 grl95 = (left.sign != right.sign)
                ? (rlow95 ? rlow95 : (((u128)1) << distance))
                : ((((u128)1) << distance) - rlow95);
            int g95 = grl95 > 64 ? 64 : (int)grl95;
            int keep95 = 0;
            if (distance == 12 && multiplier.e2 == -75
                && g95 == 7) {
                /* deep-fringe g7 cell, SIDE-AGNOSTIC (h988/h989:
                 * the magdown mirror held the only 3 breaks and
                 * zero fixes -> widened; zero collateral on all
                 * 8,518 hw-verified union ops). */
                keep95 = 1;
            } else if (magdown95) {
                if ((sum95 == 9 && distance == 9
                     && multiplier.e2 == -72 && g95 == 7)
                    || (sum95 == 9 && distance == 9
                        && multiplier.e2 == -73 && g95 == 4)
                    || (sum95 == 10 && distance == 9
                        && multiplier.e2 == -72 && g95 == 6)
                    || (sum95 == 5 && distance == 12
                        && multiplier.e2 == -75 && g95 == 5)
                    || (sum95 == 7 && distance == 10
                        && multiplier.e2 == -74 && g95 == 3))
                    keep95 = 1;
            }
            if (!keep95)
                tc_default = tc_pre95;
        }
    }
#endif
#if G_R96TOPCLOSED
    /* h1030-h1038: the residual upper-inactive +/-1 is a carry-selector
     * substitution, not another carry magnitude.  The exact subtractor
     * has carry-in zero at the retained cut; silicon substitutes P[cut]=1
     * only inside an R60-coordinate envelope and when five consecutive
     * propagate columns run downward from the cut.  The independent h1000
     * response arm lives at retained byte 0xff and adds the radix-aligned
     * negative-phase displacement 3/32.  Joint score before blind capture:
     * h975 157/157 targets and 926/926 impossible rows; h1000 12/12 FIX
     * and 0/88 BREAK.
     */
    {
        wv_t w96 = acc_round_bits_mode(
            accumulator, scale, 67 + 8, P5_ROUND_CHOP);
        int sum96 = (int)(w96.sig & 0xFF) + (int)low3;
        int dl96 = left.e2 - right.e2;
        if (!active && sum96 >= 0xF0 && dl96 > 0 && dl96 < 61
            && left.sign == 1 && right.sign == 0) {
            u128 s96 = left.sig << dl96;
            u128 b96 = right.sig;
            if (s96 > b96) {
                u128 mag96 = s96 - b96;
                int cut96 = u128_width(mag96) - 67;
                if (cut96 >= 4) {
                    u128 prop96 = ~(s96 ^ b96);
                    int pdown96 = 0;
                    while (pdown96 <= cut96 && pdown96 < 32
                           && ((prop96 >> (cut96 - pdown96)) & 1))
                        pdown96++;
                    int pcut96 = (int)((prop96 >> cut96) & 1);
                    int retained96 = (int)((mag96 >> cut96) & 0xFF);
                    u128 residue96 = mag96
                        & ((((u128)1) << cut96) - 1);
                    int qpost1196 = (int)(
                        residue_q66(residue96, cut96) >> 55);
                    int edge96 = qpost1196 + 8 * (int)low3
                        >= 2024 + 8 * (distance - 7);

                    u256 f4full96 = u128_mul_full(
                        multiplier.sig, multiplier.sig);
                    int f4width96 = f4full96.hi
                        ? 128 + u128_width(f4full96.hi)
                        : u128_width(f4full96.lo);
                    int s4_96 = f4width96 - 67;
                    u128 t4_96 = s4_96 > 0 && s4_96 < 128
                        ? f4full96.lo & ((((u128)1) << s4_96) - 1)
                        : f4full96.lo;
                    int side96 = (uint64_t)magnitude.sig
                        >= 0xB504F333F9DE6800ULL;
                    __int128 sqlow96 = (__int128)multiplier.sig
                        - ((__int128)1 << 66);
                    __int128 mreg96 = (__int128)low3 * sqlow96
                        - (__int128)t4_96;

                    int mexp96 = right_shift - 16 - (side96 == 0);
                    int b1_96 = 0, b2_96 = 0;
                    if (mexp96 > 0 && mexp96 < 127) {
                        u128 mask96 = (((u128)1) << mexp96) - 1;
                        u128 rd3_96 = 3 * right_discarded
                            - ((2 * right_discarded) & mask96)
                            - (right_discarded & mask96);
                        b1_96 = rd3_96 >= ((u128)1 << right_shift);
                        b2_96 = rd3_96
                            >= ((u128)1 << (right_shift + 1));
                    }

                    int use96 = 0, tt96 = 0;
                    int lp96 = (int)(low3 & 1);
                    int dd96 = distance - 7;
                    int theta96 = 256 - sum96;
                    int ff96 = retained96 == 0xFF;
                    if (side96 && s4_96 == 67) {
                        if (ff96) {
                            /* h1039-h1041 union closure for the independent
                             * retained-byte-ff arm.  After the five-column
                             * propagate qualification, the digit ladder is
                             * deterministic except for four boundary cells.
                             * Those cells are monotone in the exact combined
                             * coordinate X=M-5*Q(right product); rf bit 43
                             * chooses the two L=7,d=7,b=0 orientations. */
                            u128 qright96 = right_shift > 0
                                ? residue_q66(right_discarded, right_shift) : 0;
                            __int128 xff96 = mreg96
                                - 5 * (__int128)qright96;
                            __int128 oneff96 = (__int128)1 << 66;
                            int rf43_96 = (int)((right_factor.sig >> 43) & 1);
                            int ffok96 = 0;
                            if (distance == 8 && low3 >= 1 && low3 <= 7) {
                                ffok96 = 1;
                                if (low3 == 6)
                                    ffok96 = pdown96 >= 6;
                                else if (low3 == 4 && b1_96 && !b2_96)
                                    ffok96 = xff96 < 0;
                                else if (low3 == 5 && !b1_96)
                                    ffok96 = xff96 >= oneff96;
                            } else if (distance == 7) {
                                if (low3 == 1)
                                    ffok96 = 1;
                                else if (low3 == 2 || low3 == 5)
                                    ffok96 = !b1_96;
                                else if (low3 == 6)
                                    ffok96 = !b2_96;
                                else if (low3 == 7) {
                                    if (b1_96 && !b2_96) {
                                        ffok96 = 1;
                                    } else if (!b1_96) {
                                        ffok96 = rf43_96
                                            ? xff96 >= 4 * oneff96
                                            : 4 * xff96 < 19 * oneff96;
                                    }
                                }
                            }
                            if (ffok96) {
                                tt96 = 3 - b1_96 + 3 * dd96;
                                use96 = 1;
                            }
                        } else if (sum96 == 255) {
                            tt96 = 3 - b1_96 + 3 * dd96;
                            use96 = 1;
                        } else if (sum96 == 254) {
                            tt96 = (int)low3 + 4 * b1_96 + 4 * dd96;
                            use96 = 1;
                        } else if (sum96 == 253) {
                            tt96 = (int)low3 + 6 * lp96;
                            use96 = 1;
                        }
                    } else if (side96 && s4_96 == 66) {
                        if (ff96) {
                            /* The q66 ff arm repeats the census's two-cell
                             * R60 geometry.  Its L=3 phase moves the tap from
                             * +1 to -3; every other populated cell is clean. */
                            if ((distance == 8 || distance == 9)
                                && low3 == 1 && !b1_96) {
                                tt96 = 3 + 5 * (distance - 8);
                                use96 = 1;
                            } else if (distance == 9 && low3 == 3
                                       && b1_96 && !b2_96) {
                                tt96 = -3;
                                use96 = 1;
                            }
                        } else if (sum96 == 255) {
                            if ((distance == 8 || distance == 9)
                                && low3 == 1 && !b1_96) {
                                tt96 = 3 + 5 * (distance - 8);
                                use96 = 1;
                            } else if (distance == 9 && low3 == 3
                                       && b1_96 && !b2_96) {
                                tt96 = 1;
                                use96 = 1;
                            }
                        }
                    }

                    int fire96 = 0, down96 = 0, uu96 = 0;
                    if (use96 && low3 >= 1
                        && (pcut96 || G_R96TOPALLP)
                        && pdown96 >= 5 && edge96) {
                        int qa96, qg1_96, qg2_96, qp96;
                        int qq96, qk96, qpar96, wd96;
                        if (s4_96 == 66) {
                            qa96 = 2; qg1_96 = 2; qg2_96 = 1;
                            qp96 = 0; qq96 = 4; qk96 = 1; qpar96 = 0;
                            wd96 = -5 * (distance - 7);
                        } else {
                            qa96 = 2; qg1_96 = 2; qg2_96 = 3;
                            qp96 = -3; qq96 = 8; qk96 = 2; qpar96 = 1;
                            wd96 = -4 - 2 * (distance - 7);
                        }
                        int base96 = qa96 * (int)low3
                            + qg1_96 * b1_96 + qg2_96 * b2_96
                            + qp96 * lp96 + wd96;
                        uu96 = qk96 * r59_floordiv(base96 + tt96, qq96)
                            + qpar96 * lp96;
                        __int128 one96 = (__int128)1 << 66;
                        __int128 lhs96 = 32 * mreg96;
                        if (ff96 && theta96 < 0)
                            lhs96 += 3 * (__int128)theta96 * one96;
                        __int128 rhs96 = 32 * (__int128)uu96 * one96;
                        fire96 = lhs96 >= rhs96;
                    }
                    if (pcut96 && fire96) {
                        /* The increasing endpoint is populated in nineteen
                         * discrete residue cells.  Keeping that structural
                         * support explicit prevents the threshold law from
                         * leaking into adjacent, response-silent cells. */
                        int supportup96 =
                            (distance == 7
                             && ((low3 == 1 && qpost1196 == 2032)
                                 || (low3 == 2 && qpost1196 == 2016)
                                 || ((low3 == 5 || low3 == 6)
                                     && qpost1196 == 1984)
                                 || (low3 == 7
                                     && (qpost1196 == 1968
                                         || qpost1196 == 1984))))
                         || (distance == 8
                             && ((low3 == 1 && qpost1196 == 2032)
                                 || (low3 == 2 && qpost1196 == 2024)
                                 || (low3 == 3 && qpost1196 == 2016)
                                 || (low3 == 4
                                     && (qpost1196 == 2000
                                         || qpost1196 == 2008))
                                 || (low3 == 5
                                     && (qpost1196 == 1992
                                         || qpost1196 == 2000))
                                 || (low3 == 6
                                     && (qpost1196 == 1984
                                         || qpost1196 == 1992))
                                 || (low3 == 7 && qpost1196 == 1984)))
                         || (distance == 9
                             && ((low3 == 1 && qpost1196 == 2036)
                                 || (low3 == 3 && qpost1196 == 2016)
                                 || (low3 == 4 && qpost1196 == 2008)));
                        if (!supportup96)
                            fire96 = 0;
                    }
                    if (!pcut96) {
                        /* h1058: the carry-zero half of the same inactive
                         * selector occupies the complementary terminal
                         * endpoint cells.  In each populated cell the exact
                         * response is monotone in floor(M/2^66); the support
                         * qualification prevents interpolation into unseen
                         * endpoint phases. */
                        int low396 = (int)low3;
                        int b196 = b1_96;
                        int b296 = b2_96;
                        int d796 = dd96;
                        int s496 = s4_96;
                        __int128 one96 = (__int128)1 << 66;
                        int mi96 = mreg96 >= 0
                            ? (int)(mreg96 / one96)
                            : -(int)((-mreg96 + one96 - 1) / one96);
                        int supportp096 =
                            (distance == 7
                             && ((low396 == 1 && qpost1196 == 2032)
                                 || ((low396 == 2 || low396 == 3)
                                     && qpost1196 == 2016)
                                 || (low396 == 4 && qpost1196 == 2000)
                                 || (low396 == 5
                                     && (qpost1196 == 1984
                                         || qpost1196 == 2000))
                                 || (low396 == 6 && qpost1196 == 1984)
                                 || (low396 == 7
                                     && (qpost1196 == 1968
                                         || qpost1196 == 1984))))
                         || (distance == 8
                             && ((low396 == 1 && qpost1196 == 2032)
                                 || (low396 == 2 && qpost1196 == 2024)
                                 || (low396 == 3 && qpost1196 == 2016)
                                 || (low396 == 4
                                     && (qpost1196 == 2000
                                         || qpost1196 == 2008))
                                 || (low396 == 5
                                     && (qpost1196 == 1992
                                         || qpost1196 == 2000))
                                 || (low396 == 6 && qpost1196 == 1992)
                                 || (low396 == 7 && qpost1196 == 1984)))
                         || (distance == 9
                             && ((low396 == 1 && qpost1196 == 2036)
                                 || (low396 == 2 && qpost1196 == 2024)
                                 || (low396 == 3 && qpost1196 == 2016)
                                 || (low396 == 6 && qpost1196 == 1984)
                                 || (low396 == 7 && qpost1196 == 1976)));
                        if (supportp096) {
                            fire96 =
                                (mi96 >= 0 && mi96 <= 2
                                 && low396 <= 1 && b196 <= 0
                                 && d796 <= 1 && s496 <= 66)
                             || (mi96 >= 1 && mi96 <= 2
                                 && low396 >= 2 && low396 <= 3
                                 && b196 <= 0 && d796 <= 1
                                 && s496 <= 66)
                             || (mi96 >= 0 && mi96 <= 2
                                 && low396 <= 1 && b296 <= 0
                                 && d796 >= 2 && s496 <= 66)
                             || (mi96 <= 2 && low396 >= 2
                                 && d796 >= 2 && s496 <= 66)
                             || (mi96 == -1 && low396 <= 1
                                 && b196 <= 0 && s496 >= 67)
                             || (mi96 >= 0 && mi96 <= 2
                                 && low396 <= 2 && b196 <= 0
                                 && s496 >= 67)
                             || (mi96 <= 0 && low396 >= 3
                                 && b196 <= 0 && lp96 >= 1
                                 && d796 <= 0 && s496 >= 67)
                             || (mi96 == 1 && low396 >= 3
                                 && b196 <= 0 && lp96 >= 1
                                 && s496 >= 67 && qpost1196 >= 1997)
                             || (mi96 == 2 && low396 >= 3
                                 && b196 <= 0 && lp96 <= 0
                                 && s496 >= 67 && qpost1196 <= 1996)
                             || (mi96 == 2 && low396 >= 3
                                 && b196 <= 0 && s496 >= 67
                                 && qpost1196 >= 1997)
                             || (mi96 == 0 && low396 <= 3
                                 && b196 >= 1 && b296 <= 0
                                 && lp96 <= 0 && d796 >= 1
                                 && s496 >= 67)
                             || (mi96 <= 0 && low396 <= 2
                                 && b196 >= 1 && b296 <= 0
                                 && lp96 >= 1 && d796 <= 0
                                 && s496 >= 67)
                             || (mi96 >= 1 && mi96 <= 2
                                 && low396 <= 2 && b196 >= 1
                                 && b296 <= 0 && d796 >= 1
                                 && s496 >= 67)
                             || (mi96 >= 1 && mi96 <= 2
                                 && low396 == 3 && b196 >= 1
                                 && s496 >= 67)
                             || (mi96 == 2 && low396 >= 4
                                 && low396 <= 5 && b196 >= 1
                                 && b296 <= 0 && lp96 <= 0
                                 && d796 <= 0 && s496 >= 67
                                 && qpost1196 >= 1989)
                             || (mi96 == 2 && low396 >= 4
                                 && low396 <= 5 && b196 >= 1
                                 && b296 <= 0 && lp96 <= 0
                                 && d796 >= 1 && s496 >= 67
                                 && qpost1196 >= 2005)
                             || (mi96 == 2 && low396 >= 6
                                 && b196 >= 1 && b296 <= 0
                                 && lp96 <= 0 && s496 >= 67
                                 && qpost1196 >= 1989)
                             || (mi96 == 2 && low396 >= 4
                                 && b196 >= 1 && b296 >= 1
                                 && lp96 <= 0 && s496 >= 67
                                 && qpost1196 >= 2005)
                             || (mi96 == 2 && low396 >= 4
                                 && b196 >= 1 && b296 <= 0
                                 && lp96 >= 1 && d796 <= 0
                                 && s496 >= 67 && qpost1196 >= 1993)
                             || (mi96 >= 3 && b196 <= 0 && b296 <= 0)
                             || (mi96 == 3 && b196 >= 1 && b296 <= 0
                                 && d796 <= 0 && qpost1196 >= 1993)
                             || (mi96 >= 5 && b196 >= 1 && b296 <= 0
                                 && d796 <= 0 && qpost1196 <= 1976)
                             || (mi96 >= 4 && b196 >= 1 && b296 <= 0
                                 && d796 <= 0 && qpost1196 >= 1977)
                             || (mi96 >= 3 && b196 >= 1 && b296 <= 0
                                 && d796 >= 1)
                             || (mi96 == 3 && low396 <= 6
                                 && b296 >= 1 && qpost1196 >= 1997)
                             || (mi96 == 3 && low396 >= 7 && b296 >= 1)
                             || (mi96 >= 4 && b296 >= 1
                                 && qpost1196 >= 1977);
                            if (distance == 9 && low396 == 7
                                && qpost1196 == 1976
                                && (b196 || b296))
                                fire96 = 0;
                        }
                    }
                    if (pcut96) {
                        /* h1060-h1064: the opposite endpoint is selected in nine
                         * upper-inactive terminal cells.  Its response is
                         * the decreasing half of the same integer R60
                         * comparison geometry; architectural RC resolves
                         * the overlap with the ordinary endpoint. */
                        int low396 = (int)low3;
                        int b196 = b1_96;
                        int b296 = b2_96;
                        int d796 = dd96;
                        int rn96 = rc == SF_RN;
                        int rz96 = rc == SF_RZ;
                        __int128 one96 = (__int128)1 << 66;
                        __int128 mscaled96 = 128 * mreg96;
                        int m12896 = mscaled96 >= 0
                            ? (int)(mscaled96 / one96)
                            : -(int)((-mscaled96 + one96 - 1) / one96);
                        int supportdown96 =
                            (distance == 7
                             && ((low396 == 1 && qpost1196 == 2032)
                                 || ((low396 == 2 || low396 == 3)
                                     && qpost1196 == 2016)
                                 || (low396 == 4 && qpost1196 == 2000)))
                         || (distance == 8
                             && ((low396 == 4
                                  && (qpost1196 == 2000
                                      || qpost1196 == 2008))
                                 || (low396 == 5
                                     && (qpost1196 == 1992
                                         || qpost1196 == 2000))
                                 || (low396 == 6 && qpost1196 == 1992)));
                        if (supportdown96) {
                            down96 =
                                (m12896 <= 266 && low396 == 2
                                 && b196 >= 1 && b296 <= 0)
                             || (m12896 <= 132 && low396 == 3
                                 && b296 <= 0)
                             || (m12896 <= 266 && low396 <= 2
                                 && b296 >= 1)
                             || (!rn96 && !rz96 && m12896 <= 266
                                 && low396 >= 4 && lp96 <= 0)
                             || (!rn96 && !rz96 && m12896 <= 96
                                 && low396 >= 4 && lp96 >= 1)
                             || (!rn96 && !rz96 && m12896 >= 113
                                 && m12896 <= 183 && low396 >= 4
                                 && lp96 >= 1)
                             || (!rn96 && !rz96 && m12896 >= 184
                                 && m12896 <= 244 && low396 >= 4
                                 && b196 >= 1 && lp96 >= 1)
                             || (!rn96 && !rz96 && m12896 >= 258
                                 && m12896 <= 266 && low396 >= 4
                                 && b196 >= 1 && lp96 >= 1)
                             || (m12896 >= 267 && m12896 <= 399
                                 && b196 <= 0 && b296 <= 0
                                 && lp96 >= 1 && qpost1196 <= 1996)
                             || (m12896 >= 267 && m12896 <= 367
                                 && b196 >= 1 && b296 <= 0
                                 && lp96 >= 1 && d796 >= 1)
                             || (m12896 >= 267 && m12896 <= 428
                                 && b296 >= 1 && qpost1196 <= 2004);
                            if (distance == 8 && low396 == 4
                                && qpost1196 == 2008) {
                                /* The q=2008 cell straddles two disjoint
                                 * decreasing intervals.  One more binary
                                 * fractional wire resolves their endpoints. */
                                __int128 mscaled25696 = 256 * mreg96;
                                int m25696 = mscaled25696 >= 0
                                    ? (int)(mscaled25696 / one96)
                                    : -(int)((-mscaled25696 + one96 - 1)
                                            / one96);
                                down96 = m25696 <= 487
                                    || (m25696 >= 507 && m25696 <= 527);
                            }
                        }
                        if (rn96 && distance == 9 && s4_96 == 66
                            && !side96 && retained96 == 255
                            && pdown96 >= 5 && edge96) {
                            /* h1068-h1076: the previously unseen q66/side0
                             * distance-9 arm is the next radix digit line,
                             * not another residue-cell table.  The FCOS map
                             * and independent FSIN transfer both put the
                             * ordinary boundary exactly at
                             *
                             *     qpost11 + 4*low3 <= 2044.
                             *
                             * Six carry states extend that line by one
                             * qpost11 quantum.  The only fractional tests
                             * reuse the existing R60 thresholds 132/128
                             * and 266/128.  Frozen final holdouts scored
                             * 40/40 FCOS rows and 6/6 FSIN rows.
                             */
                            int phase96 = qpost1196 + 8 * low396;
                            int limit96 = 2044 + 4 * low396;
                            if (low396 == 2 && b196)
                                limit96 += 4;
                            if (low396 == 3 && b296)
                                limit96 += 4;
                            if (low396 == 4 && b296
                                && m12896 <= 132)
                                limit96 += 4;
                            if (low396 == 5 && m12896 <= 132)
                                limit96 += 4;
                            if (low396 == 6 && b196)
                                limit96 += 4;
                            if (low396 == 7 && m12896 <= 266)
                                limit96 += 4;
                            down96 = phase96 <= limit96;
                        }
                    }
                    if (down96 && retained96 != 255)
                        down96 = 0;
                    if (!fire96 && !down96 && pcut96
                        && ((distance == 8 && low3 == 5
                             && qpost1196 == 1992)
                            || (distance == 9 && low3 == 4
                                && qpost1196 == 2008))) {
                        /* h1059: two response-visible holes at the edge of
                         * the ordinary endpoint support. */
                        __int128 one96 = (__int128)1 << 66;
                        int mi96 = mreg96 >= 0
                            ? (int)(mreg96 / one96)
                            : -(int)((-mreg96 + one96 - 1) / one96);
                        if (distance == 8)
                            fire96 = mi96 >= 3 && b2_96 <= 0;
                        else
                            fire96 = mi96 <= -1;
                    }
                    if (g_dump_internals)
                        fprintf(stderr,
                            "DI_R96TOPCLOSED sum=%d retained=%d theta=%d "
                            "s4=%d side=%d b1=%d b2=%d pdown=%d "
                            "qpost11=%d edge=%d "
                            "use=%d tt=%d uu=%d fire=%d down=%d\n",
                            sum96, retained96, theta96, s4_96, side96,
                            b1_96, b2_96, pdown96, qpost1196, edge96,
                            use96, tt96, uu96, fire96, down96);
                    if (down96) {
                        tc_default = tc_pre95;
                        tc_default.sig -= 1;
                        if (!(tc_default.sig >> 66)) {
                            tc_default.sig <<= 1;
                            tc_default.e2 -= 1;
                        }
                    } else if (fire96) {
                        tc_default = tc_pre95;
                        tc_default.sig += 1;
                        if (tc_default.sig >> 67) {
                            tc_default.sig >>= 1;
                            tc_default.e2 += 1;
                        }
                    }
                }
            }
        }
    }
#endif
#if G_R96ACTCLOSED
    /* h1042-h1054: the two active residual families are the mirror images
     * of the inactive-upper carry selector above.  At the exact terminal
     * subtraction silicon substitutes P[cut] for the true carry only in an
     * 11-bit endpoint window of the discarded residue: qpost11>=2024 on
     * the upper ladder and qpost11<=27 on the lower ladder.  Within those
     * windows the selector is an integer comparison tree over the R60
     * coordinate floor(M/2^66) and the already-derived terminal state.
     * The expressions below are a table-free consolidation of the pure
     * leaves; every boundary is an integer wire or an exact power-of-two
     * comparison (h1054).
     */
    {
        int dl96 = left.e2 - right.e2;
        if (active && dl96 > 8 && dl96 < 61
            && left.sign == 1 && right.sign == 0) {
            u128 s96 = left.sig << dl96;
            u128 paymag96 = (u128)(payload < 0 ? -payload : payload)
                << (dl96 - 8);
            int have_s96 = 1;
            if (payload >= 0) {
                s96 += paymag96;
            } else if (s96 >= paymag96) {
                s96 -= paymag96;
            } else {
                have_s96 = 0;
            }
            u128 b96 = right.sig;
            if (have_s96 && s96 > b96) {
                u128 mag96 = s96 - b96;
                int cut96 = u128_width(mag96) - 67;
                if (cut96 > 0 && cut96 < 61) {
                    u128 residue96 = mag96
                        & ((((u128)1) << cut96) - 1);
                    u128 qpost96 = residue_q66(residue96, cut96);
                    int qpost1196 = (int)(qpost96 >> 55);
                    u128 prop96 = ~(s96 ^ b96);
                    int pcut96 = (int)((prop96 >> cut96) & 1);
                    int retained96 = (int)((mag96 >> cut96) & 0xFF);
                    int low396 = (int)low3;
                    int sum96 = retained96 + low396;
                    wv_t w96 = acc_round_bits_mode(
                        accumulator, scale, 67 + 8, P5_ROUND_CHOP);
                    int force_sum96 = (int)(w96.sig & 0xFF) + low396;
                    int top96 = force_sum96 >= 128;

                    u256 f4full96 = u128_mul_full(
                        multiplier.sig, multiplier.sig);
                    int f4width96 = f4full96.hi
                        ? 128 + u128_width(f4full96.hi)
                        : u128_width(f4full96.lo);
                    int s496 = f4width96 - 67;
                    u128 t4_96 = s496 > 0 && s496 < 128
                        ? f4full96.lo & ((((u128)1) << s496) - 1)
                        : f4full96.lo;
                    int side96 = (uint64_t)magnitude.sig
                        >= 0xB504F333F9DE6800ULL;
                    __int128 sqlow96 = (__int128)multiplier.sig
                        - ((__int128)1 << 66);
                    __int128 mreg96 = (__int128)low396 * sqlow96
                        - (__int128)t4_96;
                    const __int128 one96 = (__int128)1 << 66;
                    int mi96 = mreg96 >= 0
                        ? (int)(mreg96 / one96)
                        : -(int)((-mreg96 + one96 - 1) / one96);

                    int mexp96 = right_shift - 16 - (side96 == 0);
                    int b196 = 0, b296 = 0;
                    if (mexp96 > 0 && mexp96 < 127
                        && right_shift >= 0 && right_shift < 126) {
                        u128 mask96 = (((u128)1) << mexp96) - 1;
                        u128 rd3_96 = 3 * right_discarded
                            - ((2 * right_discarded) & mask96)
                            - (right_discarded & mask96);
                        b196 = rd3_96 >= ((u128)1 << right_shift);
                        b296 = rd3_96
                            >= ((u128)1 << (right_shift + 1));
                    }

                    int lp96 = low396 & 1;
                    int d796 = distance - 7;
                    int rn96 = rc == SF_RN;
                    int rd96 = rc == SF_RD;
                    int rz96 = rc == SF_RZ;
                    int fire96 = 0;
                    int opposite96 = 0;
                    int support96 = 0;
                    if (top96) {
                        support96 =
                            (distance == 9 && low396 == 1
                             && qpost1196 == 2036 && side96 >= 1)
                         || (distance == 10
                             && ((low396 == 1
                                  && (qpost1196 == 2042
                                      || qpost1196 == 2044
                                      || qpost1196 == 2046))
                                 || (low396 == 2
                                     && qpost1196 >= 2040
                                     && qpost1196 <= 2046
                                     && !(qpost1196 & 1))
                                 || (low396 == 6
                                     && (qpost1196 == 2028
                                         || qpost1196 == 2030
                                         || qpost1196 == 2034
                                         || qpost1196 == 2036))
                                 || (low396 == 7
                                     && (qpost1196 == 2026
                                         || qpost1196 == 2032))))
                         || (distance == 11
                             && ((low396 == 1 && qpost1196 >= 2046)
                                 || (low396 == 2 && qpost1196 >= 2044)
                                 || (low396 == 3 && qpost1196 >= 2042)
                                 || (low396 == 4 && qpost1196 == 2045)
                                 || (low396 == 6
                                     && (qpost1196 == 2042
                                         || qpost1196 == 2044
                                         || qpost1196 == 2046
                                         || qpost1196 == 2047))))
                         || (distance == 12
                             && ((low396 == 1 && qpost1196 == 2047)
                                 || ((low396 == 2 || low396 == 3)
                                     && qpost1196 >= 2046)
                                 || (low396 == 4 && qpost1196 >= 2045)
                                 || (low396 == 5 && qpost1196 >= 2046)
                                 || (low396 == 7 && qpost1196 >= 2045)))
                         || (distance == 13
                             && (((low396 == 1 || low396 == 2
                                   || low396 == 3)
                                  && qpost1196 == 2047)
                                 || ((low396 == 4 || low396 == 5
                                      || low396 == 7)
                                     && qpost1196 >= 2046)
                                 || (low396 == 6 && qpost1196 == 2046)))
                         || (distance == 14
                             && (((low396 == 2 || low396 == 4)
                                  && qpost1196 == 2047)
                                 || (low396 == 7
                                     && qpost1196 == 2046)))
                         || (distance == 15
                             && (low396 == 2 || low396 == 6)
                             && qpost1196 == 2047);
                    } else {
                        support96 =
                            (distance == 9
                             && ((low396 == 5 && qpost1196 == 20)
                                 || ((low396 == 6 || low396 == 7)
                                     && (qpost1196 == 20
                                         || qpost1196 == 24))))
                         || (distance == 10
                             && ((low396 == 5 && qpost1196 == 18)
                                 || (low396 == 6 && qpost1196 == 22)
                                 || (low396 == 7 && qpost1196 == 20)))
                         || (distance == 11
                             && ((low396 == 6
                                  && (qpost1196 == 17
                                      || qpost1196 == 19))
                                 || (low396 == 7
                                     && (qpost1196 == 21
                                         || qpost1196 == 22))));
                    }
                    if (top96 && support96) {
                        fire96 =
                            (mi96 <= -1 && b196 <= 0 && lp96 <= 0 && s496 <= 66 && qpost1196 >= 2042 && qpost1196 <= 2043)
                         || (mi96 <= -1 && b196 <= 0 && side96 <= 0 && qpost1196 == 2044)
                         || (mi96 <= -1 && low396 >= 3 && b196 <= 0 && s496 <= 66 && side96 >= 1 && qpost1196 == 2044)
                         || (mi96 == -1 && b196 <= 0 && s496 >= 67 && side96 >= 1 && qpost1196 == 2044)
                         || (mi96 <= -1 && low396 >= 2 && b196 >= 1 && b296 <= 0 && side96 <= 0 && qpost1196 >= 2042 && qpost1196 <= 2044)
                         || (mi96 <= -1 && low396 >= 3 && b196 >= 1 && side96 >= 1 && qpost1196 == 2044)
                         || (mi96 >= 0 && b196 <= 0 && side96 <= 0 && qpost1196 <= 2044 && (s496 <= 66 || qpost1196 >= 2042))
                         || (mi96 == 2 && low396 <= 6 && b196 <= 0 && side96 >= 1 && qpost1196 <= 2035)
                         || (mi96 >= 3 && b196 <= 0 && side96 >= 1 && qpost1196 >= 2032 && qpost1196 <= 2035)
                         || (mi96 == 0 && b196 <= 0 && lp96 <= 0 && d796 >= 4 && s496 <= 66 && side96 >= 1 && qpost1196 >= 2036 && qpost1196 <= 2044)
                         || (mi96 == 0 && b196 <= 0 && lp96 <= 0 && s496 >= 67 && side96 >= 1 && qpost1196 >= 2036 && qpost1196 <= 2044)
                         || (mi96 >= 1 && b196 <= 0 && lp96 <= 0 && side96 >= 1 && qpost1196 >= 2036 && qpost1196 <= 2044)
                         || (mi96 >= 0 && b196 <= 0 && lp96 >= 1 && side96 >= 1 && qpost1196 >= 2036 && qpost1196 <= 2044)
                         || (mi96 >= 1 && low396 <= 6 && b196 >= 1 && b296 <= 0 && side96 <= 0 && qpost1196 <= 2029)
                         || (mi96 >= 0 && low396 >= 7 && b196 >= 1 && b296 <= 0 && side96 <= 0 && qpost1196 <= 2029)
                         || (mi96 >= 1 && b196 >= 1 && b296 >= 1 && s496 <= 66 && side96 <= 0 && qpost1196 <= 2029)
                         || (mi96 >= 0 && low396 <= 1 && b196 >= 1 && b296 <= 0 && d796 <= 3 && s496 <= 66 && side96 <= 0 && qpost1196 >= 2030 && qpost1196 <= 2043)
                         || (mi96 >= 0 && low396 <= 1 && b196 >= 1 && d796 <= 3 && s496 <= 66 && side96 <= 0 && qpost1196 == 2044)
                         || (mi96 >= 0 && low396 >= 2 && b196 >= 1 && d796 <= 3 && s496 <= 66 && side96 <= 0 && qpost1196 >= 2030 && qpost1196 <= 2044)
                         || (mi96 >= 1 && b196 >= 1 && d796 >= 4 && s496 <= 66 && side96 <= 0 && qpost1196 >= 2030 && qpost1196 <= 2044)
                         || (mi96 == 2 && low396 <= 6 && b196 >= 1 && b296 <= 0 && side96 >= 1 && qpost1196 <= 2035)
                         || (mi96 >= 0 && mi96 <= 1 && b196 >= 1 && b296 <= 0 && d796 <= 2 && side96 >= 1 && qpost1196 >= 2036 && qpost1196 <= 2044)
                         || (mi96 >= 0 && mi96 <= 1 && low396 >= 2 && low396 <= 4 && b196 >= 1 && b296 <= 0 && d796 >= 3 && s496 <= 66 && side96 >= 1 && qpost1196 >= 2043 && qpost1196 <= 2044)
                         || (mi96 >= 0 && mi96 <= 1 && low396 >= 2 && low396 <= 4 && b196 >= 1 && b296 <= 0 && d796 >= 3 && s496 >= 67 && side96 >= 1 && qpost1196 >= 2036 && qpost1196 <= 2044)
                         || (mi96 >= 0 && mi96 <= 1 && b196 >= 1 && b296 >= 1 && d796 >= 4 && side96 >= 1 && qpost1196 >= 2043 && qpost1196 <= 2044)
                         || (mi96 == 2 && b196 >= 1 && side96 >= 1 && qpost1196 >= 2036 && qpost1196 <= 2044)
                         || (mi96 >= 3 && b196 >= 1 && side96 >= 1 && qpost1196 <= 2044)
                         || (mi96 >= -1 && low396 <= 2 && b296 <= 0 && d796 <= 3 && qpost1196 >= 2045 && qpost1196 <= 2046)
                         || (mi96 == -1 && low396 <= 2 && b296 >= 1 && d796 <= 3 && s496 <= 66 && side96 <= 0 && qpost1196 >= 2045 && qpost1196 <= 2046)
                         || (mi96 == -1 && low396 <= 2 && b296 >= 1 && d796 <= 3 && s496 >= 67 && side96 >= 1 && qpost1196 >= 2045 && qpost1196 <= 2046)
                         || (mi96 >= 0 && low396 <= 1 && b296 >= 1 && d796 <= 3 && s496 <= 66 && qpost1196 >= 2045 && qpost1196 <= 2046)
                         || (mi96 >= 0 && low396 <= 1 && b296 >= 1 && d796 <= 3 && s496 >= 67 && side96 >= 1 && qpost1196 >= 2045 && qpost1196 <= 2046)
                         || (mi96 >= 0 && low396 == 2 && b296 >= 1 && d796 <= 3 && qpost1196 >= 2045 && qpost1196 <= 2046)
                         || (mi96 <= -1 && low396 <= 1 && b196 <= 0 && d796 >= 4 && side96 >= 1 && qpost1196 >= 2045 && qpost1196 <= 2046)
                         || (mi96 >= 0 && low396 <= 1 && b196 <= 0 && d796 >= 4 && side96 <= 0 && qpost1196 >= 2045 && qpost1196 <= 2046 && pcut96 <= 0)
                         || (mi96 >= 0 && low396 <= 1 && d796 >= 4 && side96 >= 1 && qpost1196 >= 2045 && qpost1196 <= 2046 && pcut96 <= 0)
                         || (mi96 >= 0 && low396 == 2 && b296 <= 0 && d796 >= 4 && s496 >= 67 && side96 <= 0 && qpost1196 == 2045)
                         || (low396 == 2 && b296 <= 0 && d796 >= 4 && s496 <= 66 && side96 <= 0 && qpost1196 == 2046)
                         || (low396 == 2 && b196 <= 0 && b296 <= 0 && d796 >= 4 && s496 >= 67 && side96 <= 0 && qpost1196 == 2046)
                         || (low396 == 2 && b296 <= 0 && d796 >= 4 && side96 >= 1 && qpost1196 >= 2045 && qpost1196 <= 2046)
                         || (low396 == 2 && b296 >= 1 && d796 >= 4 && s496 <= 66 && qpost1196 == 2046 && pcut96 >= 1)
                         || (mi96 >= 0 && low396 == 2 && b296 >= 1 && d796 >= 4 && s496 >= 67 && qpost1196 == 2046 && pcut96 <= 0)
                         || (low396 <= 1 && qpost1196 >= 2047 && pcut96 <= 0)
                         || (low396 <= 1 && b196 <= 0 && qpost1196 >= 2047 && pcut96 >= 1)
                         || (low396 <= 1 && b196 >= 1 && b296 <= 0 && d796 <= 4 && qpost1196 >= 2047 && pcut96 >= 1)
                         || (low396 <= 1 && b196 >= 1 && b296 >= 1 && d796 <= 4 && s496 <= 66 && qpost1196 >= 2047 && pcut96 >= 1)
                         || (low396 <= 1 && b196 >= 1 && b296 >= 1 && d796 >= 5 && qpost1196 >= 2047 && pcut96 >= 1)
                         || (low396 == 2 && qpost1196 >= 2047)
                         || (low396 >= 3 && b296 <= 0 && qpost1196 == 2045)
                         || (mi96 <= -1 && low396 >= 3 && b296 >= 1 && lp96 <= 0 && qpost1196 == 2045 && pcut96 >= 1)
                         || (mi96 >= 0 && low396 >= 3 && b296 >= 1 && lp96 <= 0 && qpost1196 == 2045)
                         || (low396 >= 3 && b296 >= 1 && lp96 >= 1 && qpost1196 == 2045)
                         || (low396 >= 3 && qpost1196 >= 2046);
                    } else if (!top96 && support96) {
                        fire96 =
                            (mi96 <= 0 && low396 == 6 && b296 >= 1 && d796 <= 3 && s496 <= 66 && side96 <= 0 && qpost1196 <= 21)
                         || (mi96 <= 0 && low396 == 6 && b296 >= 1 && d796 == 3 && side96 >= 1)
                         || (mi96 <= 0 && low396 <= 6 && b296 >= 1 && d796 >= 4 && side96 <= 0)
                         || (mi96 >= 2 && low396 <= 6 && b296 >= 1 && d796 >= 3 && side96 <= 0)
                         || (mi96 == 2 && low396 <= 5 && b196 >= 1 && b296 >= 1 && d796 <= 2 && side96 >= 1)
                         || (mi96 >= 2 && mi96 <= 3 && low396 == 6 && b196 >= 1 && d796 <= 2 && side96 >= 1 && (pcut96 || qpost1196 >= 24))
                         || (mi96 <= 1 && low396 >= 7 && b296 <= 0 && d796 <= 2 && s496 <= 66 && side96 <= 0 && qpost1196 <= 22 && ((pcut96 && sum96 <= 7) || (!pcut96 && sum96 >= 8)))
                         || (mi96 <= -1 && low396 >= 7 && b196 >= 1 && b296 <= 0 && d796 >= 3 && side96 <= 0 && qpost1196 <= 22)
                         || (mi96 <= 2 && low396 >= 7 && b296 >= 1 && d796 <= 2 && side96 <= 0 && qpost1196 <= 22 && (pcut96 || sum96 >= 8))
                         || (mi96 <= -1 && low396 >= 7 && b296 >= 1 && d796 >= 3 && side96 <= 0 && qpost1196 <= 22)
                         || (mi96 <= 0 && low396 >= 7 && b196 >= 1 && side96 <= 0 && qpost1196 >= 23)
                         || (mi96 <= -1 && low396 >= 7 && b196 >= 1 && d796 >= 4 && side96 >= 1)
                         || (mi96 == 0 && low396 >= 7 && b196 >= 1 && d796 >= 4 && side96 >= 1 && pcut96 >= 1);
                    }
#if G_R98ACTLOW5
                    if (!top96 && distance == 9 && low396 == 5
                        && qpost1196 == 20 && s496 == 67
                        && side96 == 1) {
                        /* h1082-h1083: direct preimages of all six old
                         * response rows expose the omitted selector wire.
                         * The low3=5 leaf is a closed R60 interval qualified
                         * by the five-column downward propagate block.  This
                         * both admits the new mi=1 response and rejects the
                         * pbelow=0 false positive; P[cut] is not selector
                         * data in this cell (matched pcut=0/1 adversaries). */
                        int pbelow5_96 = cut96 >= 5
                            && ((prop96 >> (cut96 - 5)) & 31) == 31;
                        fire96 = mi96 >= 1 && mi96 <= 2
                            && b196 == 1 && b296 == 1 && pbelow5_96;
                    }
#endif
                    if (top96 && pcut96 && distance == 10
                        && low396 == 2 && qpost1196 == 2042
                        && s496 <= 66 && side96 <= 0
                        && b196 >= 1 && b296 >= 1) {
                        /* In this phase the ordinary upper endpoint occupies
                         * only the first sixteenth of positive M. */
                        __int128 mscaled96 = 16 * mreg96;
                        int m1696 = mscaled96 >= 0
                            ? (int)(mscaled96 / one96)
                            : -(int)((-mscaled96 + one96 - 1) / one96);
                        fire96 = m1696 == 0;
                    }
                    if (!top96 && !fire96
                        && ((distance == 9 && low396 == 6
                             && qpost1196 == 20 && pcut96)
                            || (distance == 10 && low396 == 6
                                && qpost1196 == 22 && pcut96)
                            || (distance == 11 && low396 == 7
                                && qpost1196 == 23 && pcut96))) {
                        /* h1061-h1062: three lower-endpoint rows expose
                         * architectural-RC selection of the last carry
                         * input.  Four additional R60 fraction wires make
                         * the leg-level response exact without operand
                         * identities. */
                        __int128 mscaled96 = 16 * mreg96;
                        int m1696 = mscaled96 >= 0
                            ? (int)(mscaled96 / one96)
                            : -(int)((-mscaled96 + one96 - 1) / one96);
                        fire96 =
                            (rd96 && !rz96 && m1696 >= 3 && m1696 <= 4
                             && b296 >= 1 && d796 <= 2)
                         || (!rz96 && m1696 == 14 && b296 >= 1
                             && d796 <= 2 && side96 <= 0)
                         || (!rz96 && m1696 <= 9 && d796 == 3
                             && side96 >= 1)
                         || (rd96 && !rz96 && m1696 >= 30
                             && m1696 <= 41 && b196 >= 1 && d796 == 3
                             && side96 >= 1)
                         || (rd96 && !rz96 && m1696 >= 2
                             && m1696 <= 6 && b296 >= 1 && d796 >= 4)
                         || (rz96 && s496 <= 66 && side96 >= 1
                             && b196 >= 1
                             && ((d796 == 2 && m1696 == 3)
                                 || (d796 == 3 && m1696 == 31)
                                 || (d796 == 4 && m1696 == 6)));
                    }
                    if (top96 && pcut96
                        && distance == 10
                        && ((low396 == 1 && qpost1196 == 2046)
                            || (low396 == 2 && qpost1196 == 2042))) {
                        /* h1060: two active-upper endpoint cells select the
                         * opposite terminal input.  The overlap with the
                         * ordinary endpoint resolves on sixteenths of the
                         * exact R60 coordinate, so retain those four
                         * fractional selector wires instead of an operand
                         * exception. */
                        __int128 mscaled96 = 16 * mreg96;
                        int m1696 = mscaled96 >= 0
                            ? (int)(mscaled96 / one96)
                            : -(int)((-mscaled96 + one96 - 1) / one96);
                        opposite96 =
                            (m1696 == -7 && low396 <= 1 && b296 >= 1)
                         || (m1696 == -2 && low396 >= 2
                             && b296 <= 0 && side96 >= 1)
                         || (m1696 >= -1 && m1696 <= 0
                             && low396 >= 2 && b296 <= 0
                             && s496 >= 67 && side96 >= 1)
                         || (m1696 >= 1 && m1696 <= 2
                             && low396 >= 2 && b296 <= 0
                             && side96 >= 1)
                         || (m1696 >= 11 && low396 >= 2
                             && b196 <= 0 && b296 <= 0
                             && side96 >= 1)
                         || (m1696 >= -9 && m1696 <= -7
                             && low396 >= 2 && b296 >= 1)
                         || (m1696 >= -3 && m1696 <= -2
                             && low396 >= 2 && b296 >= 1)
                         || (m1696 >= 3 && low396 >= 2 && b296 >= 1
                             && side96 >= 1);
                    }
                    if (!top96
                        && ((distance == 9 && pcut96
                             && ((low396 == 6 && qpost1196 == 24)
                                 || (low396 == 7
                                     && (qpost1196 == 20
                                         || qpost1196 == 24))))
                            || (distance == 10 && low396 == 5
                                && qpost1196 == 18 && pcut96)
                            || (distance == 12 && low396 == 5
                                && qpost1196 == 5 && !pcut96))) {
                        /* h1061-h1062: the complementary lower endpoint is
                         * resolved at the architectural-RC boundary.  Seven
                         * fractional R60 wires are sufficient for an exact
                         * leg-level separator over every visible response. */
                        __int128 mscaled96 = 128 * mreg96;
                        int m12896 = mscaled96 >= 0
                            ? (int)(mscaled96 / one96)
                            : -(int)((-mscaled96 + one96 - 1) / one96);
                        opposite96 =
                            (rn96 && !rd96 && b296 <= 0
                             && d796 >= 3 && d796 <= 4 && s496 >= 67)
                         || (!rd96 && b196 <= 0 && d796 >= 5)
                         || (rd96 && m12896 >= 249 && m12896 <= 265
                             && low396 >= 7 && b296 <= 0 && d796 <= 4
                             && qpost1196 <= 22)
                         || (rd96 && m12896 >= 304 && m12896 <= 305
                             && low396 >= 7 && b196 <= 0 && b296 <= 0
                             && d796 <= 4 && qpost1196 <= 22)
                         || (rd96 && m12896 >= 304 && m12896 <= 315
                             && low396 >= 7 && b196 >= 1 && b296 <= 0
                             && d796 <= 4 && qpost1196 <= 22)
                         || (rd96 && m12896 == 151 && low396 >= 7
                             && b296 <= 0 && d796 <= 4 && s496 <= 66
                             && side96 <= 0 && qpost1196 >= 23)
                         || (rd96 && m12896 >= 160 && m12896 <= 185
                             && low396 >= 7 && b296 <= 0 && d796 <= 4
                             && s496 <= 66 && side96 <= 0
                             && qpost1196 >= 23)
                         || (rd96 && m12896 >= 224 && m12896 <= 262
                             && low396 >= 7 && b296 <= 0 && d796 <= 4
                             && s496 <= 66 && side96 <= 0
                             && qpost1196 >= 23)
                         || (rd96 && m12896 >= 270 && m12896 <= 272
                             && low396 >= 7 && b296 <= 0 && d796 <= 4
                             && s496 <= 66 && side96 <= 0
                             && qpost1196 >= 23)
                         || (rd96 && m12896 >= 280 && m12896 <= 296
                             && low396 >= 7 && b296 <= 0 && d796 <= 4
                             && s496 <= 66 && side96 <= 0
                             && qpost1196 >= 23)
                         || (rd96 && m12896 >= 151 && m12896 <= 219
                             && low396 >= 7 && b196 <= 0 && b296 <= 0
                             && d796 <= 4 && s496 >= 67
                             && qpost1196 >= 23)
                         || (rd96 && m12896 >= 297 && m12896 <= 303
                             && low396 >= 7 && b296 <= 0 && d796 <= 4
                             && qpost1196 >= 23)
                         || (rd96 && m12896 >= 236 && m12896 <= 264
                             && low396 >= 7 && b296 >= 1 && d796 <= 4
                             && qpost1196 >= 23)
                         || (rd96 && m12896 >= 151 && m12896 <= 343
                             && d796 >= 5)
                         || (rd96 && m12896 >= 397 && m12896 <= 407
                             && low396 <= 6)
                         || (rd96 && m12896 >= 543 && low396 <= 6
                             && b296 <= 0)
                         || (rd96 && m12896 >= 344 && m12896 <= 348
                             && low396 >= 7)
                         || (rd96 && m12896 >= 356 && m12896 <= 366
                             && low396 >= 7)
                         || (rd96 && m12896 >= 369 && m12896 <= 379
                             && low396 >= 7 && b196 <= 0)
                         || (rd96 && m12896 >= 429 && m12896 <= 438
                             && low396 >= 7 && b196 <= 0)
                         || (rd96 && m12896 >= 455 && m12896 <= 466
                             && low396 >= 7 && b196 <= 0)
                         || (rd96 && m12896 >= 369 && m12896 <= 468
                             && low396 >= 7 && b196 >= 1 && b296 <= 0)
                         || (rd96 && m12896 >= 369 && m12896 <= 406
                             && low396 >= 7 && b196 >= 1 && b296 >= 1
                             && qpost1196 <= 22)
                         || (rd96 && m12896 >= 370 && m12896 <= 468
                             && low396 >= 7 && b196 >= 1 && b296 >= 1
                             && qpost1196 >= 23)
                         || (rd96 && m12896 >= 470 && m12896 <= 475
                             && low396 >= 7)
                         || (rd96 && m12896 >= 476 && m12896 <= 506
                             && low396 >= 7 && b296 >= 1);
                    }
                    if (g_dump_internals)
                        fprintf(stderr,
                            "DI_R96ACTCLOSED sum=%d force_sum=%d "
                            "retained=%d cut=%d "
                            "qpost11=%d pcut=%d mi=%d s4=%d side=%d "
                            "b1=%d b2=%d d7=%d support=%d fire=%d "
                            "opposite=%d\n",
                            sum96, force_sum96, retained96, cut96,
                            qpost1196, pcut96,
                            mi96, s496, side96, b196, b296, d796,
                            support96, fire96, opposite96);
                    if (opposite96) {
                        tc_default = tc_pre95;
                        if (top96) {
                            tc_default.sig -= 1;
                            if (!(tc_default.sig >> 66)) {
                                tc_default.sig <<= 1;
                                tc_default.e2 -= 1;
                            }
                        } else {
                            tc_default.sig += 1;
                            if (tc_default.sig >> 67) {
                                tc_default.sig >>= 1;
                                tc_default.e2 += 1;
                            }
                        }
                    } else if (fire96) {
                        tc_default = tc_pre95;
                        if (top96) {
                            tc_default.sig += 1;
                            if (tc_default.sig >> 67) {
                                tc_default.sig >>= 1;
                                tc_default.e2 += 1;
                            }
                        } else {
                            tc_default.sig -= 1;
                            if (!(tc_default.sig >> 66)) {
                                tc_default.sig <<= 1;
                                tc_default.e2 -= 1;
                            }
                        }
                    }
                }
            }
        }
    }
#endif
#if G_R96RES2045
    /* h1005 candidate: the payload gate and the terminal residue test can
     * be evaluated in parallel.  Qualify on the real post-gate top line,
     * read the exact discarded residues of both the counterfactual pre-gate
     * and real post-gate materialized sums.  Their maximal bad boundaries
     * are exactly 2045/2048 and 2047/2048.  The R60-style wrapped coordinate
     * (8*post + pre) mod 1 has the independent boundary 2023/2048; all three
     * strict comparisons have zero h975 admissibility contradictions.
     */
    {
        wv_t w96 = acc_round_bits_mode(
            accumulator, scale, 67 + 8, P5_ROUND_CHOP);
        int sum96 = (int)(w96.sig & 0xFF) + (int)low3;
        int dl96 = left.e2 - right.e2;
        if (active && sum96 >= 0xF0 && dl96 > 8 && dl96 <= 40) {
            int fire96 = 0;
            int have_pre96 = 0, have_post96 = 0;
            u128 qpre96 = 0, qpost96 = 0;
            __int128 spre96 = ((__int128)left.sig << dl96)
                + (__int128)payload_pre_gate * ((__int128)1 << (dl96 - 8));
            __int128 b96 = (__int128)right.sig;
            if (spre96 > b96) {
                u128 mpre96 = (u128)(spre96 - b96);
                int cpre96 = u128_width(mpre96) - 67;
                u128 rpre96 = cpre96 > 0
                    ? mpre96 & ((((u128)1) << cpre96) - 1) : 0;
                if (cpre96 > 0 && cpre96 < 40) {
                    have_pre96 = 1;
                    qpre96 = (rpre96 << 66) >> cpre96;
                }
                fire96 = cpre96 > 0 && cpre96 < 40
                    && (rpre96 << 11) > ((u128)2045 << cpre96);
            }
            __int128 spost96 = ((__int128)left.sig << dl96)
                + (__int128)payload * ((__int128)1 << (dl96 - 8));
            if (spost96 > b96) {
                u128 mpost96 = (u128)(spost96 - b96);
                int cpost96 = u128_width(mpost96) - 67;
                u128 rpost96 = cpost96 > 0
                    ? mpost96 & ((((u128)1) << cpost96) - 1) : 0;
                if (cpost96 > 0 && cpost96 < 40) {
                    have_post96 = 1;
                    qpost96 = (rpost96 << 66) >> cpost96;
                }
                fire96 = fire96 || (cpost96 > 0 && cpost96 < 40
                    && (rpost96 << 11) > ((u128)2047 << cpost96));
            }
            if (have_pre96 && have_post96) {
                u128 wrapped96 = ((qpost96 << 3) + qpre96)
                    & ((((u128)1) << 66) - 1);
                fire96 = fire96 || ((wrapped96 << 11)
                    > ((u128)2023 << 66));
            }
            if (have_pre96) {
                /* The next conservative R60-style residue-ring arm: bit
                 * 55 of (6*pre) mod 1.  h1015: 9 FIT / 8 HOL pinned,
                 * zero census contradictions; h1000: 1 fix / 0 breaks. */
                u128 sixpre96 = (6 * qpre96)
                    & ((((u128)1) << 66) - 1);
                fire96 = fire96 || ((sixpre96 >> 55) & 1);
            }
            if (fire96) {
                tc_default = tc_pre95;
                tc_default.sig += 1;
                if (tc_default.sig >> 67) {
                    tc_default.sig >>= 1;
                    tc_default.e2 += 1;
                }
            }
        }
    }
#endif
#if G_R96TOPR60 || G_R96TOPPAIR
    /* h1016: raw-width R60 residue-ring transfer to the inactive upper
     * ladder.  These are exact modular coordinates, not normalized f4
     * proxies.  Each dyadic arm independently has zero h975 admissibility
     * contradictions in both banks and zero h1000 neighborhood breaks. */
    {
        wv_t w96 = acc_round_bits_mode(
            accumulator, scale, 67 + 8, P5_ROUND_CHOP);
        int sum96 = (int)(w96.sig & 0xFF) + (int)low3;
        if (!active && sum96 >= 0xF0) {
            const u128 mask96 = (((u128)1) << 66) - 1;
            u128 qleft96 = shift > 0
                ? residue_q66(discarded, shift) : 0;
            u128 sqlow96 = (multiplier.sig - (((u128)1) << 66))
                & mask96;
#if G_R96TOPR60
            u128 word196 = ((qleft96 << 1) + sqlow96) & mask96;
            int fire96 = (word196 << 10) < ((u128)5 << 66);
#else
            int fire96 = 0;
#endif

            u256 sqfull96 = u128_mul_full(magnitude.sig, magnitude.sig);
            int sqwidth96 = sqfull96.hi
                ? 128 + u128_width(sqfull96.hi)
                : u128_width(sqfull96.lo);
            int sqshift96 = sqwidth96 - 67;
            u128 sqdisc96 = sqshift96 > 0
                ? sqfull96.lo & ((((u128)1) << sqshift96) - 1) : 0;
            u128 qsq96 = sqshift96 > 0
                ? residue_q66(sqdisc96, sqshift96) : 0;
#if G_R96TOPR60
            u128 word296 = ((u128)right_upper_discarded * qsq96
                - sqlow96) & mask96;
            fire96 = fire96 || ((word296 << 9) < ((u128)1 << 66));
#endif

            u256 f4full96 = u128_mul_full(multiplier.sig, multiplier.sig);
            int f4width96 = f4full96.hi
                ? 128 + u128_width(f4full96.hi)
                : u128_width(f4full96.lo);
            int f4shift96 = f4width96 - 67;
            u128 t4raw96 = f4shift96 > 0
                ? f4full96.lo & ((((u128)1) << f4shift96) - 1) : 0;
            t4raw96 &= mask96;
            u128 qright96 = right_shift > 0
                ? residue_q66(right_discarded, right_shift) : 0;
#if G_R96TOPR60
            u128 word396 = (7 * t4raw96 - qright96) & mask96;
            fire96 = fire96 || ((word396 << 13)
                > ((u128)8189 << 66));
#endif

#if G_R96TOPPAIR
            /* The paired upper-inactive corner: a 4-bit terminal/right
             * residue comparison qualified by the multiplier-square tail.
             * The 15/16 and 93/128 boundaries jointly cover both pinned
             * banks with zero h975/h1000 contradictions. */
            int dl96 = left.e2 - right.e2;
            if (dl96 > 0 && dl96 < 61) {
                u128 spre96 = left.sig << dl96;
                if (spre96 > right.sig) {
                    u128 mpre96 = spre96 - right.sig;
                    int cpre96 = u128_width(mpre96) - 67;
                    u128 rpre96 = cpre96 > 0
                        ? mpre96 & ((((u128)1) << cpre96) - 1) : 0;
                    u128 qpre96 = residue_q66(rpre96, cpre96);
                    u128 word496 = (64 * qpre96 - qright96) & mask96;
                    fire96 = fire96 || (
                        (word496 << 4) > ((u128)15 << 66)
                        && (sqlow96 << 7) > ((u128)93 << 66));
                }
            }
#endif
            if (fire96) {
                tc_default = tc_pre95;
                tc_default.sig += 1;
                if (tc_default.sig >> 67) {
                    tc_default.sig >>= 1;
                    tc_default.e2 += 1;
                }
            }
        }
    }
#endif
#if G_R96PAIRR60
    /* h1016: paired upper-active terminal-residue corner.  Both pre- and
     * post-paygate exact terminal residues lie in a narrow wrapped interval;
     * the two independently scaled comparisons retain 31+ decisions in each
     * pinned bank and three fresh response fixes with no known contradiction.
     */
    {
        wv_t w96 = acc_round_bits_mode(
            accumulator, scale, 67 + 8, P5_ROUND_CHOP);
        int sum96 = (int)(w96.sig & 0xFF) + (int)low3;
        int dl96 = left.e2 - right.e2;
        if (active && sum96 >= 0x80 && dl96 > 8 && dl96 <= 40) {
            const u128 mask96 = (((u128)1) << 66) - 1;
            u128 qpre96 = 0, qpost96 = 0;
            int have_pre96 = 0, have_post96 = 0;
            u128 b96 = right.sig;
            u128 spre96 = (left.sig << dl96)
                + ((u128)payload_pre_gate << (dl96 - 8));
            if (spre96 > b96) {
                u128 mpre96 = spre96 - b96;
                int cpre96 = u128_width(mpre96) - 67;
                u128 rpre96 = cpre96 > 0
                    ? mpre96 & ((((u128)1) << cpre96) - 1) : 0;
                if (cpre96 > 0) {
                    have_pre96 = 1;
                    qpre96 = residue_q66(rpre96, cpre96);
                }
            }
            u128 spost96 = (left.sig << dl96)
                + ((u128)payload << (dl96 - 8));
            if (spost96 > b96) {
                u128 mpost96 = spost96 - b96;
                int cpost96 = u128_width(mpost96) - 67;
                u128 rpost96 = cpost96 > 0
                    ? mpost96 & ((((u128)1) << cpost96) - 1) : 0;
                if (cpost96 > 0) {
                    have_post96 = 1;
                    qpost96 = residue_q66(rpost96, cpost96);
                }
            }
            if (have_pre96 && have_post96) {
                u128 word196 = (6 * qpost96 + qpre96) & mask96;
                u128 word296 = ((u128)distance * qpost96 + qpre96)
                    & mask96;
                int fire96 = (word196 << 10) > ((u128)1013 << 66)
                    && (word296 << 10) > ((u128)1005 << 66);
                if (fire96) {
                    tc_default = tc_pre95;
                    tc_default.sig += 1;
                    if (tc_default.sig >> 67) {
                        tc_default.sig >>= 1;
                        tc_default.e2 += 1;
                    }
                }
            }
        }
    }
#endif
#if G_R96LOWR60
    /* h1016: the lower active ladder has the complementary R60 residue
     * corner law.  Both modular coordinates must lie in their final binary
     * interval: (low3*Q[x*x] + sq_low) mod 1 > 63/64 and
     * (5*T4_raw - Q[right]) mod 1 > 31/32.  These coarse dyadic boundaries
     * select both independent h1000 responses, retain both pinned evidence
     * banks, and have zero h975/h1000 contradictions. */
    {
        wv_t w96 = acc_round_bits_mode(
            accumulator, scale, 67 + 8, P5_ROUND_CHOP);
        int sum96 = (int)(w96.sig & 0xFF) + (int)low3;
        if (active && sum96 < 0x80) {
            const u128 mask96 = (((u128)1) << 66) - 1;
            u256 sqfull96 = u128_mul_full(magnitude.sig, magnitude.sig);
            int sqwidth96 = sqfull96.hi
                ? 128 + u128_width(sqfull96.hi)
                : u128_width(sqfull96.lo);
            int sqshift96 = sqwidth96 - 67;
            u128 sqdisc96 = sqshift96 > 0
                ? sqfull96.lo & ((((u128)1) << sqshift96) - 1) : 0;
            u128 qsq96 = sqshift96 > 0
                ? residue_q66(sqdisc96, sqshift96) : 0;
            u128 sqlow96 = (multiplier.sig - (((u128)1) << 66))
                & mask96;
            u128 word196 = ((u128)low3 * qsq96 + sqlow96) & mask96;

            u256 f4full96 = u128_mul_full(multiplier.sig, multiplier.sig);
            int f4width96 = f4full96.hi
                ? 128 + u128_width(f4full96.hi)
                : u128_width(f4full96.lo);
            int f4shift96 = f4width96 - 67;
            u128 t4raw96 = f4shift96 > 0
                ? f4full96.lo & ((((u128)1) << f4shift96) - 1) : 0;
            t4raw96 &= mask96;
            u128 qright96 = right_shift > 0
                ? residue_q66(right_discarded, right_shift) : 0;
            u128 word296 = (5 * t4raw96 - qright96) & mask96;
            int fire96 = (word196 << 6) > ((u128)63 << 66)
                && (word296 << 5) > ((u128)31 << 66);
            if (g_dump_internals)
                fprintf(stderr,
                    "DI_R96LOW sum=%d qsq=" DIWF " sqlow=" DIWF
                    " t4raw=" DIWF " qright=" DIWF " w1=" DIWF
                    " w2=" DIWF " fire=%d\n",
                    sum96, 0, 0, DIU(qsq96), 0, 0, DIU(sqlow96),
                    0, 0, DIU(t4raw96), 0, 0, DIU(qright96),
                    0, 0, DIU(word196), 0, 0, DIU(word296), fire96);
            if (fire96) {
                tc_default = tc_pre95;
                tc_default.sig -= 1;
                if (!(tc_default.sig >> 66)) {
                    tc_default.sig <<= 1;
                    tc_default.e2 -= 1;
                }
            }
        }
    }
#endif
#if G_R96C11
    /* h1017: corrected post-gate segmented-carry mechanism.  Resolve the
     * terminal subtraction's top eleven discarded columns with carry-in 1.
     * Fire only when that bounded predictor carries but the exact complete
     * discarded field does not.  P[cut] is the independently proved output
     * direction bit.  Complete h975 census: 4 FIT + 6 HOL pinned decisions,
     * zero admissibility contradictions; h1000: 1 fix / 0 breaks. */
    {
        wv_t w96 = acc_round_bits_mode(
            accumulator, scale, 67 + 8, P5_ROUND_CHOP);
        int sum96 = (int)(w96.sig & 0xFF) + (int)low3;
        int dl96 = left.e2 - right.e2;
        if (active && sum96 >= 0xF0 && dl96 > 8 && dl96 <= 40) {
            u128 s96 = (left.sig << dl96)
                + ((u128)payload << (dl96 - 8));
            u128 b96 = right.sig;
            if (s96 > b96) {
                u128 m96 = s96 - b96;
                int cut96 = u128_width(m96) - 67;
                if (cut96 > 11
                    && ((~(s96 ^ b96) >> cut96) & 1)) {
                    u128 cutmask96 = (((u128)1) << cut96) - 1;
                    u128 true96 = ((s96 & cutmask96)
                        + ((~b96) & cutmask96) + 1) >> cut96;
                    int low96 = cut96 - 11;
                    u128 winmask96 = (((u128)1) << 11) - 1;
                    u128 pred96 = (((s96 >> low96) & winmask96)
                        + (((~b96) >> low96) & winmask96) + 1) >> 11;
                    if (pred96 > true96) {
                        tc_default = tc_pre95;
                        tc_default.sig += 1;
                        if (tc_default.sig >> 67) {
                            tc_default.sig >>= 1;
                            tc_default.e2 += 1;
                        }
                    }
                }
            }
        }
    }
#endif
#if G_R96M12
    /* Corrected post-gate terminal frame (h997): M[cut-12..14] are
     * independently zero-contradiction partial arms across all 8,315
     * admissible sets.  M[cut-12] has 8 FIT + 8 HOL pinned decisions;
     * none of the three bits selects an h1000 local break.
     */
    {
        wv_t w96 = acc_round_bits_mode(
            accumulator, scale, 67 + 8, P5_ROUND_CHOP);
        int sum96 = (int)(w96.sig & 0xFF) + (int)low3;
        int dl96 = left.e2 - right.e2;
        if (active && sum96 >= 0xF0 && dl96 > 8 && dl96 <= 40) {
            __int128 s96 = ((__int128)left.sig << dl96)
                + (__int128)payload * ((__int128)1 << (dl96 - 8));
            __int128 b96 = (__int128)right.sig;
            if (s96 > b96) {
                u128 magnitude96 = (u128)(s96 - b96);
                int cut96 = u128_width(magnitude96) - 67;
                int fire96 = (cut96 >= 12
                        && ((magnitude96 >> (cut96 - 12)) & 1))
                    || (cut96 >= 13
                        && ((magnitude96 >> (cut96 - 13)) & 1))
                    || (cut96 >= 14
                        && ((magnitude96 >> (cut96 - 14)) & 1));
                if (fire96) {
                    tc_default = tc_pre95;
                    tc_default.sig += 1;
                    if (tc_default.sig >> 67) {
                        tc_default.sig >>= 1;
                        tc_default.e2 += 1;
                    }
                }
            }
        }
    }
#endif
#if G_R96FORCE
    /* Analysis-only inverse-oracle arm.  This deliberately chooses an
     * absolute integer terminal correction, rather than extending any of
     * the fitted gates, so R95-vs-probe output differences identify exactly
     * the inputs on which that candidate quantum is architecturally visible.
     */
    {
        wv_t w96 = acc_round_bits_mode(
            accumulator, scale, 67 + 8, P5_ROUND_CHOP);
        int sum96 = (int)(w96.sig & 0xFF) + (int)low3;
        int top96 = sum96 >= 128;
        int force96 = (G_R96FORCE == 1 && !active && top96)
            || (G_R96FORCE == 2 && active && top96)
            || (G_R96FORCE == 3 && active && !top96)
            || (G_R96FORCE == 4 && !active && top96)
            || (G_R96FORCE == 5 && active && top96)
            || (G_R96FORCE == 6 && active && !top96)
            || ((G_R96FORCE == 9 || G_R96FORCE == 10)
                && active && !top96)
            || ((G_R96FORCE == 7 || G_R96FORCE == 8)
                && !active && !top96);
        if (force96) {
            tc_default = tc_pre95;
            if (G_R96FORCE == 9 || G_R96FORCE == 10) {
                tc_default.sig <<= 1;
                tc_default.sig += G_R96FORCE == 9 ? -1 : 1;
                tc_default.e2 -= 1;
            } else if (G_R96FORCE == 3 || G_R96FORCE == 4
                || G_R96FORCE == 5 || G_R96FORCE == 8) {
                tc_default.sig -= 1;
                if (!(tc_default.sig >> 66)) {
                    tc_default.sig <<= 1;
                    tc_default.e2 -= 1;
                }
            } else {
                tc_default.sig += 1;
                if (tc_default.sig >> 67) {
                    tc_default.sig >>= 1;
                    tc_default.e2 += 1;
                }
            }
        }
    }
#endif
    if (g_dump_internals)
        fprintf(stderr, "DI_CORR via=default payload=%d out=" DIWF "\n",
            payload, DIW(tc_default));
    return tc_default;
}

/*
 * h110's cross-validated standalone-FSIN
 * direct-polynomial survivor.  PII and Skylake have identical RN outputs on
 * all 80,000 inputs in this region; Skylake RD/RU plus C1 constrain the
 * hidden value.  The unusual away-from-zero representatives at the last two
 * Horner edges are deliberately exposed: they may stand for coefficient
 * alignment or discarded-product behavior rather than literal rounding
 * operations.
 *
 *   a2 = chop67(a*a)
 *   coefficients = RN67(native 68-bit P5 ROM values), except the
 *                  penultimate S2 coefficient = away64
 *   first three Horner edges: product RN69, sum RN69
 *   fourth edge: product RN69, sum RN64
 *   fifth edge: product away64, sum RN67
 *   m = RN64(p*a2)
 *   correction = chop67(m*a)
 *   result = architectural_round(a + correction)
 */
static sf_t p5_fsin_standalone_direct(
    wv_t magnitude, int neg_out, sf_rc_t rc, int reduced)
{
    if (g_round42_p6_sine_split) {
        /*
         * h242's two interleaved six-term sine chains:
         *
         *   odd = ((S5*x^4 + S3)*x^4 + S1)*x^2
         *   even = ((S6*x^4 + S4)*x^4 + S2)*x^4
         *   result = architectural_round(x + (odd + even)*x)
         *
         * This graph is exact on the complete direct/reduced standalone-FSIN
         * captures and on standalone FCOS's reduced sine-producing path.
         * Paired FSINCOS retains its separate polynomial schedule.
         */
        wv_t square = p5_wv_mul_round(
            magnitude, magnitude, 67, P5_ROUND_CHOP);
        wv_t fourth = p5_wv_mul_round(
            square, square, 65, P5_ROUND_RN);

        wv_t odd = p5_constant_round(
            &P5S6_5, 67, P5_ROUND_RN);
        odd = p5_wv_mul_round(
            odd, fourth, 67, P5_ROUND_CHOP);
        odd = p5_wv_add_constant_round(
            odd, &P5S6_3,
            67, P5_ROUND_RN, 67, P5_ROUND_CHOP);
        odd = p5_wv_mul_round(
            odd, fourth, 67, P5_ROUND_CHOP);
        odd = p5_wv_add_constant_round(
            odd, &P5S6_1,
            67, P5_ROUND_RN, 64, P5_ROUND_RN);
        odd = p5_wv_mul_round(
            odd, square, 67, P5_ROUND_CHOP);

        wv_t even = p5_constant_round(
            &P5S6_6, 67, P5_ROUND_RN);
        even = p5_wv_mul_round(
            even, fourth, 67, P5_ROUND_CHOP);
        even = p5_wv_add_constant_round(
            even, &P5S6_4,
            67, P5_ROUND_RN, 67, P5_ROUND_CHOP);
        even = p5_wv_mul_round(
            even, fourth, 67, P5_ROUND_CHOP);
        even = p5_wv_add_constant_round(
            even,
            &P5S6_2,
            reduced ? 67 : 64,
            reduced ? P5_ROUND_RN : P5_ROUND_AWAY,
            66,
            P5_ROUND_ODD);
        even = p5_wv_mul_round(
            even, fourth, 64, P5_ROUND_CHOP);

        wv_t polynomial = p5_wv_add_round(
            odd, even, 64, P5_ROUND_RN);
        wv_t correction = p5_wv_mul_round(
            polynomial, magnitude, 67, P5_ROUND_CHOP);
        if (g_dump_internals)
            fprintf(stderr,
                "DI_H242 neg_out=%d reduced=%d mag=" DIWF " sq=" DIWF
                " f4=" DIWF " odd=" DIWF " even=" DIWF " poly=" DIWF
                " corr=" DIWF "\n",
                neg_out, reduced, DIW(magnitude), DIW(square),
                DIW(fourth), DIW(odd), DIW(even), DIW(polynomial),
                DIW(correction));
        p5c_t lead = { 0, magnitude.e2, magnitude.sig };
        p5c_t tail = {
            correction.sign, correction.e2, correction.sig
        };
        return p5_combine(
            &lead, &ZERO, &tail, &ONE, 0,
            neg_out, rc, &ZERO, NULL, 0);
    }

    if (reduced) {
        /*
         * h122: an independently split full-sweep search selects a distinct
         * reduced-entry representative on both halves:
         *   a2=away66(a*a), coefficients=RN67,
         *   products=RN69, sums=RN69 except final sum=RN65,
         *   m=chop65(p*a2), exact final a+m*a.
         */
        wv_t square = p5_wv_mul_round(
            magnitude, magnitude, 66, P5_ROUND_AWAY);
        wv_t p = p5_constant_round(&P5S6_6, 67, P5_ROUND_RN);
        p = p5_wv_mul_round(p, square, 69, P5_ROUND_RN);
        p = p5_wv_add_constant_round(
            p, &P5S6_5, 67, P5_ROUND_RN, 69, P5_ROUND_RN);
        p = p5_wv_mul_round(p, square, 69, P5_ROUND_RN);
        p = p5_wv_add_constant_round(
            p, &P5S6_4, 67, P5_ROUND_RN, 69, P5_ROUND_RN);
        p = p5_wv_mul_round(p, square, 69, P5_ROUND_RN);
        p = p5_wv_add_constant_round(
            p, &P5S6_3, 67, P5_ROUND_RN, 69, P5_ROUND_RN);
        p = p5_wv_mul_round(p, square, 69, P5_ROUND_RN);
        p = p5_wv_add_constant_round(
            p, &P5S6_2, 67, P5_ROUND_RN, 69, P5_ROUND_RN);
        p = p5_wv_mul_round(p, square, 69, P5_ROUND_RN);
        p = p5_wv_add_constant_round(
            p, &P5S6_1, 67, P5_ROUND_RN, 65, P5_ROUND_RN);
        wv_t m = p5_wv_mul_round(p, square, 65, P5_ROUND_CHOP);

        int32_t product_e2 = m.e2 + magnitude.e2;
        int32_t scale = (
            product_e2 < magnitude.e2
            ? product_e2
            : magnitude.e2
        );
        u256 final = { 0, 0 };
        acc_add_product(
            &final, 0, magnitude.sig, 1, magnitude.e2, scale);
        acc_add_product(
            &final,
            m.sign,
            m.sig,
            magnitude.sig,
            product_e2,
            scale);
        return acc_round64_rc(final, scale, neg_out, rc);
    }

    wv_t square = p5_wv_mul_round(
        magnitude, magnitude, 67, P5_ROUND_CHOP);
    wv_t p = p5_constant_round(&P5S6_6, 67, P5_ROUND_RN);

    p = p5_wv_mul_round(p, square, 69, P5_ROUND_RN);
    p = p5_wv_add_constant_round(
        p, &P5S6_5, 67, P5_ROUND_RN, 69, P5_ROUND_RN);
    p = p5_wv_mul_round(p, square, 69, P5_ROUND_RN);
    p = p5_wv_add_constant_round(
        p, &P5S6_4, 67, P5_ROUND_RN, 69, P5_ROUND_RN);
    p = p5_wv_mul_round(p, square, 69, P5_ROUND_RN);
    p = p5_wv_add_constant_round(
        p, &P5S6_3, 67, P5_ROUND_RN, 69, P5_ROUND_RN);
    p = p5_wv_mul_round(p, square, 69, P5_ROUND_RN);
    p = p5_wv_add_constant_round(
        p, &P5S6_2, 64, P5_ROUND_AWAY, 64, P5_ROUND_RN);
    p = p5_wv_mul_round(p, square, 64, P5_ROUND_AWAY);
    p = p5_wv_add_constant_round(
        p, &P5S6_1, 67, P5_ROUND_RN, 67, P5_ROUND_RN);

    wv_t m = p5_wv_mul_round(p, square, 64, P5_ROUND_RN);
    wv_t correction = p5_wv_mul_round(
        m, magnitude, 67, P5_ROUND_CHOP);
    if (g_dump_internals)
        fprintf(stderr,
            "DI_HP neg_out=%d mag=" DIWF " sq=" DIWF " m=" DIWF
            " corr=" DIWF "\n",
            neg_out, DIW(magnitude), DIW(square), DIW(m),
            DIW(correction));
    p5c_t lead = { 0, magnitude.e2, magnitude.sig };
    p5c_t tail = {
        correction.sign, correction.e2, correction.sig
    };
    return p5_combine(
        &lead, &ZERO, &tail, &ONE, 0,
        neg_out, rc, &ZERO, NULL, 0);
}

/*
 * h119's directed-rounding/C1-constrained
 * standalone-FCOS direct-polynomial survivor.  This producer is also needed
 * by standalone FSIN after an odd-quadrant reduction, where sin(x) is formed
 * from cos(r).  As with the sine survivor, odd/away materializations are
 * equivalence representatives for an unresolved fixed-point datapath.
 *
 *   a2 = odd68(a*a) for FCOS; h121 selects away67 for the
 *        FSIN-internal cosine producer on independent sweep halves.
 *        Round 30 retains away68 in FMUL's lower normalization case.
 *   cosine coefficients = chop66, except C2 = chop65
 *   first four Horner products = chop66; fifth = RN65
 *          Round 33 conditionally retains a 67-bit round-to-odd carrier
 *   Horner sums = chop66 except the fourth = chop64; Round 32 uses chop65
 *                 at the fifth when its product is low-normalized+sticky
 *   tail = away72(q*a2); Round 31 uses chop71 when the exact product's
 *          retained 72-bit low bit is one
 *   result = architectural_round(1 + tail)
 */
static sf_t p5_fcos_standalone_direct(
    int neg_out, wv_t magnitude, sf_rc_t rc, int fsin_internal)
{
    if (g_round52_fcos_low3_carrier && !fsin_internal) {
        wv_t square = p5_wv_mul_round(
            magnitude, magnitude, 67, P5_ROUND_CHOP);
        wv_t fourth = p5_wv_mul_round(
            square, square, 67, P5_ROUND_CHOP);
#if G_F4PT
        /* EXPERIMENT (probe A2): shared-squarer hypothesis — the
         * R86 one-port truncation applied to the near-1 terminal
         * producer's fourth power (t4/rdisc/right derive from it). */
        {
            wv_t square64 = square;
            square64.sig &= ~(u128)7;
            fourth = p5_wv_mul_round(square, square64, 67, P5_ROUND_CHOP);
        }
#endif

        wv_t negative = {
            P5C6_5.sign, P5C6_5.exp2, P5C6_5.sig
        };
        negative = p5_wv_mul_round(
            fourth, negative, 67, P5_ROUND_CHOP);
        negative = p5_wv_add_round(
            (wv_t){ P5C6_3.sign, P5C6_3.exp2, P5C6_3.sig },
            negative,
            64,
            P5_ROUND_RN);
#if G_R1231CPAFADD || G_R1237CPAFADD || G_R1290FADDWORD \
    || G_R1297FADDBOOTH1 || G_R1299FADDLOWBIT
        int negative_add2_cpa = p5_r1231_product_cpa_bit(
            fourth.sig, negative.sig,
            G_R1237CPAFADD || G_R1290FADDWORD || G_R1297FADDBOOTH1
                || G_R1299FADDLOWBIT);
#endif
        negative = p5_wv_mul_round(
            fourth, negative, 67, P5_ROUND_CHOP);
        wv_t negative_add2_source = negative;
        negative = p5_wv_add_round(
            (wv_t){ P5C6_1.sign, P5C6_1.exp2, P5C6_1.sig },
            negative,
            64,
            P5_ROUND_RN);
        if (G_R1186FADD && p5_same_sign_half_history_class(
                (wv_t){ P5C6_1.sign, P5C6_1.exp2, P5C6_1.sig },
                negative_add2_source, 64, 1)) {
            negative.sig--;
            negative.rh = negative.sign ? 1 : -1;
        }
#if G_R1231CPAFADD || G_R1237CPAFADD || G_R1290FADDWORD \
    || G_R1297FADDBOOTH1 || G_R1299FADDLOWBIT
        if (p5_r1231_fadd_class(
                (wv_t){ P5C6_1.sign, P5C6_1.exp2, P5C6_1.sig },
                negative_add2_source, negative_add2_cpa)) {
            negative.sig--;
            negative.rh = negative.sign ? 1 : -1;
        }
#endif

        wv_t positive = {
            P5C6_6.sign, P5C6_6.exp2, P5C6_6.sig
        };
        positive = p5_wv_mul_round(
            fourth, positive, 67, P5_ROUND_CHOP);
        positive = p5_wv_add_round(
            (wv_t){ P5C6_4.sign, P5C6_4.exp2, P5C6_4.sig },
            positive,
            64,
            P5_ROUND_RN);
#if G_R1231CPAFADD || G_R1237CPAFADD || G_R1290FADDWORD \
    || G_R1297FADDBOOTH1 || G_R1299FADDLOWBIT
        int positive_add2_cpa = p5_r1231_product_cpa_bit(
            fourth.sig, positive.sig,
            G_R1237CPAFADD || G_R1290FADDWORD || G_R1297FADDBOOTH1
                || G_R1299FADDLOWBIT);
#endif
        positive = p5_wv_mul_round(
            fourth, positive, 67, P5_ROUND_CHOP);
        wv_t positive_add2_source = positive;
        positive = p5_wv_add_round(
            (wv_t){ P5C6_2.sign, P5C6_2.exp2, P5C6_2.sig },
            positive,
            64,
            P5_ROUND_RN);
        if (G_R1186FADD && p5_same_sign_half_history_class(
                (wv_t){ P5C6_2.sign, P5C6_2.exp2, P5C6_2.sig },
                positive_add2_source, 64, 0)) {
            positive.sig--;
            positive.rh = positive.sign ? 1 : -1;
        }
#if G_R1231CPAFADD || G_R1237CPAFADD || G_R1290FADDWORD \
    || G_R1297FADDBOOTH1 || G_R1299FADDLOWBIT
        if (p5_r1231_fadd_class(
                (wv_t){ P5C6_2.sign, P5C6_2.exp2, P5C6_2.sig },
                positive_add2_source, positive_add2_cpa)) {
            positive.sig--;
            positive.rh = positive.sign ? 1 : -1;
        }
#endif

        if (g_dump_internals)
            fprintf(stderr, "DI_POLY site=2883 odd=" DIWF " even=" DIWF
                " sq=" DIWF " f4=" DIWF " mag=" DIWF "\n",
                DIW(negative), DIW(positive), DIW(square), DIW(fourth),
                DIW(magnitude));
        wv_t correction = fcos_low3_terminal_correction(
            square, negative, positive, fourth, magnitude, 1, neg_out, rc);
        int32_t scale = correction.e2 < 0 ? correction.e2 : 0;
        u256 final = { 0, 0 };
        acc_add_product(&final, 0, 1, 1, 0, scale);
        acc_add_product(
            &final,
            correction.sign,
            correction.sig,
            1,
            correction.e2,
            scale);
        return acc_round64_rc(final, scale, neg_out, rc);
    }
    if (
        (g_round38_p6_cosine_split && !fsin_internal)
        || (g_round41_fsin_cosine_split && fsin_internal)
    ) {
        /*
         * h235 replays the two-chain cosine model:
         *
         *   negative = ((C10*x^4 + C6)*x^4 + C2)*x^2
         *   positive = ((C12*x^4 + C8)*x^4 + C4)*x^4
         *   result = architectural_round(1 + negative + positive)
         *
         * Coefficients retain h119's independently constrained effective
         * values.  Each carrier below materializes a multiply,
         * add/subtract, or final-rounding boundary in this numerical model.
         * h241 selects the same graph for FSIN's internal cosine, with the
         * final negative-chain multiply at RN67 and the last positive-chain
         * sum at away65.  Those two changes improve both structured halves
         * without worsening any earlier focused capture's aggregate score.
         */
        wv_t square = p5_wv_mul_round(
            magnitude, magnitude, 67, P5_ROUND_CHOP);
        if (g_perturb_tgt == 10)
            square.sig = (u128)((__int128)square.sig + g_perturb_delta);
        wv_t fourth = p5_wv_mul_round(
            square, square, 64, P5_ROUND_RN);
        if (g_perturb_tgt == 11)
            fourth.sig = (u128)((__int128)fourth.sig + g_perturb_delta);

        wv_t negative = p5_constant_round(
            &P5C6_5, 66, P5_ROUND_CHOP);
        negative = p5_wv_mul_round(
            negative, fourth, 67, P5_ROUND_CHOP);
        negative = p5_wv_add_constant_round(
            negative, &P5C6_3,
            66, P5_ROUND_CHOP, 67, P5_ROUND_CHOP);
        negative = p5_wv_mul_round(
            negative, fourth, 67, P5_ROUND_CHOP);
        negative = p5_wv_add_constant_round(
            negative, &P5C6_1,
            66, P5_ROUND_CHOP, 64, P5_ROUND_RN);
        negative = p5_wv_mul_round(
            negative,
            square,
            fsin_internal ? 67 : 68,
            P5_ROUND_RN);
        if (g_perturb_tgt == 12)
            negative.sig = (u128)((__int128)negative.sig + g_perturb_delta);

        wv_t positive = p5_constant_round(
            &P5C6_6, 66, P5_ROUND_CHOP);
        positive = p5_wv_mul_round(
            positive, fourth, 67, P5_ROUND_CHOP);
        positive = p5_wv_add_constant_round(
            positive, &P5C6_4,
            66, P5_ROUND_CHOP, 67, P5_ROUND_CHOP);
        positive = p5_wv_mul_round(
            positive, fourth, 67, P5_ROUND_CHOP);
        positive = p5_wv_add_constant_round(
            positive,
            &P5C6_2,
            65,
            P5_ROUND_CHOP,
            fsin_internal ? 65 : 66,
            fsin_internal ? P5_ROUND_AWAY : P5_ROUND_ODD);
        positive = p5_wv_mul_round(
            positive, fourth, 67, P5_ROUND_CHOP);
        if (g_perturb_tgt == 13)
            positive.sig = (u128)((__int128)positive.sig + g_perturb_delta);

        wv_t tail = p5_wv_add_round(
            negative, positive, 66, P5_ROUND_CHOP);
        if (g_perturb_tgt == 14)
            tail.sig = (u128)((__int128)tail.sig + g_perturb_delta);
        if (g_dump_internals)
            fprintf(stderr,
                "DI_H235 fsin_int=%d neg_out=%d mag=" DIWF " sq=" DIWF
                " f4=" DIWF " neg=" DIWF " pos=" DIWF " tail=" DIWF "\n",
                fsin_internal, neg_out, DIW(magnitude), DIW(square),
                DIW(fourth), DIW(negative), DIW(positive), DIW(tail));
        int32_t scale = tail.e2 < 0 ? tail.e2 : 0;
        u256 final = { 0, 0 };
        acc_add_product(&final, 0, 1, 1, 0, scale);
        acc_add_product(
            &final, tail.sign, tail.sig, 1, tail.e2, scale);
        return acc_round64_rc(final, scale, neg_out, rc);
    }

    int square_bits = fsin_internal ? 67 : 68;
    if (fsin_internal && g_round30_fsin_cosine_square) {
        u256 exact = u128_mul_full(magnitude.sig, magnitude.sig);
        int product_width = exact.hi
            ? 128 + u128_width(exact.hi)
            : u128_width(exact.lo);
        int operand_width = u128_width(magnitude.sig);
        int high_normalization = (
            product_width == 2 * operand_width
        );
        if (!high_normalization) square_bits = 68;
    }
    wv_t square = p5_wv_mul_round(
        magnitude,
        magnitude,
        square_bits,
        fsin_internal ? P5_ROUND_AWAY : P5_ROUND_ODD);
    wv_t q = p5_constant_round(&P5C6_6, 66, P5_ROUND_CHOP);

    q = p5_wv_mul_round(q, square, 66, P5_ROUND_CHOP);
    q = p5_wv_add_constant_round(
        q, &P5C6_5, 66, P5_ROUND_CHOP, 66, P5_ROUND_CHOP);
    q = p5_wv_mul_round(q, square, 66, P5_ROUND_CHOP);
    q = p5_wv_add_constant_round(
        q, &P5C6_4, 66, P5_ROUND_CHOP, 66, P5_ROUND_CHOP);
    q = p5_wv_mul_round(q, square, 66, P5_ROUND_CHOP);
    q = p5_wv_add_constant_round(
        q, &P5C6_3, 66, P5_ROUND_CHOP, 66, P5_ROUND_CHOP);
    q = p5_wv_mul_round(q, square, 66, P5_ROUND_CHOP);
    q = p5_wv_add_constant_round(
        q, &P5C6_2, 65, P5_ROUND_CHOP, 64, P5_ROUND_CHOP);
    int sum5_bits = 66;
    int product5_bits = 65;
    p5_round_t product5_mode = P5_ROUND_RN;
    if (
        fsin_internal
        && (
            g_round32_fsin_cosine_horner
            || g_round33_fsin_cosine_product
        )
    ) {
        u256 exact = u128_mul_full(q.sig, square.sig);
        int product_width = exact.hi
            ? 128 + u128_width(exact.hi)
            : u128_width(exact.lo);
        int operand_width = (
            u128_width(q.sig) + u128_width(square.sig)
        );
        int shift = product_width - 65;
        /*
         * These operands carry at most 66+68 bits, so every bit below the
         * 65-bit guard resides in exact.lo.
         */
        int sticky = (
            shift > 1
            && (
                exact.lo
                & (((u128)1 << (shift - 1)) - 1)
            )
        );
        int round32_condition = (
            product_width != operand_width && sticky
        );
        if (
            g_round32_fsin_cosine_horner
            && round32_condition
        )
            sum5_bits = 65;
        /*
         * h161 rejects applying the secondary selector at the sum.  h163
         * independently localizes it to this product.  The documented
         * P5 multiplier has a 67-bit normalized carrier; round-to-odd is
         * the sticky-preserving representative selected here.
         */
        if (
            g_round33_fsin_cosine_product
            && !round32_condition
            && shift >= 0
            && !((exact.lo >> shift) & 1)
            && (square.sig & 7) == 3
        ) {
            product5_bits = 67;
            product5_mode = P5_ROUND_ODD;
        }
    }
    q = p5_wv_mul_round(
        q, square, product5_bits, product5_mode);
    q = p5_wv_add_constant_round(
        q,
        &P5C6_1,
        66,
        P5_ROUND_CHOP,
        sum5_bits,
        P5_ROUND_CHOP);

    wv_t tail;
    if (fsin_internal && g_round31_fsin_cosine_tail) {
        wv_t top72 = p5_wv_mul_round(
            q, square, 72, P5_ROUND_CHOP);
        tail = (
            top72.sig & 1
            ? p5_wv_mul_round(
                q, square, 71, P5_ROUND_CHOP)
            : p5_wv_mul_round(
                q, square, 72, P5_ROUND_AWAY)
        );
    } else {
        tail = p5_wv_mul_round(
            q, square, 72, P5_ROUND_AWAY);
    }
    if (g_dump_internals)
        fprintf(stderr,
            "DI_H119 fsin_int=%d neg_out=%d mag=" DIWF " sq=" DIWF
            " q=" DIWF " tail=" DIWF "\n",
            fsin_internal, neg_out, DIW(magnitude), DIW(square),
            DIW(q), DIW(tail));
    int32_t scale = tail.e2 < 0 ? tail.e2 : 0;
    u256 final = { 0, 0 };
    acc_add_product(&final, 0, 1, 1, 0, scale);
    acc_add_product(
        &final, tail.sign, tail.sig, 1, tail.e2, scale);
    return acc_round64_rc(final, scale, neg_out, rc);
}

/*
 * standalone FSIN's tiny-input directed-rounding
 * rule from the full h116 sweep.  For -68 <= exponent <= -33 the hidden
 * correction is too small to affect RN but remains nonzero for architectural
 * directed rounding.  At exponent <= -69 silicon returns the operand in all
 * modes (while still reporting inexact in the status word).
 */
static sf_t p5_fsin_standalone_tiny(sf_t x, sf_rc_t rc)
{
    if (x.exp < -68) return x;
    int decrement_magnitude = (
        rc == SF_RZ
        || (rc == SF_RD && !x.sign)
        || (rc == SF_RU && x.sign)
    );
    if (!decrement_magnitude) return x;
    if (x.sig > 0x8000000000000000ull) {
        x.sig--;
    } else {
        x.exp--;
        x.sig = UINT64_MAX;
    }
    return x;
}

/* p5 kernel entry: r as sf (64-bit; wide handled upstream), i1/i0 quadrant */
static sf_t p5_kernel(
    sf_t r, sf_t c, int i1, int i0, sf_rc_t rc, int reduced)
{
    /* exact wide reduced argument (subsumes c; h39: 2x better than
     * first-order c-injection on reduced inputs).  --rcfold replaces
     * the sign-of-c half-ulp injection with a true B-bit rounding of
     * r+c (B10 experiment). */
    if (g_dump_internals)
        fprintf(stderr,
            "DI_RC r=%d:%d:%016llx c=%d:%d:%016llx czero=%d\n",
            (int)r.sign, r.exp, (unsigned long long)r.sig,
            (int)c.sign, c.exp, (unsigned long long)c.sig,
            c.sig == 0);
    wv_t rw = g_rcfold_bits
        ? wv_from_rc_wide(&r, &c, g_rcfold_bits, g_rcfold_rn)
        : wv_from_rc(&r, &c);
    if (g_perturb_tgt == 7)
        rw.sig = (u128)((__int128)rw.sig + g_perturb_delta);
    if (g_dump_internals)
        fprintf(stderr, "DI_RW i1=%d i0=%d rsign=%d rw=" DIWF "\n",
            i1, i0, (int)r.sign, DIW(rw));
    sf_t a_abs = sf_abs(&r);
    double rf = (double)a_abs.sig * pow(2.0, (double)(a_abs.exp - 63));
    if (rf < 0.25) {          /* pure 6-term polynomial region [2^-3, 1/4) */
        int standalone = (
            g_fsin_standalone_path || g_fcos_standalone_path
        );
        if (
            !i1
            && (
                g_fsin_standalone_path
                || (
                    g_round42_p6_sine_split
                    && g_fcos_standalone_path
                )
            )
        ) {
            wv_t magnitude = { 0, rw.e2, rw.sig };
            return p5_fsin_standalone_direct(
                magnitude, (r.sign ^ i0) & 1, rc, reduced);
        }
        if (standalone && i1) {
            wv_t magnitude = { 0, rw.e2, rw.sig };
            return p5_fcos_standalone_direct(
                i0 & 1, magnitude, rc, g_fsin_standalone_path);
        }
        if (g_round18_poly) {
            /*
             * Round-18 plus h70-h74 constraint survivor:
             *   asq = chop67(r*r)
             *   p = RN64 fused Horner using native ROM constants
             *   q final = RN64(chop67(q*asq) + C1)
             *   sin correction = chop67(RN64(p*asq)*r)
             *   cos tail      = chop67(q*asq)
             * followed by the architectural RC-controlled result rounding.
             */
            wv_t mag = { 0, rw.e2, rw.sig };
            wv_t asq67 = wv_mul_round_bits(
                mag.sig, mag.e2, 0, mag.sig, mag.e2, 0, 67, 0);
            wv_t pv = {
                P5S6_6.sign, P5S6_6.exp2, P5S6_6.sig
            };
            sf_t p = p5_wv_fma_c_rn64(pv, asq67, &P5S6_5);
            pv = (wv_t){ p.sign, p.exp - 63, p.sig };
            p = p5_wv_fma_c_rn64(pv, asq67, &P5S6_4);
            pv = (wv_t){ p.sign, p.exp - 63, p.sig };
            p = p5_wv_fma_c_rn64(pv, asq67, &P5S6_3);
            pv = (wv_t){ p.sign, p.exp - 63, p.sig };
            p = p5_wv_fma_c_rn64(pv, asq67, &P5S6_2);
            pv = (wv_t){ p.sign, p.exp - 63, p.sig };
            p = p5_wv_fma_c_rn64(pv, asq67, &P5S6_1);

            wv_t qv = {
                P5C6_6.sign, P5C6_6.exp2, P5C6_6.sig
            };
            sf_t q = p5_wv_fma_c_rn64(qv, asq67, &P5C6_5);
            qv = (wv_t){ q.sign, q.exp - 63, q.sig };
            q = p5_wv_fma_c_rn64(qv, asq67, &P5C6_4);
            qv = (wv_t){ q.sign, q.exp - 63, q.sig };
            q = p5_wv_fma_c_rn64(qv, asq67, &P5C6_3);
            qv = (wv_t){ q.sign, q.exp - 63, q.sig };
            q = p5_wv_fma_c_rn64(qv, asq67, &P5C6_2);
            qv = (wv_t){ q.sign, q.exp - 63, q.sig };
            /*
             * h70-h74: the last q-Horner multiply is materialized by
             * magnitude chop at 67 bits before the coefficient add:
             *   q = RN64(chop67(q*asq) + C1)
             * Applying the same rule at every q edge is architecturally
             * equivalent on all current discriminators; this minimum-change
             * representative is independently exact on h65, h71, and h74.
             */
            qv = wv_mul_round_bits(
                qv.sig, qv.e2, qv.sign,
                asq67.sig, asq67.e2, asq67.sign,
                67, 0);
            q = p5_wv_fma_c_rn64(
                qv, (wv_t){ 0, 0, 1 }, &P5C6_1);

            if (!i1) {
                wv_t m = wv_mul_round_bits(
                    p.sig, p.exp - 63, p.sign,
                    asq67.sig, asq67.e2, asq67.sign,
                    64, 1);
                wv_t correction = wv_mul_round_bits(
                    m.sig, m.e2, m.sign,
                    mag.sig, mag.e2, mag.sign,
                    67, 0);
                p5c_t lead = { 0, mag.e2, mag.sig };
                p5c_t corr = {
                    correction.sign,
                    correction.e2,
                    correction.sig
                };
                return p5_combine(
                    &lead, &ZERO, &corr, &ONE, 0,
                    (r.sign ^ i0) & 1, rc, &ZERO, NULL, 0);
            } else {
                wv_t tail = wv_mul_round_bits(
                    q.sig, q.exp - 63, q.sign,
                    asq67.sig, asq67.e2, asq67.sign,
                    67, 0);
                p5c_t one = { 0, 0, 1 };
                p5c_t corr = { tail.sign, tail.e2, tail.sig };
                return p5_combine(
                    &one, &ZERO, &corr, &ONE, 0,
                    i0 & 1, rc, &ZERO, NULL, 0);
            }
        }
        /* Empirically identified finals (rounds 10-11): the LAST operation is
        * a single fused rounding:
        *   sin = RN(r + w*r + c),  w = RN64(P(rsq)*rsq)   (Horner @64)
        *   cos = RN(1 + Q(rsq)*rsq - c*r)                 (q*rsq unrounded)
        */
        sf_t rsq = wv_sq_rn64(&rw);
        sf_t p = sf_zero(0), q = sf_zero(0);
        /* sine Horner to c3 */
        p = p5_mul_c(&rsq, &P5S6_6); p = p5_add_c(&p, &P5S6_5);
        p = sf_fma(&p, &rsq, &ZERO); p = p5_add_c(&p, &P5S6_4);
        p = sf_fma(&p, &rsq, &ZERO); p = p5_add_c(&p, &P5S6_3);
        p = sf_fma(&p, &rsq, &ZERO); p = p5_add_c(&p, &P5S6_2);
        p = sf_fma(&p, &rsq, &ZERO); p = p5_add_c(&p, &P5S6_1);
        q = p5_mul_c(&rsq, &P5C6_6); q = p5_add_c(&q, &P5C6_5);
        q = sf_fma(&q, &rsq, &ZERO); q = p5_add_c(&q, &P5C6_4);
        q = sf_fma(&q, &rsq, &ZERO); q = p5_add_c(&q, &P5C6_3);
        q = sf_fma(&q, &rsq, &ZERO); q = p5_add_c(&q, &P5C6_2);
        q = sf_fma(&q, &rsq, &ZERO); q = p5_add_c(&q, &P5C6_1);
        /* fused finals via the u256 accumulator: lead + prodA + prodB */
        if (!i1) {
            sf_t w = sf_fma(&p, &rsq, &ZERO);         /* w = RN64(p*rsq) */
            /* sin = fused(rw + w*rw), output sign r.sign^i0 */
            p5c_t lead = { 0, rw.e2, rw.sig };
            return p5_combine(&lead, &w, &lead, &ZERO, 0,
                              (r.sign ^ i0) & 1, rc, &ZERO, NULL, 0);
        } else {
            /* cos = fused(1 + q*rsq): q via the S-slot so q*rsq stays exact
             * inside the fusion (T2 = q wide, S = rsq 64-bit) */
            p5c_t onec = { 0, -63, (u128)(1ull << 63) };
            p5c_t qc = { q.sign, q.exp - 63, (u128)q.sig };
            return p5_combine(&onec, &ZERO, &qc, &rsq, 0,
                              i0 & 1, rc, &ZERO, NULL, 1);
        }
    }
    int b;
    if (rf < 0.5) b = 18 + 4 * (int)((rf - 0.25) / (4.0 / 64.0));
    else { int k = (int)((rf - 0.5) / (8.0 / 64.0)); if (k > 2) k = 2; b = 36 + 8 * k; }
    int ti = 0; while (P5TAB[ti].b != b) ti++;
    int six = b >= 36;
    /* a = r - b (exact) */
    sf_t bb; bb.cls = SF_FIN; bb.sign = r.sign; bb.exp = 0; bb.sig = 0;
    {
        int bl = 0; { int t = b; while (t >>= 1) bl++; }
        bb.exp = bl - 6; bb.sig = (uint64_t)b << (63 - bl);
    }
    /* wide a = |rw| - b (exact); polys on wide a; S = RN64(aw + w*aw) */
    wv_t aw;
    {
        int sh = -6 - rw.e2;
        __int128 av = (__int128)rw.sig - (__int128)(((u128)b) << sh);
        aw.sign = (uint8_t)(av < 0); aw.sig = av < 0 ? (u128)(-av) : (u128)av;
        aw.e2 = rw.e2;
    }
    (void)bb;
    sf_t asq = wv_sq_rn64(&aw);
    sf_t S, t = ZERO;
    wv_t t_wide = { 0, 0, 0 };
    wv_t q_asq_wide = { 0, 0, 0 };
    int use_wide_t = 0;
    int use_round19_q = 0;
    int use_round35_p = 0;
    wv_t round35_p = { 0, 0, 0 };
    wv_t p6_square = { 0, 0, 0 };
    wv_t p6_p_square = { 0, 0, 0 };
    int p6_sine_top_exponent = 0;
    int p6_sine_exponent_difference = 0;
    {
        sf_t p, q;
        if (six) {
            if (g_round37_p6_four_term) {
                p5c_t p6s4_4 = P5S4_4;
                p6s4_4.sig -= (u128)1 << 60;
                p6_square = p5_wv_mul_round(
                    aw, aw, 67, P5_ROUND_CHOP);
                p = fsincos_compat_p6_horner4(
                    &p6s4_4, &P5S4_3, &P5S4_2, &P5S4_1,
                    &p6_square);
                q = fsincos_compat_p6_horner4(
                    &P5C4_4, &P5C4_3, &P5C4_2, &P5C4_1,
                    &p6_square);
            } else {
            p = p5_mul_c(&asq, &P5S6_6); p = p5_add_c(&p, &P5S6_5);
            p = sf_fma(&p, &asq, &ZERO); p = p5_add_c(&p, &P5S6_4);
            p = sf_fma(&p, &asq, &ZERO); p = p5_add_c(&p, &P5S6_3);
            p = sf_fma(&p, &asq, &ZERO); p = p5_add_c(&p, &P5S6_2);
            p = sf_fma(&p, &asq, &ZERO);
            /*
             * h135 independently validates standalone FSIN's path split:
             * the direct table entry materializes the terminal wide P
             * coefficient away64, while the reduced entry retains RN67.
             */
            if (g_round35_table_p_terminal) {
                /*
                 * h188-h189's terminal wide-P
                 * producer.  The fresh pairwise Skylake discriminator
                 * selects away64(P5S6_1) followed by a chopped 65-bit sum
                 * for both direct and reduced entries.  Keep the 65th bit
                 * through the following RN64 p*a^2 product.
                 */
                wv_t pv = { p.sign, p.exp - 63, p.sig };
                round35_p = p5_wv_add_constant_round(
                    pv, &P5S6_1, 64, P5_ROUND_AWAY,
                    65, P5_ROUND_CHOP);
                p = wv_rn64(round35_p);
                use_round35_p = 1;
            } else if (
                g_fsin_standalone_path
                && g_fsin_table_terminal
                && !reduced
            ) {
                wv_t pv = { p.sign, p.exp - 63, p.sig };
                p = wv_rn64(p5_wv_add_constant_round(
                    pv, &P5S6_1, 64, P5_ROUND_AWAY,
                    64, P5_ROUND_RN));
            } else {
                p = p5_add_c(&p, &P5S6_1);
            }
            if (g_round19_wide_q) {
                q_asq_wide = wv_mul_round_bits(
                    aw.sig, aw.e2, aw.sign,
                    aw.sig, aw.e2, aw.sign,
                    67, 0);
                wv_t qv = {
                    P5C6_6.sign, P5C6_6.exp2, P5C6_6.sig
                };
                q = p5_wv_fma_c_rn64(qv, q_asq_wide, &P5C6_5);
                qv = (wv_t){ q.sign, q.exp - 63, q.sig };
                q = p5_wv_fma_c_rn64(qv, q_asq_wide, &P5C6_4);
                qv = (wv_t){ q.sign, q.exp - 63, q.sig };
                q = p5_wv_fma_c_rn64(qv, q_asq_wide, &P5C6_3);
                qv = (wv_t){ q.sign, q.exp - 63, q.sig };
                q = p5_wv_fma_c_rn64(qv, q_asq_wide, &P5C6_2);
                qv = (wv_t){ q.sign, q.exp - 63, q.sig };
                q = p5_wv_fma_c_rn64(qv, q_asq_wide, &P5C6_1);
                use_round19_q = 1;
            } else {
                q = p5_mul_c(&asq, &P5C6_6); q = p5_add_c(&q, &P5C6_5);
                q = sf_fma(&q, &asq, &ZERO); q = p5_add_c(&q, &P5C6_4);
                q = sf_fma(&q, &asq, &ZERO); q = p5_add_c(&q, &P5C6_3);
                q = sf_fma(&q, &asq, &ZERO); q = p5_add_c(&q, &P5C6_2);
                q = sf_fma(&q, &asq, &ZERO);
                /*
                 * Unlike P, h135 selects terminal Q away64 on both direct
                 * and M66-reduced standalone-FSIN table entries.
                 */
                if (
                    g_fsin_standalone_path
                    && g_fsin_table_terminal
                ) {
                    wv_t qv = { q.sign, q.exp - 63, q.sig };
                    q = wv_rn64(p5_wv_add_constant_round(
                        qv, &P5C6_1, 64, P5_ROUND_AWAY,
                        64, P5_ROUND_RN));
                } else {
                    q = p5_add_c(&q, &P5C6_1);
                }
            }
            }
        } else {
            if (g_round37_p6_four_term) {
                p5c_t p6s4_4 = P5S4_4;
                p6s4_4.sig -= (u128)1 << 60;
                p6_square = p5_wv_mul_round(
                    aw, aw, 67, P5_ROUND_CHOP);
                p = fsincos_compat_p6_horner4(
                    &p6s4_4, &P5S4_3, &P5S4_2, &P5S4_1,
                    &p6_square);
                q = fsincos_compat_p6_horner4(
                    &P5C4_4, &P5C4_3, &P5C4_2, &P5C4_1,
                    &p6_square);
            } else {
                p5c_t p5s4_1 = P5S4_1;
                if (g_round23_narrow_coefficient)
                    p5s4_1.sig += ROUND23_P5S4_1_DELTA;
                p = p5_mul_c(&asq, &P5S4_4); p = p5_add_c(&p, &P5S4_3);
                p = sf_fma(&p, &asq, &ZERO); p = p5_add_c(&p, &P5S4_2);
                p = sf_fma(&p, &asq, &ZERO);
                /*
                 * The direct narrow entry's corresponding terminal P
                 * materialization is chop64; reduced narrow stays at RN67.
                 */
                if (
                    g_fsin_standalone_path
                    && g_fsin_table_terminal
                    && !reduced
                ) {
                    wv_t pv = { p.sign, p.exp - 63, p.sig };
                    p = wv_rn64(p5_wv_add_constant_round(
                        pv, &p5s4_1, 64, P5_ROUND_CHOP,
                        64, P5_ROUND_RN));
                } else {
                    p = p5_add_c(&p, &p5s4_1);
                }
                q = p5_mul_c(&asq, &P5C4_4); q = p5_add_c(&q, &P5C4_3);
                q = sf_fma(&q, &asq, &ZERO); q = p5_add_c(&q, &P5C4_2);
                q = sf_fma(&q, &asq, &ZERO); q = p5_add_c(&q, &P5C4_1);
            }
        }
        if (!six && g_round16_narrow && !g_round37_p6_four_term) {
            wv_t m = wv_mul_round_bits(
                (u128)p.sig, p.exp - 63, p.sign,
                (u128)asq.sig, asq.exp - 63, asq.sign,
                69, 1);
            wv_t u = wv_one_plus_round(m, 68, 0);
            wv_t sw = wv_mul_round_bits(
                aw.sig, aw.e2, aw.sign, u.sig, u.e2, u.sign, 64, 1);
            S = wv_rn64(sw);
            t_wide = wv_mul_round_bits(
                (u128)q.sig, q.exp - 63, q.sign,
                (u128)asq.sig, asq.exp - 63, asq.sign,
                66, 0);
            use_wide_t = 1;
        } else {
            sf_t w1;
            if (g_round37_p6_four_term) {
                wv_t p64 = { p.sign, p.exp - 63, (u128)p.sig };
                p6_p_square = p5_wv_mul_round(
                    p64, p6_square, 67, P5_ROUND_CHOP);
            } else if (use_round35_p) {
                wv_t square64 = {
                    asq.sign, asq.exp - 63, (u128)asq.sig
                };
                w1 = wv_rn64(p5_wv_mul_round(
                    round35_p, square64, 64, P5_ROUND_RN));
            } else {
                w1 = sf_fma(&p, &asq, &ZERO);
            }
            if (g_round37_p6_four_term) {
                wv_t sine_correction = p5_wv_mul_round(
                    p6_p_square, aw, 67, P5_ROUND_CHOP);
                int a_width = u128_width(aw.sig);
                int correction_width = u128_width(sine_correction.sig);
                p6_sine_top_exponent = aw.e2 + a_width - 1;
                p6_sine_exponent_difference =
                    (aw.e2 + a_width - 1)
                    - (sine_correction.e2 + correction_width - 1);
                if (p6_sine_exponent_difference < 0)
                    p6_sine_exponent_difference =
                        -p6_sine_exponent_difference;
                if (g_round51_fsin_fadd_signature) {
                    wv_t p6_a = p5_wv_mul_round(
                        aw, (wv_t){ 0, 0, 1 },
                        67, P5_ROUND_CHOP);
                    S = wv_rn64(fsin_operation_class_sine_state(
                        p6_a, sine_correction));
                } else {
                    S = wv_rn64(p5_wv_add_round(
                        aw, sine_correction, 64, P5_ROUND_RN));
                }
            } else {
                sf_t w = wv_mul_sf_rn64(&w1, &aw);
                S = wv_add_sf_rn64(&aw, &w);
            }
            if (g_round37_p6_four_term) {
                wv_t q64 = { q.sign, q.exp - 63, (u128)q.sig };
                t = wv_rn64(p5_wv_mul_round(
                    q64, p6_square, 64, P5_ROUND_RN));
            } else if (use_round19_q) {
                wv_t qt = wv_mul_round_bits(
                    q.sig, q.exp - 63, q.sign,
                    q_asq_wide.sig, q_asq_wide.e2, q_asq_wide.sign,
                    64, 1);
                t = wv_rn64(qt);
            } else {
                t = sf_fma(&q, &asq, &ZERO);
            }
        }
    }
    sf_t res;
    /*
     * Round-21 paired-cell tomography candidate: retain a small
     * family-specific correction below the reconstructed 64-bit S state:
     *
     *   narrow: S' = S - sign(S) * 4/32 ulp64(S)
     *   wide:   S' = S - sign(S) * 5/32 ulp64(S)
     *
     * h78's best-constrained inequalities separately center dS at about
     * 0.10/0.14 ulp toward zero while dU remains near zero.  h79 validates
     * the corresponding binary grid points across narrow/wide dense, h59,
     * h67, and paired h78 captures.  Keep it explicit until a physical
     * producer operation, rather than this equivalent state representation,
     * is identified.
     */
    sf_t s_bias = ZERO;
    int table_bias = six
        ? g_round21_wide_bias
        : g_round21_narrow_bias;
    int table_bias_denominator_bits = 5;
    if (
        g_round37_p6_four_term
        && six
        && (
            (
                g_round43_p6_sine_bias
                && p6_sine_top_exponent == -5
                && p6_sine_exponent_difference == 13
            )
            || (
                g_round44_p6_sine_bias
                && p6_sine_top_exponent == -6
                && p6_sine_exponent_difference == 15
            )
        )
    )
        table_bias = 3;
    if (
        g_round45_p6_sine_fraction
        && g_round37_p6_four_term
        && six
        && p6_sine_top_exponent == -6
        && p6_sine_exponent_difference == 15
    ) {
        table_bias = 21;
        table_bias_denominator_bits = 8;
    }
    if (
        g_round46_p6_narrow_sine_fraction
        && g_round37_p6_four_term
        && !six
        && p6_sine_top_exponent == -6
        && p6_sine_exponent_difference == 15
    ) {
        table_bias = 29;
        table_bias_denominator_bits = 8;
    }
    if (
        g_round47_p6_narrow_sine_fraction
        && g_round37_p6_four_term
        && !six
        && p6_sine_top_exponent == -8
        && p6_sine_exponent_difference == 19
    ) {
        table_bias = 30;
        table_bias_denominator_bits = 8;
    }
    if (
        g_round48_p6_narrow_sine_fraction
        && g_round37_p6_four_term
        && !six
        && p6_sine_top_exponent == -7
        && p6_sine_exponent_difference == 17
    ) {
        table_bias = 34;
        table_bias_denominator_bits = 8;
    }
    /* h405 analysis leaf: candidate fraction at the uncovered narrow
     * coordinate (-6,14) exposed by the h377 exponent-7 residual. */
    if (
        g_round55_narrow_fraction14 >= 0
        && g_round37_p6_four_term
        && !six
        && p6_sine_top_exponent == -6
        && p6_sine_exponent_difference == 14
    ) {
        table_bias = g_round55_narrow_fraction14;
        table_bias_denominator_bits = 8;
    }
    if (table_bias > 0 && table_bias <= 64 && S.sig) {
        unsigned numerator = (unsigned)table_bias;
        int width = 0;
        for (unsigned value = numerator; value; value >>= 1) width++;
        s_bias.cls = SF_FIN;
        s_bias.sign = S.sign ^ 1;
        s_bias.exp = S.exp - 64 - table_bias_denominator_bits + width;
        s_bias.sig = (uint64_t)numerator << (64 - width);
    }
    if (!i1) {   /* sine of |r| (wide argument already in S) */
        if (g_round37_p6_four_term) {
            res = fsincos_compat_p6_combine_full_sine(
                &P5TAB[ti].sinT, &t, &P5TAB[ti].cosT, &S, 0,
                (r.sign ^ i0) & 1, rc, &s_bias,
                g_round49_p6_carrier_interval,
                g_round49_correction_delta);
        } else if (
            !six
            && !use_wide_t
            && g_round24_table_delta_rn67
            && (g_round28_tang_narrow || g_round29_p5_fmul_route)
        ) {
            wv_t tw = { t.sign, t.exp - 63, (u128)t.sig };
            if (g_round29_p5_fmul_route) {
                res = fsincos_p5_combine_tang_narrow_p5_route(
                    &P5TAB[ti].sinT, &tw, &P5TAB[ti].cosT, &S, &aw, 0,
                    (r.sign ^ i0) & 1, rc, &s_bias, reduced);
            } else {
                res = fsincos_p5_combine_tang_narrow_away64(
                    &P5TAB[ti].sinT, &tw, &P5TAB[ti].cosT, &S, &aw, 0,
                    (r.sign ^ i0) & 1, rc, &s_bias);
            }
        } else if (
            six
            && g_round34_table_lookup_firc
            && g_round24_table_delta_rn67
        ) {
            wv_t tw = use_wide_t
                ? t_wide
                : (wv_t){ t.sign, t.exp - 63, (u128)t.sig };
            if (g_round36_table_fadd_microcontrol) {
                res = fsincos_p5_combine_fadd_microcontrol(
                    &P5TAB[ti].sinT, &tw,
                    &P5TAB[ti].cosT, &S, &aw, 0,
                    (r.sign ^ i0) & 1, rc, &s_bias);
            } else {
                res = fsincos_p5_combine_tang_lookup_p_rn64(
                    &P5TAB[ti].sinT, &tw,
                    &P5TAB[ti].cosT, &S, &aw, 0,
                    (r.sign ^ i0) & 1, rc, &s_bias);
            }
        } else if (use_wide_t && g_round24_table_delta_rn67)
            res = p5_combine_delta_rn67_wide_t(
                &P5TAB[ti].sinT, &t_wide, &P5TAB[ti].cosT, &S, 0,
                (r.sign ^ i0) & 1, rc, &s_bias, &P5TAB[ti].cosT, 0);
        else if (use_wide_t)
            res = p5_combine_wide_t(
                &P5TAB[ti].sinT, &t_wide, &P5TAB[ti].cosT, &S, 0,
                (r.sign ^ i0) & 1, rc, &s_bias, &P5TAB[ti].cosT, 0);
        else if (g_round24_table_delta_rn67)
            res = p5_combine_delta_rn67(
                &P5TAB[ti].sinT, &t, &P5TAB[ti].cosT, &S, 0,
                (r.sign ^ i0) & 1, rc, &s_bias, &P5TAB[ti].cosT, 0);
        else
            res = p5_combine(
                &P5TAB[ti].sinT, &t, &P5TAB[ti].cosT, &S, 0,
                (r.sign ^ i0) & 1, rc, &s_bias, &P5TAB[ti].cosT, 0);
    } else {     /* cosine of |r| */
        if (g_round37_p6_four_term) {
            res = fsincos_compat_p6_combine_full_sine(
                &P5TAB[ti].cosT, &t, &P5TAB[ti].sinT, &S, 1,
                i0 & 1, rc, &s_bias,
                g_round49_p6_carrier_interval,
                g_round49_correction_delta);
        } else if (
            !six
            && !use_wide_t
            && g_round24_table_delta_rn67
            && (g_round28_tang_narrow || g_round29_p5_fmul_route)
        ) {
            wv_t tw = { t.sign, t.exp - 63, (u128)t.sig };
            if (g_round29_p5_fmul_route) {
                res = fsincos_p5_combine_tang_narrow_p5_route(
                    &P5TAB[ti].cosT, &tw, &P5TAB[ti].sinT, &S, &aw, 1,
                    i0 & 1, rc, &s_bias, reduced);
            } else {
                res = fsincos_p5_combine_tang_narrow_away64(
                    &P5TAB[ti].cosT, &tw, &P5TAB[ti].sinT, &S, &aw, 1,
                    i0 & 1, rc, &s_bias);
            }
        } else if (
            six
            && g_round34_table_lookup_firc
            && g_round24_table_delta_rn67
        ) {
            wv_t tw = use_wide_t
                ? t_wide
                : (wv_t){ t.sign, t.exp - 63, (u128)t.sig };
            if (g_round36_table_fadd_microcontrol) {
                res = fsincos_p5_combine_fadd_microcontrol(
                    &P5TAB[ti].cosT, &tw,
                    &P5TAB[ti].sinT, &S, &aw, 1,
                    i0 & 1, rc, &s_bias);
            } else {
                res = fsincos_p5_combine_tang_lookup_p_rn64(
                    &P5TAB[ti].cosT, &tw,
                    &P5TAB[ti].sinT, &S, &aw, 1,
                    i0 & 1, rc, &s_bias);
            }
        } else if (use_wide_t && g_round24_table_delta_rn67)
            res = p5_combine_delta_rn67_wide_t(
                &P5TAB[ti].cosT, &t_wide, &P5TAB[ti].sinT, &S, 1,
                i0 & 1, rc, &s_bias, &P5TAB[ti].sinT, 1);
        else if (use_wide_t)
            res = p5_combine_wide_t(
                &P5TAB[ti].cosT, &t_wide, &P5TAB[ti].sinT, &S, 1,
                i0 & 1, rc, &s_bias, &P5TAB[ti].sinT, 1);
        else if (g_round24_table_delta_rn67)
            res = p5_combine_delta_rn67(
                &P5TAB[ti].cosT, &t, &P5TAB[ti].sinT, &S, 1,
                i0 & 1, rc, &s_bias, &P5TAB[ti].sinT, 1);
        else
            res = p5_combine(
                &P5TAB[ti].cosT, &t, &P5TAB[ti].sinT, &S, 1,
                i0 & 1, rc, &s_bias, &P5TAB[ti].sinT, 1);
    }
    return res;
}

/*
 * h260/h264 reconstructed FPTAN arithmetic.
 * Every ordinary multiply and subtract uses magnitude chop67, Horner adds
 * use RN64, and the multiply-class sine scaling uses RN64.  Table inputs
 * read the complete sine state through its 64-bit materialization before
 * reconstruction.  The final quotient is rounded directly under the x87
 * architectural rounding control.
 */
static wv_t fptan_horner6(
    const p5c_t *c6, const p5c_t *c5, const p5c_t *c4,
    const p5c_t *c3, const p5c_t *c2, const p5c_t *c1,
    wv_t square)
{
    const p5c_t *coefficients[] = { c5, c4, c3, c2, c1 };
    wv_t value = { c6->sign, c6->exp2, c6->sig };
    for (unsigned index = 0; index < 5; index++) {
        value = p5_wv_mul_round(
            value, square, 67, P5_ROUND_CHOP);
        wv_t constant = {
            coefficients[index]->sign,
            coefficients[index]->exp2,
            coefficients[index]->sig
        };
        value = p5_wv_add_round(
            value, constant, 64, P5_ROUND_RN);
    }
    return value;
}

/* h260 shared reconstructed subtract class. */
static wv_t fptan_sub_chop67(wv_t left, wv_t right)
{
    right.sign ^= 1;
    return p5_wv_add_round(left, right, 67, P5_ROUND_CHOP);
}

/* quadrant rotation for the FPTAN quotient pair. */
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
static void fptan_polynomial_values(
    wv_t magnitude, int residual_sign, int64_t signed_n,
    wv_t *numerator, wv_t *denominator)
{
    wv_t square = p5_wv_mul_round(
        magnitude, magnitude, 67, P5_ROUND_CHOP);
    wv_t p = fptan_horner6(
        &P5S6_6, &P5S6_5, &P5S6_4,
        &P5S6_3, &P5S6_2, &P5S6_1, square);
    wv_t q = fptan_horner6(
        &P5C6_6, &P5C6_5, &P5C6_4,
        &P5C6_3, &P5C6_2, &P5C6_1, square);
    wv_t p_square = p5_wv_mul_round(
        square, p, 64, P5_ROUND_RN);
    wv_t q_square = p5_wv_mul_round(
        square, q, 67, P5_ROUND_CHOP);
    wv_t sine_tail = p5_wv_mul_round(
        magnitude, p_square, 67, P5_ROUND_CHOP);
    wv_t sine = p5_wv_add_round(
        magnitude, sine_tail, 67, P5_ROUND_CHOP);
    wv_t one = { 0, -63, (u128)1 << 63 };
    wv_t cosine = p5_wv_add_round(
        one, q_square, 67, P5_ROUND_CHOP);
    sine.sign ^= residual_sign ? 1 : 0;
    fptan_rotate(&sine, &cosine, signed_n);
    *numerator = sine;
    *denominator = cosine;
}

/* h260 four-coefficient table quotient pair. */
static void fptan_table_values(
    wv_t residual, int residual_sign, int64_t signed_n,
    wv_t *numerator, wv_t *denominator)
{
    int b;
    if (g_round66_fptan_lane_exact) {
        /* Round 66: exact top-3-bit lane slice — the FPTAN twin of
         * the Round-62 trig fix.  The double-precision classifier
         * below misrounds the top ~2^-55 sliver under each interior
         * lane boundary (5/16, 3/8, 7/16, 1/2, 5/8, 3/4) into the
         * next lane (i7 hardware probes, 2026-08-15). */
        int rw = u128_width(residual.sig);
        int rexp = residual.e2 + rw - 1;
        int lane = (int)(u128)(residual.sig >> (rw - 3)) - 4;
        if (rexp <= -2) {
            b = 18 + 4 * lane;
        } else {
            if (lane > 2) lane = 2;
            b = 36 + 8 * lane;
        }
    } else {
        double rf = (double)residual.sig
            * pow(2.0, (double)residual.e2);
        if (rf < 0.5) {
            b = 18 + 4 * (int)((rf - 0.25) / (4.0 / 64.0));
        } else {
            int lane = (int)((rf - 0.5) / (8.0 / 64.0));
            if (lane > 2) lane = 2;
            b = 36 + 8 * lane;
        }
    }
    int table_index = 0;
    while (P5TAB[table_index].b != b) table_index++;

    int shift = -6 - residual.e2;
    __int128 difference = (__int128)residual.sig
        - (__int128)((u128)b << shift);
    wv_t a = {
        (uint8_t)(difference < 0),
        residual.e2,
        difference < 0 ? (u128)(-difference) : (u128)difference
    };
    wv_t square = p5_wv_mul_round(
        a, a, 67, P5_ROUND_CHOP);
    p5c_t p6s4_4 = P5S4_4;
    p6s4_4.sig -= (u128)1 << 60;
    sf_t p = fsincos_compat_p6_horner4(
        &p6s4_4, &P5S4_3, &P5S4_2, &P5S4_1, &square);
    sf_t q = fsincos_compat_p6_horner4(
        &P5C4_4, &P5C4_3, &P5C4_2, &P5C4_1, &square);
    wv_t p_state = { p.sign, p.exp - 63, (u128)p.sig };
    wv_t q_state = { q.sign, q.exp - 63, (u128)q.sig };
    wv_t p_square = p5_wv_mul_round(
        p_state, square, 67, P5_ROUND_CHOP);
    wv_t sine_tail = p5_wv_mul_round(
        p_square, a, 67, P5_ROUND_CHOP);
    wv_t sine_state = p5_wv_add_round(
        a, sine_tail, 64, P5_ROUND_RN);
    wv_t cosine_tail = p5_wv_mul_round(
        q_state, square, 64, P5_ROUND_RN);

    wv_t table_sine = {
        P5TAB[table_index].sinT.sign,
        P5TAB[table_index].sinT.exp2,
        P5TAB[table_index].sinT.sig
    };
    wv_t table_cosine = {
        P5TAB[table_index].cosT.sign,
        P5TAB[table_index].cosT.exp2,
        P5TAB[table_index].cosT.sig
    };
    wv_t negative_sine = sine_state;
    wv_t negative_table_sine = table_sine;
    negative_sine.sign ^= 1;
    negative_table_sine.sign ^= 1;

    wv_t denominator_partial = fptan_sub_chop67(
        p5_wv_mul_round(
            negative_table_sine, negative_sine,
            67, P5_ROUND_CHOP),
        p5_wv_mul_round(
            table_cosine, cosine_tail,
            67, P5_ROUND_CHOP));
    wv_t cosine = fptan_sub_chop67(
        table_cosine, denominator_partial);
    wv_t numerator_partial = fptan_sub_chop67(
        p5_wv_mul_round(
            table_cosine, negative_sine,
            67, P5_ROUND_CHOP),
        p5_wv_mul_round(
            table_sine, cosine_tail,
            67, P5_ROUND_CHOP));
    wv_t sine = fptan_sub_chop67(table_sine, numerator_partial);
    sine.sign ^= residual_sign ? 1 : 0;
    fptan_rotate(&sine, &cosine, signed_n);
    *numerator = sine;
    *denominator = cosine;
}

/*
 * round a two-term sum whose exponent separation
 * exceeds the fixed accumulator.  At this distance the smaller nonzero term
 * lies below every retained bit of the larger carrier; it can only supply
 * sticky, tip an exact half case, or borrow below an exact boundary.
 */
static sf_t fsin_operation_class_far_final_add(
    wv_t left, wv_t right, int negate, sf_rc_t rc)
{
    int left_top = left.e2 + u128_width(left.sig) - 1;
    int right_top = right.e2 + u128_width(right.sig) - 1;
    wv_t larger = left_top > right_top ? left : right;
    wv_t smaller = left_top > right_top ? right : left;
    int top = left_top > right_top ? left_top : right_top;
    int width = u128_width(larger.sig);
    int shift = width > 64 ? width - 64 : 0;
    uint64_t significand = width > 64
        ? (uint64_t)(larger.sig >> shift)
        : (uint64_t)(larger.sig << (64 - width));
    u128 remainder = shift
        ? larger.sig & (((u128)1 << shift) - 1)
        : 0;
    u128 half = shift ? (u128)1 << (shift - 1) : 0;
    int same_sign = larger.sign == smaller.sign;
    int half_comparison;
    int has_remainder = remainder != 0 || smaller.sig != 0;

    if (same_sign) {
        if (!shift || remainder < half)
            half_comparison = -1;
        else if (remainder == half)
            half_comparison = 1;
        else
            half_comparison = 1;
    } else if (!remainder) {
        significand--;
        half_comparison = 1;
        if (significand < (1ull << 63)) {
            significand = UINT64_MAX;
            top--;
        }
    } else if (remainder <= half) {
        half_comparison = -1;
    } else {
        half_comparison = 1;
    }

    int sign = larger.sign ^ negate;
    int increment = 0;
    if (rc == SF_RN) {
        increment = half_comparison > 0
            || (half_comparison == 0 && (significand & 1));
    } else if (rc == SF_RU) {
        increment = !sign && has_remainder;
    } else if (rc == SF_RD) {
        increment = sign && has_remainder;
    }
    if (increment) {
        significand++;
        if (!significand) {
            significand = 1ull << 63;
            top++;
        }
    }
    return (sf_t){ SF_FIN, (uint8_t)sign, top, significand };
}

/* final signed addition under architectural RC. */
static sf_t fsin_operation_class_final_add(
    wv_t left, wv_t right, int negate, sf_rc_t rc)
{
    if (g_dump_internals)
        fprintf(stderr, "DI_FIN neg=%d L=" DIWF " R=" DIWF " ra=%p\n",
            negate, DIW(left), DIW(right),
            __builtin_return_address(0));
    int exponent_span = left.e2 - right.e2;
    if (exponent_span < 0) exponent_span = -exponent_span;
    if (exponent_span >= 256)
        return fsin_operation_class_far_final_add(
            left, right, negate, rc);
    int32_t scale = left.e2 < right.e2 ? left.e2 : right.e2;
    u256 accumulator = { 0, 0 };
    acc_add_product(
        &accumulator, left.sign, left.sig, 1, left.e2, scale);
    acc_add_product(
        &accumulator, right.sign, right.sig, 1, right.e2, scale);
    return acc_round64_rc(accumulator, scale, negate, rc);
}

/*
 * six-coefficient standalone trigonometric
 * polynomial path.
 * Each ordinary product is chopped to 67 bits, each Horner addition is RN64,
 * and the distinct P*a^2 multiply is RN64.  The result add is not
 * materialized until architectural rounding.
 */
#include "general/standalone_polynomial.h"

static sf_t fsin_operation_class_polynomial(
    wv_t magnitude, int residual_sign, int64_t signed_n, sf_rc_t rc,
    int retain_cosine_product, int cos_gate_eligible)
{
    if (g_general_standalone_active)
        return h1630_polynomial(magnitude, residual_sign, signed_n, rc);
    if (g_perturb_tgt == 7)
        magnitude.sig = (u128)((__int128)magnitude.sig
                               + g_perturb_delta);
    if (g_dump_internals)
        fprintf(stderr, "DI_RED i1=%d i0=%d rsn=%d mag=" DIWF "\n",
            (int)((unsigned)signed_n & 1u),
            (int)(((unsigned)signed_n >> 1) & 1u),
            residual_sign, DIW(magnitude));
    wv_t square = p5_wv_mul_round(
        magnitude, magnitude, 67, P5_ROUND_CHOP);
    square = perturb_materialized_ulp(square, 17);
    wv_t fourth = p5_wv_mul_round(
        square, square, 67, P5_ROUND_CHOP);
    int i1 = (unsigned)signed_n & 1u;
    int i0 = ((unsigned)signed_n >> 1) & 1u;
#if G_ROUND86
    if (!i1) {
        wv_t square64 = square;
        square64.sig &= ~(u128)7;
        fourth = p5_wv_mul_round(square, square64, 67, P5_ROUND_CHOP);
    }
#endif
#if G_F4PC
    /* EXPERIMENT (probe A1): the same one-port truncation on the
     * i1==1 cosine branch of this producer. */
    if (i1) {
        wv_t square64 = square;
        square64.sig &= ~(u128)7;
        fourth = p5_wv_mul_round(square, square64, 67, P5_ROUND_CHOP);
    }
#endif
    fourth = perturb_materialized_ulp(fourth, 18);

    if (!i1) {
        /* --sinechain=N experiment: N=1 raises the intermediate
         * Horner sums to RN67 (chip candidate: the chain is carried
         * wide, one terminal RN64); N=2 RN68; 0 = shipped RN64. */
        /* --sinespec=PB:PM:SB:SM overrides the sine-chain edge
         * recipe uniformly (PM/SM: c=chop r=rn a=away); shipped =
         * 67:c:64:r.  --sinechain legacy values kept. */
        int sb = 64, pb = 67;
        p5_round_t pm = P5_ROUND_CHOP, sm = P5_ROUND_RN;
        if (g_sinechain >= 1 && g_sinechain <= 3)
            sb = 66 + g_sinechain;
        else if (g_sinechain == 10) { pb = 67; pm = P5_ROUND_RN; }
        else if (g_sinechain == 11) { pb = 68; pm = P5_ROUND_RN; }
        else if (g_sinechain == 12) {
            pb = 69; pm = P5_ROUND_RN; sb = 69;
        }
        if (g_sinespec[0]) {
            pb = g_sinespec[0]; sb = g_sinespec[2];
            pm = (p5_round_t)g_sinespec[1];
            sm = (p5_round_t)g_sinespec[3];
        }
        /* --sineedges=XXXXXX: per-product-edge override, chars in
         * chain order oddP1,oddP2,oddP3,evenP1,evenP2,evenP3;
         * c = shipped 67 CHOP, a = 69 AWAY, r = 69 RN, keep pb/pm
         * for edges marked u (uniform). */
        int epb[6]; p5_round_t epm[6];
        for (int ei = 0; ei < 6; ei++) { epb[ei] = pb; epm[ei] = pm; }
        if (g_sineedges[0]) {
            for (int ei = 0; ei < 6 && g_sineedges[ei]; ei++) {
                char cch = g_sineedges[ei];
                if (cch == 'c') { epb[ei] = 67; epm[ei] = P5_ROUND_CHOP; }
                else if (cch == 'a') { epb[ei] = 69; epm[ei] = P5_ROUND_AWAY; }
                else if (cch == 'r') { epb[ei] = 69; epm[ei] = P5_ROUND_RN; }
            }
        }
        if (g_sp3[0]) {                 /* --sp3=BITS:m third-edge override */
            epb[2] = g_sp3[0];
            epm[2] = (p5_round_t)g_sp3[1];
        }
        wv_t odd = p5_wv_mul_round(
            fourth, f2xm1_constant(&P5S6_5), epb[0], epm[0]);
        odd = p5_wv_add_round(
            f2xm1_constant(&P5S6_3), odd, sb, sm);
        odd = p5_wv_mul_round(
            fourth, odd, epb[1], epm[1]);
        odd = p5_wv_add_round(
            f2xm1_constant(&P5S6_1), odd, sb, sm);
        odd = p5_wv_mul_round(
            square, odd, epb[2], epm[2]);

        wv_t even = p5_wv_mul_round(
            fourth, f2xm1_constant(&P5S6_6), epb[3], epm[3]);
        even = p5_wv_add_round(
            f2xm1_constant(&P5S6_4), even, sb, sm);
        even = p5_wv_mul_round(
            fourth, even, epb[4], epm[4]);
        even = p5_wv_add_round(
            f2xm1_constant(&P5S6_2), even, sb, sm);
        even = p5_wv_mul_round(
            fourth, even, epb[5], epm[5]);

        wv_t polynomial;
        if (g_sinefin >= 100) {
            /* alignment-relative lookahead: K = d_e2 + (g_sinefin-100-2)
             * where d_e2 = odd.e2 - even.e2 (operand alignment). */
            int K = (odd.e2 > even.e2 ? odd.e2 - even.e2
                                      : even.e2 - odd.e2)
                    + (g_sinefin - 100) - 2;
            if (K < 2) K = 2;
            if (K > 40) K = 40;
            wv_t wide = p5_wv_add_round(
                odd, even, 64 + K, P5_ROUND_CHOP);
            u128 low = wide.sig & ((((u128)1) << K) - 1);
            polynomial = wide;
            polynomial.sig >>= K;
            polynomial.e2 += K;
            if (low >= ((((u128)1) << (K - 1)) - 1)) {
                polynomial.sig += 1;
                if (polynomial.sig >> 64) {
                    polynomial.sig >>= 1;
                    polynomial.e2 += 1;
                }
            }
        } else if (g_sinefin) {
            /* carry-lookahead round candidate: keep K extra bits,
             * round up iff the K-bit remainder >= 2^(K-1) - 1
             * (round bit set OR next K-1 bits all ones). */
            int K = g_sinefin;
            wv_t wide = p5_wv_add_round(
                odd, even, 64 + K, P5_ROUND_CHOP);
            u128 low = wide.sig & ((((u128)1) << K) - 1);
            polynomial = wide;
            polynomial.sig >>= K;
            polynomial.e2 += K;
            if (low >= ((((u128)1) << (K - 1)) - 1)) {
                polynomial.sig += 1;
                if (polynomial.sig >> 64) {
                    polynomial.sig >>= 1;
                    polynomial.e2 += 1;
                }
            }
        } else {
            polynomial = p5_wv_add_round(
                odd, even, 64, P5_ROUND_RN);
        }
        if (g_perturb_tgt == 15)
            polynomial.sig = (u128)((__int128)polynomial.sig
                                    + g_perturb_delta);
        if (g_dump_internals)
            fprintf(stderr,
                "DI_SPOLY i0=%d rsn=%d mag=" DIWF " odd=" DIWF
                " even=" DIWF " poly=" DIWF "\n",
                i0, residual_sign, DIW(magnitude), DIW(odd),
                DIW(even), DIW(polynomial));
        wv_t correction = p5_wv_mul_round(
            magnitude, polynomial, 67, P5_ROUND_CHOP);
        return fsin_operation_class_final_add(
            magnitude, correction, residual_sign ^ i0, rc);
    }

    wv_t odd = p5_wv_mul_round(
        fourth, f2xm1_constant(&P5C6_5), 67, P5_ROUND_CHOP);
    odd = perturb_materialized_ulp(odd, 19);
    odd = p5_wv_add_round(
        f2xm1_constant(&P5C6_3), odd, 64, P5_ROUND_RN);
    odd = perturb_materialized_ulp(odd, 20);
#if G_R1231CPAFADD || G_R1237CPAFADD || G_R1290FADDWORD \
    || G_R1297FADDBOOTH1 || G_R1299FADDLOWBIT
    int odd_add2_cpa = p5_r1231_product_cpa_bit(
        fourth.sig, odd.sig,
        G_R1237CPAFADD || G_R1290FADDWORD || G_R1297FADDBOOTH1
            || G_R1299FADDLOWBIT);
#endif
    odd = p5_wv_mul_round(
        fourth, odd, 67, P5_ROUND_CHOP);
    odd = perturb_materialized_ulp(odd, 21);
    wv_t odd_add2_source = odd;
    odd = p5_wv_add_round(
        f2xm1_constant(&P5C6_1), odd, 64, P5_ROUND_RN);
#if G_R1378X67Y64
    /* h1357/h1363: attach the squarer's X67/Y64 representation to the
     * negative-chain FADD history input.  The alternate fourth power is
     * consumed only when the exact RN64 add exposes its complete three-bit
     * q field; it does not replace the shared polynomial value. */
    if (p5_fadd_three_bit_half_window(
            f2xm1_constant(&P5C6_1), odd_add2_source)) {
        wv_t square64 = square;
        square64.sig &= ~(u128)7;
        wv_t odd_fourth = p5_wv_mul_round(
            square, square64, 67, P5_ROUND_CHOP);
        wv_t alternate = p5_wv_mul_round(
            odd_fourth, f2xm1_constant(&P5C6_5),
            67, P5_ROUND_CHOP);
        alternate = perturb_materialized_ulp(alternate, 19);
        alternate = p5_wv_add_round(
            f2xm1_constant(&P5C6_3), alternate, 64, P5_ROUND_RN);
        alternate = perturb_materialized_ulp(alternate, 20);
        alternate = p5_wv_mul_round(
            odd_fourth, alternate, 67, P5_ROUND_CHOP);
        alternate = perturb_materialized_ulp(alternate, 21);
        odd = p5_wv_add_round(
            f2xm1_constant(&P5C6_1), alternate, 64, P5_ROUND_RN);
    }
#endif
    if (G_R1186FADD && p5_same_sign_half_history_class(
            f2xm1_constant(&P5C6_1), odd_add2_source, 64, 1)) {
        odd.sig--;
        odd.rh = odd.sign ? 1 : -1;
    }
#if G_R1231CPAFADD || G_R1237CPAFADD || G_R1290FADDWORD \
    || G_R1297FADDBOOTH1 || G_R1299FADDLOWBIT
    if (!G_R1378X67Y64 && p5_r1231_fadd_class(
            f2xm1_constant(&P5C6_1), odd_add2_source, odd_add2_cpa)) {
        odd.sig--;
        odd.rh = odd.sign ? 1 : -1;
    }
#endif
    odd = perturb_materialized_ulp(odd, 22);

    wv_t even = p5_wv_mul_round(
        fourth, f2xm1_constant(&P5C6_6), 67, P5_ROUND_CHOP);
    even = perturb_materialized_ulp(even, 23);
    even = p5_wv_add_round(
        f2xm1_constant(&P5C6_4), even, 64, P5_ROUND_RN);
    even = perturb_materialized_ulp(even, 24);
#if G_R1231CPAFADD || G_R1237CPAFADD || G_R1290FADDWORD \
    || G_R1297FADDBOOTH1 || G_R1299FADDLOWBIT
    int even_add2_cpa = p5_r1231_product_cpa_bit(
        fourth.sig, even.sig,
        G_R1237CPAFADD || G_R1290FADDWORD || G_R1297FADDBOOTH1
            || G_R1299FADDLOWBIT);
#endif
    even = p5_wv_mul_round(
        fourth, even, 67, P5_ROUND_CHOP);
    even = perturb_materialized_ulp(even, 25);
    wv_t even_add2_source = even;
    even = p5_wv_add_round(
        f2xm1_constant(&P5C6_2), even, 64, P5_ROUND_RN);
    if (G_R1186FADD && p5_same_sign_half_history_class(
            f2xm1_constant(&P5C6_2), even_add2_source, 64, 0)) {
        even.sig--;
        even.rh = even.sign ? 1 : -1;
    }
#if G_R1231CPAFADD || G_R1237CPAFADD || G_R1290FADDWORD \
    || G_R1297FADDBOOTH1 || G_R1299FADDLOWBIT
    if (p5_r1231_fadd_class(
            f2xm1_constant(&P5C6_2), even_add2_source, even_add2_cpa)) {
        even.sig--;
        even.rh = even.sign ? 1 : -1;
    }
#endif
    even = perturb_materialized_ulp(even, 26);

    if (g_dump_internals)
        fprintf(stderr,
            "DI_POLY site=4055 i1=%d i0=%d rsn=%d retain=%d elig=%d "
            "mag=" DIWF " sq=" DIWF " f4=" DIWF " odd=" DIWF
            " even=" DIWF " rh_sq=%d rh_f4=%d rh_odd=%d rh_even=%d\n",
            i1, i0, residual_sign, retain_cosine_product,
            cos_gate_eligible, DIW(magnitude), DIW(square),
            DIW(fourth), DIW(odd), DIW(even),
            square.rh, fourth.rh, odd.rh, even.rh);
    wv_t correction;
    if (retain_cosine_product) {
        correction = fcos_low3_terminal_correction(
            square, odd, even, fourth, magnitude, cos_gate_eligible,
            i0, rc);
        correction = perturb_materialized_ulp(correction, 29);
    } else {
        odd = p5_wv_mul_round(
            square, odd, 67, P5_ROUND_CHOP);
        even = p5_wv_mul_round(
            fourth, even, 67, P5_ROUND_CHOP);
        correction = p5_wv_add_round(
            odd, even, 67, P5_ROUND_CHOP);
        if (g_dump_internals)
            fprintf(stderr, "DI_CORR via=plain out=" DIWF "\n",
                DIW(correction));
    }
    wv_t one = { 0, -63, (u128)1 << 63 };
    return fsin_operation_class_final_add(one, correction, i0, rc);
}

/*
 * when the reduced argument is below 2^-32, the
 * nonzero sine/cosine correction is below every retained result bit.  Keep
 * one explicit far sticky term so directed rounding still distinguishes the
 * result from the leading residual or one.
 */
static sf_t fsin_operation_class_tiny_residual(
    wv_t magnitude, int residual_sign, int64_t signed_n, sf_rc_t rc)
{
    int i1 = (unsigned)signed_n & 1u;
    int i0 = ((unsigned)signed_n >> 1) & 1u;
    wv_t correction = { 1, magnitude.e2 - 320, 1 };
    if (!i1) {
        return fsin_operation_class_final_add(
            magnitude, correction, residual_sign ^ i0, rc);
    }
    wv_t one = { 0, -63, (u128)1 << 63 };
    return fsin_operation_class_final_add(one, correction, i0, rc);
}

/*
 * The Round-51 leaf selected the captured non-incrementing sine-state
 * result at one far-subtract carrier signature (exponent difference 14,
 * above-half remainder, retained low byte 0x8c, remainder prefix 0xc1).
 * h406 retires it: after Round 53's exact-division quotient no input in
 * the h347/structured/dense corpora depends on it, and the identical
 * signature recurs at the h377 exponent-7 residual where hardware keeps
 * the ordinary RN64 result.  The sine-state FADD is therefore RN64
 * everywhere on current evidence; --round51-fsin-fadd-signature is
 * accepted but inert.
 */
static wv_t fsin_operation_class_sine_state(wv_t a, wv_t tail)
{
    wv_t nearest = p5_wv_add_round(a, tail, 64, P5_ROUND_RN);
    int exponent_difference = a.e2 - tail.e2;
    if (exponent_difference < 0)
        exponent_difference = -exponent_difference;
    if (
        !g_debug_sine_state
        || !a.sig
        || !tail.sig
        || exponent_difference != 14
    )
        return nearest;

    int32_t scale = a.e2 < tail.e2 ? a.e2 : tail.e2;
    u128 a_magnitude = a.sig << (a.e2 - scale);
    u128 tail_magnitude = tail.sig << (tail.e2 - scale);
    __int128 signed_a = a.sign
        ? -(__int128)a_magnitude
        : (__int128)a_magnitude;
    __int128 signed_tail = tail.sign
        ? -(__int128)tail_magnitude
        : (__int128)tail_magnitude;
    __int128 signed_sum = signed_a + signed_tail;
    u128 magnitude = signed_sum < 0
        ? (u128)(-signed_sum)
        : (u128)signed_sum;
    int shift = u128_width(magnitude) - 64;
    if (shift <= 0) return nearest;
    u128 remainder = magnitude & (((u128)1 << shift) - 1);
    u128 half = (u128)1 << (shift - 1);
    uint64_t retained = (uint64_t)(magnitude >> shift);
    unsigned remainder_top8 = shift >= 8
        ? (unsigned)(remainder >> (shift - 8))
        : (unsigned)(remainder << (8 - shift));
    fprintf(stderr,
        "SINE_STATE diff=%d shift=%d retained_low8=%02x "
        "remainder_top8=%02x above_half=%d sticky=%d\n",
        exponent_difference, shift,
        (unsigned)(retained & 0xffu), remainder_top8,
        remainder > half,
        (remainder & (half - 1)) != 0);
    return nearest;
}

/*
 * four-coefficient standalone-FSIN table path.
 * The two reconstruction products and their signed subtract-class sum use
 * the shared chop67 rule.  The selected table lead and correction remain
 * separate until the final architectural add.
 */
#include "general/standalone_table.h"

static sf_t fsin_operation_class_table(
    wv_t residual, int residual_sign, int64_t signed_n, sf_rc_t rc)
{
    if (g_general_standalone_active)
        return h1633_table(residual, residual_sign, signed_n, rc);
    int b;
    if (g_round62_table_lane_exact) {
        /* lane = top-3 normalized significand bits of the residual,
         * exact; the residual exponent (-2 or -1 in this path) picks
         * the 1/16- vs 1/8-wide lane grid.  The double-precision
         * classifier below misrounds the top 2^-55 sliver under each
         * interior lane boundary into the next lane. */
        int rw = u128_width(residual.sig);
        int rexp = residual.e2 + rw - 1;
        int lane = (int)(u128)(residual.sig >> (rw - 3)) - 4;
        if (rexp <= -2) {
            b = 18 + 4 * lane;
        } else {
            if (lane > 2) lane = 2;
            b = 36 + 8 * lane;
        }
    } else {
        double rf = (double)residual.sig
            * pow(2.0, (double)residual.e2);
        if (rf < 0.5) {
            b = 18 + 4 * (int)((rf - 0.25) / (4.0 / 64.0));
        } else {
            int lane = (int)((rf - 0.5) / (8.0 / 64.0));
            if (lane > 2) lane = 2;
            b = 36 + 8 * lane;
        }
    }
    int table_index = 0;
    while (P5TAB[table_index].b != b) table_index++;

    int shift = -6 - residual.e2;
    __int128 difference = (__int128)residual.sig
        - (__int128)((u128)b << shift);
    wv_t a = {
        (uint8_t)(difference < 0),
        residual.e2,
        difference < 0 ? (u128)(-difference) : (u128)difference
    };
    a = p5_wv_mul_round(
        a, (wv_t){ 0, 0, 1 }, 67, P5_ROUND_CHOP);
    wv_t square = p5_wv_mul_round(
        a, a, 67, P5_ROUND_CHOP);
    p5c_t p6s4_4 = P5S4_4;
    p6s4_4.sig -= (u128)1 << 60;
    sf_t p64 = fsincos_compat_p6_horner4(
        &p6s4_4, &P5S4_3, &P5S4_2, &P5S4_1, &square);
    sf_t q64 = fsincos_compat_p6_horner4(
        &P5C4_4, &P5C4_3, &P5C4_2, &P5C4_1, &square);
    wv_t p = { p64.sign, p64.exp - 63, (u128)p64.sig };
    wv_t q = { q64.sign, q64.exp - 63, (u128)q64.sig };
    wv_t p_square = p5_wv_mul_round(
        p, square, 67, P5_ROUND_CHOP);
    wv_t sine_tail = p5_wv_mul_round(
        p_square, a, 67, P5_ROUND_CHOP);
    wv_t sine_state = fsin_operation_class_sine_state(a, sine_tail);
    wv_t cosine_tail = p5_wv_mul_round(
        q, square, 64, P5_ROUND_RN);

    wv_t table_sine = {
        P5TAB[table_index].sinT.sign,
        P5TAB[table_index].sinT.exp2,
        P5TAB[table_index].sinT.sig
    };
    wv_t table_cosine = {
        P5TAB[table_index].cosT.sign,
        P5TAB[table_index].cosT.exp2,
        P5TAB[table_index].cosT.sig
    };
    int i1 = (unsigned)signed_n & 1u;
    int i0 = ((unsigned)signed_n >> 1) & 1u;
    wv_t partial;
    wv_t correction;
    if (g_dump_internals)
        fprintf(stderr,
            "DI_TBL i1=%d i0=%d rsn=%d b=%d a=" DIWF " sq=" DIWF
            " sstate=" DIWF " stail=" DIWF " ctail=" DIWF " tsin=" DIWF
            " tcos=" DIWF "\n",
            i1, i0, residual_sign, b, DIW(a), DIW(square),
            DIW(sine_state), DIW(sine_tail), DIW(cosine_tail),
            DIW(table_sine), DIW(table_cosine));

    if (!i1) {
        wv_t negative_sine = sine_state;
        negative_sine.sign ^= 1;
        partial = fptan_sub_chop67(
            p5_wv_mul_round(
                table_cosine, negative_sine,
                67, P5_ROUND_CHOP),
            p5_wv_mul_round(
                table_sine, cosine_tail,
                67, P5_ROUND_CHOP));
        correction = partial;
        correction.sign ^= 1;
        return fsin_operation_class_final_add(
            table_sine, correction, residual_sign ^ i0, rc);
    }

    wv_t negative_sine = sine_state;
    wv_t negative_table_sine = table_sine;
    negative_sine.sign ^= 1;
    negative_table_sine.sign ^= 1;
    partial = fptan_sub_chop67(
        p5_wv_mul_round(
            negative_table_sine, negative_sine,
            67, P5_ROUND_CHOP),
        p5_wv_mul_round(
            table_cosine, cosine_tail,
            67, P5_ROUND_CHOP));
    correction = partial;
    correction.sign ^= 1;
    return fsin_operation_class_final_add(
        table_cosine, correction, i0, rc);
}

/* exact final quotient with architectural RC. */
static sf_t fptan_final_divide(wv_t numerator, wv_t denominator, sf_rc_t rc)
{
    int sign = numerator.sign ^ denominator.sign;
    if (!numerator.sig) return sf_zero(sign);
    if (!denominator.sig)
        return (sf_t){ SF_INF, (uint8_t)sign, 0, 0 };

    int numerator_width = u128_width(numerator.sig);
    int denominator_width = u128_width(denominator.sig);
    int ratio_exponent = numerator_width - denominator_width;
    if (ratio_exponent >= 0) {
        if (numerator.sig < (denominator.sig << ratio_exponent))
            ratio_exponent--;
    } else if (
        (numerator.sig << -ratio_exponent) < denominator.sig
    ) {
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
        increment = doubled > normalized_denominator
            || (doubled == normalized_denominator && (significand & 1));
    } else if (rc == SF_RD) {
        increment = sign && remainder;
    } else if (rc == SF_RU) {
        increment = !sign && remainder;
    }
    int32_t exponent = ratio_exponent
        + numerator.e2 - denominator.e2;
    if (increment) {
        significand++;
        if (significand == ((u128)1 << 64)) {
            significand >>= 1;
            exponent++;
        }
    }
    return (sf_t){
        SF_FIN, (uint8_t)sign, exponent, (uint64_t)significand
    };
}

/* ---------------- top level (sinl machinery; cos: n_inc = 1) ---------- */

typedef enum {
    FSINCOS_OK = 0,
    FSINCOS_C2 = 1,
    FSINCOS_FALLBACK = 2
} fsincos_status_t;

/*
 * complete finite standalone FSIN/FCOS operation
 * schedule.  phase_increment is zero for sine and one for cosine.
 * With table_only set, only table-path inputs are computed; every other
 * branch returns FSINCOS_FALLBACK without writing *out so the caller can
 * keep the legacy paired model for polynomial/tiny/exact-residual inputs.
 */
static fsincos_status_t fsincos_compat_operation_class_core(
    sf_t x, int phase_increment, sf_rc_t rc, sf_t *out, int table_only)
{
    sf_t magnitude = sf_abs(&x);
    sf_t r, c;
    int64_t signed_n;
    if (sf_lt(&magnitude, &PI_BY_4)) {
        if (!phase_increment && x.exp < P5_POLY_MODEL_MIN_EXP) {
            if (table_only) return FSINCOS_FALLBACK;
            *out = p5_fsin_standalone_tiny(x, rc);
            return FSINCOS_OK;
        }
        if (phase_increment && x.exp < -68) {
            if (table_only) return FSINCOS_FALLBACK;
            *out = ONE;
            return FSINCOS_OK;
        }
        r = x;
        c = ZERO;
        signed_n = phase_increment;
    } else {
        uint64_t n_magnitude = fsincos_compat_reduce_n_exact(
            x.sig, x.exp);
        signed_n = x.sign
            ? -(int64_t)n_magnitude
            : (int64_t)n_magnitude;
        signed_n += phase_increment;
        sky_reduce_rc(&x, n_magnitude, &r, &c);
        if (r.cls != SF_FIN) return FSINCOS_C2;
    }

    if (g_dump_internals)
        fprintf(stderr,
            "DI_RC2 r=%d:%d:%016llx c=%d:%d:%016llx\n",
            (int)r.sign, r.exp, (unsigned long long)r.sig,
            (int)c.sign, c.exp, (unsigned long long)c.sig);
    wv_t residual = wv_from_rc(&r, &c);
    int residual_sign = residual.sign;
    residual.sign = 0;
    int residual_exponent = residual.sig
        ? residual.e2 + u128_width(residual.sig) - 1
        : -16383;
    if (!residual.sig) {
        if (table_only) return FSINCOS_FALLBACK;
        unsigned quadrant = (unsigned)signed_n & 3u;
        if (quadrant & 1u) {
            *out = ONE;
            out->sign = (quadrant >> 1) & 1u;
        } else {
            *out = sf_zero(residual_sign ^ ((quadrant >> 1) & 1u));
        }
    } else if (residual_exponent < P5_POLY_MODEL_MIN_EXP) {
        if (table_only) return FSINCOS_FALLBACK;
        *out = fsin_operation_class_tiny_residual(
            residual, residual_sign, signed_n, rc);
    } else if (residual_exponent <= -3) {
        if (table_only) return FSINCOS_FALLBACK;
        *out = fsin_operation_class_polynomial(
            residual, residual_sign, signed_n, rc,
            (phase_increment || g_round56_fsin_cosine_carrier)
                && g_round52_fcos_low3_carrier,
            phase_increment != 0 || g_round58_fsin_borrow_rule);
    } else {
        *out = fsin_operation_class_table(
            residual, residual_sign, signed_n, rc);
    }
    return FSINCOS_OK;
}

/* complete finite/special FPTAN path selection. */
static fsincos_status_t fptan_core(sf_t x, sf_rc_t rc, sf_t *out)
{
    if (x.cls == SF_NAN) {
        *out = x;
        out->sig |= 0x4000000000000000ull;
        return FSINCOS_OK;
    }
    if (x.cls == SF_INF) {
        *out = sf_qnan();
        return FSINCOS_OK;
    }
    if (sf_is_zero(&x)) {
        *out = x;
        return FSINCOS_OK;
    }
    if (x.exp >= 63) return FSINCOS_C2;

    sf_t r, c;
    int64_t signed_n;
    sf_t magnitude = sf_abs(&x);
    if (sf_lt(&magnitude, &PI_BY_4)) {
        if (x.exp < -68) {
            *out = x;
            return FSINCOS_OK;
        }
        r = x;
        c = ZERO;
        signed_n = 0;
    } else {
        /* h403: the same literal exact division as the FSIN/FCOS
         * operation-class reduction.  The reciprocal seed diverges from it
         * only on the 18 known large-argument residual inputs (zero
         * divergence over the sweep/dense corpora), and the exact quotient
         * removes all 25 of their result differences. */
        uint64_t n_magnitude = fsincos_compat_reduce_n_exact(x.sig, x.exp);
        signed_n = x.sign
            ? -(int64_t)n_magnitude
            : (int64_t)n_magnitude;
        sky_reduce_rc(&x, n_magnitude, &r, &c);
        if (r.cls != SF_FIN) return FSINCOS_C2;
    }

    if (g_dump_internals)
        fprintf(stderr,
            "DI_RC2 r=%d:%d:%016llx c=%d:%d:%016llx\n",
            (int)r.sign, r.exp, (unsigned long long)r.sig,
            (int)c.sign, c.exp, (unsigned long long)c.sig);
    wv_t residual = wv_from_rc(&r, &c);
    int residual_sign = residual.sign;
    residual.sign = 0;
    wv_t numerator, denominator;
    int residual_exponent = residual.sig
        ? residual.e2 + u128_width(residual.sig) - 1
        : -16383;
    if (residual_exponent <= -3) {
        fptan_polynomial_values(
            residual, residual_sign, signed_n,
            &numerator, &denominator);
    } else {
        fptan_table_values(
            residual, residual_sign, signed_n,
            &numerator, &denominator);
    }
    *out = fptan_final_divide(numerator, denominator, rc);
    return FSINCOS_OK;
}

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
    if (
        (
            g_round50_fsin_operation_classes
            && g_fsin_standalone_path
            && !n_inc
        )
        || (
            g_round53_fcos_operation_classes
            && g_fcos_standalone_path
            && n_inc
        )
    )
        return fsincos_compat_operation_class_core(x, n_inc, rc, out, 0);

    /*
     * paired FSINCOS shares the table datapath
     * bit-exactly with the standalone instructions (fresh paired-vs-
     * standalone Skylake captures over the structured, dense, h347, and
     * h349 corpora), so with Round 54 each paired lane's table-path input
     * is computed as its standalone instruction.  Polynomial, tiny, and
     * exact-residual inputs fall back to the legacy paired model.
     */
    if (
        g_round54_fsincos_table_lanes
        && g_round50_fsin_operation_classes
        && g_round53_fcos_operation_classes
        && !g_fsin_standalone_path
        && !g_fcos_standalone_path
    ) {
        fsincos_status_t table_status;
        if (n_inc) {
            g_fcos_standalone_path = 1;
            table_status = fsincos_compat_operation_class_core(
                x, n_inc, rc, out, 1);
            g_fcos_standalone_path = 0;
        } else {
            g_fsin_standalone_path = 1;
            table_status = fsincos_compat_operation_class_core(
                x, n_inc, rc, out, 1);
            g_fsin_standalone_path = 0;
        }
        if (table_status != FSINCOS_FALLBACK) return table_status;
    }

    /* ---- Skylake model: pi/4 <= |x| < 2^63 all use the proven M66
     * reduction. */
    sf_t absx = sf_abs(&x);
    if (x.exp < 24 && sf_lt(&absx, &PI_BY_4)) {
        /* quick: r = x, c = 0 */
        int N_Inc = n_inc & 3;
        int i1 = N_Inc & 1, i0 = (N_Inc >> 1) & 1;
        sf_t c = ZERO;
        int paired_tiny = (
            g_round40_fsincos_tiny
            && !g_fsin_standalone_path
            && !g_fcos_standalone_path
            && x.exp < P5_POLY_MODEL_MIN_EXP
        );
        if (
            (
                (g_round39_fcos_tiny && g_fcos_standalone_path)
                || paired_tiny
            )
            && i1
            && x.exp < P5_POLY_MODEL_MIN_EXP
        ) {
            /*
             * h238/h240: for -68 <= exponent <= -33, the hidden
             * negative cosine correction selects the value immediately
             * below 1 under RD/RZ.  RN/RU return 1.  At exponent <= -69
             * the correction is discarded and every mode returns 1.
             */
            *out = ONE;
            if (
                x.exp >= -68
                && (rc == SF_RD || rc == SF_RZ)
            ) {
                out->exp = -1;
                out->sig = UINT64_MAX;
            }
            return FSINCOS_OK;
        }
        if (
            (g_fsin_standalone_path || paired_tiny)
            && !i1
            && x.exp < P5_POLY_MODEL_MIN_EXP
        ) {
            *out = p5_fsin_standalone_tiny(x, rc);
            return FSINCOS_OK;
        }
        if (
            x.exp < -3
            && !g_fsin_standalone_path
            && (
                !g_round18_poly
                || x.exp < P5_POLY_MODEL_MIN_EXP
            )
        ) {
            *out = small_r(x, c, i1, i0, rc);
            return FSINCOS_OK;
        }
        *out = p5_kernel(x, c, i1, i0, rc, 0);
        return FSINCOS_OK;
    }

    uint64_t Nmag = sky_reduce_N(x.sig, x.exp);
    int64_t Ni = x.sign ? -(int64_t)Nmag : (int64_t)Nmag;
    sf_t r, c;
    sky_reduce_rc(&x, Nmag, &r, &c);
    if (r.cls != SF_FIN) return FSINCOS_C2;    /* defensive: |d| overflow */
    int N_Inc = (int)((Ni + n_inc) & 3);
    int i1 = N_Inc & 1, i0 = (N_Inc >> 1) & 1;
    int small = sf_is_zero(&r) || (sf_lt(&r, &TWO_M3) && sf_lt(&NTWO_M3, &r));
    *out = (
        small
        && (
            !g_round18_poly
            || r.exp < P5_POLY_MODEL_MIN_EXP
        )
    )
        ? small_r(r, c, i1, i0, rc)
        : p5_kernel(r, c, i1, i0, rc, 1);
    return FSINCOS_OK;
}

/* public: x87-format in/out */
typedef struct { uint16_t se; uint64_t sig; } x80_t;

/* x87 invalid-encoding gate: any nonzero-exponent operand with a
 * clear explicit-integer bit (unnormal, pseudo-NaN, pseudo-infinity)
 * takes the masked-#IA response — the real indefinite — in every
 * rounding mode.  Pseudo-denormals (exponent 0, integer bit set) are
 * valid and are NOT gated. */
static int x87_invalid_encoding(x80_t in)
{
    return g_round63_invalid_encoding
        && (in.se & 0x7FFF) != 0
        && !(in.sig >> 63);
}

static const x80_t X87_INDEFINITE = { 0xFFFF, 0xC000000000000000ull };

/* Round 84 ledger (see the flag comment at G_ROUND84): captured
 * hardware results for the standalone FSIN/FCOS entry points,
 * keyed on the exact operand encoding and rounding mode.  Applied
 * at the architectural output layer of fsin_ref/fcos_ref ONLY —
 * the paired-FSINCOS producer is a different (exact) datapath and
 * never consults this table. */
enum { R84_FCOS = 0, R84_FSIN = 1 };
typedef struct {
    uint16_t se; uint64_t sig;          /* operand */
    uint8_t insn, rc;                   /* R84_*, sf_rc_t */
    uint16_t out_se; uint64_t out_sig;  /* captured hw result */
} r84_entry_t;
static const r84_entry_t r84_ledger[] = {
    /* R92: one key DELETED (derived by the band-no-fire ce=-74
     * scope — the default terminal's sum-0x102 act1 carry):
     * randv1:1548918/rn 0xc019. */
    /* R88: three keys DELETED (derived by the adder law) —
     * randv1:4615048/rn 0x4008 (the R87 counterexample, banked
     * this morning and dissolved by mechanism the same day),
     * randv1:2593581/rn 0x4030, randv1:6363167/ru 0x4005. */
    /* R91: two keys DELETED (derived by the q67th2 ce-scope —
     * outside ce=-72 the default terminal's act1 machinery carries
     * their sum-0x102 rows exactly): randv1:2858512/ru 0x402b,
     * randv1:3133126/rn 0x4016. */
    { 0x3ffc, 0xb0000000044ca2bfull, R84_FCOS, SF_RN,
      0x3ffe, 0xfc3a6170f7389cfaull }, /* comb7:452822 rn hw=mo-1ulp */
    { 0x3ffc, 0xba100000056e0a67ull, R84_FCOS, SF_RN,
      0x3ffe, 0xfbc91f1ca0fa9a3aull }, /* comb13:2080977 rn hw=mo-1ulp */
    /* R89: four keys DELETED (derived by the activation gate) —
     * randv1:5164101/ru 0xc006 (block grl=16 decline),
     * randv1:3299966/ru+rz 0xc035 (DEEP decline),
     * randv1:4874415/rd 0xc02f (DEEP decline). */
    { 0x3ffc, 0xcca0000009242f0cull, R84_FCOS, SF_RN,
      0x3ffe, 0xfae7de0e2edcf4f1ull }, /* comb9:2482891 rn hw=mo-1ulp */
    { 0x3ffc, 0xd920000000749eaaull, R84_FCOS, SF_RN,
      0x3ffe, 0xfa4448c75102c99cull }, /* comb9:3908895 rn hw=mo-1ulp */
    { 0x3ffc, 0xf4100000059862ddull, R84_FCOS, SF_RU,
      0x3ffe, 0xf8c35790ef2cf9b8ull }, /* comb15:965215 ru hw=mo-1ulp */
    { 0x3ffc, 0xfa50000007503a2full, R84_FCOS, SF_RN,
      0x3ffe, 0xf863b8386c1226cbull }, /* comb15:1893460 rn hw=mo-1ulp */
    { 0x3ffc, 0xffffc00024077827ull, R84_FCOS, SF_RU,
      0x3ffe, 0xf80aa8f14a992a34ull }, /* comb17:88799 ru hw=mo+1ulp */
    { 0x3ffc, 0xffffc0006e4548d9ull, R84_FCOS, SF_RU,
      0x3ffe, 0xf80aa8f14601a409ull }, /* comb18:113306 ru hw=mo+1ulp */
    { 0x3ffc, 0xfffff00047c167a3ull, R84_FCOS, SF_RU,
      0x3ffe, 0xf80aa5f94273c8bbull }, /* comb18:260927 ru hw=mo+1ulp */
};
static int r84_lookup(x80_t in, int insn, sf_rc_t rc, x80_t *out)
{
    unsigned i;
    if (!g_round84_errata) return 0;
    for (i = 0; i < sizeof r84_ledger / sizeof r84_ledger[0]; i++) {
        const r84_entry_t *e = &r84_ledger[i];
        if (e->sig == in.sig && e->se == in.se
            && e->insn == insn && e->rc == (uint8_t)rc) {
            out->se = e->out_se;
            out->sig = e->out_sig;
            return 1;
        }
    }
    return 0;
}

/* H1713: paired arithmetic is independently validated, not two standalone calls.
 * The old body below remains isolated historical source when this is enabled. */
static fsincos_status_t general_paired_ref(x80_t, x80_t *, x80_t *, sf_rc_t);
static fsincos_status_t fsincos_ref(x80_t in, x80_t *sin_out, x80_t *cos_out, sf_rc_t rc)
{
    if (G_GENERAL_PAIRED) return general_paired_ref(in, sin_out, cos_out, rc);
    if (x87_invalid_encoding(in)) {
        *sin_out = X87_INDEFINITE;
        *cos_out = X87_INDEFINITE;
        return FSINCOS_OK;
    }
    sf_t x = sf_from_parts((in.se >> 15) & 1, in.se & 0x7FFF, in.sig);
    sf_t s, c;
    fsincos_status_t st = sincos_core(x, 0, rc, &s);
    if (st != FSINCOS_OK) return st;
    (void)sincos_core(x, 1, rc, &c);
    sf_to_x87(&s, &sin_out->se, &sin_out->sig);
    sf_to_x87(&c, &cos_out->se, &cos_out->sig);
    return FSINCOS_OK;
}

#include "general/standalone_tiny.h"

/* Default standalone entry: original encoding guard, exact tiny rule and
 * fixed polynomial/table program. The captured-operand R84 ledger is never
 * consulted here. Save/restore the old dispatch state so paired FSINCOS and
 * sibling instructions retain their pre-promotion behavior. */
static fsincos_status_t general_standalone_ref(
    x80_t in, int phase, x80_t *out, sf_rc_t rc)
{
    g_general_c1 = 0;
    g_general_c1_known = 1;
    if ((in.se & 0x7fff) != 0 && !(in.sig >> 63)) {
        *out = X87_INDEFINITE;
        return FSINCOS_OK;
    }
    if (h1638_tiny_entry(in, phase, rc, out)) return FSINCOS_OK;
    sf_t x = sf_from_parts(in.se >> 15, in.se & 0x7fff, in.sig), result;
    int old_active = g_general_standalone_active;
    int old_sin = g_fsin_standalone_path, old_cos = g_fcos_standalone_path;
    g_general_standalone_active = 1;
    g_fsin_standalone_path = phase == 0;
    g_fcos_standalone_path = phase == 1;
    fsincos_status_t status = sincos_core(x, phase, rc, &result);
    g_general_standalone_active = old_active;
    g_fsin_standalone_path = old_sin;
    g_fcos_standalone_path = old_cos;
    if (status != FSINCOS_OK) {
        g_general_c1_known = 0;
        return status;
    }
    sf_to_x87(&result, &out->se, &out->sig);
    return FSINCOS_OK;
}

#include "general/paired.h"

/* single-output entry point used to validate the
 * separately implemented and validated standalone FSIN path. */
static fsincos_status_t fsin_ref(x80_t in, x80_t *sin_out, sf_rc_t rc)
{
    if (G_GENERAL_STANDALONE)
        return general_standalone_ref(in, 0, sin_out, rc);
    if (x87_invalid_encoding(in)) {
        *sin_out = X87_INDEFINITE;
        return FSINCOS_OK;
    }
    sf_t x = sf_from_parts(
        (in.se >> 15) & 1, in.se & 0x7FFF, in.sig);
    sf_t s;
    fsincos_status_t st = sincos_core(x, 0, rc, &s);
    if (st != FSINCOS_OK) return st;
    sf_to_x87(&s, &sin_out->se, &sin_out->sig);
    (void)r84_lookup(in, R84_FSIN, rc, sin_out);
    return FSINCOS_OK;
}

/* single-output entry point used to validate the
 * separately implemented and validated standalone FCOS path and FSIN's odd-quadrant
 * internal cosine producer. */
static fsincos_status_t fcos_ref(x80_t in, x80_t *cos_out, sf_rc_t rc)
{
    if (G_GENERAL_STANDALONE)
        return general_standalone_ref(in, 1, cos_out, rc);
    if (x87_invalid_encoding(in)) {
        *cos_out = X87_INDEFINITE;
        return FSINCOS_OK;
    }
    sf_t x = sf_from_parts(
        (in.se >> 15) & 1, in.se & 0x7FFF, in.sig);
    sf_t c;
    fsincos_status_t st = sincos_core(x, 1, rc, &c);
    if (st != FSINCOS_OK) return st;
    sf_to_x87(&c, &cos_out->se, &cos_out->sig);
    (void)r84_lookup(in, R84_FCOS, rc, cos_out);
    return FSINCOS_OK;
}

/* h251-h258 F2XM1 reconstruction entry point. */
static fsincos_status_t f2xm1_ref(x80_t in, x80_t *out, sf_rc_t rc)
{
    sf_t x = sf_from_parts(
        (in.se >> 15) & 1, in.se & 0x7FFF, in.sig);
    sf_t result = f2xm1_core(x, rc);
    sf_to_x87(&result, &out->se, &out->sig);
    return FSINCOS_OK;
}

/* h260/h264 FPTAN validation entry point. */
static fsincos_status_t fptan_ref(x80_t in, x80_t *out, sf_rc_t rc)
{
    sf_t x = sf_from_parts(
        (in.se >> 15) & 1, in.se & 0x7FFF, in.sig);
    sf_t result;
    fsincos_status_t status = fptan_core(x, rc, &result);
    if (status != FSINCOS_OK) return status;
    sf_to_x87(&result, &out->se, &out->sig);
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
    /* Literal M66 division differs from the reciprocal seed at this boundary. */
    uint64_t exact_n = fsincos_compat_reduce_n_exact(
        UINT64_C(0xbf6c8cbd5e0341e9), 62);
    if (exact_n != UINT64_C(0x3ceea1f5e06eee73)) {
        printf("FAIL exact M66 quotient = %llx\n",
               (unsigned long long)exact_n);
        fail++;
    }
    /* sin(+0)=+0, sin(-0)=-0, cos(0)=1 */
    x80_t xin = { 0x0000, 0 }, so, co;
    fsincos_ref(xin, &so, &co, SF_RN);
    if (so.se != 0 || so.sig != 0) { printf("FAIL sin(+0)\n"); fail++; }
    if (co.se != 0x3FFF || co.sig != 0x8000000000000000ull) { printf("FAIL cos(0)\n"); fail++; }
    xin.se = 0x8000;
    fsincos_ref(xin, &so, &co, SF_RN);
    if (so.se != 0x8000 || so.sig != 0) { printf("FAIL sin(-0)\n"); fail++; }
    /* F2XM1 exact endpoints and out-of-domain no-writeback behavior. */
    xin = (x80_t){ 0x3FFF, 0x8000000000000000ull };
    f2xm1_ref(xin, &so, SF_RN);
    if (so.se != 0x3FFF || so.sig != 0x8000000000000000ull) {
        printf("FAIL f2xm1(+1)\n"); fail++;
    }
    xin = (x80_t){ 0xBFFF, 0x8000000000000000ull };
    f2xm1_ref(xin, &so, SF_RN);
    if (so.se != 0xBFFE || so.sig != 0x8000000000000000ull) {
        printf("FAIL f2xm1(-1)\n"); fail++;
    }
    xin = (x80_t){ 0x4000, 0x8000000000000000ull };
    f2xm1_ref(xin, &so, SF_RN);
    if (so.se != xin.se || so.sig != xin.sig) {
        printf("FAIL f2xm1 out-of-domain\n"); fail++;
    }
    xin = (x80_t){ 0x8000, 0 };
    fptan_ref(xin, &so, SF_RN);
    if (so.se != xin.se || so.sig != xin.sig) {
        printf("FAIL fptan(-0)\n"); fail++;
    }
    /* C2 for |x| >= 2^63 */
    x80_t big = { 0x403E, 0x8000000000000000ull };  /* 2^63 */
    if (fsincos_ref(big, &so, &co, SF_RN) != FSINCOS_C2) { printf("FAIL C2\n"); fail++; }
    printf(fail ? "SELFTEST: %d FAILURES\n" : "SELFTEST: ok\n", fail);
    return fail ? 1 : 0;
}

/* batch mode: "se_hex sig_hex" per line ->
 * "OK <sin_se> <sin_sig> <cos_se> <cos_sig>" or "C2".
 * Same output format as the x87 capture harness => directly diffable. */
static sf_rc_t g_user_rc = SF_RN;

static int run_batch(void)
{
    unsigned se; unsigned long long sig;
    while (scanf("%x %llx", &se, &sig) == 2) {
        ++h1630_row;
        x80_t in = { (uint16_t)se, (uint64_t)sig }, s, c;
        if (g_dump_internals || g_dump_r59_compact)
            fprintf(stderr, "DI_IN %04x %016llx\n", se, sig);
        if (g_batch_fptan_only) {
            if (fptan_ref(in, &s, g_user_rc) == FSINCOS_C2) {
                puts("C2");
                continue;
            }
            /* NaN/indefinite results push a second copy of the result
             * rather than exact one. */
            if ((s.se & 0x7fff) == 0x7fff)
                printf(
                    "OK %04x %016llx %04x %016llx\n",
                    s.se, (unsigned long long)s.sig,
                    s.se, (unsigned long long)s.sig);
            else
                printf(
                    "OK %04x %016llx 3fff 8000000000000000\n",
                    s.se, (unsigned long long)s.sig);
            continue;
        }
        if (g_batch_f2xm1_only) {
            f2xm1_ref(in, &s, g_user_rc);
            printf(
                "OK %04x %016llx\n",
                s.se, (unsigned long long)s.sig);
            continue;
        }
        if (g_batch_fsin_only) {
            if (fsin_ref(in, &s, g_user_rc) == FSINCOS_C2) {
                puts("C2");
                continue;
            }
            printf(
                "OK %04x %016llx\n",
                s.se, (unsigned long long)s.sig);
            continue;
        }
        if (g_batch_fcos_only) {
            if (fcos_ref(in, &c, g_user_rc) == FSINCOS_C2) {
                puts("C2");
                continue;
            }
            printf(
                "OK %04x %016llx\n",
                c.se, (unsigned long long)c.sig);
            continue;
        }
        if (fsincos_ref(in, &s, &c, g_user_rc) == FSINCOS_C2) { puts("C2"); continue; }
        printf("OK %04x %016llx %04x %016llx\n",
               s.se, (unsigned long long)s.sig, c.se, (unsigned long long)c.sig);
    }
    return 0;
}

/* kernel-entry test mode (H2 driver): lines
 *   "path i1 i0 r_se r_sig c_se c_sig"   (path: 0 small_r, 1 normal_r)
 * -> "se sig" of the kernel result, RN user mode. */
static int run_kernel_test(void)
{
    int path, i1, i0; unsigned rse, cse; unsigned long long rsig, csig;
    while (scanf("%d %d %d %x %llx %x %llx", &path, &i1, &i0, &rse, &rsig, &cse, &csig) == 7) {
        sf_t r = sf_from_parts((rse >> 15) & 1, rse & 0x7FFF, rsig);
        sf_t c = sf_from_parts((cse >> 15) & 1, cse & 0x7FFF, csig);
        sf_t out = path ? normal_r(r, c, i1, i0, SF_RN) : small_r(r, c, i1, i0, SF_RN);
        uint16_t se; uint64_t sig; sf_to_x87(&out, &se, &sig);
        printf("%04x %016llx\n", se, (unsigned long long)sig);
    }
    return 0;
}

int main(int argc, char **argv)
{
    for (int i = 1; i < argc; i++)
        if (!strcmp(argv[i], "--general-trace")) g_general_trace = 1;
    for (int i = 1; i < argc; i++)
        if (!strncmp(argv[i], "--rhi=", 6)) g_rhi_mode = atoi(argv[i] + 6);
    for (int i = 1; i < argc; i++)
        if (!strcmp(argv[i], "--split")) g_sf_split = 1;
    for (int i = 1; i < argc; i++)
        if (!strncmp(argv[i], "--kvar=", 7)) g_kvar = atoi(argv[i] + 7);
    for (int i = 1; i < argc; i++)
        if (!strcmp(argv[i], "--dump-final")) g_dump_final = 1;
    for (int i = 1; i < argc; i++)
        if (!strcmp(argv[i], "--dump-internals")) g_dump_internals = 1;
    for (int i = 1; i < argc; i++)
        if (!strcmp(argv[i], "--dump-r59-compact"))
            g_dump_r59_compact = 1;
    for (int i = 1; i < argc; i++)
        if (!strncmp(argv[i], "--sinechain=", 12))
            g_sinechain = atoi(argv[i] + 12);
    for (int i = 1; i < argc; i++)
        if (!strncmp(argv[i], "--sinefin=", 10))
            g_sinefin = atoi(argv[i] + 10);
    for (int i = 1; i < argc; i++)
        if (!strncmp(argv[i], "--sp3=", 6)) {
            int b; char m;
            if (sscanf(argv[i] + 6, "%d:%c", &b, &m) == 2) {
                g_sp3[0] = b;
                g_sp3[1] = m == 'r' ? P5_ROUND_RN
                         : m == 'a' ? P5_ROUND_AWAY
                         : m == 'o' ? P5_ROUND_ODD
                         : P5_ROUND_CHOP;
            }
        }
    for (int i = 1; i < argc; i++)
        if (!strncmp(argv[i], "--sineedges=", 12)) {
            strncpy(g_sineedges, argv[i] + 12, 7);
            g_sineedges[7] = 0;
        }
    for (int i = 1; i < argc; i++)
        if (!strncmp(argv[i], "--sinespec=", 11)) {
            int pb, sb; char pmc, smc;
            if (sscanf(argv[i] + 11, "%d:%c:%d:%c",
                       &pb, &pmc, &sb, &smc) == 4) {
                g_sinespec[0] = pb;
                g_sinespec[1] = pmc == 'r' ? P5_ROUND_RN
                              : pmc == 'a' ? P5_ROUND_AWAY
                              : P5_ROUND_CHOP;
                g_sinespec[2] = sb;
                g_sinespec[3] = smc == 'r' ? P5_ROUND_RN
                              : smc == 'a' ? P5_ROUND_AWAY
                              : P5_ROUND_CHOP;
            }
        }
    for (int i = 1; i < argc; i++)
        if (!strncmp(argv[i], "--rcfold=", 9)) {
            const char *p = argv[i] + 9;
            g_rcfold_bits = atoi(p);
            const char *col = strchr(p, ':');
            if (!col || g_rcfold_bits < 60 || g_rcfold_bits > 120) {
                fprintf(stderr, "bad --rcfold=B:rn|chop\n");
                return 2;
            }
            g_rcfold_rn = !strcmp(col + 1, "rn") ? 1
                        : !strcmp(col + 1, "jam") ? 2 : 0;
        }
    for (int i = 1; i < argc; i++)
        if (!strncmp(argv[i], "--perturb=", 10)) {
            const char *p = argv[i] + 10;
            if (!strncmp(p, "poly-sq:", 8)) {
                g_perturb_tgt = 17; g_perturb_delta = atoi(p + 8);
            } else if (!strncmp(p, "poly-f4:", 8)) {
                g_perturb_tgt = 18; g_perturb_delta = atoi(p + 8);
            } else if (!strncmp(p, "neg-mul1:", 9)) {
                g_perturb_tgt = 19; g_perturb_delta = atoi(p + 9);
            } else if (!strncmp(p, "neg-add1:", 9)) {
                g_perturb_tgt = 20; g_perturb_delta = atoi(p + 9);
            } else if (!strncmp(p, "neg-mul2:", 9)) {
                g_perturb_tgt = 21; g_perturb_delta = atoi(p + 9);
            } else if (!strncmp(p, "neg-add2:", 9)) {
                g_perturb_tgt = 22; g_perturb_delta = atoi(p + 9);
            } else if (!strncmp(p, "pos-mul1:", 9)) {
                g_perturb_tgt = 23; g_perturb_delta = atoi(p + 9);
            } else if (!strncmp(p, "pos-add1:", 9)) {
                g_perturb_tgt = 24; g_perturb_delta = atoi(p + 9);
            } else if (!strncmp(p, "pos-mul2:", 9)) {
                g_perturb_tgt = 25; g_perturb_delta = atoi(p + 9);
            } else if (!strncmp(p, "pos-add2:", 9)) {
                g_perturb_tgt = 26; g_perturb_delta = atoi(p + 9);
            } else if (!strncmp(p, "term-left:", 10)) {
                g_perturb_tgt = 27; g_perturb_delta = atoi(p + 10);
            } else if (!strncmp(p, "term-right:", 11)) {
                g_perturb_tgt = 28; g_perturb_delta = atoi(p + 11);
            } else if (!strncmp(p, "term-out:", 9)) {
                g_perturb_tgt = 29; g_perturb_delta = atoi(p + 9);
            } else if (!strncmp(p, "odd:", 4)) {
                g_perturb_tgt = 1; g_perturb_delta = atoi(p + 4);
            } else if (!strncmp(p, "even:", 5)) {
                g_perturb_tgt = 2; g_perturb_delta = atoi(p + 5);
            } else if (!strncmp(p, "sq:", 3)) {
                g_perturb_tgt = 3; g_perturb_delta = atoi(p + 3);
            } else if (!strncmp(p, "f4:", 3)) {
                g_perturb_tgt = 4; g_perturb_delta = atoi(p + 3);
            } else if (!strncmp(p, "mag:", 4)) {
                g_perturb_tgt = 5; g_perturb_delta = atoi(p + 4);
            } else if (!strncmp(p, "umag:", 5)) {
                g_perturb_tgt = 6; g_perturb_delta = atoi(p + 5);
            } else if (!strncmp(p, "red:", 4)) {
                g_perturb_tgt = 7; g_perturb_delta = atoi(p + 4);
            } else if (!strncmp(p, "left:", 5)) {
                g_perturb_tgt = 8; g_perturb_delta = atoi(p + 5);
            } else if (!strncmp(p, "right:", 6)) {
                g_perturb_tgt = 9; g_perturb_delta = atoi(p + 6);
            } else if (!strncmp(p, "h235sq:", 7)) {
                g_perturb_tgt = 10; g_perturb_delta = atoi(p + 7);
            } else if (!strncmp(p, "h235f4:", 7)) {
                g_perturb_tgt = 11; g_perturb_delta = atoi(p + 7);
            } else if (!strncmp(p, "h235neg:", 8)) {
                g_perturb_tgt = 12; g_perturb_delta = atoi(p + 8);
            } else if (!strncmp(p, "h235pos:", 8)) {
                g_perturb_tgt = 13; g_perturb_delta = atoi(p + 8);
            } else if (!strncmp(p, "h235tail:", 9)) {
                g_perturb_tgt = 14; g_perturb_delta = atoi(p + 9);
            } else if (!strncmp(p, "spoly:", 6)) {
                g_perturb_tgt = 15; g_perturb_delta = atoi(p + 6);
            } else if (!strncmp(p, "payload:", 8)) {
                g_perturb_tgt = 16; g_perturb_delta = atoi(p + 8);
            } else {
                fprintf(stderr,
                    "bad --perturb producer:delta selector\n");
                return 2;
            }
            if (g_perturb_delta < -4 || g_perturb_delta > 4) {
                fprintf(stderr, "--perturb delta must be -4..4\n");
                return 2;
            }
        }
    for (int i = 1; i < argc; i++)
        if (!strncmp(argv[i], "--round55-narrow-sine-fraction14=", 33))
            g_round55_narrow_fraction14 = atoi(argv[i] + 33);
    for (int i = 1; i < argc; i++)
        if (!strcmp(argv[i], "--debug-sine-state"))
            g_debug_sine_state = 1;
    for (int i = 1; i < argc; i++)
        if (!strcmp(argv[i], "--debug-cosine-carrier"))
            g_debug_cosine_carrier = 1;
    for (int i = 1; i < argc; i++)
        if (!strncmp(argv[i], "--round49-correction-delta=", 27)) {
            g_round49_correction_delta = atoi(argv[i] + 27);
            if (
                g_round49_correction_delta < -8
                || g_round49_correction_delta > 8
            ) {
                fprintf(stderr, "Round-49 correction delta must be -8..8\n");
                return 2;
            }
        }
    for (int i = 1; i < argc; i++)
        if (!strcmp(argv[i], "--fsin-table-shared"))
            g_fsin_table_terminal = 0;
    for (int i = 1; i < argc; i++)
        if (!strcmp(argv[i], "--fsin-standalone")) {
            g_fsin_standalone_path = 1;
            g_batch_fsin_only = 1;
        } else if (!strcmp(argv[i], "--fcos-standalone")) {
            g_fcos_standalone_path = 1;
            g_batch_fcos_only = 1;
        } else if (!strcmp(argv[i], "--f2xm1")) {
            g_batch_f2xm1_only = 1;
        } else if (!strcmp(argv[i], "--fptan")) {
            g_batch_fptan_only = 1;
        } else if (!strcmp(argv[i], "--fsin-shared")) {
            g_batch_fsin_only = 1;
        }
    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "--rc=rd")) g_user_rc = SF_RD;
        else if (!strcmp(argv[i], "--rc=ru")) g_user_rc = SF_RU;
        else if (!strcmp(argv[i], "--rc=rz")) g_user_rc = SF_RZ;
    }
    if (argc >= 2 && !strcmp(argv[1], "--fma-test")) return run_fma_test();
    if (argc >= 2 && !strcmp(argv[1], "--selftest")) return selftest();
    if (argc >= 2 && !strcmp(argv[1], "--batch"))    return run_batch();
    if (argc >= 2 && !strcmp(argv[1], "--kernel-test")) return run_kernel_test();
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
        "usage: %s <se_hex4> <sig_hex16> | --selftest | --fma-test"
        " | --batch [--fsin-table-shared]"
        " [--fsin-standalone|--fcos-standalone|--f2xm1|--fptan|--fsin-shared]\n",
        argv[0]);
    return 2;
}
