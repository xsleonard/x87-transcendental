/* Exact targeted search for a second external R1382 witness.
 *
 * The positive Horner result is a monotone step function of the 67-bit
 * fourth-power significand.  On each maximal interval where that result is
 * constant, the hard R1382 right-product condition becomes the linear
 * modular inequality
 *
 *     RIGHT_LOW72 <= (fourth * positive) mod 2^72 <= RIGHT_HIGH72.
 *
 * We count and locate every solution of that inequality with Euclidean
 * floor-sums instead of scanning the interval.  Each resulting fourth power
 * is inverted exactly through the chopped square and first-square maps, then
 * checked by H1469's reduced d0d0-path prefilter.  Outside d0d0's complete
 * intermediate rounding schedule this is not sufficient, so every emitted
 * operand requires independent incumbent/candidate replay.  Random sampling
 * chooses step-function intervals; it does not make this an exhaustive search
 * or an UNSAT proof.
 *
 * No x87 instruction is executed and this file does not alter the emulator.
 */
#define H1469_NO_MAIN 1
#include "h1469_r1382_targeted_wrap.c"

#include <errno.h>

static const u128 F_FIRST = (u128)1 << 66;
static const u128 F_LAST = ((u128)1 << 67) - 3;
static const u128 MOD72 = (u128)1 << 72;

static u128 positive_sig(u128 fourth_sig)
{
    fpv fourth = {0, -76, fourth_sig};
    fpv positive = chain(fourth, C6_6, C6_4, C6_2);
    if (positive.sign != 0 || positive.e2 != -68) {
        fprintf(stderr, "positive chain escaped fixed sign/binade\n");
        exit(3);
    }
    return positive.sig;
}

static u128 low72_product(u128 left, u128 right)
{
    u256 product = mul128(left, right);
    return ((u128)(product.w[1] & UINT64_C(0xff)) << 64)
         | product.w[0];
}

static u128 floor_sum_unsigned(u128 n, u128 modulus, u128 multiplier,
                               u128 offset)
{
    u128 answer = 0;
    for (;;) {
        if (multiplier >= modulus) {
            answer += (n - 1) * n * (multiplier / modulus) / 2;
            multiplier %= modulus;
        }
        if (offset >= modulus) {
            answer += n * (offset / modulus);
            offset %= modulus;
        }
        u128 y_max = multiplier * n + offset;
        if (y_max < modulus)
            return answer;
        n = y_max / modulus;
        offset = y_max % modulus;
        u128 swap = modulus;
        modulus = multiplier;
        multiplier = swap;
    }
}

static u128 count_residue_less(u128 multiplier, u128 first, u128 last,
                               u128 limit)
{
    if (first > last || limit == 0)
        return 0;
    u128 n = last - first + 1;
    if (limit >= MOD72)
        return n;
    u128 offset = low72_product(multiplier, first);
    u128 base = floor_sum_unsigned(n, MOD72, multiplier, offset);
    u128 shifted = floor_sum_unsigned(
        n, MOD72, multiplier, offset + MOD72 - limit);
    return n - (shifted - base);
}

static u128 count_interval_hits(u128 multiplier, u128 first, u128 last)
{
    return count_residue_less(multiplier, first, last, RIGHT_HIGH72 + 1)
         - count_residue_less(multiplier, first, last, RIGHT_LOW72);
}

static u128 first_interval_hit(u128 multiplier, u128 first, u128 last)
{
    if (count_interval_hits(multiplier, first, last) == 0)
        return last + 1;
    u128 low = first;
    u128 high = last;
    while (low < high) {
        u128 midpoint = low + ((high - low) >> 1);
        if (count_interval_hits(multiplier, first, midpoint) != 0)
            high = midpoint;
        else
            low = midpoint + 1;
    }
    return low;
}

static void constant_positive_interval(u128 sample, u128 target,
                                       u128 *first, u128 *last)
{
    u128 low = F_FIRST;
    u128 high = sample;
    while (low < high) {
        u128 midpoint = low + ((high - low) >> 1);
        if (positive_sig(midpoint) < target)
            low = midpoint + 1;
        else
            high = midpoint;
    }
    *first = low;

    low = sample;
    high = F_LAST + 1;
    while (low < high) {
        u128 midpoint = low + ((high - low) >> 1);
        if (midpoint <= F_LAST && positive_sig(midpoint) <= target)
            low = midpoint + 1;
        else
            high = midpoint;
    }
    *last = low - 1;
}

static u128 fourth_from_square(u128 square_sig)
{
    fpv square = {0, -71, square_sig};
    fpv fourth = mul_chop67(square, square);
    if (fourth.e2 != -76)
        return 0;
    return fourth.sig;
}

