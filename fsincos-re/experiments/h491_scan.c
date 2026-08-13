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
 */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef unsigned __int128 u128;
typedef struct { uint64_t w[4]; } u256;   /* little-endian limbs */

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
        fpv mag = {0, -66, m};
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
        if (M & (((u128)1 << k) - 1)) continue;      /* ties only */
        u128 R = M >> k;
        int corr_e = scale + k;

        /* observability: R vs R-1 differ in any mode */
        int obs = 0;
        for (int md = 0; md < 3 && !obs; md++)
            if (final_result(R, corr_e, md) !=
                final_result(R - 1, corr_e, md)) obs = 1;
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

        printf("%016llx %d %d %d %d %03x %03x %01x%016llx %d\n",
               (unsigned long long)m, dist, low3, k, rud,
               (unsigned)(t12 & 0xfff), (unsigned)(rd12 & 0xfff),
               (unsigned)(R >> 64), (unsigned long long)R, corr_e);
    }
    return 0;
}
