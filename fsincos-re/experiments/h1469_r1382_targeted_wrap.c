/* Deterministic software search for an external R1382 second witness.
 *
 * The exact H1463 comparator interval is only about 2^-16.6 of the right
 * product's low 64 bits.  Uniform operand scans spend almost all their time
 * outside it.  This scanner samples a square significand, measures the exact
 * right-product increment for the next low3=3 square, and jumps to the two
 * lattice points bracketing the next interval midpoint.  Every hit is then
 * checked against the reduced d0d0-path predicates and exact external-square
 * inversion.  Outside d0d0's complete intermediate rounding schedule, the
 * six-residue lemma is only a prefilter; every emitted operand therefore
 * requires independent incumbent/candidate replay.  The jump is a search
 * acceleration, not an exhaustiveness claim.
 *
 * No x87 instruction is executed and this file does not alter the emulator.
 */
#define main h491_scan3_original_main
#include "h491_scan3.c"
#undef main

#include <inttypes.h>

static const u128 Q_FIRST = (u128)1 << 66;
static const u128 Q_LAST = (((u128)5 << 64)
                           | UINT64_C(0xa827999fcef32423)) - 1;
static const u128 RIGHT_LOW72 = ((u128)3 << 64)
                              | UINT64_C(0xaaaaaaaaaaaaaaab);
static const u128 RIGHT_HIGH72 = ((u128)3 << 64)
                               | UINT64_C(0xaaaaffffffffffff);
static const u128 MASK72 = ((u128)1 << 72) - 1;
static const u128 TEMPLATE_Q = ((u128)5 << 64)
                             | UINT64_C(0x52954800a66eecbb);
static const uint64_t SIDE_BOUNDARY = UINT64_C(0xb504f333f9de6800);

typedef struct {
    fpv fourth;
    fpv positive;
    fpv right;
    u256 right_product;
} right_path;

static uint64_t rng_next(uint64_t *state)
{
    uint64_t x = *state;
    x ^= x >> 12;
    x ^= x << 25;
    x ^= x >> 27;
    *state = x;
    return x * UINT64_C(2685821657736338717);
}

#ifndef H1469_NO_MAIN
static u128 random_square(uint64_t *state)
{
    const u128 span = Q_LAST - Q_FIRST + 1;
    for (;;) {
        uint64_t high_source = rng_next(state);
        uint64_t low = rng_next(state);
        u128 offset = ((u128)(high_source & 1) << 64) | low;
        if (offset >= span)
            continue;
        u128 value = Q_FIRST + offset;
        value = (value & ~(u128)7) | 3;
        if (value <= Q_LAST)
            return value;
    }
}
#endif

static right_path run_right(u128 square_sig)
{
    fpv square = {0, -71, square_sig};
    right_path out;
    out.fourth = mul_chop67(square, square);
    out.positive = chain(out.fourth, C6_6, C6_4, C6_2);
    out.right = mul_chop67(out.fourth, out.positive);
    out.right_product = mul128(out.fourth.sig, out.positive.sig);
    return out;
}

static u128 low72(const u256 *value)
{
    return ((u128)(value->w[1] & UINT64_C(0xff)) << 64) | value->w[0];
}

#ifndef H1469_NO_MAIN
static u128 positive_difference(const u256 *high, const u256 *low)
{
    uint64_t words[4];
    uint64_t borrow = 0;
    for (int index = 0; index < 4; ++index) {
        uint64_t a = high->w[index];
        uint64_t b = low->w[index];
        words[index] = a - b - borrow;
        borrow = (a < b) || (borrow && a == b);
    }
    if (borrow || words[2] || words[3]) {
        fprintf(stderr, "right product increment escaped 128 bits\n");
        exit(3);
    }
    return ((u128)words[1] << 64) | words[0];
}
#endif

static uint64_t isqrt128(u128 value)
{
    uint64_t low = 0;
    uint64_t high = UINT64_MAX;
    while (low < high) {
        uint64_t midpoint = low + ((high - low) >> 1) + 1;
        u128 square = (u128)midpoint * midpoint;
        if (square <= value)
            low = midpoint;
        else
            high = midpoint - 1;
    }
    return low;
}

static int external_preimage(u128 square_sig, uint64_t *external)
{
    u128 lower_square = square_sig << 61;
    u128 upper_square = ((square_sig + 1) << 61) - 1;
    uint64_t lower = isqrt128(lower_square);
    if ((u128)lower * lower < lower_square)
        ++lower;
    uint64_t upper = isqrt128(upper_square);
    if (lower != upper || lower < SIDE_BOUNDARY)
        return 0;
    if (((u128)lower * lower >> 61) != square_sig)
        return 0;
    *external = lower;
    return 1;
}

static int endpoint_residue(unsigned value)
{
    static const unsigned residues[6] = {
        0x000, 0x100, 0x001, 0x101, 0x081, 0x180,
    };
    for (int index = 0; index < 6; ++index)
        if (value == residues[index])
            return 1;
    return 0;
}

