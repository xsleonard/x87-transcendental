/* Exact modular-lattice search for the R1382 product-cut-45 arm.
 *
 * H1470 targets d0d0's right-product shift 64 and therefore only exercises
 * H1495's absolute selector column 46.  On the shift-63 arm, s4=66,
 * side=1, low3=3, distance=9, and payload=2, the incumbent hard-3x merge
 * changes b1 from zero to one when the 63 discarded product bits lie in
 *
 *   [0x2aaaaaaaaaaaaaab, 0x2aaabfffffffffff].
 *
 * The recovered tie law uses floor division: base0=-4 without the merge and
 * base0=-2 with it both give u0=-1.  The comparator change is therefore
 * architecturally inert throughout this fixed cell.  Exact terminal discard
 * zero also fixes bits 71:63 of the right product to four.  This file reuses
 * H1470's plateau/floor-sum and exact square-inverse machinery to find a
 * strongest adversary: an exact external operand that changes b1, lies in the
 * formerly proposed Mreg window, and has an endpoint-visible residue, yet
 * must retain the same output because u0 is unchanged.
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


static const u128 C45_DISCARD_LOW = ((u128)0x2aaaaaaaaaaaaaabULL);
static const u128 C45_DISCARD_HIGH = ((u128)0x2aaabfffffffffffULL);
static const u128 C45_RIGHT_LOW72 = ((u128)4 << 63) | C45_DISCARD_LOW;
static const u128 C45_RIGHT_HIGH72 = ((u128)4 << 63) | C45_DISCARD_HIGH;


typedef struct {
    uint64_t right_shift_path;
    uint64_t left_path;
    uint64_t active_gate;
    uint64_t mreg_negative;
    uint64_t mreg_window;
    uint64_t positive_terminal;
    uint64_t retained_binade;
    uint64_t zero_discard;
    uint64_t endpoint_residue;
} c45_filter_counts;


static u128 c45_count_interval_hits(u128 multiplier, u128 first, u128 last)
{
    return count_residue_less(
        multiplier, first, last, C45_RIGHT_HIGH72 + 1)
        - count_residue_less(
            multiplier, first, last, C45_RIGHT_LOW72);
}


static u128 c45_first_interval_hit(u128 multiplier, u128 first, u128 last)
{
    if (c45_count_interval_hits(multiplier, first, last) == 0)
        return last + 1;
    u128 low = first;
    u128 high = last;
    while (low < high) {
        u128 midpoint = low + ((high - low) >> 1);
        if (c45_count_interval_hits(multiplier, first, midpoint) != 0)
            high = midpoint;
        else
            low = midpoint + 1;
    }
    return low;
}


static int c45_path_prefilter(u128 square_sig,
                              const right_path *right_path_value,
                              c45_filter_counts *counts,
                              unsigned *base_low9_out)
{
    fpv square = {0, -71, square_sig};
    fpv fourth = right_path_value->fourth;
    fpv positive = right_path_value->positive;
    fpv right = right_path_value->right;
    if (fourth.e2 != -76 || positive.e2 != -68 || right.e2 != -81)
        return 0;
    ++counts->right_shift_path;

    fpv negative = chain(fourth, C6_5, C6_3, C6_1);
    fpv left = mul_chop67(square, negative);
    if (negative.e2 != -64 || left.e2 != -72)
        return 0;
    ++counts->left_path;

    u256 left_product = mul128(square.sig, negative.sig);
    if (((left_product.w[0] >> 58) & 7) == 0)
        return 0;
    ++counts->active_gate;

    u256 square_product = mul128(square.sig, square.sig);
    u128 t4 = ((u128)(square_product.w[1] & 3) << 64)
            | square_product.w[0];
    u128 sqlow = square.sig - ((u128)1 << 66);
    __int128 mreg = (__int128)(3 * sqlow) - (__int128)t4;
    if (mreg >= 0)
        return 0;
    ++counts->mreg_negative;
    if (mreg < -((__int128)1 << 66))
        return 0;
    ++counts->mreg_window;

    u128 source = (left.sig << 9) + 4;
    if (source <= right.sig)
        return 0;
    ++counts->positive_terminal;
    u128 umag = source - right.sig;
    if (bitlen128(umag) != 75)
        return 0;
    ++counts->retained_binade;
    if (umag & (((u128)1 << 9) - 1))
        return 0;
    ++counts->zero_discard;

    unsigned base_low9 = (unsigned)(
        (left.sig - (right.sig >> 9)) & 0x1ff);
    *base_low9_out = base_low9;
    if (!endpoint_residue(base_low9))
        return 2;
    ++counts->endpoint_residue;
    return 1;
}


static int c45_selftest(void)
{
    uint64_t state = UINT64_C(0x1497c045cafef00d);
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
            if (residue >= C45_RIGHT_LOW72
                && residue <= C45_RIGHT_HIGH72) {
                if (brute == 0)
                    expected_first = value;
                ++brute;
            }
        }
        u128 counted = c45_count_interval_hits(multiplier, first, last);
        u128 located = c45_first_interval_hit(multiplier, first, last);
        if (counted != brute || located != expected_first) {
            fprintf(stderr, "column-45 floor-sum selftest failed at %u\n",
                    test);
            return 1;
        }
    }
    puts("SELFTEST: ok");
    return 0;
}


#ifndef H1497_NO_MAIN
int main(int argc, char **argv)
{
    if (argc == 2 && strcmp(argv[1], "--selftest") == 0)
        return c45_selftest();
    if (argc < 3 || argc > 4) {
        fprintf(stderr,
                "usage: INTERVAL_SAMPLES SEED [--max-witnesses=N]\n");
        return 2;
    }
    uint64_t max_witnesses = 1;
    if (argc == 4) {
        if (strncmp(argv[3], "--max-witnesses=", 16) != 0) {
            fprintf(stderr, "unknown option: %s\n", argv[3]);
            return 2;
        }
        max_witnesses = strtoull(argv[3] + 16, 0, 10);
        if (!max_witnesses) {
            fprintf(stderr, "maximum witnesses must be nonzero\n");
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
    uint64_t witnesses = 0;
    c45_filter_counts filter_counts = { 0 };
    for (uint64_t iteration = 0; iteration < samples; ++iteration) {
        u128 sample = random_fourth(&state);
        u128 positive = positive_sig(sample);
        u128 first = 0;
        u128 last = 0;
        constant_positive_interval(sample, positive, &first, &last);
        u128 count = c45_count_interval_hits(positive, first, last);
        if (!count)
            continue;
        ++intervals_with_hits;

        u128 candidate = c45_first_interval_hit(positive, first, last);
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
                        unsigned base_low9 = 0;
                        int filter_state = c45_path_prefilter(
                            square, &path, &filter_counts, &base_low9);
                        if (filter_state == 2) {
                            printf("NEARCANDIDATE45 3ffc %016" PRIx64
                                   " square ", external);
                            print_u128_hex(square);
                            printf(" fourth ");
                            print_u128_hex(candidate);
                            printf(" right_low72 ");
                            print_u128_hex(low72(&path.right_product));
                            printf(" base_low9 %03x iteration %" PRIu64
                                   "\n", base_low9, iteration);
                        } else if (filter_state == 1) {
                            ++reduced_prefilter_hits;
                            printf("INERTCANDIDATE45 3ffc %016" PRIx64
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
            if (candidate == last)
                break;
            candidate = c45_first_interval_hit(
                positive, candidate + 1, last);
        }
    }

    printf("NO_INERT_WITNESS samples=%" PRIu64
           " intervals_with_hits=%" PRIu64
           " right_hits=%" PRIu64
           " square_preimages=%" PRIu64
           " low3_hits=%" PRIu64
           " external_preimages=%" PRIu64
           " right_shift_path=%" PRIu64
           " left_path=%" PRIu64
           " active_gate=%" PRIu64
           " mreg_negative=%" PRIu64
           " mreg_window=%" PRIu64
           " positive_terminal=%" PRIu64
           " retained_binade=%" PRIu64
           " zero_discard=%" PRIu64
           " endpoint_residue=%" PRIu64
           " reduced_prefilter_hits=%" PRIu64
           " witnesses=%" PRIu64
           " final_seed=%" PRIu64 "\n",
           samples, intervals_with_hits, right_hits, square_preimages,
           low3_hits, external_preimages,
           filter_counts.right_shift_path, filter_counts.left_path,
           filter_counts.active_gate, filter_counts.mreg_negative,
           filter_counts.mreg_window, filter_counts.positive_terminal,
           filter_counts.retained_binade, filter_counts.zero_discard,
           filter_counts.endpoint_residue, reduced_prefilter_hits,
           witnesses, state);
    return witnesses ? 0 : 1;
}
#endif
