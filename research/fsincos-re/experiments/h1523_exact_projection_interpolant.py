#!/usr/bin/env python3
"""Synthesize an explicit 63-coordinate decoder for the H1522 quotient.

H1522 proves that valid H1516 states agreeing on its 63 retained Boolean
coordinates have the same pair-A/pair-B defect.  This experiment asks CVC5
for a Craig interpolant between the defect-one and defect-zero copies.  Any
successful interpolant is a closed Boolean formula over the shared retained
coordinates only, and therefore an explicit decoder rather than an
existential quotient statement.

No x87 instruction or hardware capture is executed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

try:
    import z3
except ImportError as error:
    raise SystemExit("z3-solver 4.15.3.0 is required") from error

try:
    import cvc5
except ImportError as error:
    raise SystemExit("cvc5 1.3.1 is required") from error

from h1400_p5_representation_audit import tree_variants
from h1516_minimal_ordered_quartet_state import EXPECTED_A, EXPECTED_B, defect
from h1517_quartet_state_bit_support import (
    canonical_validity_constraints,
    decode_state,
)
from h1521_width_reduced_valid_projection import CANDIDATE, key, reduced_states


def sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def conjunction(terms):
    terms = tuple(terms)
    return z3.And(*terms) if terms else z3.BoolVal(True)


def load_cvc5_problem(declarations: str, assertion: str, conjecture: str,
                      timeout_ms: int, full_sygus_verify: bool):
    solver = cvc5.Solver()
    solver.setLogic("QF_BV")
    solver.setOption("produce-interpolants", "true")
    solver.setOption("interpolants-mode", "shared")
    solver.setOption("tlimit-per", str(timeout_ms))
    if full_sygus_verify:
        solver.setOption("full-sygus-verify", "true")
    parser = cvc5.InputParser(solver)
    parser.setIncrementalStringInput(
        cvc5.InputLanguage.SMT_LIB_2_6, "h1523"
    )
    parser.appendIncrementalStringInput(
        declarations + "\n(assert " + assertion + ")\n"
    )
    while not parser.done():
        command = parser.nextCommand()
        if command.isNull():
            break
        command.invoke(solver, parser.getSymbolManager())
    parser.appendIncrementalStringInput(conjecture + "\n")
    conjecture_term = parser.nextTerm()
    if conjecture_term.isNull():
        raise RuntimeError("failed to parse interpolant conjecture")
    return solver, conjecture_term


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("h1517", type=Path)
    parser.add_argument("h1522", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--timeout-ms", type=int, default=300_000)
    parser.add_argument("--full-sygus-verify", action="store_true")
    arguments = parser.parse_args()
    if arguments.output.exists():
        raise SystemExit(f"refusing to overwrite {arguments.output}")
    query_path = arguments.output.with_name(arguments.output.stem + ".smt2")
    interpolant_path = arguments.output.with_name(
        arguments.output.stem + "_interpolant.smt2"
    )
    for path in (query_path, interpolant_path):
        if path.exists():
            raise SystemExit(f"refusing to overwrite {path}")
    if z3.get_version_string() != "4.15.3" or cvc5.__version__ != "1.3.1":
        raise RuntimeError("validated solver versions changed")

    h1517 = json.loads(arguments.h1517.read_text())
    h1522 = json.loads(arguments.h1522.read_text())
    if h1517["status"] != "EXACT_EXTENSION_SUPPORT_WITH_REACHABILITY_GAP" \
            or h1522["status"] != "EXACT_63_COORDINATE_MINIMUM":
        raise RuntimeError("H1517/H1522 boundary changed")
    extension = {key(row) for row in h1517["canonical_extension_support"]}
    mandatory = {key(row) for row in h1517["reachable_state_support"]}
    retained = mandatory | {CANDIDATE}
    if (len(extension), len(mandatory), len(retained)) != (87, 62, 63):
        raise RuntimeError("retained-coordinate counts changed")

    layouts = {name: config for name, _, config in tree_variants()}
    pair_a = layouts[EXPECTED_A]
    pair_b = layouts[EXPECTED_B]
    left, right, shared, left_optional, right_optional = reduced_states(
        "h1523", retained, extension
    )
    left_defect = defect(decode_state(left), pair_a, pair_b)
    right_defect = defect(decode_state(right), pair_a, pair_b)
    left_valid = conjunction(canonical_validity_constraints(left))
    right_valid = conjunction(canonical_validity_constraints(right))
    antecedent = z3.And(left_valid, left_defect == z3.BitVecVal(1, 1))
    conjecture = z3.Implies(
        right_valid, right_defect == z3.BitVecVal(1, 1)
    )

    variables = sorted(
        set(shared.values())
        | set(left_optional.values())
        | set(right_optional.values()),
        key=str,
    )
    declarations = "\n".join(
        f"(declare-fun {variable} () Bool)" for variable in variables
    )
    query = (
        "(set-logic QF_BV)\n"
        + declarations
        + "\n(assert " + antecedent.sexpr() + ")\n"
        + "; conjecture passed to get-interpolant\n"
        + "; " + conjecture.sexpr().replace("\n", "\n; ") + "\n"
    )
    query_path.parent.mkdir(parents=True, exist_ok=True)
    query_path.write_text(query)

    solver, conjecture_term = load_cvc5_problem(
        declarations, antecedent.sexpr(), conjecture.sexpr(),
        arguments.timeout_ms, arguments.full_sygus_verify,
    )
    started = time.monotonic()
    failure = None
    try:
        interpolant = solver.getInterpolant(conjecture_term)
    except RuntimeError as error:
        interpolant = None
        failure = str(error)
    elapsed_ms = round((time.monotonic() - started) * 1000)

    if interpolant is not None and not interpolant.isNull():
        interpolant_text = str(interpolant) + "\n"
        interpolant_path.write_text(interpolant_text)
        status = "EXPLICIT_63_COORDINATE_DECODER"
        result = {
            "status": "success",
            "elapsed_ms": elapsed_ms,
            "interpolant_artifact": interpolant_path.name,
            "interpolant_bytes": len(interpolant_text.encode()),
            "interpolant_sha256": sha256(interpolant_text.encode()),
            "interpolant": str(interpolant),
        }
    else:
        status = "STOPPING_UNKNOWN"
        result = {
            "status": "unknown",
            "elapsed_ms": elapsed_ms,
            "reason": failure or "CVC5 returned a null interpolant",
        }

    report = {
        "experiment": "h1523_exact_projection_interpolant",
        "status": status,
        "z3_version": z3.get_version_string(),
        "cvc5_version": cvc5.__version__,
        "full_sygus_verify": arguments.full_sygus_verify,
        "retained_coordinates": [
            {"field": field, "bit": bit}
            for field, bit in sorted(retained)
        ],
        "retained_coordinate_count": len(retained),
        "left_private_coordinate_count": len(left_optional),
        "right_private_coordinate_count": len(right_optional),
        "interpolant_result": result,
        "query_artifact": query_path.name,
        "query_bytes": len(query.encode()),
        "query_sha256": sha256(query.encode()),
        "interpretation": (
            "A successful Craig interpolant is a Boolean decoder over only "
            "the 63 retained coordinates. A timeout or null result does not "
            "weaken H1522's exact quotient theorem."
        ),
        "claim_boundary": (
            "This concerns the abstract pair-A/pair-B defect representation. "
            "It does not choose the physical Skylake orientation or validate "
            "a silicon selector."
        ),
        "hardware_execution": "none",
        "hardware_labels_opened": "none",
        "capture_manifest": "none",
        "emulator_change": "none",
        "paper_change": "none",
        "sha256": {
            "h1517": sha256(arguments.h1517.read_bytes()),
            "h1522": sha256(arguments.h1522.read_bytes()),
        },
    }
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    arguments.output.write_text(text)
    print(json.dumps({
        "output": str(arguments.output),
        "report_sha256": sha256(text.encode()),
        "status": status,
        "elapsed_ms": elapsed_ms,
        **({
            "interpolant_bytes": result["interpolant_bytes"],
            "interpolant_sha256": result["interpolant_sha256"],
        } if result["status"] == "success" else {
            "reason": result["reason"],
        }),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
