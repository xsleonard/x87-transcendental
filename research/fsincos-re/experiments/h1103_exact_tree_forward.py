#!/usr/bin/env python3
"""Test literal P5 multiplier carry-save forwarding into the R59 terminal.

Unlike h1101's single-wire census, this composes the patent's final S/C pair
with the terminal subtraction.  It tests whether omitting or block-predicting
the product CPA carry into the 67-bit cut reproduces the admissible hardware
retained integer for the remaining R59 operands.
"""

import argparse
import csv
from collections import Counter, defaultdict
from itertools import product

from h1100_p5_multiplier_tree import PRODUCT_MASK, multiplier_tree


def carry_into(a, b, position, start=0, carry=0):
    for column in range(start, position):
        abit = (a >> column) & 1
        bbit = (b >> column) & 1
        carry = (abit & bbit) | (abit & carry) | (bbit & carry)
    return carry


def representations(multiplicand, multiplier):
    exact = multiplicand * multiplier
    cut = exact.bit_length() - 67
    state = multiplier_tree(multiplicand, multiplier)
    sum_vector = state["sum"] & PRODUCT_MASK
    carry_vector = state["carry"] & PRODUCT_MASK
    top = (sum_vector >> cut) + (carry_vector >> cut)
    exact_carry = carry_into(sum_vector, carry_vector, cut)
    if top + exact_carry != exact >> cut:
        raise AssertionError("cut carry reconstruction failed")
    values = {
        "exact": exact >> cut,
        "nocarry": top,
        "carry0": top,
        "carry1": top + 1,
    }
    for block in (4, 8, 16, 32):
        start = max(0, cut - block)
        for assumed in (0, 1):
            predicted = carry_into(sum_vector, carry_vector, cut,
                                   start=start, carry=assumed)
            values["b%d_c%d" % (block, assumed)] = top + predicted
    return values


def terminal_delta(row, left_sig, right_sig):
    left_e2 = int(row["tc_left_exp"])
    right_e2 = int(row["tc_right_exp"])
    payload = int(row["payload"])
    scale = min(left_e2, right_e2,
                left_e2 - 8 if payload else left_e2)
    S = left_sig << (left_e2 - scale)
    if payload:
        S += payload << (left_e2 - 8 - scale)
    B = right_sig << (right_e2 - scale)
    magnitude = S - B
    if magnitude <= 0:
        return 999
    baseline = int(row["umag"], 16)
    cut = int(row["k"])
    if baseline != ((int(row["S"], 16) - int(row["B"], 16))):
        raise AssertionError("dump terminal mismatch")
    return (magnitude >> cut) - (baseline >> cut)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("features")
    parser.add_argument("allmodes")
    args = parser.parse_args()
    with open(args.features) as source:
        rows = list(csv.DictReader(source, delimiter="\t"))
    admissible = defaultdict(lambda: set(range(-2, 3)))
    with open(args.allmodes) as source:
        for row in csv.DictReader(source, delimiter="\t"):
            admissible[row["op"]].intersection_update(
                int(value) - 3 for value in row["matches"].split(","))

    positives = [row for row in rows if row["label"] == "POS"]
    cache = {}
    records = []
    for row in rows:
        key_l = int(row["tc_mul_sig"], 16), int(row["tc_lf_sig"], 16)
        key_r = int(row["tc_f4_sig"], 16), int(row["tc_rf_sig"], 16)
        if key_l not in cache:
            cache[key_l] = representations(*key_l)
        if key_r not in cache:
            cache[key_r] = representations(*key_r)
        records.append((row, cache[key_l], cache[key_r]))

    variants = tuple(next(iter(cache.values())))
    scores = []
    for left_name, right_name in product(variants, repeat=2):
        pos_ok = 0
        neg_same = 0
        neg_changed = 0
        deltas = Counter()
        for row, left, right in records:
            delta = terminal_delta(row, left[left_name], right[right_name])
            if row["label"] == "POS":
                pos_ok += delta in admissible[row["op"]]
                deltas[delta] += 1
            else:
                current = int(row["br_r"], 16) - (
                    int(row["umag"], 16) >> int(row["k"]))
                neg_same += delta == current
                neg_changed += delta != current
        scores.append((pos_ok, -neg_changed, left_name, right_name,
                       neg_same, deltas))
    scores.sort(reverse=True)
    print("rows", len(rows), "positive", len(positives),
          "variants", len(variants))
    print("pos_ok neg_changed neg_same left right positive_deltas")
    for pos_ok, minus_changed, left_name, right_name, neg_same, deltas \
            in scores[:40]:
        print(pos_ok, -minus_changed, neg_same, left_name, right_name,
              dict(sorted(deltas.items())))

    best = scores[0]
    _, _, left_name, right_name, _, _ = best
    print("\nbest positive details", left_name, right_name)
    for row, left, right in records:
        if row["label"] != "POS":
            continue
        delta = terminal_delta(row, left[left_name], right[right_name])
        print(row["op"], row["branch"], "candidate", delta,
              "admissible", sorted(admissible[row["op"]]),
              "OK" if delta in admissible[row["op"]] else "MISS")


if __name__ == "__main__":
    main()