static int square_preimage(u128 fourth_sig, u128 *square_sig)
{
    u128 low = Q_FIRST;
    u128 high = Q_LAST;
    while (low < high) {
        u128 midpoint = low + ((high - low) >> 1);
        if (fourth_from_square(midpoint) < fourth_sig)
            low = midpoint + 1;
        else
            high = midpoint;
    }
    if (fourth_from_square(low) != fourth_sig)
        return 0;
    *square_sig = low;
    return 1;
}

static fpv mul_chop67_trace(fpv left, fpv right, int *shift)
{
    u256 product = mul128(left.sig, right.sig);
    int length = bitlen256(&product);
    *shift = length - 67;
    return mul_chop67(left, right);
}

static fpv add_rn64_trace(fpv left, fpv right, int *shift, int *increment)
{
    int scale = left.e2 < right.e2 ? left.e2 : right.e2;
    __int128 accumulator = 0;
    accumulator += (left.sign ? -(__int128)1 : (__int128)1)
                 * (__int128)(left.sig << (left.e2 - scale));
    accumulator += (right.sign ? -(__int128)1 : (__int128)1)
                 * (__int128)(right.sig << (right.e2 - scale));
    u128 magnitude = accumulator < 0
                   ? (u128)(-accumulator) : (u128)accumulator;
    *shift = bitlen128(magnitude) - 64;
    *increment = 0;
    if (*shift > 0) {
        u128 top = magnitude >> *shift;
        int guard = (int)((magnitude >> (*shift - 1)) & 1);
        u128 below = magnitude & (((u128)1 << (*shift - 1)) - 1);
        *increment = guard && (below || (top & 1));
    }
    return add_rn64(left, right);
}

static fpv chain_trace(fpv fourth, fpv lead, fpv middle, fpv last,
                       int *mul1_shift, int *add1_shift, int *add1_round,
                       int *mul2_shift, int *add2_shift, int *add2_round)
{
    fpv first = mul_chop67_trace(fourth, lead, mul1_shift);
    fpv added = add_rn64_trace(
        middle, first, add1_shift, add1_round);
    fpv second = mul_chop67_trace(fourth, added, mul2_shift);
    return add_rn64_trace(last, second, add2_shift, add2_round);
}

static int d0d0_materialization_path(u128 square_sig)
{
    fpv square = {0, -71, square_sig};
    int fourth_shift = 0;
    fpv fourth = mul_chop67_trace(
        square, square, &fourth_shift);
    int nm1 = 0, na1 = 0, nr1 = 0, nm2 = 0, na2 = 0, nr2 = 0;
    fpv negative = chain_trace(
        fourth, C6_5, C6_3, C6_1,
        &nm1, &na1, &nr1, &nm2, &na2, &nr2);
    int pm1 = 0, pa1 = 0, pr1 = 0, pm2 = 0, pa2 = 0, pr2 = 0;
    fpv positive = chain_trace(
        fourth, C6_6, C6_4, C6_2,
        &pm1, &pa1, &pr1, &pm2, &pa2, &pr2);
    int left_shift = 0;
    int right_shift = 0;
    (void)mul_chop67_trace(square, negative, &left_shift);
    (void)mul_chop67_trace(fourth, positive, &right_shift);
    return fourth_shift == 66
        && nm1 == 67 && na1 == 24 && nr1 == 1
        && nm2 == 64 && na2 == 21 && nr2 == 0
        && pm1 == 66 && pa1 == 26 && pr1 == 1
        && pm2 == 64 && pa2 == 23 && pr2 == 0
        && left_shift == 63 && right_shift == 64;
}

static u128 random_fourth(uint64_t *state)
{
    for (;;) {
        u128 offset = ((u128)(rng_next(state) & 3) << 64)
                    | rng_next(state);
        u128 value = F_FIRST + offset;
        if (value <= F_LAST)
            return value;
    }
}

static int selftest(void)
{
    uint64_t state = UINT64_C(0x1470c0decafef00d);
    for (unsigned test = 0; test < 200; ++test) {
        u128 multiplier = (u128)(rng_next(&state) | 1);
        u128 first = random_fourth(&state);
        u128 length = rng_next(&state) % 2000;
        u128 last = first + length;
        if (last > F_LAST)
            last = F_LAST;
        u128 brute = 0;
        u128 expected_first = last + 1;
        for (u128 value = first; value <= last; ++value) {
            u128 residue = low72_product(multiplier, value);
            if (residue >= RIGHT_LOW72 && residue <= RIGHT_HIGH72) {
                if (brute == 0)
                    expected_first = value;
                ++brute;
            }
        }
        u128 counted = count_interval_hits(multiplier, first, last);
        u128 located = first_interval_hit(multiplier, first, last);
        if (counted != brute || located != expected_first) {
            fprintf(stderr, "floor-sum selftest failed at test %u\n", test);
            return 1;
        }
    }

    u128 known_fourth = fourth_from_square(TEMPLATE_Q);
    u128 recovered_square = 0;
    if (!known_fourth || !square_preimage(known_fourth, &recovered_square)
        || recovered_square != TEMPLATE_Q) {
        fprintf(stderr, "known fourth/square inversion failed\n");
        return 1;
    }
    if (!d0d0_materialization_path(TEMPLATE_Q)
        || d0d0_materialization_path(
            ((u128)5 << 64) | UINT64_C(0x805ed72c1597550b))) {
        fprintf(stderr, "d0d0 materialization-path classifier failed\n");
        return 1;
    }
    puts("SELFTEST: ok");
    return 0;
}

