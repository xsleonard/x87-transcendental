#!/usr/bin/env python3
"""Test the patented P5 multiplier CPA/carry-select representation.

US 5,195,051 describes a special 129-bit final product adder whose group
generate/propagate terms are latched before a four-bit carry-select last
stage.  Earlier R59 searches exposed the Booth/CSA tree and exact ripple
carry, but not this physical intermediate layer.  This experiment builds
fixed 4/8/16-bit group and conditional-carry wires for all terminal products
and the reconstructed full square, then tests every two-input Boolean gate
with the incumbent selector carry.  No operand identity or learned numeric
threshold enters the feature construction.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from pathlib import Path

import numpy as np

from h1100_p5_multiplier_tree import TREE_MASK, csa3, multiplier_tree
from h1110_carry_gate_mine import (
    GATE_NAMES,
    allmode_allowed,
    extract_carry_state,
    gate_changes,
    gate_errors,
    state_bad_counts,
)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def bit(value: int, position: int) -> int:
    return (value >> position) & 1 if position >= 0 else 0


def group_state(sum_vector: int, carry_vector: int, start: int, end: int):
    """Return G/P, conditional carries, and selected input/output carries."""
    g = 0
    p = 1
    c0, c1 = 0, 1
    for position in range(start, end):
        a, b = bit(sum_vector, position), bit(carry_vector, position)
        generate, propagate = a & b, a ^ b
        g = generate | (propagate & g)
        p &= propagate
        c0 = generate | (propagate & c0)
        c1 = generate | (propagate & c1)
    carry = 0
    for position in range(0, start):
        a, b = bit(sum_vector, position), bit(carry_vector, position)
        carry = (a & b) | ((a ^ b) & carry)
    selected = c1 if carry else c0
    return g, p, c0, c1, carry, selected


def add_cpa_features(values, prefix, sum_vector, carry_vector, cut):
    # The patent's 129-bit adder consumes product columns 2..130.  Origin 2
    # is therefore primary; origins 0 and the normalized cut are bounded
    # layout controls for undocumented physical grouping.
    for width in (4, 8, 16):
        for alignment, origin in (("p5", 2), ("abs", 0), ("cut", cut)):
            base = origin + ((cut - origin) // width) * width
            for relative in range(-4, 5):
                start = base + relative * width
                end = start + width
                stem = f"{prefix}.{alignment}.w{width:02d}.rel{relative:+d}"
                if start < 0 or end > 131:
                    for name in ("g", "p", "c0", "c1", "cin", "cout"):
                        values[f"{stem}.{name}"] = 0
                    continue
                state = group_state(sum_vector, carry_vector, start, end)
                for name, value in zip(
                        ("g", "p", "c0", "c1", "cin", "cout"), state):
                    values[f"{stem}.{name}"] = value

                # A four-bit carry-select stage precomputes both sum words.
                # Emit each physical conditional sum output and the muxed bit.
                if width == 4:
                    for assumed in (0, 1):
                        carry = assumed
                        for offset, position in enumerate(range(start, end)):
                            a = bit(sum_vector, position)
                            b = bit(carry_vector, position)
                            values[f"{stem}.sum{assumed}.b{offset}"] = (
                                a ^ b ^ carry)
                            carry = (a & b) | ((a ^ b) & carry)

    # X2 group G/P can be interpreted as a prefix from the adder's first
    # consumed column.  Expose endpoints around the retained-product cut.
    for offset in range(-24, 25):
        end = cut + offset + 1
        stem = f"{prefix}.p5prefix.rel{offset:+d}"
        if end <= 2 or end > 131:
            for name in ("g", "p", "c0", "c1"):
                values[f"{stem}.{name}"] = 0
            continue
        g, p, c0, c1, _, _ = group_state(
            sum_vector, carry_vector, 2, end)
        values[f"{stem}.g"] = g
        values[f"{stem}.p"] = p
        values[f"{stem}.c0"] = c0
        values[f"{stem}.c1"] = c1


def product_state(multiplicand: int, multiplier: int):
    state = multiplier_tree(multiplicand, multiplier)
    product = multiplicand * multiplier
    cut = product.bit_length() - 67
    return state["sum"], state["carry"], cut


def row_features(row: dict[str, str]) -> dict[str, int]:
    multiplier = int(row["tc_mul_sig"], 16)
    left_factor = int(row["tc_lf_sig"], 16)
    fourth = int(row["tc_f4_sig"], 16)
    right_factor = int(row["tc_rf_sig"], 16)
    values = {}
    for prefix, x, y in (
            ("L", multiplier, left_factor),
            ("R", fourth, right_factor),
            ("Q", multiplier, multiplier >> 3)):
        sum_vector, carry_vector, cut = product_state(x, y)
        add_cpa_features(values, prefix, sum_vector, carry_vector, cut)

    # Restore the square's external radix-8 low digit as in h1101's QX
    # representation, then pass that redundant pair through the same CPA.
    qstate = multiplier_tree(multiplier, multiplier >> 3)
    square_sum, square_carry = csa3(
        (qstate["sum"] << 3) & TREE_MASK,
        (qstate["carry"] << 3) & TREE_MASK,
        multiplier * (multiplier & 7))
    square = multiplier * multiplier
    square_cut = square.bit_length() - 67
    if ((square_sum + square_carry) & ((1 << 134) - 1)) != square:
        raise AssertionError("full-square reconstruction mismatch")
    add_cpa_features(values, "QX", square_sum, square_carry, square_cut)
    return values


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("features", type=Path)
    parser.add_argument("positive_allmode", type=Path)
    parser.add_argument("control_allmode", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    positive_delta = allmode_allowed(args.positive_allmode)
    control_delta = allmode_allowed(args.control_allmode)
    with args.features.open(newline="") as source:
        rows = list(csv.DictReader(source, delimiter="\t"))
    states = []
    feature_rows = []
    names = None
    for index, row in enumerate(rows):
        bank = positive_delta if row["label"] == "POS" else control_delta
        states.append(extract_carry_state(row, bank[row["op"]]))
        values = row_features(row)
        if names is None:
            names = sorted(values)
        elif set(values) != set(names):
            raise AssertionError("feature schema changed")
        feature_rows.append([values[name] for name in names])
        if (index + 1) % 5000 == 0:
            print(f"features {index + 1}/{len(rows)}", flush=True)
    if names is None:
        raise SystemExit("empty feature bank")

    matrix = np.asarray(feature_rows, dtype=np.uint8)
    current = np.asarray([state[2] for state in states], dtype=np.uint8)
    allowed = np.asarray(
        [[carry in state[3] for carry in (0, 1)] for state in states],
        dtype=bool)
    capable = allowed.any(axis=1)
    positives = np.asarray([row["label"] == "POS" for row in rows])
    subsets = {
        "base": (~positives) & capable,
        "positive": positives & capable,
        "all": capable,
    }
    counts = {name: state_bad_counts(matrix, current, allowed, subset)
              for name, subset in subsets.items()}
    scores = []
    for gate in range(16):
        errors = {name: gate_errors(value, gate)
                  for name, value in counts.items()}
        changes = gate_changes(matrix, current, subsets["base"], gate)
        for feature, name in enumerate(names):
            scores.append((
                int(errors["all"][feature]),
                int(errors["positive"][feature]),
                int(errors["base"][feature]),
                int(changes[feature]), GATE_NAMES[gate], gate, name,
            ))
    scores.sort()
    improvements = [score for score in scores
                    if score[2] == 0 and score[1] < 26]
    exact = [score for score in scores if score[0] == 0]

    # Separately rank direct predicates for the three carry-impossible rows.
    impossible_target = (~capable).astype(np.uint8)
    decrement_scores = []
    for feature, name in enumerate(names):
        column = matrix[:, feature]
        for invert in (0, 1):
            predicted = column ^ invert
            decrement_scores.append((
                int(np.count_nonzero(predicted != impossible_target)),
                int(np.count_nonzero(positives &
                                     (predicted != impossible_target))),
                int(np.count_nonzero((~positives) &
                                     (predicted != impossible_target))),
                invert, name,
            ))
    decrement_scores.sort()

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as target:
        target.write(f"features_sha256\t{digest(args.features)}\n")
        target.write(f"rows\t{len(rows)}\nfeatures\t{len(names)}\n")
        target.write(f"carry_capable\t{int(capable.sum())}\n")
        target.write(f"carry_impossible\t{int((~capable).sum())}\n")
        target.write(f"zero_collateral_improvements\t{len(improvements)}\n")
        target.write(f"zero_error_gates\t{len(exact)}\n")
        target.write("\n[carry gate ranking]\n")
        target.write("all_bad\tpositive_bad\tbase_bad\tbase_changes\t"
                     "gate\tgate_mask\tfeature\n")
        for score in scores[:1000]:
            target.write("\t".join(map(str, score)) + "\n")
        target.write("\n[zero-collateral improvements]\n")
        for score in improvements[:1000]:
            target.write("\t".join(map(str, score)) + "\n")
        target.write("\n[upstream decrement ranking]\n")
        target.write("all_bad\tpositive_bad\tbase_bad\tinvert\tfeature\n")
        for score in decrement_scores[:1000]:
            target.write("\t".join(map(str, score)) + "\n")
    print(
        f"wrote {args.report} rows={len(rows)} features={len(names)} "
        f"best={scores[0]} improvements={len(improvements)} exact={len(exact)}",
        flush=True)


if __name__ == "__main__":
    main()
