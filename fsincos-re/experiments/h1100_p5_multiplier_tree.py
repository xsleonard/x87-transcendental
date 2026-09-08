#!/usr/bin/env python3
"""Literal P5 67x64 radix-8 Booth / four-level 4:2 multiplier tree.

This is a structural transcription of Figures 2, 4, 5, 7, and 8 of
Intel US 5,195,051.  It is intentionally separate from the emulator:
the purpose is to expose the redundant sum/carry state at every tree
node without changing any production result.

The negative-row correction for PP i is embedded in the vacant low
columns of PP i+1, as Figure 8 depicts.  The final (PP21) digit is always
nonnegative for the floating-point/unsigned recoding, so all corrections
fit in the 22 physical row inputs.  The remaining two inputs of the six
first-level 4:2 compressors are W (the bit-69 sign-generate correction)
and zero.
"""

import argparse
import random


PP_BITS = 70
TREE_BITS = 136
PP_MASK = (1 << PP_BITS) - 1
TREE_MASK = (1 << TREE_BITS) - 1
PRODUCT_MASK = (1 << 131) - 1

# Table III, indexed by Y[i+2:i-1].
BOOTH8 = (0, 1, 1, 2, 2, 3, 3, 4,
          -4, -3, -3, -2, -2, -1, -1, 0)


def booth_code(multiplier, row):
    """Return the four-bit radix-8 window for PP ``row``.

    Floating-point multiplication appends y[-1]=0 and y[64]=y[65]=0.
    """
    code = 0
    for out_bit, source_bit in enumerate(range(3 * row - 1,
                                                3 * row + 3)):
        if 0 <= source_bit < 64:
            code |= ((multiplier >> source_bit) & 1) << out_bit
    return code


def booth_digits(multiplier):
    if not 0 <= multiplier < (1 << 64):
        raise ValueError("multiplier is not 64 bits")
    return [BOOTH8[booth_code(multiplier, row)] for row in range(22)]


def encoded_pp(multiplicand, digit):
    """Return the patent's 70-bit sign-generate PP before row shifting."""
    if not (1 << 66) <= multiplicand < (1 << 67):
        raise ValueError("multiplicand must be a normalized 67-bit value")
    magnitude = abs(digit) * multiplicand
    if magnitude >= (1 << 69):
        raise AssertionError("4x multiplicand exceeded 69 magnitude bits")
    positive = (1 << 69) | magnitude
    if digit < 0:
        return (~positive) & PP_MASK
    # Table II suppresses negation for the selected zero multiple.  Thus
    # the 1111 Booth window is +0 in the physical PP encoding, not -0.
    return positive


def physical_rows(multiplicand, multiplier):
    """Return the 22 Figure-8 row inputs, W, and the zero tree input."""
    digits = booth_digits(multiplier)
    rows = []
    prior_negative = False
    for index, digit in enumerate(digits):
        # Figure 8 widens every 70-bit PP to 72 bits by prepending 11.
        row = (encoded_pp(multiplicand, digit) | (3 << 70)) << (3 * index)
        if prior_negative:
            # The two's-complement +1 for PP(i-1) occupies the first
            # vacant position of the following physical row.
            row |= 1 << (3 * (index - 1))
        rows.append(row & TREE_MASK)
        prior_negative = digit < 0
    if prior_negative:
        raise AssertionError("PP21 must be nonnegative in FP recoding")
    w = 1 << 69
    return rows, w, 0, digits


def csa3(a, b, c):
    """A vector 3:2 CSA; carry bits are returned in their result columns."""
    total_sum = (a ^ b ^ c) & TREE_MASK
    carry = (((a & b) | (a & c) | (b & c)) << 1) & TREE_MASK
    return total_sum, carry


def csa42(a, b, c, d):
    """Figure-5 4:2 compressor, with D as its distinguished fourth input."""
    first_sum, first_carry = csa3(a, b, c)
    out_sum, out_carry = csa3(d, first_sum, first_carry)
    return out_sum, out_carry, first_sum, first_carry