int main(int argc, char **argv)
{
    if (argc == 2 && strcmp(argv[1], "--selftest") == 0)
        return selftest();
    if (argc < 3 || argc > 5) {
        fprintf(stderr,
                "usage: INTERVAL_SAMPLES SEED [--fixed-d0d0-path] "
                "[--max-witnesses=N]\n");
        return 2;
    }
    int require_fixed_path = 0;
    uint64_t max_witnesses = 1;
    for (int index = 3; index < argc; ++index) {
        if (strcmp(argv[index], "--fixed-d0d0-path") == 0) {
            require_fixed_path = 1;
        } else if (strncmp(argv[index], "--max-witnesses=", 16) == 0) {
            max_witnesses = strtoull(argv[index] + 16, 0, 10);
            if (!max_witnesses) {
                fprintf(stderr, "maximum witnesses must be nonzero\n");
                return 2;
            }
        } else {
            fprintf(stderr, "unknown option: %s\n", argv[index]);
            return 2;
        }
    }
    errno = 0;
    uint64_t samples = strtoull(argv[1], 0, 10);
    uint64_t state = strtoull(argv[2], 0, 0);
    if (errno || !samples || !state) {
        fprintf(stderr, "samples and seed must be nonzero integers\n");
        return 2;
    }

    uint64_t intervals_with_hits = 0;
    uint64_t right_hits = 0;
    uint64_t square_preimages = 0;
    uint64_t low3_hits = 0;
    uint64_t external_preimages = 0;
    uint64_t reduced_prefilter_hits = 0;
    uint64_t fixed_path_hits = 0;
    uint64_t witnesses = 0;
    for (uint64_t iteration = 0; iteration < samples; ++iteration) {
        u128 sample = random_fourth(&state);
        u128 positive = positive_sig(sample);
        u128 first = 0;
        u128 last = 0;
        constant_positive_interval(sample, positive, &first, &last);
        u128 count = count_interval_hits(positive, first, last);
        if (!count)
            continue;
        ++intervals_with_hits;

        u128 candidate = first_interval_hit(positive, first, last);
        while (candidate <= last) {
            ++right_hits;
            u128 square = 0;
            if (square_preimage(candidate, &square)) {
                ++square_preimages;
                if ((square & 7) == 3) {
                    ++low3_hits;
                    uint64_t external = 0;
                    if (external_preimage(square, &external)) {
                        ++external_preimages;
                        right_path path = run_right(square);
                        if (reduced_path_prefilter(square, &path)) {
                            ++reduced_prefilter_hits;
                            int fixed = d0d0_materialization_path(square);
                            if (fixed)
                                ++fixed_path_hits;
                            if (require_fixed_path && !fixed)
                                goto next_candidate;
                            if (square != TEMPLATE_Q) {
                                printf("PRECANDIDATE 3ffc %016" PRIx64
                                       " square ", external);
                                print_u128_hex(square);
                                printf(" fourth ");
                                print_u128_hex(candidate);
                                printf(" right_low72 ");
                                print_u128_hex(low72(&path.right_product));
                                printf(" iteration %" PRIu64 "\n", iteration);
                                ++witnesses;
                                if (witnesses == max_witnesses)
                                    return 0;
                            }
                        }
                    }
                }
            }
next_candidate:
            if (candidate == last)
                break;
            candidate = first_interval_hit(positive, candidate + 1, last);
        }
    }

    printf("NO_WITNESS samples=%" PRIu64
           " intervals_with_hits=%" PRIu64
           " right_hits=%" PRIu64
           " square_preimages=%" PRIu64
           " low3_hits=%" PRIu64
           " external_preimages=%" PRIu64
           " reduced_prefilter_hits=%" PRIu64
           " fixed_path_hits=%" PRIu64
           " witnesses=%" PRIu64
           " require_fixed_path=%d"
           " final_seed=%" PRIu64 "\n",
           samples, intervals_with_hits, right_hits, square_preimages,
           low3_hits, external_preimages, reduced_prefilter_hits,
           fixed_path_hits, witnesses, require_fixed_path, state);
    return witnesses ? 0 : 1;
}
