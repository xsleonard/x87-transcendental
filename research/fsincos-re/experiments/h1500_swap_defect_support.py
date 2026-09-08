#!/usr/bin/env python3
"""Prove the essential local support of H1498's swap defect.

H1498 bounded the final-propagate dependency cone by nine physical columns
for arbitrary 24-word compressor inputs.  The real radix-8 rows have stronger
geometry: row r begins at column 3*r, and row r+1 may also receive the
one-bit correction for a negative row r at column 3*r.  This experiment
rebuilds the four-level 4:2 graph as a Boolean column network, imposes exactly
those structural zeros, and uses SAT sensitivity queries to identify every
input coordinate on which pair A XOR pair B genuinely depends.

The row payload bits remain otherwise independent.  This proves a support
theorem for the radix-8 shift geometry, not for the more constrained set of
valid Booth multiples.  No x87 instruction is executed and no label is opened.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

try:
    import z3
except ImportError as error:
    raise SystemExit("z3-solver 4.15.3.0 is required") from error

from h1400_p5_representation_audit import tree_variants


POSITIONS = (45, 46)
RADIUS = 8
ROWS = 24
LANES_PER_GROUP = 4
EXPECTED_A = "pair_02_14_35_hold2"
EXPECTED_B = "pair_03_14_25_hold2"


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def majority(a, b, c):
    return z3.Or(z3.And(a, b), z3.And(a, c), z3.And(b, c))


def csa3(a, b, c):
    width = len(a)
    sums = [
        z3.Xor(z3.Xor(a[index], b[index]), c[index])
        for index in range(width)
    ]
    carries = [z3.BoolVal(False)] + [
        majority(a[index], b[index], c[index]) for index in range(width - 1)
    ]
    return sums, carries


def csa42(values, d_slot: int):
    ordered = list(values)
    distinguished = ordered.pop(d_slot)
    first_sum, first_carry = csa3(*ordered)
    return csa3(distinguished, first_sum, first_carry)


def reduce_tree(inputs, config):
    if config.input_order != "natural" or config.d_slots != (0, 0, 0, 0):
        raise RuntimeError("surviving layout stopped using canonical lanes")
    level1 = [
        csa42(inputs[4 * index:4 * index + 4], config.d_slots[0])
        for index in range(6)
    ]
    level2 = [
        csa42(level1[left] + level1[right], config.d_slots[1])
        for left, right in config.pairing
    ]
    remaining = [index for index in range(3) if index != config.hold]
    level3 = csa42(
        level2[remaining[0]] + level2[remaining[1]], config.d_slots[2]
    )
    return csa42(level3 + level2[config.hold], config.d_slots[3])


def bits_to_bv(bits):
    one = z3.BitVecVal(1, 1)
    zero = z3.BitVecVal(0, 1)
    return z3.Concat(*[
        z3.If(bit, one, zero) for bit in reversed(bits)
    ])


def bv_csa3(a, b, c):
    return a ^ b ^ c, ((a & b) | (a & c) | (b & c)) << 1


def bv_csa42(values, d_slot: int):
    ordered = list(values)
    distinguished = ordered.pop(d_slot)
    first_sum, first_carry = bv_csa3(*ordered)
    return bv_csa3(distinguished, first_sum, first_carry)


def bv_reduce_tree(inputs, config):
    level1 = [
        bv_csa42(inputs[4 * index:4 * index + 4], config.d_slots[0])
        for index in range(6)
    ]
    level2 = [
        bv_csa42(level1[left] + level1[right], config.d_slots[1])
        for left, right in config.pairing
    ]
    remaining = [index for index in range(3) if index != config.hold]
    level3 = bv_csa42(
        level2[remaining[0]] + level2[remaining[1]], config.d_slots[2]
    )
    return bv_csa42(level3 + level2[config.hold], config.d_slots[3])


def prove_bool_bv_equivalence(boolean_pair, inputs, config, timeout_ms: int):
    bitvector_pair = bv_reduce_tree([bits_to_bv(word) for word in inputs], config)
    width = len(inputs[0])
    solver = z3.SolverFor("QF_BV")
    solver.set(timeout=timeout_ms)
    solver.add(z3.Or(
        boolean_pair[0][-1] != (z3.Extract(width - 1, width - 1,
                                           bitvector_pair[0]) == 1),
        boolean_pair[1][-1] != (z3.Extract(width - 1, width - 1,
                                           bitvector_pair[1]) == 1),
    ))
    status = solver.check()
    if status != z3.unsat:
        reason = solver.reason_unknown() if status == z3.unknown else "counterexample"
        raise RuntimeError(f"Boolean/bit-vector equivalence is {status}: {reason}")
    return {"status": "unsat"}


def structurally_live(row: int, column: int) -> tuple[bool, str]:
    if row >= 22:
        return False, "constant_scaffold"
    payload = 3 * row <= column <= 3 * row + 71
    correction = row >= 1 and column == 3 * (row - 1)
    if payload and correction:
        raise AssertionError("payload and correction coordinates overlap")
    if payload:
        return True, "partial_product"
    if correction:
        return True, "negate_correction"
    return False, "structural_zero"


def build_inputs(position: int):
    low = position - RADIUS
    inputs = []
    coordinates = {}
    for row in range(ROWS):
        word = []
        for column in range(low, position + 1):
            live, kind = structurally_live(row, column)
            if live:
                variable = z3.Bool(f"r{row:02d}_c{column:02d}")
                word.append(variable)
                coordinates[variable] = {
                    "row": row,
                    "group": row // LANES_PER_GROUP,
                    "lane": row % LANES_PER_GROUP,
                    "column": column,
                    "relative_column": column - position,
                    "kind": kind,
                }
            else:
                word.append(z3.BoolVal(False))
        inputs.append(word)
    return inputs, coordinates


def collect_boolean_variables(expression):
    """Collect Boolean leaves without z3util's repeated string rendering."""
    pending = [expression]
    visited = set()
    variables = {}
    while pending:
        node = pending.pop()
        identity = node.get_id()
        if identity in visited:
            continue
        visited.add(identity)
        if z3.is_const(node):
            if not z3.is_true(node) and not z3.is_false(node):
                variables[identity] = node
            continue
        pending.extend(node.children())
    return list(variables.values())


