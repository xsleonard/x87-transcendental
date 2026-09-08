#!/usr/bin/env python3
"""Formally test pairwise equivalence inside H1486's surviving class.

The four H1479 layouts split as 0011/1100 on fresh software rows.  Random
testing suggests that layouts 0/1 are one function and layouts 2/3 are a
second function.  This script reconstructs the exact 136-bit radix-8 Booth
tree as QF_BV and asks Z3 for a normalized-input counterexample to each
within-pair equality at both possible cut-18 columns (45 and 46).

This is analysis-only.  It executes no x87 instruction and opens no label.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

try:
    import z3
except ImportError as error:
    raise SystemExit("z3-solver 4.15.3.0 is required") from error

from h1400_p5_representation_audit import BOOTH8, tree_variants
from h1486_surviving_propagate_class import EXPECTED_SIGNALS, candidate_values


WIDTH = 136
PP_MASK = (1 << 70) - 1
POSITIONS = (45, 46)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def bv(value: int):
    return z3.BitVecVal(value & ((1 << WIDTH) - 1), WIDTH)


def source_bit(multiplier, source: int):
    if source < 0 or source >= 64:
        return z3.BitVecVal(0, 1)
    return z3.Extract(source, source, multiplier)


def booth_code(multiplier, row: int):
    bits = [source_bit(multiplier, source)
            for source in range(3 * row - 1, 3 * row + 3)]
    return z3.Concat(bits[3], bits[2], bits[1], bits[0])


def booth_partial(multiplicand, multiplier, row: int):
    code = booth_code(multiplier, row)
    wide_m = z3.ZeroExt(WIDTH - 67, multiplicand)
    magnitude = bv(0)
    negative = z3.BoolVal(False)
    for encoding, digit in enumerate(BOOTH8):
        if abs(digit) == 0:
            candidate = bv(0)
        elif abs(digit) == 1:
            candidate = wide_m
        elif abs(digit) == 2:
            candidate = wide_m << 1
        elif abs(digit) == 3:
            candidate = wide_m + (wide_m << 1)
        elif abs(digit) == 4:
            candidate = wide_m << 2
        else:
            raise AssertionError(digit)
        magnitude = z3.If(code == encoding, candidate, magnitude)
        negative = z3.If(code == encoding, z3.BoolVal(digit < 0), negative)
    positive = magnitude | bv(1 << 69)
    encoded = z3.If(negative, (~positive) & bv(PP_MASK), positive)
    row_value = (encoded | bv(3 << 70)) << (3 * row)
    return row_value, negative


def csa3(a, b, c):
    return a ^ b ^ c, ((a & b) | (a & c) | (b & c)) << 1


def csa42(values):
    first_sum, first_carry = csa3(values[1], values[2], values[3])
    return csa3(values[0], first_sum, first_carry)


def physical_inputs(multiplicand, multiplier):
    rows = []
    negatives = []
    for row in range(22):
        value, negative = booth_partial(multiplicand, multiplier, row)
        rows.append(value)
        negatives.append(negative)
    for row in range(21):
        rows[row + 1] = rows[row + 1] + z3.If(
            negatives[row], bv(1 << (3 * row)), bv(0))
    return rows + [bv(1 << 69), bv(0)]


def candidate_vectors(multiplicand, multiplier, configs):
    inputs = physical_inputs(multiplicand, multiplier)
    level1 = [csa42(inputs[4 * index:4 * index + 4]) for index in range(6)]
    result = []
    for config in configs:
        level2 = [
            csa42(level1[left] + level1[right])
            for left, right in config.pairing
        ]
        remaining = [index for index in range(3) if index != config.hold]
        level3 = csa42(level2[remaining[0]] + level2[remaining[1]])
        final = csa42(level3 + level2[config.hold])
        result.append(final[0] ^ final[1])
    return result


def solve_pair(solver, vectors, left: int, right: int, timeout_ms: int):
    solver.push()
    solver.set(timeout=timeout_ms)
    solver.add(z3.Or(*[
        z3.Extract(position, position, vectors[left])
        != z3.Extract(position, position, vectors[right])
        for position in POSITIONS
    ]))
    status = solver.check()
    result = {"status": str(status), "positions": list(POSITIONS)}
    if status == z3.sat:
        model = solver.model()
        result["multiplicand"] = f"{model.eval(MULTIPLICAND).as_long():017x}"
        result["multiplier"] = f"{model.eval(MULTIPLIER).as_long():016x}"
    elif status == z3.unknown:
        result["reason_unknown"] = solver.reason_unknown()
    solver.pop()
    return result


MULTIPLICAND = z3.BitVec("multiplicand", 67)
MULTIPLIER = z3.BitVec("multiplier", 64)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("h1486", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--timeout-ms", type=int, default=60_000)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")
    if z3.get_version_string() != "4.15.3":
        raise RuntimeError(f"unexpected Z3 version {z3.get_version_string()}")

    prior = json.loads(args.h1486.read_text())
    signal_order = prior["survivor_class"]["signal_order"]
    if set(signal_order) != EXPECTED_SIGNALS:
        raise RuntimeError("H1486 signal class changed")
    layouts = {name: config for name, _, config in tree_variants()}
    config_names = [signal.split(".final.")[0] for signal in signal_order]
    configs = [layouts[name] for name in config_names]

    vectors = candidate_vectors(MULTIPLICAND, MULTIPLIER, configs)
    solver = z3.SolverFor("QF_BV")
    solver.add(z3.Extract(66, 66, MULTIPLICAND) == 1)
    solver.add(z3.Extract(63, 63, MULTIPLIER) == 1)
    within_a = solve_pair(solver, vectors, 0, 1, args.timeout_ms)
    within_b = solve_pair(solver, vectors, 2, 3, args.timeout_ms)
    cross = solve_pair(solver, vectors, 0, 2, args.timeout_ms)

    witness = prior["random_normalized_product_audit"][
        "first_layout_disagreement"]
    if witness is None:
        raise RuntimeError("H1486 lacks concrete cross-pair witness")
    concrete_pattern = candidate_values(
        int(witness["multiplicand"], 16),
        int(witness["multiplier"], 16), configs)
    if concrete_pattern != witness["pattern"]:
        raise RuntimeError("H1486 concrete witness did not replay")

    pair_proven = within_a["status"] == "unsat" and within_b["status"] == "unsat"
    report = {
        "experiment": "h1487_propagate_pair_equivalence",
        "status": (
            "TWO_FORMALLY_DISTINCT_SURVIVING_FUNCTIONS"
            if pair_proven and cross["status"] == "sat"
            else "PAIR_EQUIVALENCE_NOT_CLOSED"
        ),
        "hardware_execution": "none",
        "hardware_labels_opened": "none",
        "z3_version": z3.get_version_string(),
        "normalized_input_constraints": {
            "multiplicand_width": 67,
            "multiplicand_top_bit": 1,
            "multiplier_width": 64,
            "multiplier_top_bit": 1,
        },
        "candidate_signal_order": signal_order,
        "target_absolute_columns": list(POSITIONS),
        "queries": {
            "layout_0_xor_layout_1": within_a,
            "layout_2_xor_layout_3": within_b,
            "layout_0_xor_layout_2": cross,
        },
        "h1486_concrete_witness_replay": {
            **witness,
            "replayed_pattern": concrete_pattern,
        },
        "interpretation": (
            "UNSAT within each pair proves that the four 28-label aliases "
            "collapse to exactly two functions at both possible cut-18 "
            "columns for every normalized 67x64 input. SAT across pairs "
            "proves that those two functions are not algebraically identical."
        ) if pair_proven and cross["status"] == "sat" else (
            "At least one bounded solver query did not establish the expected "
            "two-function partition; UNKNOWN is not treated as equivalence."
        ),
        "claim_boundary": (
            "This classifies arithmetic representations. It does not identify "
            "which pairing, if either, exists in Skylake silicon."
        ),
        "emulator_change": "none",
        "paper_change": "none",
        "sha256": {"h1486": digest(args.h1486)},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as target:
        json.dump(report, target, indent=2, sort_keys=True)
        target.write("\n")
    print(json.dumps({
        "output": str(args.output),
        "status": report["status"],
        "within_a": within_a["status"],
        "within_b": within_b["status"],
        "cross": cross["status"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
