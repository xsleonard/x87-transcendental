/* h1242_r1237_fadd_scan.c -- preimage scanner for the R1237 FADD boundary.
 *
 * Ordinary input-neighborhood mutations almost never remain on the exact
 * internal halfway surface.  This scanner instead evaluates the validated
 * P5C6 polynomial graph for a dense input interval and emits every second
 * Horner FADD whose RN64 discarded remainder lies within two units below or
 * seven units above one half:
 *
 *   m_hex chain q retained_lsb increments product_bit65 r1237_fires
 *
 * q is remainder-half in exact integer units.  product_bit65 is bit 65 of
 * the unrounded fourth*first_add product; it is the selected MSB of the
 * P5-aligned four-bit CPA word used by R1237.  This is a software-only
 * generator: it neither executes x87 nor consults a hardware result.
 *
 * Usage: h1242_r1237_fadd_scan START_HEX COUNT
 * Compile: cc -O3 -Wall -Wextra -o h1242_r1237_fadd_scan \
 *              h1242_r1237_fadd_scan.c
 */
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef unsigned __int128 u128;
typedef struct { uint64_t w[4]; } u256;   /* little-endian limbs */
typedef struct { int sign; int e2; u128 sig; } fpv;

#ifndef MAG_E2
#define MAG_E2 (-66)
#endif

/* h1293 analysis extension.  The default output above remains byte-for-byte
 * compatible.  FULL_WORD adds the exact/selected P5 columns-62..65 word and
 * the product cut so the complete four-bit comparator can be attacked. */
#ifndef FULL_WORD
#define FULL_WORD 0
#endif

/* h1301 extension.  Compute only after a rare near-half event has been
 * found, and append the ten still-live h1300 P5-tree predicates as a bit
 * mask.  FULL_WORD-only output remains byte-for-byte unchanged. */
#ifndef DEEP_TREE
#define DEEP_TREE 0
#endif

/* h1312 extension.  Append the exact discarded-product remainder after the
 * ordinary FULL_WORD fields.  For this graph product_cut is 63 or 64, so the
 * complete remainder resides in the low 64-bit product limb. */
#ifndef TAIL_STATE
#define TAIL_STATE 0
#endif

static u256 mul128(u128 a, u128 b)
{
    uint64_t a0 = (uint64_t)a, a1 = (uint64_t)(a >> 64);
    uint64_t b0 = (uint64_t)b, b1 = (uint64_t)(b >> 64);
    u128 p00 = (u128)a0 * b0;
    u128 p01 = (u128)a0 * b1;
    u128 p10 = (u128)a1 * b0;
    u128 p11 = (u128)a1 * b1;
    u256 result;
    u128 middle;
    u128 high;

    result.w[0] = (uint64_t)p00;
    middle = (p00 >> 64) + (uint64_t)p01 + (uint64_t)p10;
    result.w[1] = (uint64_t)middle;
    high = (middle >> 64) + (p01 >> 64) + (p10 >> 64)
         + (uint64_t)p11;
    result.w[2] = (uint64_t)high;
    result.w[3] = (uint64_t)(high >> 64) + (uint64_t)(p11 >> 64);
    return result;
}

static int bitlen256(const u256 *value)
{
    int limb;

    for (limb = 3; limb >= 0; --limb) {
        if (value->w[limb])
            return 64 * limb + 64 - __builtin_clzll(value->w[limb]);
    }
    return 0;
}

static int bitlen128(u128 value)
{
    uint64_t high = (uint64_t)(value >> 64);
    uint64_t low = (uint64_t)value;

    if (high)
        return 128 - __builtin_clzll(high);
    return low ? 64 - __builtin_clzll(low) : 0;
}