def essential_support(expression, coordinates, timeout_ms: int):
    syntactic = collect_boolean_variables(expression)
    unknown = sorted(str(value) for value in syntactic if value not in coordinates)
    if unknown:
        raise RuntimeError(f"unregistered variables in expression: {unknown}")
    support = []
    inessential = []
    for variable in sorted(syntactic, key=str):
        flipped = z3.substitute(expression, (variable, z3.Not(variable)))
        solver = z3.Solver()
        solver.set(timeout=timeout_ms)
        solver.add(expression != flipped)
        status = solver.check()
        if status == z3.unknown:
            raise RuntimeError(
                f"support query for {variable} is UNKNOWN: {solver.reason_unknown()}"
            )
        if status == z3.sat:
            support.append(coordinates[variable])
        else:
            inessential.append(coordinates[variable])
    return support, inessential, len(syntactic)


def summarize(position: int, support, inessential, syntactic_count: int):
    support = sorted(
        support, key=lambda item: (item["group"], item["row"], item["column"])
    )
    by_group = Counter(item["group"] for item in support)
    by_row = Counter(item["row"] for item in support)
    by_relative = Counter(item["relative_column"] for item in support)
    by_kind = Counter(item["kind"] for item in support)
    minimum_relative = min(item["relative_column"] for item in support)
    return {
        "position": position,
        "window": [position - RADIUS, position],
        "syntactic_variables": syntactic_count,
        "essential_variables": len(support),
        "algebraically_inessential_syntactic_variables": len(inessential),
        "essential_radius": -minimum_relative,
        "radius_eight_tight": minimum_relative == -RADIUS,
        "essential_by_group": {
            str(key): value for key, value in sorted(by_group.items())
        },
        "essential_by_row": {
            str(key): value for key, value in sorted(by_row.items())
        },
        "essential_by_relative_column": {
            str(key): value for key, value in sorted(by_relative.items())
        },
        "essential_by_kind": dict(sorted(by_kind.items())),
        "support": support,
        "inessential_syntactic_coordinates": sorted(
            inessential,
            key=lambda item: (item["group"], item["row"], item["column"]),
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("h1498", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--timeout-ms", type=int, default=10_000)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")
    if z3.get_version_string() != "4.15.3":
        raise RuntimeError(f"unexpected Z3 version {z3.get_version_string()}")

    h1498 = json.loads(args.h1498.read_text())
    if h1498["status"] != "EXACT_LOCAL_SWAP_ISOMORPHISM":
        raise RuntimeError("H1498 status changed")
    layouts = {name: config for name, _, config in tree_variants()}
    pair_a = layouts[EXPECTED_A]
    pair_b = layouts[EXPECTED_B]
    if pair_a.pairing != ((0, 2), (1, 4), (3, 5)) or pair_a.hold != 2:
        raise RuntimeError("pair A topology changed")
    if pair_b.pairing != ((0, 3), (1, 4), (2, 5)) or pair_b.hold != 2:
        raise RuntimeError("pair B topology changed")

    results = []
    equivalence = []
    for position in POSITIONS:
        inputs, coordinates = build_inputs(position)
        out_a = reduce_tree(inputs, pair_a)
        out_b = reduce_tree(inputs, pair_b)
        equivalence.append({
            "position": position,
            "pair_a": prove_bool_bv_equivalence(
                out_a, inputs, pair_a, args.timeout_ms
            ),
            "pair_b": prove_bool_bv_equivalence(
                out_b, inputs, pair_b, args.timeout_ms
            ),
        })
        defect = z3.Xor(
            z3.Xor(out_a[0][-1], out_a[1][-1]),
            z3.Xor(out_b[0][-1], out_b[1][-1]),
        )
        support, inessential, syntactic_count = essential_support(
            defect, coordinates, args.timeout_ms
        )
        results.append(summarize(
            position, support, inessential, syntactic_count
        ))

    report = {
        "experiment": "h1500_swap_defect_support",
        "status": "EXACT_RADIX8_SHIFT_GEOMETRY_SUPPORT",
        "z3_version": z3.get_version_string(),
        "function": "D_j = pair_A.final.propagate[j] XOR pair_B.final.propagate[j]",
        "layouts": {"pair_a": EXPECTED_A, "pair_b": EXPECTED_B},
        "boolean_to_bitvector_equivalence": equivalence,
        "domain": {
            "window_radius": RADIUS,
            "partial_product_rows": 22,
            "compressor_inputs": ROWS,
            "constraints": (
                "row r payload is zero below column 3*r; row r+1 may have "
                "the independent negate-correction bit at column 3*r; "
                "remaining live payload bits are independent"
            ),
            "not_imposed": (
                "Booth-code selection, shared multiplicand multiples, and "
                "correlation between correction bits and row signs"
            ),
        },
        "positions": results,
        "interpretation": (
            "Each listed coordinate is essential by a SAT witness obtained "
            "by toggling only that coordinate; each omitted syntactic "
            "coordinate is proven inessential by UNSAT. Structural zeros "
            "are imposed before the Boolean graph is built."
        ),
        "claim_boundary": (
            "This is a universal support theorem for the shifted-row domain, "
            "not a physical-netlist identification and not a selector over "
            "valid external x87 operands."
        ),
        "hardware_execution": "none",
        "hardware_labels_opened": "none",
        "capture_manifest": "none",
        "emulator_change": "none",
        "paper_change": "none",
        "sha256": {"h1498": digest(args.h1498)},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    args.output.write_text(text)
    print(json.dumps({
        "output": str(args.output),
        "report_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "positions": [
            {
                "position": row["position"],
                "essential": row["essential_variables"],
                "radius": row["essential_radius"],
                "groups": row["essential_by_group"],
            }
            for row in results
        ],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
