#!/usr/bin/env python3
"""Validate P5 square-CPA group-propagate signals on dense hard cells.

The h1172 sampled-wall search found a patent-aligned 16-bit group-propagate
wire that isolates two required upper-R59 carry flips.  This pass evaluates
the complete fixed family of Q/QX 4/8/16-bit group-propagate wires on every
h1168/h1169 archived hard-cell row.  It is a cached-label validation and
executes no x87 instruction.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
from collections import Counter
from pathlib import Path

from h1100_p5_multiplier_tree import TREE_MASK, csa3, multiplier_tree


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def group_propagates(sum_vector, carry_vector, cut, origin, width, relative):
    base = origin + ((cut - origin) // width) * width
    start = base + relative * width
    if start < 0 or start + width > 131:
        return 0
    mask = (1 << width) - 1
    return int((((sum_vector ^ carry_vector) >> start) & mask) == mask)


def features(row):
    multiplier = int(row["tc_mul_sig"], 16)
    state = multiplier_tree(multiplier, multiplier >> 3)
    q_sum, q_carry = state["sum"], state["carry"]
    q_product = multiplier * (multiplier >> 3)
    q_cut = q_product.bit_length() - 67
    qx_sum, qx_carry = csa3(
        (q_sum << 3) & TREE_MASK,
        (q_carry << 3) & TREE_MASK,
        multiplier * (multiplier & 7))
    square = multiplier * multiplier
    qx_cut = square.bit_length() - 67
    if ((qx_sum + qx_carry) & ((1 << 134) - 1)) != square:
        raise AssertionError("full-square reconstruction mismatch")

    result = {}
    for prefix, sum_vector, carry_vector, cut in (
            ("Q", q_sum, q_carry, q_cut),
            ("QX", qx_sum, qx_carry, qx_cut)):
        for width in (4, 8, 16):
            for alignment, origin in (("p5", 2), ("abs", 0), ("cut", cut)):
                for relative in range(-4, 5):
                    name = (f"{prefix}.{alignment}.w{width:02d}."
                            f"rel{relative:+d}.p")
                    result[name] = group_propagates(
                        sum_vector, carry_vector, cut, origin, width, relative)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("selected", type=Path)
    parser.add_argument("labels", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    counts = Counter()
    true_operands = {}
    with gzip.open(args.selected, "rt", newline="") as selected_source, \
            args.labels.open(newline="") as label_source:
        selected_rows = csv.DictReader(selected_source, delimiter="\t")
        label_rows = csv.DictReader(label_source, delimiter="\t")
        names = None
        row_count = 0
        for row_count, (row, label) in enumerate(
                zip(selected_rows, label_rows), 1):
            if row["op"] != label["op"]:
                raise RuntimeError(f"row desync {row_count}")
            values = features(row)
            if names is None:
                names = tuple(sorted(values))
            elif set(values) != set(names):
                raise AssertionError("feature schema changed")
            status = label["selector_status"]
            target_flip = int(label["target_flip"])
            for name in names:
                value = values[name]
                counts[(name, status, target_flip, value)] += 1
                # Retain only residual witnesses.  Keeping every true control
                # operand for every feature would turn this dense validation
                # into an avoidable multi-gigabyte object graph.
                if value and target_flip:
                    true_operands.setdefault(name, []).append(row["op"])
            if row_count % 100000 == 0:
                print(f"features {row_count}", flush=True)
        try:
            next(selected_rows)
        except StopIteration:
            pass
        else:
            raise RuntimeError("extra selected rows")
        try:
            next(label_rows)
        except StopIteration:
            pass
        else:
            raise RuntimeError("extra label rows")
    if names is None:
        raise SystemExit("empty dense input")

    scores = []
    for name in names:
        required_true = counts[name, "constraining", 1, 1]
        required_false = counts[name, "constraining", 1, 0]
        forbidden_true = counts[name, "constraining", 0, 1]
        neutral_true = counts[name, "neutral", 0, 1]
        impossible_true = counts[name, "unrepresented", 1, 1]
        scores.append((
            required_false + forbidden_true,
            required_false,
            forbidden_true,
            -required_true,
            neutral_true,
            impossible_true,
            name,
        ))
    scores.sort()
    zero_collateral = [score for score in scores if score[2] == 0
                       and score[3] < 0]

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as target:
        target.write(f"selected_sha256\t{digest(args.selected)}\n")
        target.write(f"labels_sha256\t{digest(args.labels)}\n")
        target.write(f"rows\t{row_count}\nfeatures\t{len(names)}\n")
        target.write(f"zero_collateral\t{len(zero_collateral)}\n")
        target.write("\n[ranking]\n")
        target.write("errors\trequired_miss\tforbidden_fire\trequired_hit\t"
                     "neutral_fire\timpossible_fire\tfeature\n")
        for score in scores[:500]:
            rendered = list(score)
            rendered[3] = -rendered[3]
            target.write("\t".join(map(str, rendered)) + "\n")
        target.write("\n[zero-collateral]\n")
        for score in zero_collateral:
            rendered = list(score)
            rendered[3] = -rendered[3]
            target.write("\t".join(map(str, rendered)) + "\n")
            target.write("operands\t" + ",".join(true_operands[score[6]]) + "\n")
    print(
        f"wrote {args.report} rows={row_count} best={scores[0]} "
        f"zero_collateral={len(zero_collateral)}",
        flush=True,
    )


if __name__ == "__main__":
    main()