static u128 shr256_to128(const u256 *value, int shift)
{
    int limb = shift / 64;
    int offset = shift % 64;
    uint64_t words[6] = {0, 0, 0, 0, 0, 0};
    u128 low;
    u128 high;

    memcpy(words, value->w, sizeof(value->w));
    if (!offset) {
        low = words[limb];
        high = limb + 1 < 4 ? words[limb + 1] : 0;
    } else {
        low = (words[limb] >> offset)
            | (limb + 1 < 4
               ? (u128)words[limb + 1] << (64 - offset) : 0);
        high = (limb + 1 < 4 ? words[limb + 1] >> offset : 0)
             | (limb + 2 < 4
                ? (u128)words[limb + 2] << (64 - offset) : 0);
    }
    return low | (high << 64);
}

/* Magnitude chop to 67 bits of a 128-by-128 product. */
static fpv mul_chop67(fpv left, fpv right)
{
    u256 product = mul128(left.sig, right.sig);
    int shift = bitlen256(&product) - 67;
    fpv result;

    result.sign = left.sign ^ right.sign;
    if (shift > 0) {
        result.sig = shr256_to128(&product, shift);
        result.e2 = left.e2 + right.e2 + shift;
    } else {
        result.sig = (u128)product.w[0] << (-shift);
        result.e2 = left.e2 + right.e2 + shift;
    }
    return result;
}

typedef struct {
    fpv rounded;
    int q;
    int retained_lsb;
    int increments;
    int near_half;
} add_trace;

/* Same-sign add, RN to 64 bits, retaining a narrow exact-half trace. */
static add_trace add_rn64_trace(fpv left, fpv right)
{
    int scale = left.e2 < right.e2 ? left.e2 : right.e2;
    u128 magnitude = (left.sig << (left.e2 - scale))
                   + (right.sig << (right.e2 - scale));
    int shift = bitlen128(magnitude) - 64;
    u128 retained;
    u128 remainder;
    u128 half;
    add_trace trace;

    trace.rounded.sign = left.sign;
    trace.q = 0;
    trace.retained_lsb = 0;
    trace.increments = 0;
    trace.near_half = 0;
    if (left.sign != right.sign) {
        fputs("internal error: expected same-sign Horner add\n", stderr);
        exit(3);
    }
    if (shift <= 0) {
        trace.rounded.sig = magnitude << (-shift);
        trace.rounded.e2 = scale + shift;
        return trace;
    }

    retained = magnitude >> shift;
    remainder = magnitude & (((u128)1 << shift) - 1);
    half = (u128)1 << (shift - 1);
    trace.retained_lsb = (int)(retained & 1);
    if (remainder >= half) {
        u128 delta = remainder - half;
        if (delta <= 7) {
            trace.q = (int)delta;
            trace.near_half = 1;
        }
    } else {
        u128 delta = half - remainder;
        if (delta <= 2) {
            trace.q = -(int)delta;
            trace.near_half = 1;
        }
    }
    trace.increments = remainder > half
        || (remainder == half && (retained & 1));
    if (trace.increments) {
        ++retained;
        if (retained >> 64) {
            retained >>= 1;
            ++shift;
        }
    }
    trace.rounded.sig = retained;
    trace.rounded.e2 = scale + shift;
    return trace;
}

static fpv add_rn64(fpv left, fpv right)
{
    return add_rn64_trace(left, right).rounded;
}

#if DEEP_TREE
typedef struct {
    u128 sum;
    u128 carry;
    u128 first_sum;
    u128 first_carry;
} tree_node;

typedef struct {
    u128 rows[22];
    tree_node level1[6];
    tree_node level2[3];
    tree_node level3;
    tree_node final;
} deep_tree_state;

static tree_node tree_compress4(u128 d, u128 a, u128 b, u128 c)
{
    tree_node result;
    result.first_sum = a ^ b ^ c;
    result.first_carry = ((a & b) | (a & c) | (b & c)) << 1;
    result.sum = d ^ result.first_sum ^ result.first_carry;
    result.carry = ((d & result.first_sum)
                  | (d & result.first_carry)
                  | (result.first_sum & result.first_carry)) << 1;
    return result;
}