def multiplier_tree(multiplicand, multiplier, d_slot=0):
    """Reduce all physical rows with the exact four-level Figure-7 topology.

    ``d_slot`` identifies which of each ordered group of four physical
    wires feeds D in Figure 5.  The patent drawing shows D to the left of
    A/B/C, hence slot zero is the architectural default.  Other slots are
    useful only as a falsification control: the arithmetic sum is invariant
    but the redundant representation changes.
    """
    if d_slot not in range(4):
        raise ValueError("d_slot must be 0..3")
    rows, w, zero, digits = physical_rows(multiplicand, multiplier)
    inputs = rows + [w, zero]
    nodes = {}

    def compress(name, wires):
        ordered = list(wires)
        d = ordered.pop(d_slot)
        out_sum, out_carry, first_sum, first_carry = csa42(
            ordered[0], ordered[1], ordered[2], d)
        nodes[name] = {
            "in": tuple(wires),
            "sum": out_sum,
            "carry": out_carry,
            "first_sum": first_sum,
            "first_carry": first_carry,
        }
        return out_sum, out_carry

    level1 = [compress("l1_%d" % index, inputs[4 * index:4 * index + 4])
              for index in range(6)]
    level2 = [compress("l2_%d" % index,
                       level1[2 * index] + level1[2 * index + 1])
              for index in range(3)]
    level3 = compress("l3_0", level2[0] + level2[1])
    final_sum, final_carry = compress("l4_0", level3 + level2[2])
    return {
        "sum": final_sum,
        "carry": final_carry,
        "nodes": nodes,
        "rows": tuple(rows),
        "digits": tuple(digits),
        "w": w,
    }


def assert_product(multiplicand, multiplier, d_slot=0):
    state = multiplier_tree(multiplicand, multiplier, d_slot=d_slot)
    got = (state["sum"] + state["carry"]) & PRODUCT_MASK
    expected = (multiplicand * multiplier) & PRODUCT_MASK
    if got != expected:
        raise AssertionError(
            "product mismatch x=%017x y=%016x d=%d got=%033x want=%033x" %
            (multiplicand, multiplier, d_slot, got, expected))
    if state["carry"] & 3:
        raise AssertionError("the patent guarantees carry[1:0] == 0")
    return state


def self_test(random_count, seed):
    # Deliberately include all-zero, all-one, alternating, isolated-run,
    # and normalized endpoints.  The all-one cases exercise 1111 windows
    # and therefore distinguish a physical zero row from a fictitious -0.
    multipliers = (
        0, 1, 2, 3, 7, 8, 15, 31, 63,
        0x1249249249249249, 0x2492492492492492,
        0x5555555555555555, 0xAAAAAAAAAAAAAAAA,
        0x7FFFFFFFFFFFFFFF, 0x8000000000000000,
        0xFFFFFFFFFFFFFFF0, 0xFFFFFFFFFFFFFFFF,
    )
    multiplicands = (
        1 << 66,
        (1 << 66) + 1,
        0x55555555555555555,
        0x6AAAAAAAAAAAAAAAA,
        (1 << 67) - 2,
        (1 << 67) - 1,
    )
    cases = [(x, y) for x in multiplicands for y in multipliers]
    rng = random.Random(seed)
    for _ in range(random_count):
        cases.append(((1 << 66) | rng.getrandbits(66), rng.getrandbits(64)))
    for d_slot in range(4):
        for multiplicand, multiplier in cases:
            assert_product(multiplicand, multiplier, d_slot=d_slot)
    print("validated", len(cases), "products x 4 D slots",
          "(%d tree evaluations)" % (4 * len(cases)))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", type=int, metavar="RANDOM_CASES",
                        help="validate edge cases plus this many random cases")
    parser.add_argument("--seed", type=int, default=0x5195051)
    parser.add_argument("--x", type=lambda text: int(text, 0))
    parser.add_argument("--y", type=lambda text: int(text, 0))
    parser.add_argument("--d-slot", type=int, default=0)
    args = parser.parse_args()
    if args.self_test is not None:
        self_test(args.self_test, args.seed)
        return
    if args.x is None or args.y is None:
        parser.error("supply --self-test N or both --x and --y")
    state = assert_product(args.x, args.y, args.d_slot)
    print("digits", ",".join("%+d" % digit for digit in state["digits"]))
    print("sum   %034x" % state["sum"])
    print("carry %034x" % state["carry"])
    print("total %034x" % ((state["sum"] + state["carry"]) & TREE_MASK))
    for name, node in state["nodes"].items():
        print("%-4s sum=%034x carry=%034x first_sum=%034x first_carry=%034x" %
              (name, node["sum"], node["carry"],
               node["first_sum"], node["first_carry"]))


if __name__ == "__main__":
    main()
