#!/usr/bin/env python3
"""Test whether operand-role exchange maps the two surviving propagate forms.

H1502 proves that the pair-A/pair-B defect is asymmetric under exchanging the
two low Booth operands.  This experiment computes the exact normalized-input
support of each individual propagate function and tests the four possible
pair-A/pair-B mappings under operand-residue exchange.

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

from h1400_p5_representation_audit import tree_variants
from h1501_booth_defect_operand_support import (
    EXPECTED_A,
    EXPECTED_B,
    POSITIONS,
    bits_from_model,
    booth_rows,
    operand_support,
    physical_inputs,
    propagate,
    reduce_tree,
)


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


def coordinate_map(multiplicand_bits, multiplier_bits):
    coordinates = {
        variable: {"operand": "multiplicand", "bit": bit}
        for bit, variable in enumerate(multiplicand_bits[:-1])
    }
    coordinates.update({
        variable: {"operand": "multiplier", "bit": bit}
        for bit, variable in enumerate(multiplier_bits[:-1])
    })
    return coordinates


def outputs(multiplicand_bits, multiplier_bits, pair_a, pair_b):
    rows, negatives = booth_rows(
        multiplicand_bits, multiplier_bits, max(POSITIONS)
    )
    result = {}
    for position in POSITIONS:
        inputs = physical_inputs(position, rows, negatives)
        result[position] = {
            "A": propagate(reduce_tree(inputs, pair_a)),
            "B": propagate(reduce_tree(inputs, pair_b)),
        }
    return result


def summarize_support(expression, coordinates, multiplicand_bits,
                      multiplier_bits, timeout_ms: int):
    essential, inessential, syntactic = operand_support(
        expression, coordinates, multiplicand_bits, multiplier_bits,
        timeout_ms
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
    return {
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
    }


def swap_constraints(left_bits, right_bits, left_support, right_support):
    left_m, left_q = left_bits
    right_m, right_q = right_bits
    left_m_support = set(left_support["essential_bits"]["multiplicand"])
    left_q_support = set(left_support["essential_bits"]["multiplier"])
    right_m_support = set(right_support["essential_bits"]["multiplicand"])
    right_q_support = set(right_support["essential_bits"]["multiplier"])
    mq_bits = sorted(left_m_support | right_q_support)
    qm_bits = sorted(left_q_support | right_m_support)
    if any(bit >= len(right_q) for bit in mq_bits) \
            or any(bit >= len(left_q) for bit in qm_bits):
        raise RuntimeError("operand swap needs a bit outside the 64-bit port")
    constraints = [left_m[bit] == right_q[bit] for bit in mq_bits]
    constraints.extend(left_q[bit] == right_m[bit] for bit in qm_bits)
    return constraints, {"m_to_q_bits": mq_bits, "q_to_m_bits": qm_bits}


def relation_query(constraints, predicate, left_bits, right_bits,
                   left_output, right_output, timeout_ms: int):
    solver = z3.Solver()
    solver.set(timeout=timeout_ms)
    solver.add(*constraints, predicate)
    status = solver.check()
    if status == z3.unknown:
        raise RuntimeError(f"port-swap query is UNKNOWN: {solver.reason_unknown()}")
    result = {"status": str(status)}
    if status == z3.sat:
        model = solver.model()
        left_m, left_q = left_bits
        right_m, right_q = right_bits
        result["witness"] = {
            "left": {
                "multiplicand": f"{bits_from_model(model, left_m):017x}",
                "multiplier": f"{bits_from_model(model, left_q):016x}",
                "output": int(z3.is_true(model.eval(
                    left_output, model_completion=True
                ))),
            },
            "right": {
                "multiplicand": f"{bits_from_model(model, right_m):017x}",
                "multiplier": f"{bits_from_model(model, right_q):016x}",
                "output": int(z3.is_true(model.eval(
                    right_output, model_completion=True
                ))),
            },
        }
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("h1501", type=Path)
    parser.add_argument("h1502", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--timeout-ms", type=int, default=60_000)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")
    if z3.get_version_string() != "4.15.3":
        raise RuntimeError(f"unexpected Z3 version {z3.get_version_string()}")

    h1501 = json.loads(args.h1501.read_text())
    h1502 = json.loads(args.h1502.read_text())
    if h1501["status"] != "EXACT_NORMALIZED_BOOTH_OPERAND_SUPPORT":
        raise RuntimeError("H1501 proof chain changed")
    if h1502["status"] != "PRODUCT_QUOTIENT_AND_SWAP_SYMMETRY_REJECTED":
        raise RuntimeError("H1502 quotient result changed")

    layouts = {name: config for name, _, config in tree_variants()}
    pair_a = layouts[EXPECTED_A]
    pair_b = layouts[EXPECTED_B]
    left_bits = normalized_bits("left")
    right_bits = normalized_bits("right")
    left_outputs = outputs(*left_bits, pair_a, pair_b)
    right_outputs = outputs(*right_bits, pair_a, pair_b)
    coordinates = coordinate_map(*left_bits)

    support = {}
    for position in POSITIONS:
        support[position] = {}
        for pair in ("A", "B"):
            support[position][pair] = summarize_support(
                left_outputs[position][pair], coordinates,
                *left_bits, args.timeout_ms
            )

    mappings = []
    exact_isomorphisms = []
    for position in POSITIONS:
        for left_pair in ("A", "B"):
            for right_pair in ("A", "B"):
                constraints, mapped_bits = swap_constraints(
                    left_bits, right_bits,
                    support[position][left_pair], support[position][right_pair]
                )
                left_output = left_outputs[position][left_pair]
                right_output = right_outputs[position][right_pair]
                inequality = relation_query(
                    constraints, left_output != right_output,
                    left_bits, right_bits, left_output, right_output,
                    args.timeout_ms
                )
                equality = relation_query(
                    constraints, left_output == right_output,
                    left_bits, right_bits, left_output, right_output,
                    args.timeout_ms
                )
                if inequality["status"] == "unsat":
                    relation = "exact_equality"
                    exact_isomorphisms.append({
                        "position": position,
                        "left_pair": left_pair,
                        "right_pair": right_pair,
                        "relation": relation,
                    })
                elif equality["status"] == "unsat":
                    relation = "exact_complement"
                    exact_isomorphisms.append({
                        "position": position,
                        "left_pair": left_pair,
                        "right_pair": right_pair,
                        "relation": relation,
                    })
                else:
                    relation = "no_constant_xor_relation"
                mappings.append({
                    "position": position,
                    "left_pair": left_pair,
                    "right_pair": right_pair,
                    "mapped_support_bits": mapped_bits,
                    "counterexample_to_equality": inequality,
                    "counterexample_to_complement": equality,
                    "relation": relation,
                })

    report = {
        "experiment": "h1503_propagate_port_swap_audit",
        "status": (
            "EXACT_PORT_SWAP_ISOMORPHISM_FOUND"
            if exact_isomorphisms else "PORT_SWAP_ISOMORPHISM_REJECTED"
        ),
        "z3_version": z3.get_version_string(),
        "normalized_domain": h1501["normalized_domain"],
        "individual_propagate_support": [
            {
                "position": position,
                "pair_a": support[position]["A"],
                "pair_b": support[position]["B"],
            }
            for position in POSITIONS
        ],
        "port_swap_mappings": mappings,
        "exact_isomorphisms": exact_isomorphisms,
        "interpretation": (
            "Each mapping compares complete individual propagate functions "
            "after exchanging every operand coordinate on which either side "
            "semantically depends. SAT equality and inequality witnesses "
            "reject both equality and complement when relation is "
            "no_constant_xor_relation."
        ),
        "claim_boundary": (
            "This tests operand-role exchange as an abstract isomorphism. It "
            "does not identify the physical Skylake quartet orientation."
        ),
        "hardware_execution": "none",
        "hardware_labels_opened": "none",
        "capture_manifest": "none",
        "emulator_change": "none",
        "paper_change": "none",
        "sha256": {
            "h1501": digest(args.h1501),
            "h1502": digest(args.h1502),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    args.output.write_text(text)
    print(json.dumps({
        "output": str(args.output),
        "report_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "support": [
            {
                "position": position,
                "pair": pair,
                "essential": support[position][pair][
                    "essential_free_operand_bits"
                ],
                "by_operand": support[position][pair]["essential_by_operand"],
            }
            for position in POSITIONS for pair in ("A", "B")
        ],
        "relations": {
            relation: sum(row["relation"] == relation for row in mappings)
            for relation in sorted({row["relation"] for row in mappings})
        },
        "exact_isomorphisms": exact_isomorphisms,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