static int tree_booth_digit(uint64_t multiplier, int row)
{
    static const int8_t booth8[16] = {
         0,  1,  1,  2,  2,  3,  3,  4,
        -4, -3, -3, -2, -2, -1, -1,  0
    };
    int code = 0;
    int output_bit;
    for (output_bit = 0; output_bit < 4; ++output_bit) {
        int source_bit = 3 * row - 1 + output_bit;
        if (source_bit >= 0 && source_bit < 64)
            code |= (int)((multiplier >> source_bit) & 1) << output_bit;
    }
    return booth8[code];
}

static deep_tree_state deep_tree(u128 multiplicand, uint64_t multiplier)
{
    const u128 pp_mask = ((u128)1 << 70) - 1;
    u128 inputs[24] = {0};
    deep_tree_state state;
    int prior_negative = 0;
    int row;
    int index;

    memset(&state, 0, sizeof(state));
    for (row = 0; row < 22; ++row) {
        int digit = tree_booth_digit(multiplier, row);
        u128 magnitude = multiplicand * (u128)(digit < 0 ? -digit : digit);
        u128 encoded = ((u128)1 << 69) | magnitude;
        u128 physical;
        if (digit < 0)
            encoded = (~encoded) & pp_mask;
        physical = (encoded | ((u128)3 << 70)) << (3 * row);
        if (prior_negative)
            physical |= (u128)1 << (3 * (row - 1));
        inputs[row] = physical;
        state.rows[row] = physical;
        prior_negative = digit < 0;
    }
    inputs[22] = (u128)1 << 69;
    for (index = 0; index < 6; ++index) {
        u128 *wire = &inputs[4 * index];
        state.level1[index] = tree_compress4(
            wire[0], wire[1], wire[2], wire[3]);
    }
    for (index = 0; index < 3; ++index) {
        tree_node left = state.level1[2 * index];
        tree_node right = state.level1[2 * index + 1];
        state.level2[index] = tree_compress4(
            left.sum, left.carry, right.sum, right.carry);
    }
    state.level3 = tree_compress4(
        state.level2[0].sum, state.level2[0].carry,
        state.level2[1].sum, state.level2[1].carry);
    state.final = tree_compress4(
        state.level3.sum, state.level3.carry,
        state.level2[2].sum, state.level2[2].carry);
    return state;
}

static int tree_bit(u128 value, int position)
{
    return (int)((value >> position) & 1);
}

static unsigned deep_tree_mask(u128 multiplicand, uint64_t multiplier)
{
    deep_tree_state state = deep_tree(multiplicand, multiplier);
    unsigned mask = 0;
    mask |= (unsigned)tree_bit(state.level1[1].first_carry, 37) << 0;
    mask |= (unsigned)tree_bit(state.level2[0].sum, 60) << 1;
    mask |= (unsigned)tree_bit(state.level2[1].carry, 42) << 2;
    mask |= (unsigned)tree_bit(state.rows[4], 33) << 3;
    mask |= (unsigned)tree_bit(state.rows[7], 21) << 4;
    mask |= (unsigned)tree_bit(state.rows[7], 45) << 5;
    mask |= (unsigned)!tree_bit(state.level1[0].sum, 17) << 6;
    mask |= (unsigned)!tree_bit(state.level2[0].carry, 44) << 7;
    mask |= (unsigned)!tree_bit(state.level2[0].first_sum, 43) << 8;
    mask |= (unsigned)!tree_bit(state.level3.first_sum, 71) << 9;
    return mask;
}
#endif

/* P5 ROM constants (sign, exponent, significand). */
static const fpv C6_1 = {1, -68,
    ((u128)0x7 << 64) | UINT64_C(0xfffffffffffffffe)};
static const fpv C6_2 = {0, -71,
    ((u128)0x5 << 64) | UINT64_C(0x5555555555554277)};
