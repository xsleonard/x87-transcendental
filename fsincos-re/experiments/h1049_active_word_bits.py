#!/usr/bin/env python3
"""h1049: search carry bits of combined R60/terminal residue words."""

import argparse
import csv
import math


def load(family):
    with open(f"/tmp/h1042_{family}_union.tsv") as source:
        rows = list(csv.DictReader(source, delimiter="\t"))
    for row in rows:
        for key in row.keys() - {"label", "insn", "op"}:
            row[key] = int(row[key])
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("family", choices=("top1", "low1"))
    args = parser.parse_args()
    rows = load(args.family)
    target_count = sum(row["label"] == "FIX" for row in rows)
    ranked = []
    seen = set()
    for second in ("qpost", "qpre", "qright", "qleft", "qf4", "qsq"):
        for first_coeff in range(1, 17):
            for second_coeff in range(-64, 65):
                divisor = math.gcd(first_coeff, abs(second_coeff))
                signature = (second, first_coeff // divisor,
                             second_coeff // divisor)
                if signature in seen:
                    continue
                seen.add(signature)
                values = [first_coeff * row["mreg"]
                          + second_coeff * row[second] for row in rows]
                for bit in range(52, 74):
                    ones_fix = sum(row["label"] == "FIX"
                                   and ((value >> bit) & 1)
                                   for row, value in zip(rows, values))
                    ones_break = sum(row["label"] == "BREAK"
                                     and ((value >> bit) & 1)
                                     for row, value in zip(rows, values))
                    for wanted, tp, fp in (
                            (1, ones_fix, ones_break),
                            (0, target_count - ones_fix,
                             len(rows) - target_count - ones_break)):
                        fn = target_count - tp
                        ranked.append((fp + fn, fp, fn, -tp, second,
                                       first_coeff, second_coeff, bit,
                                       wanted))
    print(args.family, "rows", len(rows), "targets", target_count)
    for result in sorted(ranked)[:100]:
        print(result[4:], "errors/fp/fn/tp", result[:4])


if __name__ == "__main__":
    main()
