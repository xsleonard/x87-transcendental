#!/usr/bin/env python3
"""Test exact quotient representations of H1501's Booth swap defect.

H1501 proves D_j is a function of the two low operand residues.  This script
asks whether that pair can be quotiented further to the ordinary low product
residue, and whether the function is symmetric under exchanging the two low
residues.  The queries use two independent normalized Booth inputs.

No x87 instruction is executed and no hardware label is opened.
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
    EXPECTED_A,
    EXPECTED_B,
    POSITIONS,
    bits_from_model,
    bits_to_bv,
    booth_rows,
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


def defect(position: int, multiplicand_bits, multiplier_bits, pair_a, pair_b):
    rows, negatives = booth_rows(
        multiplicand_bits, multiplier_bits, max(POSITIONS)
    )
    inputs = physical_inputs(position, rows, negatives)
    return z3.Xor(
        propagate(reduce_tree(inputs, pair_a)),
        propagate(reduce_tree(inputs, pair_b)),
    )


def residue(bits, width: int):
    return bits_to_bv(bits[:width])


def product_residue(multiplicand_bits, multiplier_bits, width: int):
    left = residue(multiplicand_bits, width)
    right = residue(multiplier_bits, width)
    return left * right


def solve(name: str, constraints, left_bits, right_bits, defects,
          position: int, timeout_ms: int, expected: str | None = None):
    solver = z3.SolverFor("QF_BV")
    solver.set(timeout=timeout_ms)
    solver.add(*constraints)
    status = solver.check()
    if status == z3.unknown:
        raise RuntimeError(f"{name} is UNKNOWN: {solver.reason_unknown()}")
    if expected is not None and str(status) != expected:
        reason = solver.reason_unknown() if status == z3.unknown else "unexpected"
        raise RuntimeError(f"{name} is {status}, expected {expected}: {reason}")
    result = {"status": str(status)}
    if status == z3.sat:
        model = solver.model()
        left_m, left_q = left_bits
        right_m, right_q = right_bits
        result.update({
            "left": {
                "multiplicand": f"{bits_from_model(model, left_m):017x}",
                "multiplier": f"{bits_from_model(model, left_q):016x}",
                "defect": int(z3.is_true(model.eval(
                    defects[0], model_completion=True
                ))),
            },
            "right": {
                "multiplicand": f"{bits_from_model(model, right_m):017x}",
                "multiplier": f"{bits_from_model(model, right_q):016x}",
                "defect": int(z3.is_true(model.eval(
                    defects[1], model_completion=True
                ))),
            },
            "product_residue": (
                f"{model.eval(product_residue(left_m, left_q, position), model_completion=True).as_long():0{(position + 3) // 4}x}"
            ),
        })
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("h1501", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--timeout-ms", type=int, default=60_000)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")
    if z3.get_version_string() != "4.15.3":
        raise RuntimeError(f"unexpected Z3 version {z3.get_version_string()}")

    h1501 = json.loads(args.h1501.read_text())
    if h1501["status"] != "EXACT_NORMALIZED_BOOTH_OPERAND_SUPPORT":
        raise RuntimeError("H1501 support theorem changed")
    expected_support = {
        row["position"]: row["essential_bits"] for row in h1501["positions"]
    }
    for position in POSITIONS:
        expected = list(range(position))
        if expected_support[position]["multiplicand"] != expected \
                or expected_support[position]["multiplier"] != expected:
            raise RuntimeError(f"H1501 residue support changed at {position}")

    layouts = {name: config for name, _, config in tree_variants()}
    pair_a = layouts[EXPECTED_A]
    pair_b = layouts[EXPECTED_B]
    left_m, left_q = normalized_bits("left")
    right_m, right_q = normalized_bits("right")

    results = []
    for position in POSITIONS:
        left_d = defect(position, left_m, left_q, pair_a, pair_b)
        right_d = defect(position, right_m, right_q, pair_a, pair_b)
        different_defect = left_d != right_d
        pair_residue_well_defined = {
            "status": "proven_by_h1501_support_composition"
        }
        same_product = (
            product_residue(left_m, left_q, position)
            == product_residue(right_m, right_q, position)
        )
        product_collision = solve(
            f"product-residue quotient at {position}",
            (same_product, different_defect),
            (left_m, left_q), (right_m, right_q), (left_d, right_d),
            position, args.timeout_ms
        )
        swapped_residues = (
            residue(left_m, position) == residue(right_q, position),
            residue(left_q, position) == residue(right_m, position),
        )
        swap_collision = solve(
            f"operand-swap symmetry at {position}",
            (*swapped_residues, different_defect),
            (left_m, left_q), (right_m, right_q), (left_d, right_d),
            position, args.timeout_ms
        )
        results.append({
            "position": position,
            "pair_residue_well_defined": pair_residue_well_defined,
            "product_residue_collision": product_collision,
            "operand_swap_collision": swap_collision,
        })

    product_statuses = [
        row["product_residue_collision"]["status"] for row in results
    ]
    swap_statuses = [
        row["operand_swap_collision"]["status"] for row in results
    ]
    rejected = all(status == "sat" for status in product_statuses)
    asymmetric = all(status == "sat" for status in swap_statuses)
    report = {
        "experiment": "h1502_defect_quotient_audit",
        "status": (
            "PRODUCT_QUOTIENT_AND_SWAP_SYMMETRY_REJECTED"
            if rejected and asymmetric else "EXACT_QUOTIENT_AUDIT_COMPLETE"
        ),
        "z3_version": z3.get_version_string(),
        "normalized_domain": h1501["normalized_domain"],
        "positions": results,
        "interpretation": (
            "D_j is well-defined by the ordered pair of low operand residues. "
            + (
                "SAT collisions at both columns reject the ordinary product "
                "residue as a sufficient quotient. " if rejected else
                "The product-residue quotient results are recorded per column. "
            )
            + (
                "SAT swap collisions at both columns prove operand-role "
                "asymmetry. " if asymmetric else
                "The operand-swap results are recorded per column. "
            )
            + "The exact outcomes determine which factorization and role "
            "information the carry-save topology retains."
        ),
        "claim_boundary": (
            "These are exact quotient tests of the two surviving abstract "
            "representations. They do not identify the physical Skylake "
            "orientation or close the x87 frontier."
        ),
        "hardware_execution": "none",
        "hardware_labels_opened": "none",
        "capture_manifest": "none",
        "emulator_change": "none",
        "paper_change": "none",
        "sha256": {"h1501": digest(args.h1501)},
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
                "pair_residue": row["pair_residue_well_defined"]["status"],
                "product_quotient": row["product_residue_collision"]["status"],
                "swap_symmetry": row["operand_swap_collision"]["status"],
            }
            for row in results
        ],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