static const fpv C6_3 = {1, -76,
    ((u128)0x5 << 64) | UINT64_C(0xb05b05b05a18a1ba)};
static const fpv C6_4 = {0, -82,
    ((u128)0x6 << 64) | UINT64_C(0x80680675b559f2cf)};
static const fpv C6_5 = {1, -88,
    ((u128)0x4 << 64) | UINT64_C(0x9f93af61f5349300)};
static const fpv C6_6 = {0, -95,
    ((u128)0x4 << 64) | UINT64_C(0x7a4f2483514c1af8)};

static void scan_chain(uint64_t input, const char *name, fpv fourth,
                       fpv lead, fpv middle, fpv last)
{
    fpv first_product = mul_chop67(fourth, lead);
    fpv first_add = add_rn64(middle, first_product);
    fpv second_product = mul_chop67(fourth, first_add);
    add_trace second_add = add_rn64_trace(last, second_product);
    u256 exact_second_product;
    int product_bit65;
    int product_word;
    int product_cut;
    int fires;
#if TAIL_STATE
    uint64_t product_remainder;
#endif
#if DEEP_TREE
    unsigned tree_mask;
#endif

    if (!second_add.near_half)
        return;
    exact_second_product = mul128(fourth.sig, first_add.sig);
    product_bit65 = (int)((exact_second_product.w[1] >> 1) & 1);
    product_word = (int)(shr256_to128(&exact_second_product, 62) & 15);
    product_cut = bitlen256(&exact_second_product) - 67;
#if TAIL_STATE
    product_remainder = exact_second_product.w[0];
    if (product_cut < 64)
        product_remainder &= (UINT64_C(1) << product_cut) - 1;
#endif
    fires = second_add.q >= 0 && second_add.q <= 4
         && second_add.increments
         && (((second_add.q >> 2) & 1) == product_bit65);
#if TAIL_STATE
    printf("%016" PRIx64 " %s %+d %d %d %d %d %x %d %016" PRIx64 "\n",
           input, name, second_add.q, second_add.retained_lsb,
           second_add.increments, product_bit65, fires,
           product_word, product_cut, product_remainder);
#elif DEEP_TREE
    tree_mask = deep_tree_mask(fourth.sig, (uint64_t)first_add.sig);
    printf("%016" PRIx64 " %s %+d %d %d %d %d %x %d %03x\n",
           input, name, second_add.q, second_add.retained_lsb,
           second_add.increments, product_bit65, fires,
           product_word, product_cut, tree_mask);
#elif FULL_WORD
    printf("%016" PRIx64 " %s %+d %d %d %d %d %x %d\n",
           input, name, second_add.q, second_add.retained_lsb,
           second_add.increments, product_bit65, fires,
           product_word, product_cut);
#else
    printf("%016" PRIx64 " %s %+d %d %d %d %d\n",
           input, name, second_add.q, second_add.retained_lsb,
           second_add.increments, product_bit65, fires);
#endif
}

int main(int argc, char **argv)
{
    uint64_t start;
    uint64_t count;
    uint64_t offset;

    if (argc != 3) {
        fputs("usage: START_HEX COUNT\n", stderr);
        return 2;
    }
    start = strtoull(argv[1], NULL, 16);
    count = strtoull(argv[2], NULL, 10);
    if (count && start > UINT64_MAX - (count - 1)) {
        fputs("range wraps uint64_t\n", stderr);
        return 2;
    }
    for (offset = 0; offset < count; ++offset) {
        uint64_t input = start + offset;
        fpv magnitude = {0, MAG_E2, input};
        fpv square = mul_chop67(magnitude, magnitude);
        fpv fourth = mul_chop67(square, square);

        scan_chain(input, "negative", fourth, C6_5, C6_3, C6_1);
        scan_chain(input, "positive", fourth, C6_6, C6_4, C6_2);
    }
    return 0;
}