static int reduced_path_prefilter(u128 square_sig,
                                  const right_path *right_path_value)
{
    fpv square = {0, -71, square_sig};
    fpv fourth = right_path_value->fourth;
    fpv positive = right_path_value->positive;
    fpv right = right_path_value->right;
    if (fourth.e2 != -76 || positive.e2 != -68 || right.e2 != -80)
        return 0;

    fpv negative = chain(fourth, C6_5, C6_3, C6_1);
    fpv left = mul_chop67(square, negative);
    if (negative.e2 != -64 || left.e2 != -72)
        return 0;

    u256 left_product = mul128(square.sig, negative.sig);
    if (((left_product.w[0] >> 58) & 7) == 0)
        return 0;

    u256 square_product = mul128(square.sig, square.sig);
    u128 t4 = ((u128)(square_product.w[1] & 3) << 64)
            | square_product.w[0];
    u128 sqlow = square.sig - ((u128)1 << 66);
    u128 mreg = 3 * sqlow - t4;
    if (mreg >> 66)
        return 0;

    u128 source = (left.sig << 8) + 3;
    if (source <= right.sig)
        return 0;
    u128 umag = source - right.sig;
    if (bitlen128(umag) != 75 || (umag & 0xff))
        return 0;

    unsigned base_low9 = (unsigned)((left.sig - (right.sig >> 8)) & 0x1ff);
    return endpoint_residue(base_low9);
}

static void print_u128_hex(u128 value)
{
    printf("%01" PRIx64 "%016" PRIx64,
           (uint64_t)(value >> 64), (uint64_t)value);
}

#ifndef H1469_NO_MAIN
int main(int argc, char **argv)
{
    if (argc != 3) {
        fprintf(stderr, "usage: ITERATIONS SEED\n");
        return 2;
    }
    uint64_t iterations = strtoull(argv[1], 0, 10);
    uint64_t state = strtoull(argv[2], 0, 0);
    if (!state) {
        fprintf(stderr, "seed must be nonzero\n");
        return 2;
    }

    right_path known = run_right(TEMPLATE_Q);
    if (low72(&known.right_product) < RIGHT_LOW72
        || low72(&known.right_product) > RIGHT_HIGH72
        || !reduced_path_prefilter(TEMPLATE_Q, &known)) {
        fprintf(stderr, "known d0d0 square failed the exact predicate\n");
        return 3;
    }
    uint64_t known_external = 0;
    if (!external_preimage(TEMPLATE_Q, &known_external)
        || known_external != UINT64_C(0xd0d000000cc0b3f8)) {
        fprintf(stderr, "known d0d0 external inversion failed\n");
        return 3;
    }

    const u128 midpoint = RIGHT_LOW72
        + ((RIGHT_HIGH72 - RIGHT_LOW72) >> 1);
    uint64_t interval_hits = 0;
    uint64_t reduced_prefilter_hits = 0;
    uint64_t external_hits = 0;
    for (uint64_t iteration = 0; iteration < iterations; ++iteration) {
        u128 origin = random_square(&state);
        if (origin + 8 > Q_LAST)
            continue;
        right_path first = run_right(origin);
        right_path next = run_right(origin + 8);
        u128 delta = positive_difference(
            &next.right_product, &first.right_product);
        if (!delta || delta >= ((u128)1 << 72))
            continue;
        u128 forward = (midpoint - low72(&first.right_product)) & MASK72;
        u128 step = forward / delta;
        for (unsigned neighbor = 0; neighbor < 2; ++neighbor) {
            u128 candidate = origin + 8 * (step + neighbor);
            if (candidate > Q_LAST || candidate == TEMPLATE_Q)
                continue;
            right_path path = run_right(candidate);
            u128 residue = low72(&path.right_product);
            if (residue < RIGHT_LOW72 || residue > RIGHT_HIGH72)
                continue;
            ++interval_hits;
            if (!reduced_path_prefilter(candidate, &path))
                continue;
            ++reduced_prefilter_hits;
            uint64_t external = 0;
            if (!external_preimage(candidate, &external))
                continue;
            ++external_hits;
            printf("PRECANDIDATE 3ffc %016" PRIx64 " square ", external);
            print_u128_hex(candidate);
            printf(" right_low72 ");
            print_u128_hex(residue);
            printf(" iteration %" PRIu64 "\n", iteration);
            return 0;
        }
    }
    printf("NO_WITNESS iterations=%" PRIu64
           " interval_hits=%" PRIu64
           " reduced_prefilter_hits=%" PRIu64
           " external_hits=%" PRIu64
           " final_seed=%" PRIu64 "\n",
           iterations, interval_hits, reduced_prefilter_hits, external_hits,
           state);
    return 1;
}
#endif
