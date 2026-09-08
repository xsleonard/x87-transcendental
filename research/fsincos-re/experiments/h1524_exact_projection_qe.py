#!/usr/bin/env python3
"""Eliminate H1522's 24 private completion bits to obtain a decoder.

For shared retained state ``k``, define F(k) as the existence of a valid left
completion whose pair-A/pair-B defect is one.  H1522 proves that all valid
completions at the same k have the same defect, so a quantifier-free result is
an exact decoder on the reachable projected image.  This experiment tries a
small fixed portfolio of Z3 Boolean quantifier-elimination pipelines and
preserves a formula only if every private variable is eliminated.

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

from h1400_p5_representation_audit import tree_variants
from h1516_minimal_ordered_quartet_state import EXPECTED_A, EXPECTED_B, defect
from h1517_quartet_state_bit_support import (
    canonical_validity_constraints,
    decode_state,
)
from h1521_width_reduced_valid_projection import CANDIDATE, key, reduced_states


def sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def symbol_info(term):
    """Return free symbol names, quantifier presence, and DAG node count."""
    names = set()
    quantified = False
    seen = set()
    stack = [term]
    while stack:
        current = stack.pop()
        identity = current.get_id()
        if identity in seen:
            continue
        seen.add(identity)
        if z3.is_quantifier(current):
            quantified = True
            stack.append(current.body())
            continue
        if z3.is_const(current) \
                and current.decl().kind() == z3.Z3_OP_UNINTERPRETED:
            names.add(str(current.decl().name()))
        stack.extend(current.children())
    return names, quantified, len(seen)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("h1517", type=Path)
    parser.add_argument("h1522", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--timeout-ms", type=int, default=120_000)
    arguments = parser.parse_args()
    if arguments.output.exists():
        raise SystemExit(f"refusing to overwrite {arguments.output}")
    decoder_path = arguments.output.with_name(
        arguments.output.stem + "_decoder.smt2"
    )
    if decoder_path.exists():
        raise SystemExit(f"refusing to overwrite {decoder_path}")
    if z3.get_version_string() != "4.15.3":
        raise RuntimeError("validated Z3 version changed")

    h1517 = json.loads(arguments.h1517.read_text())
    h1522 = json.loads(arguments.h1522.read_text())
    if h1517["status"] != "EXACT_EXTENSION_SUPPORT_WITH_REACHABILITY_GAP" \
            or h1522["status"] != "EXACT_63_COORDINATE_MINIMUM":
        raise RuntimeError("H1517/H1522 boundary changed")
    extension = {key(row) for row in h1517["canonical_extension_support"]}
    mandatory = {key(row) for row in h1517["reachable_state_support"]}
    retained = mandatory | {CANDIDATE}

    layouts = {name: config for name, _, config in tree_variants()}
    pair_a = layouts[EXPECTED_A]
    pair_b = layouts[EXPECTED_B]
    left, _, shared, left_private, _ = reduced_states(
        "h1524", retained, extension
    )
    left_defect = defect(decode_state(left), pair_a, pair_b)
    antecedent = z3.And(
        *canonical_validity_constraints(left),
        left_defect == z3.BitVecVal(1, 1),
    )
    quantified = z3.Exists(
        sorted(left_private.values(), key=str), antecedent
    )

    pipelines = (
        ("bitblast_qe2", ("simplify", "bit-blast", "qe2", "simplify", "aig")),
        ("bitblast_qe", ("simplify", "bit-blast", "qe", "simplify", "aig")),
        ("qelight_bitblast_qe2", (
            "qe-light", "simplify", "bit-blast", "qe2", "simplify", "aig"
        )),
    )
    attempts = []
    decoder = None
    winner = None
    private_names = {str(variable) for variable in left_private.values()}
    shared_names = {str(variable) for variable in shared.values()}
    for name, stages in pipelines:
        started = time.monotonic()
        try:
            tactic = z3.TryFor(z3.Then(*stages), arguments.timeout_ms)
            result = tactic(quantified)
            if len(result) != 1:
                raise RuntimeError(f"pipeline returned {len(result)} goals")
            formula = z3.simplify(z3.And(*result[0]))
            variables, has_quantifier, dag_nodes = symbol_info(formula)
            remaining_private = sorted(variables & private_names)
            foreign = sorted(variables - shared_names)
            success = not remaining_private and not foreign \
                and not has_quantifier
            attempt = {
                "pipeline": name,
                "stages": list(stages),
                "status": "success" if success else "incomplete",
                "elapsed_ms": round((time.monotonic() - started) * 1000),
                "formula_variables": len(variables),
                "formula_dag_nodes": dag_nodes,
                "remaining_private_variables": remaining_private,
                "foreign_variables": foreign,
            }
            attempts.append(attempt)
            if success:
                decoder = formula
                winner = name
                break
        except (z3.Z3Exception, RuntimeError) as error:
            attempts.append({
                "pipeline": name,
                "stages": list(stages),
                "status": "unknown",
                "elapsed_ms": round((time.monotonic() - started) * 1000),
                "reason": str(error),
            })

    if decoder is None:
        status = "STOPPING_UNKNOWN"
        decoder_record = None
    else:
        decoder_text = (
            "; exact H1524 decoder predicate over H1522 retained variables\n"
            "(assert " + decoder.sexpr() + ")\n"
        )
        decoder_path.write_text(decoder_text)
        status = "EXPLICIT_63_COORDINATE_DECODER"
        decoder_record = {
            "pipeline": winner,
            "artifact": decoder_path.name,
            "bytes": len(decoder_text.encode()),
            "sha256": sha256(decoder_text.encode()),
            "variables": len(symbol_info(decoder)[0]),
        }

    report = {
        "experiment": "h1524_exact_projection_qe",
        "status": status,
        "z3_version": z3.get_version_string(),
        "retained_coordinate_count": len(retained),
        "private_completion_coordinate_count": len(left_private),
        "definition": (
            "exists valid private completion with pair-A XOR pair-B defect 1"
        ),
        "attempts": attempts,
        **({"decoder": decoder_record} if decoder_record else {}),
        "interpretation": (
            "A successful quantifier-free formula is an exact decoder on the "
            "reachable 63-coordinate image by H1522's quotient theorem. An "
            "UNKNOWN attempt carries no semantic conclusion."
        ),
        "claim_boundary": (
            "This concerns only the abstract defect representation. It does "
            "not choose the physical Skylake orientation or validate a "
            "silicon selector."
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
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(text)
    print(json.dumps({
        "output": str(arguments.output),
        "report_sha256": sha256(text.encode()),
        "status": status,
        "attempts": [
            {"pipeline": row["pipeline"], "status": row["status"],
             "elapsed_ms": row["elapsed_ms"]}
            for row in attempts
        ],
        **({"decoder": decoder_record} if decoder_record else {}),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
