#!/usr/bin/env python3
"""h1040: bit-state census on the h1039 TOP/act0 union response set.

Absolute block placement and propagate-run length do not separate the union
FIX/BREAK rows.  Search the exact terminal lower-column kill/generate state
and the four product-array discarded fields on this correctly conditioned
population.  This is diagnostic ranking; no literal is promoted without an
arithmetic interpretation and blind transfer.
"""

import csv
from collections import Counter, defaultdict

import h1035_top0_response_score as response_score
import h1039_top0_union_block_phase as union


def normalized_bits(features, prefix, product, width=96):
    shift = product.bit_length() - 67
    discarded = product & ((1 << shift) - 1) if shift > 0 else 0
    for offset in range(width):
        position = shift - 1 - offset
        features[f"{prefix}q{offset}"] = ((discarded >> position) & 1
                                           if position >= 0 else 0)


def feature_bits(record):
    features = {}
    left, right = record["left"], record["right"]
    payload = int(record.get("pay2", record["payload"]))
    scale = min(left[1], right[1], left[1] - 8 if payload else left[1])
    s_value = left[2] << (left[1] - scale)
    if payload:
        s_value += payload << (left[1] - 8 - scale)
    b_value = right[2] << (right[1] - scale)
    magnitude = s_value - b_value
    cut = magnitude.bit_length() - 67
    for offset in range(-64, 65):
        position = cut + offset
        for prefix, value in (
                ("S", s_value), ("B", b_value), ("M", magnitude),
                ("P", ~(s_value ^ b_value)), ("G", ~s_value & b_value),
                ("K", s_value & ~b_value)):
            features[f"{prefix}{offset:+d}"] = (
                (value >> position) & 1 if position >= 0 else 0)

    products = {
        "sq": record["mag"][2] * record["mag"][2],
        "f4": record["mul"][2] * record["mul"][2],
        "left": record["mul"][2] * record["lf"][2],
        "right": record["f4"][2] * record["rf"][2],
    }
    for prefix, product in products.items():
        normalized_bits(features, prefix, product)
    for prefix, value in (
            ("mul", record["mul"][2]), ("lf", record["lf"][2]),
            ("f4k", record["f4"][2]), ("rf", record["rf"][2]),
            ("mag", record["mag"][2])):
        for bit in range(67):
            features[f"{prefix}b{bit}"] = (value >> bit) & 1
    return features


def main():
    with open("/tmp/h1039_top0_union_features.tsv") as source:
        population = list(csv.DictReader(source, delimiter="\t"))
    tests = []
    for insn in ("cos", "sin"):
        sample = [row for row in population if row["insn"] == insn]
        operands = [row["op"] for row in sample]
        _, dump = union.run(union.BASE, insn, "rn", operands, dump=True)
        records = response_score.parse_dumps(dump)
        for row, record in zip(sample, records):
            tests.append((row["label"], feature_bits(record)))
    print("tests", Counter(label for label, _ in tests))

    names = sorted(tests[0][1])
    ranked = []
    for name in names:
        counts = Counter((label, features[name]) for label, features in tests)
        for positive_value in (0, 1):
            false_negative = counts["FIX", 1 - positive_value]
            false_positive = counts["BREAK", positive_value]
            ranked.append((false_negative + false_positive, false_negative,
                           false_positive, name, positive_value, counts))
    print("\nbest literals (total error, FN, FP, feature=value):")
    for error, fn, fp, name, value, counts in sorted(ranked)[:120]:
        print(error, fn, fp, f"{name}={value}", dict(counts))

    # The first non-propagate column below cut terminates the downward run.
    # Report whether it is a subtract-kill or subtract-generate state.
    run_state = Counter()
    for label, features in tests:
        run = 0
        while run < 64 and features[f"P{-run:+d}"]:
            run += 1
        state = "G" if features[f"G{-run:+d}"] else "K"
        run_state[label, run, state] += 1
    print("\nfirst non-propagate state", run_state)

    # Best conjunctions of two literals.  Restrict to the strongest 96
    # distinct feature/value pairs so the report remains interpretable.
    literals = []
    seen = set()
    for item in sorted(ranked):
        key = item[3], item[4]
        if key not in seen:
            seen.add(key)
            literals.append(key)
        if len(literals) == 96:
            break
    pairs = []
    for index, (left_name, left_value) in enumerate(literals):
        for right_name, right_value in literals[index + 1:]:
            counts = Counter()
            for label, features in tests:
                prediction = (features[left_name] == left_value
                              and features[right_name] == right_value)
                counts[label, prediction] += 1
            error = counts["FIX", False] + counts["BREAK", True]
            pairs.append((error, counts["FIX", False],
                          counts["BREAK", True], left_name, left_value,
                          right_name, right_value))
    print("\nbest two-literal conjunctions:")
    for item in sorted(pairs)[:80]:
        print(item)


if __name__ == "__main__":
    main()
