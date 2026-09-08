/* h491_scan.c — dense-map tie scanner for the FCOS carrier terminal.
 *
 * Transcribes the hardware-validated Python forward() (h479a, which
 * reproduced 1916/1916 corpus2 rows and predicted 2,205 hardware
 * outcomes with zero OTHER results): for each input m at se=3ffc
 * (value m*2^-66), runs the P5C6 cosine polynomial replica and emits
 * one line per OBSERVABLE EXACT TIE of the terminal subtract, in
 * PRE-PATCH coordinates with patch lanes excluded:
 *
 *   m_hex dist low3 k rud t4hi12 rdhi12 R_hex corr_e
 *
 * Usage: h491_scan START_HEX COUNT   (scans [START, START+COUNT))
 * Compile: gcc -O2 -o h491_scan h491_scan.c
 * A different input binade can be selected at compile time with
 * -DMAG_E2=<value>; the historical se=3ffc scan uses the default -66.
 * The h1384 analysis extension appends the fourth-product cut s4 when
 * compiled with -DMERGE_STATE=1.  The h1389 extension appends s4 and the
 * literal-P5 QX propagate-run length with -DQX_STATE=1.  Default output
 * remains unchanged.
 */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef unsigned __int128 u128;
typedef struct { uint64_t w[4]; } u256;   /* little-endian limbs */

#ifndef MAG_E2
#define MAG_E2 (-66)
#endif

#ifndef MERGE_STATE
#define MERGE_STATE 0
#endif

#ifndef QX_STATE
#define QX_STATE 0
#endif

#ifndef QX_MIN
#define QX_MIN 0
#endif

#ifndef Q_STATE
#define Q_STATE 0
#endif

#ifndef Q_MIN
#define Q_MIN 0
#endif

static u256 mul128(u128 a, u128 b)
{
    uint64_t a0 = (uint64_t)a, a1 = (uint64_t)(a >> 64);
    uint64_t b0 = (uint64_t)b, b1 = (uint64_t)(b >> 64);
    u128 p00 = (u128)a0 * b0;
    u128 p01 = (u128)a0 * b1;
    u128 p10 = (u128)a1 * b0;
    u128 p11 = (u128)a1 * b1;
    u256 r;
    r.w[0] = (uint64_t)p00;
    u128 mid = (p00 >> 64) + (uint64_t)p01 + (uint64_t)p10;
    r.w[1] = (uint64_t)mid;
    u128 hi = (mid >> 64) + (p01 >> 64) + (p10 >> 64) + (uint64_t)p11;
    r.w[2] = (uint64_t)hi;
    r.w[3] = (uint64_t)(hi >> 64) + (uint64_t)(p11 >> 64);
    return r;
}

static int bitlen256(const u256 *v)
{
    for (int i = 3; i >= 0; i--)
        if (v->w[i])
            return 64 * i + 64 - __builtin_clzll(v->w[i]);
    return 0;
}

static u128 shr256_to128(const u256 *v, int sh)
{
    /* (v >> sh) assuming the result fits in 128 bits */
    int limb = sh / 64, off = sh % 64;
    u128 lo = 0, hi = 0;
    uint64_t w[6] = {0, 0, 0, 0, 0, 0};
    memcpy(w, v->w, sizeof(v->w));
    if (off == 0) {
        lo = w[limb];
        hi = (limb + 1 < 4) ? w[limb + 1] : 0;
    } else {
        lo = (w[limb] >> off) |
             ((limb + 1 < 4) ? ((u128)w[limb + 1] << (64 - off)) : 0);
        hi = ((limb + 1 < 4) ? (w[limb + 1] >> off) : 0) |
             ((limb + 2 < 4) ? ((u128)w[limb + 2] << (64 - off)) : 0);
    }
    return ((u128)0 | lo) | (hi << 64);
}

typedef struct { int sign; int e2; u128 sig; } fpv;   /* sig < 2^67 */

/* magnitude chop to 67 bits of a 128x128 product */
static fpv mul_chop67(fpv a, fpv b)
{
    u256 p = mul128(a.sig, b.sig);
    int L = bitlen256(&p);
    int sh = L - 67;
    fpv r;
    r.sign = a.sign ^ b.sign;
    r.sig = sh > 0 ? shr256_to128(&p, sh) : (u128)p.w[0] << (-sh);
    r.e2 = a.e2 + b.e2 + (sh > 0 ? sh : 0);
    if (sh < 0) r.e2 = a.e2 + b.e2 + sh;
    return r;
}

