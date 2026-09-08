#!/usr/bin/env python3
"""Map H1500's local swap defect onto exact normalized Booth operands.

The H1500 shifted-row theorem leaves each live partial-product bit independent.
This experiment replaces those bits with the exact radix-8 Booth functions of
a normalized 67-bit multiplicand and 64-bit multiplier, proves equivalence to
H1487's complete 136-bit construction, and determines the semantic support of
the pair-A/pair-B defect in normalized multiplier-port input bits.

No x87 instruction is executed and no hardware label is opened.
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

from h1400_p5_representation_audit import BOOTH8, tree_variants
from h1487_propagate_pair_equivalence import (
    physical_inputs as full_physical_inputs,
)


POSITIONS = (45, 46)
RADIUS = 8
ROWS = 24
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


def source_bit(bits, source: int):
    if source < 0 or source >= len(bits):
        return z3.BoolVal(False)
    return bits[source]


def booth_matches(multiplier_bits, row: int):
    sources = [source_bit(multiplier_bits, 3 * row - 1 + offset)
               for offset in range(4)]
    matches = []
    for encoding in range(16):
        terms = [
            source if (encoding >> offset) & 1 else z3.Not(source)
            for offset, source in enumerate(sources)
        ]
        matches.append(z3.And(*terms))
    return matches


def times_three_bits(multiplicand_bits, width: int):
    carry = z3.BoolVal(False)
    output = []
    for bit in range(width):
        direct = source_bit(multiplicand_bits, bit)
        shifted = source_bit(multiplicand_bits, bit - 1)
        output.append(z3.Xor(z3.Xor(direct, shifted), carry))
        carry = majority(direct, shifted, carry)
    return output


def booth_rows(multiplicand_bits, multiplier_bits, maximum_bit: int):
    three = times_three_bits(multiplicand_bits, maximum_bit + 1)
    rows = []
    negatives = []
    for row in range(22):
        matches = booth_matches(multiplier_bits, row)
        negative = z3.Or(*[
            matches[encoding]
            for encoding, digit in enumerate(BOOTH8) if digit < 0
        ])
        encoded = []
        for bit in range(maximum_bit + 1):
            candidates = {
                0: z3.BoolVal(False),
                1: source_bit(multiplicand_bits, bit),
                2: source_bit(multiplicand_bits, bit - 1),
                3: three[bit],
                4: source_bit(multiplicand_bits, bit - 2),
            }
            magnitude = z3.Or(*[
                z3.And(matches[encoding], candidates[abs(digit)])
                for encoding, digit in enumerate(BOOTH8)
            ])
            encoded.append(z3.Xor(magnitude, negative))
        rows.append(encoded)
        negatives.append(negative)
    return rows, negatives


def physical_inputs(position: int, rows, negatives):
    low = position - RADIUS
    inputs = []
    for row in range(ROWS):
        word = []
        for column in range(low, position + 1):
            if row >= 22:
                value = z3.BoolVal(False)
            elif row >= 1 and column == 3 * (row - 1):
                value = negatives[row - 1]
            elif column >= 3 * row:
                value = rows[row][column - 3 * row]
            else:
                value = z3.BoolVal(False)
            word.append(value)
        inputs.append(word)
    return inputs


def propagate(pair):
    return z3.Xor(pair[0][-1], pair[1][-1])


def collect_boolean_variables(expression):
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


def bits_to_bv(bits):
    one = z3.BitVecVal(1, 1)
    zero = z3.BitVecVal(0, 1)
    return z3.Concat(*[
        z3.If(bit, one, zero) for bit in reversed(bits)
    ])


def bits_from_model(model, bits) -> int:
    value = 0
    for bit, expression in enumerate(bits):
        if z3.is_true(model.eval(expression, model_completion=True)):
            value |= 1 << bit
    return value


def solve_input_equivalence(local_inputs, full_inputs, position: int,
                            multiplicand_bits, multiplier_bits,
                            timeout_ms: int):
    low = position - RADIUS
    differences = []
    coordinates = []
    for row in range(ROWS):
        for offset, column in enumerate(range(low, position + 1)):
            differences.append(
                local_inputs[row][offset]
                != (z3.Extract(column, column, full_inputs[row]) == 1)
            )
            coordinates.append((row, column))
    solver = z3.SolverFor("QF_BV")
    solver.set(timeout=timeout_ms)
    solver.add(z3.Or(*differences))
    status = solver.check()
    if status == z3.unknown:
        raise RuntimeError(
            f"input equivalence at {position} is UNKNOWN: "
            f"{solver.reason_unknown()}"
        )
    if status == z3.sat:
        model = solver.model()
        mismatches = [
            {
                "row": row,
                "column": column,
                "local": int(z3.is_true(model.eval(
                    local_inputs[row][column - low], model_completion=True
                ))),
                "full": int(z3.is_true(model.eval(
                    z3.Extract(column, column, full_inputs[row]) == 1,
                    model_completion=True
                ))),
            }
            for difference, (row, column) in zip(differences, coordinates)
            if z3.is_true(model.eval(difference, model_completion=True))
        ]
        raise RuntimeError(
            f"input equivalence at {position} is SAT for "
            f"m={bits_from_model(model, multiplicand_bits):017x}, "
            f"q={bits_from_model(model, multiplier_bits):016x} "
            f"at {mismatches}"
        )
    return {"status": "unsat"}


def operand_support(expression, coordinates, multiplicand_bits,
                    multiplier_bits, timeout_ms: int):
    syntactic = collect_boolean_variables(expression)
    unknown = sorted(str(value) for value in syntactic if value not in coordinates)
    if unknown:
        raise RuntimeError(f"unregistered variables in expression: {unknown}")
    essential = []
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
        coordinate = coordinates[variable]
        if status == z3.unsat:
            inessential.append(coordinate)
            continue
        model = solver.model()
        before = int(z3.is_true(model.eval(expression, model_completion=True)))
        after = int(z3.is_true(model.eval(flipped, model_completion=True)))
        if before == after:
            raise AssertionError("SAT support witness did not toggle the defect")
        essential.append({
            **coordinate,
            "witness": {
                "multiplicand": f"{bits_from_model(model, multiplicand_bits):017x}",
                "multiplier": f"{bits_from_model(model, multiplier_bits):016x}",
                "defect_before": before,
                "defect_after_flip": after,
            },
        })
    return essential, inessential, syntactic


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("h1487", type=Path)
    parser.add_argument("h1498", type=Path)
    parser.add_argument("h1500", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--timeout-ms", type=int, default=60_000)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")
    if z3.get_version_string() != "4.15.3":
        raise RuntimeError(f"unexpected Z3 version {z3.get_version_string()}")

    h1487 = json.loads(args.h1487.read_text())
    h1498 = json.loads(args.h1498.read_text())
    h1500 = json.loads(args.h1500.read_text())
    if h1487["status"] != "TWO_FORMALLY_DISTINCT_SURVIVING_FUNCTIONS":
        raise RuntimeError("H1487 function partition changed")
    if h1498["status"] != "EXACT_LOCAL_SWAP_ISOMORPHISM":
        raise RuntimeError("H1498 locality theorem changed")
    if h1500["status"] != "EXACT_RADIX8_SHIFT_GEOMETRY_SUPPORT":
        raise RuntimeError("H1500 support theorem changed")
    locality = {
        (proof["layout"], proof["position"]): proof["status"]
        for proof in h1498["locality"]["proofs"]
    }
    bool_bv = {
        (row["position"], pair): row[pair]["status"]
        for row in h1500["boolean_to_bitvector_equivalence"]
        for pair in ("pair_a", "pair_b")
    }
    for position in POSITIONS:
        if locality[(EXPECTED_A, position)] != "unsat" \
                or locality[(EXPECTED_B, position)] != "unsat" \
                or bool_bv[(position, "pair_a")] != "unsat" \
                or bool_bv[(position, "pair_b")] != "unsat":
            raise RuntimeError(f"local-circuit proof chain changed at {position}")

    multiplicand_bits = [z3.Bool(f"m{bit:02d}") for bit in range(66)]
    multiplicand_bits.append(z3.BoolVal(True))
    multiplier_bits = [z3.Bool(f"q{bit:02d}") for bit in range(63)]
    multiplier_bits.append(z3.BoolVal(True))
    coordinates = {
        variable: {"operand": "multiplicand", "bit": bit}
        for bit, variable in enumerate(multiplicand_bits[:-1])
    }
    coordinates.update({
        variable: {"operand": "multiplier", "bit": bit}
        for bit, variable in enumerate(multiplier_bits[:-1])
    })

    layouts = {name: config for name, _, config in tree_variants()}
    pair_a = layouts[EXPECTED_A]
    pair_b = layouts[EXPECTED_B]
    rows, negatives = booth_rows(
        multiplicand_bits, multiplier_bits, max(POSITIONS)
    )
    multiplicand = bits_to_bv(multiplicand_bits)
    multiplier = bits_to_bv(multiplier_bits)
    full_inputs = full_physical_inputs(multiplicand, multiplier)

    results = []
    defects = {}
    equivalence = []
    for position in POSITIONS:
        inputs = physical_inputs(position, rows, negatives)
        input_equivalence = solve_input_equivalence(
            inputs, full_inputs, position, multiplicand_bits, multiplier_bits,
            args.timeout_ms
        )
        local_a = propagate(reduce_tree(inputs, pair_a))
        local_b = propagate(reduce_tree(inputs, pair_b))
        equivalence.append({
            "position": position,
            "physical_inputs": input_equivalence,
            "pair_a": {
                "status": "proven_by_composition",
                "h1500_boolean_to_bitvector": "unsat",
                "h1498_full_to_local": "unsat",
            },
            "pair_b": {
                "status": "proven_by_composition",
                "h1500_boolean_to_bitvector": "unsat",
                "h1498_full_to_local": "unsat",
            },
        })
        defect = z3.Xor(local_a, local_b)
        defects[position] = defect
        essential, inessential, syntactic = operand_support(
            defect, coordinates, multiplicand_bits, multiplier_bits,
            args.timeout_ms
        )
        essential.sort(key=lambda item: (item["operand"], item["bit"]))
        inessential.sort(key=lambda item: (item["operand"], item["bit"]))
        support_set = {
            (item["operand"], item["bit"]) for item in essential
        }
        syntactic_set = {
            (coordinates[value]["operand"], coordinates[value]["bit"])
            for value in syntactic
        }
        all_free = {
            *(('multiplicand', bit) for bit in range(66)),
            *(('multiplier', bit) for bit in range(63)),
        }
        absent = sorted(all_free - syntactic_set)
        by_operand = Counter(item["operand"] for item in essential)
        results.append({
            "position": position,
            "syntactic_free_operand_bits": len(syntactic),
            "essential_free_operand_bits": len(essential),
            "inessential_syntactic_bits": inessential,
            "structurally_absent_free_bits": [
                {"operand": operand, "bit": bit} for operand, bit in absent
            ],
            "essential_by_operand": dict(sorted(by_operand.items())),
            "essential_bits": {
                operand: [bit for name, bit in sorted(support_set)
                          if name == operand]
                for operand in ("multiplicand", "multiplier")
            },
            "support_with_witnesses": essential,
        })

    column_difference = z3.Solver()
    column_difference.set(timeout=args.timeout_ms)
    column_difference.add(defects[45] != defects[46])
    difference_status = column_difference.check()
    if difference_status != z3.sat:
        reason = column_difference.reason_unknown() \
            if difference_status == z3.unknown else "unexpected equivalence"
        raise RuntimeError(f"cross-column defect query is {difference_status}: {reason}")
    difference_model = column_difference.model()

    report = {
        "experiment": "h1501_booth_defect_operand_support",
        "status": "EXACT_NORMALIZED_BOOTH_OPERAND_SUPPORT",
        "z3_version": z3.get_version_string(),
        "layouts": {"pair_a": EXPECTED_A, "pair_b": EXPECTED_B},
        "normalized_domain": {
            "multiplicand_width": 67,
            "multiplicand_top_bit": 1,
            "multiplier_width": 64,
            "multiplier_top_bit": 1,
        },
        "local_to_full_equivalence": equivalence,
        "positions": results,
        "cross_column_difference": {
            "status": "sat",
            "multiplicand": (
                f"{bits_from_model(difference_model, multiplicand_bits):017x}"
            ),
            "multiplier": (
                f"{bits_from_model(difference_model, multiplier_bits):016x}"
            ),
            "defect_45": int(z3.is_true(difference_model.eval(
                defects[45], model_completion=True
            ))),
            "defect_46": int(z3.is_true(difference_model.eval(
                defects[46], model_completion=True
            ))),
        },
        "interpretation": (
            "Every essential bit has a concrete normalized sensitivity "
            "witness; every listed syntactic inessential bit is UNSAT; bits "
            "absent from the exact Booth circuit are structurally irrelevant."
        ),
        "claim_boundary": (
            "This is an exact representation of pair disagreement over the "
            "complete normalized 67x64 Booth domain. It does not identify "
            "which pair orientation, if either, exists in Skylake silicon."
        ),
        "hardware_execution": "none",
        "hardware_labels_opened": "none",
        "capture_manifest": "none",
        "emulator_change": "none",
        "paper_change": "none",
        "sha256": {
            "h1487": digest(args.h1487),
            "h1498": digest(args.h1498),
            "h1500": digest(args.h1500),
        },
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
                "essential": row["essential_free_operand_bits"],
                "by_operand": row["essential_by_operand"],
            }
            for row in results
        ],
        "cross_column": report["cross_column_difference"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
