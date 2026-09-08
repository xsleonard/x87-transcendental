#!/usr/bin/env python3
"""Test canonical first-level-quartet quotients of the H1498 swap defect.

H1501 expresses pair disagreement over low multiplicand/multiplier residues.
This experiment asks whether that function factors through a smaller,
arithmetic description of the six first-level Booth quartets.  Two exact
normalized Booth inputs are constrained to share, successively, each
quartet's local arithmetic sum; sum plus top propagate; sum plus its complete
local propagate word; and sum plus the ordered first output word.  A SAT
counterexample rejects a quotient, while UNSAT proves it.

No x87 instruction or hardware capture is executed.
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

from h1400_p5_representation_audit import tree_variants
from h1501_booth_defect_operand_support import (
    POSITIONS,
    bits_from_model,
    bits_to_bv,
    booth_rows,
    csa42,
    physical_inputs,
    propagate,
    reduce_tree,
)


EXPECTED_A = "pair_02_14_35_hold2"
EXPECTED_B = "pair_03_14_25_hold2"


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def normalized_bits(prefix: str):
    multiplicand = [z3.Bool(f"{prefix}_m{bit:02d}") for bit in range(66)]
    multiplicand.append(z3.BoolVal(True))
    multiplier = [z3.Bool(f"{prefix}_q{bit:02d}") for bit in range(63)]
    multiplier.append(z3.BoolVal(True))
    return multiplicand, multiplier


def quartet_state(inputs):
    width = len(inputs[0])
    mask = (1 << width) - 1
    states = []
    for group in range(6):
        words = [
            bits_to_bv(inputs[4 * group + offset]) for offset in range(4)
        ]
        pair = csa42(
            inputs[4 * group:4 * group + 4],
            0,
        )
        output_sum = bits_to_bv(pair[0])
        output_carry = bits_to_bv(pair[1])
        arithmetic = words[0] + words[1] + words[2] + words[3]
        states.append({
            "arithmetic_sum": arithmetic & z3.BitVecVal(mask, width),
            "top_propagate": z3.Extract(
                width - 1, width - 1, output_sum ^ output_carry
            ),
            "propagate_word": output_sum ^ output_carry,
            "ordered_sum_word": output_sum,
        })
    return states


def equality_constraints(left, right, fields):
    return [
        left[group][field] == right[group][field]
        for group in range(6)
        for field in fields
    ]


def render_state(model, states, fields):
    return [
        {
            field: f"{model.eval(state[field], model_completion=True).as_long():x}"
            for field in fields
        }
        for state in states
    ]


def solve_query(
    name: str,
    defect_left,
    defect_right,
    constraints,
    left_bits,
    right_bits,
    left_states,
    right_states,
    fields,
    timeout_ms: int,
):
    solver = z3.SolverFor("QF_BV")
    solver.set(timeout=timeout_ms)
    solver.add(*constraints, defect_left != defect_right)
    status = solver.check()
    result = {"query": name, "status": str(status), "fields": list(fields)}
    if status == z3.unknown:
        result["reason_unknown"] = solver.reason_unknown()
    elif status == z3.sat:
        model = solver.model()
        left_m, left_q = left_bits
        right_m, right_q = right_bits
        result["witness"] = {
            "left": {
                "multiplicand": f"{bits_from_model(model, left_m):017x}",
                "multiplier": f"{bits_from_model(model, left_q):016x}",
                "defect": int(z3.is_true(model.eval(
                    defect_left, model_completion=True
                ))),
                "quartets": render_state(model, left_states, fields),
            },
            "right": {
                "multiplicand": f"{bits_from_model(model, right_m):017x}",
                "multiplier": f"{bits_from_model(model, right_q):016x}",
                "defect": int(z3.is_true(model.eval(
                    defect_right, model_completion=True
                ))),
                "quartets": render_state(model, right_states, fields),
            },
        }
        if result["witness"]["left"]["quartets"] \
                != result["witness"]["right"]["quartets"]:
            raise RuntimeError(f"{name}: model violates quotient equalities")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("h1498", type=Path)
    parser.add_argument("h1501", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--timeout-ms", type=int, default=60_000)
    arguments = parser.parse_args()
    if arguments.output.exists():
        raise SystemExit(f"refusing to overwrite {arguments.output}")
    if z3.get_version_string() != "4.15.3":
        raise RuntimeError(f"unexpected Z3 version {z3.get_version_string()}")

    h1498 = json.loads(arguments.h1498.read_text())
    h1501 = json.loads(arguments.h1501.read_text())
    if h1498["status"] != "EXACT_LOCAL_SWAP_ISOMORPHISM":
        raise RuntimeError("H1498 theorem changed")
    if h1501["status"] != "EXACT_NORMALIZED_BOOTH_OPERAND_SUPPORT":
        raise RuntimeError("H1501 theorem changed")

    layouts = {name: config for name, _, config in tree_variants()}
    pair_a = layouts[EXPECTED_A]
    pair_b = layouts[EXPECTED_B]
    left_bits = normalized_bits("left")
    right_bits = normalized_bits("right")
    left_rows, left_negatives = booth_rows(
        left_bits[0], left_bits[1], max(POSITIONS)
    )
    right_rows, right_negatives = booth_rows(
        right_bits[0], right_bits[1], max(POSITIONS)
    )

    field_sets = (
        ("arithmetic_sum",),
        ("arithmetic_sum", "top_propagate"),
        ("arithmetic_sum", "propagate_word"),
        ("arithmetic_sum", "ordered_sum_word"),
    )
    positions = []
    for position in POSITIONS:
        left_inputs = physical_inputs(position, left_rows, left_negatives)
        right_inputs = physical_inputs(position, right_rows, right_negatives)
        left_defect = z3.Xor(
            propagate(reduce_tree(left_inputs, pair_a)),
            propagate(reduce_tree(left_inputs, pair_b)),
        )
        right_defect = z3.Xor(
            propagate(reduce_tree(right_inputs, pair_a)),
            propagate(reduce_tree(right_inputs, pair_b)),
        )
        left_states = quartet_state(left_inputs)
        right_states = quartet_state(right_inputs)
        queries = []
        for fields in field_sets:
            queries.append(solve_query(
                "+".join(fields),
                left_defect,
                right_defect,
                equality_constraints(left_states, right_states, fields),
                left_bits,
                right_bits,
                left_states,
                right_states,
                fields,
                arguments.timeout_ms,
            ))
        positions.append({
            "position": position,
            "local_width": position - (position - 8) + 1,
            "queries": queries,
        })

    statuses = [
        query["status"]
        for position in positions
        for query in position["queries"]
    ]
    if all(status == "unsat" for status in statuses[:]):
        status = "ALL_TESTED_QUARTET_STATE_QUOTIENTS_EXACT"
    elif any(status == "unknown" for status in statuses):
        status = "QUARTET_STATE_QUOTIENT_AUDIT_PARTLY_UNKNOWN"
    else:
        status = "SOME_QUARTET_STATE_QUOTIENTS_REJECTED"

    report = {
        "experiment": "h1515_quartet_state_quotient",
        "status": status,
        "z3_version": z3.get_version_string(),
        "normalized_domain": {
            "multiplicand_width": 67,
            "multiplicand_top_bit": 1,
            "multiplier_width": 64,
            "multiplier_top_bit": 1,
        },
        "layouts": {"pair_a": EXPECTED_A, "pair_b": EXPECTED_B},
        "positions": positions,
        "interpretation": (
            "SAT rejects the named quotient with an exact normalized Booth "
            "counterexample; UNSAT proves that equal named quartet states "
            "force equal pair-A/pair-B swap defect."
        ),
        "claim_boundary": (
            "This characterizes an exact representation of the abstract pair "
            "defect. It does not identify the physical Skylake orientation or "
            "validate either pair as the silicon selector."
        ),
        "hardware_execution": "none",
        "hardware_labels_opened": "none",
        "capture_manifest": "none",
        "emulator_change": "none",
        "paper_change": "none",
        "sha256": {
            "h1498": digest(arguments.h1498),
            "h1501": digest(arguments.h1501),
        },
    }
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(text)
    print(json.dumps({
        "output": str(arguments.output),
        "report_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "status": status,
        "positions": [
            {
                "position": item["position"],
                "queries": {
                    query["query"]: query["status"]
                    for query in item["queries"]
                },
            }
            for item in positions
        ],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