static int bitlen128(u128 v)
{
    uint64_t hi = (uint64_t)(v >> 64);
    if (hi) return 128 - __builtin_clzll(hi);
    uint64_t lo = (uint64_t)v;
    return lo ? 64 - __builtin_clzll(lo) : 0;
}

#if QX_STATE || Q_STATE
typedef struct { u128 sum, carry; } csa_pair;

static csa_pair p5_csa3(u128 a, u128 b, u128 c)
{
    csa_pair out = {
        a ^ b ^ c,
        ((a & b) | (a & c) | (b & c)) << 1,
    };
    return out;
}

static csa_pair p5_compress4(u128 d, u128 a, u128 b, u128 c)
{
    csa_pair first = p5_csa3(a, b, c);
    return p5_csa3(d, first.sum, first.carry);
}

static int p5_booth_digit(uint64_t multiplier, int row)
{
    static const int8_t booth8[16] = {
         0,  1,  1,  2,  2,  3,  3,  4,
        -4, -3, -3, -2, -2, -1, -1,  0,
    };
    int code = 0;
    for (int out_bit = 0; out_bit < 4; out_bit++) {
        int source_bit = 3 * row - 1 + out_bit;
        if (source_bit >= 0 && source_bit < 64)
            code |= (int)((multiplier >> source_bit) & 1) << out_bit;
    }
    return booth8[code];
}

static csa_pair p5_product_tree(u128 multiplicand, u128 multiplier)
{
    const u128 pp_mask = (((u128)1 << 70) - 1);
    u128 inputs[24] = { 0 };
    int prior_negative = 0;
    for (int row = 0; row < 22; row++) {
        int digit = p5_booth_digit((uint64_t)multiplier, row);
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

    csa_pair level1[6];
    for (int index = 0; index < 6; index++) {
        u128 *wire = &inputs[4 * index];
        level1[index] = p5_compress4(
            wire[0], wire[1], wire[2], wire[3]);
    }
    csa_pair level2[3];
    for (int index = 0; index < 3; index++) {
        csa_pair left = level1[2 * index];
        csa_pair right = level1[2 * index + 1];
        level2[index] = p5_compress4(
            left.sum, left.carry, right.sum, right.carry);
    }
    csa_pair level3 = p5_compress4(
        level2[0].sum, level2[0].carry,
        level2[1].sum, level2[1].carry);
    return p5_compress4(
        level3.sum, level3.carry,
        level2[2].sum, level2[2].carry);
}

static int p5_qx_run(u128 square_input)
{
    csa_pair tree = p5_product_tree(square_input, square_input >> 3);
    csa_pair qx = p5_csa3(
        tree.sum << 3,
        tree.carry << 3,
        square_input * (square_input & 7));
    const u128 sqrt_two_cut = ((u128)5 << 64)
        | (u128)UINT64_C(0xa827999fcef32423);
    int cut = square_input >= sqrt_two_cut ? 67 : 66;
    int run = 0;
    u128 propagate = qx.sum ^ qx.carry;
    for (int position = cut - 1;
         position >= 0 && ((propagate >> position) & 1);
         position--)
        run++;
    return run;
}

static int p5_q_run(u128 square_input)
{
    csa_pair tree = p5_product_tree(square_input, square_input >> 3);
    u256 product = mul128(square_input, square_input >> 3);
    int cut = bitlen256(&product) - 67;
    int run = 0;
    u128 propagate = tree.sum ^ tree.carry;
    for (int position = cut - 1;
         position >= 0 && ((propagate >> position) & 1);
         position--)
        run++;
    return run;
}
#endif

/* signed add, RN to 64 bits (chain adds) */
static fpv add_rn64(fpv l, fpv r)
{
    int scale = l.e2 < r.e2 ? l.e2 : r.e2;
    __int128 acc = 0;
    acc += (l.sign ? -(__int128)1 : (__int128)1) *
           (__int128)(l.sig << (l.e2 - scale));
    acc += (r.sign ? -(__int128)1 : (__int128)1) *
           (__int128)(r.sig << (r.e2 - scale));
    fpv out;
    out.sign = acc < 0;
    u128 mag = acc < 0 ? (u128)(-acc) : (u128)acc;
    int L = bitlen128(mag);
    int sh = L - 64;
    if (sh <= 0) {
        out.sig = mag << (-sh);
        out.e2 = scale + sh;
        return out;
    }
    u128 top = mag >> sh;
    int guard = (mag >> (sh - 1)) & 1;
    u128 below = mag & (((u128)1 << (sh - 1)) - 1);
    if (guard && (below || (top & 1))) {
        top += 1;
        if (top >> 64) { top >>= 1; sh += 1; }
    }
    out.sig = top;
    out.e2 = scale + sh;
    return out;
}

/* architectural rounding of (1 + corr) with corr = -Rv * 2^corr_e */
static uint64_t final_result(u128 Rv, int corr_e, int mode)
{
    /* numerator = 2^(-corr_e) - Rv, then round to 64 bits */
    u128 numerator = ((u128)1 << (-corr_e)) - Rv;
    int L = bitlen128(numerator);
    int sh = L - 64;
    if (sh <= 0) return (uint64_t)(numerator << (-sh));
    u128 kept = numerator >> sh;
    u128 rem = numerator & (((u128)1 << sh) - 1);
    u128 half = (u128)1 << (sh - 1);
    int up = 0;
    if (mode == 0) up = (rem > half || (rem == half && (kept & 1)));
    else if (mode == 2) up = rem != 0;      /* ru (result negative
                                               corr, cos < 1: ru means
                                               round magnitude up) */
    kept += up;
    if (kept >> 64) kept >>= 1;
    return (uint64_t)kept;
}

/* P5 ROM constants (sign, e2, sig) */
static const fpv C6_1 = {1, -68, ((u128)0x7 << 64) | 0xfffffffffffffffeULL};
static const fpv C6_2 = {0, -71, ((u128)0x5 << 64) | 0x5555555555554277ULL};
static const fpv C6_3 = {1, -76, ((u128)0x5 << 64) | 0xb05b05b05a18a1baULL};
static const fpv C6_4 = {0, -82, ((u128)0x6 << 64) | 0x80680675b559f2cfULL};
static const fpv C6_5 = {1, -88, ((u128)0x4 << 64) | 0x9f93af61f5349300ULL};
static const fpv C6_6 = {0, -95, ((u128)0x4 << 64) | 0x7a4f2483514c1af8ULL};

static fpv chain(fpv f4, fpv lead, fpv mid, fpv last)
{
    fpv c = lead;
    c = add_rn64(mid, mul_chop67(f4, c));
    c = add_rn64(last, mul_chop67(f4, c));
    return c;
}

int main(int argc, char **argv)
{
    if (argc != 3) { fprintf(stderr, "usage: START_HEX COUNT\n"); return 2; }
    uint64_t start = strtoull(argv[1], 0, 16);
    uint64_t count = strtoull(argv[2], 0, 10);
    for (uint64_t i = 0; i < count; i++) {
        uint64_t m = start + i;
        fpv mag = {0, MAG_E2, m};
        fpv square = mul_chop67(mag, mag);
        fpv fourth = mul_chop67(square, square);
        fpv neg = chain(fourth, C6_5, C6_3, C6_1);
        fpv pos = chain(fourth, C6_6, C6_4, C6_2);
        fpv left = mul_chop67(square, neg);
        fpv right = mul_chop67(fourth, pos);
        if (left.sign != 1 || right.sign != 0) continue;

        /* left product discarded field for ud/u5d */
        u256 lp = mul128(square.sig, neg.sig);
        int lL = bitlen256(&lp);
        int lsh = lL - 67;
        int ud = 0, u5d = 0;
        if (lsh > 0) {
            u128 disc_top = shr256_to128(&lp, lsh >= 5 ? lsh - 5 : 0);
            u128 mask5 = ((u128)1 << 5) - 1;
            u5d = (int)(disc_top & mask5);
            /* careful: disc = lp mod 2^lsh; top-3/top-5 of disc */
            /* recompute exactly */
            if (lsh >= 5) {
                u128 d5 = shr256_to128(&lp, lsh - 5) & mask5;
                u5d = (int)d5;
                ud = (int)(d5 >> 2);
            } else {
                u128 dfull = shr256_to128(&lp, 0) &
                             (((u128)1 << lsh) - 1);
                u5d = (int)(dfull << (5 - lsh));
                ud = u5d >> 2;
            }
        }
        int low3 = (int)(square.sig & 7);
        int dist = left.e2 - right.e2;
        if (dist < 0) dist = -dist;
        int active = low3 && (ud || (dist == 7 && u5d));
        if (!active) continue;

        /* right product discard top: rud + rdhi12 */
        u256 rp = mul128(fourth.sig, pos.sig);
        int rL = bitlen256(&rp);
        int rsh = rL - 67;
        if (rsh < 12) continue;
        u128 rd12 = shr256_to128(&rp, rsh - 12) & (((u128)1 << 12) - 1);
        int rud = (int)(rd12 >> 11);

        if ((dist == 10 && low3 == 6 && rud) ||
            (dist == 8 && low3 == 7 && ud >= 3)) continue;
        int payload = low3 + 8 - dist;
        if (payload < 0 || payload > 8) continue;

        int scale = left.e2 < right.e2 ? left.e2 : right.e2;
        if (payload && left.e2 - 8 < scale) scale = left.e2 - 8;
        u128 M = (left.sig << (left.e2 - scale))
               + ((u128)payload << (left.e2 - 8 - scale))
               - (right.sig << (right.e2 - scale));
        if (!M || (__int128)M < 0) continue;
        int k = bitlen128(M) - 67;
        if (k < 3) continue;
        u128 mask = (((u128)1 << k) - 1);
        u128 D = M & mask;
        int theta;
        u128 fire_M;
        if (D == 0) { theta = 0; fire_M = M - ((u128)1 << k); }
        else if (D <= 2) { theta = (int)D; fire_M = M - ((u128)1 << k); }
        else if (D >= mask - 1) {
            theta = (int)(D - mask) - 1;              /* -1 or -2 */
            fire_M = M + ((u128)1 << k);
        } else continue;
        u128 R = M >> k;
        int corr_e = scale + k;

        /* observability: exact model value vs borrow/carry neighbor
           at raw scale (keeps the discarded field, so directed-mode
           rounding is exact for near-ties) */
        int obs = 0;
        for (int md = 0; md < 3 && !obs; md++)
            if (final_result(M, scale, md) !=
                final_result(fire_M, scale, md)) obs = 1;
        if (!obs) continue;

        /* f4 tail top 12 */
        u256 f4p = mul128(square.sig, square.sig);
        int fL = bitlen256(&f4p);
        int s4 = fL - 67;
        if (s4 < 12) continue;
        u128 t12 = shr256_to128(&f4p, s4 - 12) & (((u128)1 << 12) - 1);
        /* t12's top bit is f4_g etc.: tail top-12 excludes retained */
        /* (shr at s4-12 gives retained low bits too; mask keeps 12
           bits which are the tail's top 12 since tail = low s4 bits) */

#if QX_STATE
        int qx_run = p5_qx_run(square.sig);
        if (qx_run < QX_MIN)
            continue;
        printf("%016llx %d %d %d %d %03x %03x %01x%016llx %d %d %d %d\n",
               (unsigned long long)m, dist, low3, k, rud,
               (unsigned)(t12 & 0xfff), (unsigned)(rd12 & 0xfff),
               (unsigned)(R >> 64), (unsigned long long)R, corr_e,
               theta, s4, qx_run);
#elif Q_STATE
        int q_run = p5_q_run(square.sig);
        if (q_run < Q_MIN)
            continue;
        printf("%016llx %d %d %d %d %03x %03x %01x%016llx %d %d %d %d\n",
               (unsigned long long)m, dist, low3, k, rud,
               (unsigned)(t12 & 0xfff), (unsigned)(rd12 & 0xfff),
               (unsigned)(R >> 64), (unsigned long long)R, corr_e,
               theta, s4, q_run);
#elif MERGE_STATE
        printf("%016llx %d %d %d %d %03x %03x %01x%016llx %d %d %d\n",
               (unsigned long long)m, dist, low3, k, rud,
               (unsigned)(t12 & 0xfff), (unsigned)(rd12 & 0xfff),
               (unsigned)(R >> 64), (unsigned long long)R, corr_e,
               theta, s4);
#else
        printf("%016llx %d %d %d %d %03x %03x %01x%016llx %d %d\n",
               (unsigned long long)m, dist, low3, k, rud,
               (unsigned)(t12 & 0xfff), (unsigned)(rd12 & 0xfff),
               (unsigned)(R >> 64), (unsigned long long)R, corr_e,
               theta);
#endif
    }
    return 0;
}
