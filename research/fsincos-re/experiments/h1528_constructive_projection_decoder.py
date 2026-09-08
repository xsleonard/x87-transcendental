#!/usr/bin/env python3
"""Construct and prove an explicit decoder for H1522's 63-bit projection.

H1522 proves that the pair-A/pair-B defect is constant on each valid fiber of
the 63 retained raw coordinates, but H1523/H1524 did not extract a formula.
H1528 constructs one valid canonical completion for every projected key.  The
decoder is then simply the existing exact defect circuit evaluated on that
completion.  Two independent bit-blasted UNSAT obligations prove total
validity/projection preservation and equivalence on every valid original state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import cvc5
import z3

from h1400_p5_representation_audit import tree_variants
from h1516_minimal_ordered_quartet_state import EXPECTED_A, EXPECTED_B, defect
from h1517_quartet_state_bit_support import (
    canonical_validity_constraints,
    decode_state,
    field_names,
    free_state,
)
from h1522_exact_cnf_projection import parse_dimacs


WIDTH = 9
MASK = (1 << WIDTH) - 1
UNORDERED_WINDOWS = {4: 3, 5: 5}
EXPECTED_H1517_SHA256 = (
    "3846ebdb9d818861b9ef645daf3d5b7f637fb206dcca8a3b676c4f576d58caeb"
)
EXPECTED_H1522_SHA256 = (
    "f4e09346f6185324245d2363a922f26d8bc0e41962982157077d165e9bebf4b8"
)


def sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def digest(path: Path) -> str:
    return sha256(path.read_bytes())


def coordinate_set(rows) -> set[tuple[str, int]]:
    return {(row["field"], int(row["bit"])) for row in rows}


def expected_retained() -> set[tuple[str, int]]:
    masks = {
        "g0.T": range(0, 8), "g0.U": range(0, 5),
        "g1.T": range(0, 8), "g1.U": range(0, 4),
        "g2.T": range(0, 8), "g2.U": range(0, 5),
        "g3.T": range(0, 8), "g3.U": range(0, 5),
        "g4.T": range(3, 8), "g4.P": range(2, 4),
        "g5.T": range(5, 8), "g5.P": range(4, 6),
    }
    return {
        (field, bit)
        for field, bits in masks.items()
        for bit in bits
    }


def bit(word, index: int):
    return z3.Extract(index, index, word) == z3.BitVecVal(1, 1)


def bit_word(value, index: int):
    return z3.If(
        value,
        z3.BitVecVal(1 << index, WIDTH),
        z3.BitVecVal(0, WIDTH),
    )


def zero_fill(word, retained_bits):
    result = z3.BitVecVal(0, WIDTH)
    for index in retained_bits:
        result = result | bit_word(bit(word, index), index)
    return result


def complete_unordered(total, propagate, start: int):
    """Return a valid (T,P) completion for retained T[start..7], P[start-1..start].

    For T=P+2G, the addition carry entering `start` is
    c = T[start] XOR P[start].  P[start-1] decides whether c is seeded by
    G[start-1] directly or by G[start-2] one column earlier.  Above `start`,
    choose G=0 and propagate the carry only while P remains one.
    """

    p_previous = bit(propagate, start - 1)
    carry = z3.Xor(bit(total, start), bit(propagate, start))
    completed_p = bit_word(p_previous, start - 1)
    completed_g = (
        bit_word(z3.And(carry, z3.Not(p_previous)), start - 1)
        | bit_word(z3.And(carry, p_previous), start - 2)
    )
    for index in range(start, 8):
        p_value = z3.Xor(bit(total, index), carry)
        completed_p = completed_p | bit_word(p_value, index)
        carry = z3.And(p_value, carry)
    completed_t = completed_p + (completed_g << 1)
    return completed_t, completed_p


def constructive_completion(state):
    completed = {}
    ordered_masks = {
        0: (range(0, 8), range(0, 5)),
        1: (range(0, 8), range(0, 4)),
        2: (range(0, 8), range(0, 5)),
        3: (range(0, 8), range(0, 5)),
    }
    for group, (total_bits, ordered_bits) in ordered_masks.items():
        completed[f"g{group}.T"] = zero_fill(
            state[f"g{group}.T"], total_bits
        )
        completed[f"g{group}.U"] = zero_fill(
            state[f"g{group}.U"], ordered_bits
        )
    for group, start in UNORDERED_WINDOWS.items():
        total, propagate = complete_unordered(
            state[f"g{group}.T"], state[f"g{group}.P"], start
        )
        completed[f"g{group}.T"] = total
        completed[f"g{group}.P"] = propagate
    return completed


def retained_equal(left, right, retained):
    return [
        bit(left[field], index) == bit(right[field], index)
        for field, index in sorted(retained)
    ]


def bitblast(assertion):
    goal = z3.Goal()
    goal.add(assertion)
    pipeline = z3.Then(
        "simplify", "propagate-values", "solve-eqs", "bit-blast",
        "tseitin-cnf",
    )
    transformed = pipeline(goal)
    if len(transformed) != 1:
        raise RuntimeError(f"bit-blast produced {len(transformed)} subgoals")
    clauses = transformed[0]
    return clauses, normalize_dimacs(clauses.dimacs())


def normalize_dimacs(text: str) -> str:
    """Densify Z3's occasionally sparse DIMACS variable identifiers."""

    clauses = []
    identifiers = set()
    for line in text.splitlines():
        if not line or line.startswith("c") or line.startswith("p "):
            continue
        values = [int(value) for value in line.split()]
        if not values or values[-1] != 0:
            raise RuntimeError("unterminated DIMACS clause")
        clauses.append(values[:-1])
        identifiers.update(abs(value) for value in values[:-1])
    mapping = {
        identifier: dense
        for dense, identifier in enumerate(sorted(identifiers), start=1)
    }
    lines = [f"p cnf {len(mapping)} {len(clauses)}"]
    lines.extend(
        " ".join(
            str(mapping[abs(value)] if value > 0 else -mapping[abs(value)])
            for value in clause
        ) + " 0"
        for clause in clauses
    )
    return "\n".join(lines) + "\n"


def solve_z3(clauses, timeout_ms: int):
    solver = z3.Tactic("sat").solver()
    solver.set(timeout=timeout_ms)
    solver.add(*clauses)
    started = time.monotonic()
    result = solver.check()
    record = {
        "solver": f"z3 {z3.get_version_string()} propositional SAT",
        "status": str(result),
        "elapsed_ms": round((time.monotonic() - started) * 1000),
    }
    if result == z3.unknown:
        record["reason_unknown"] = solver.reason_unknown()
    return record


def solve_cadical(cnf_text: str, timeout_ms: int):
    solver = cvc5.Solver()
    solver.setLogic("QF_SAT")
    solver.setOption("tlimit-per", str(timeout_ms))
    solver.setOption("sat-solver", "cadical")
    _, _, clauses = parse_dimacs(cnf_text, solver)
    started = time.monotonic()
    result = solver.checkSat()
    status = (
        "sat" if result.isSat() else
        "unsat" if result.isUnsat() else
        "unknown"
    )
    record = {
        "solver": f"cvc5 {cvc5.__version__} QF_SAT CaDiCaL",
        "status": status,
        "elapsed_ms": round((time.monotonic() - started) * 1000),
        "clauses": clauses,
    }
    if result.isUnknown():
        record["reason_unknown"] = result.getUnknownExplanation().name
    return record


def prove(name: str, assertion, output: Path, timeout_ms: int):
    clauses, cnf_text = bitblast(assertion)
    cnf_path = output.with_name(output.stem + f"_{name}.cnf")
    if cnf_path.exists():
        raise SystemExit(f"refusing to overwrite {cnf_path}")
    cnf_path.write_text(cnf_text)
    z3_result = solve_z3(clauses, timeout_ms)
    cvc5_result = solve_cadical(cnf_text, timeout_ms)
    decided = {
        result["status"]
        for result in (z3_result, cvc5_result)
        if result["status"] in ("sat", "unsat")
    }
    if len(decided) > 1:
        status = "SOLVER_DISAGREEMENT"
    elif decided:
        status = next(iter(decided)).upper()
    else:
        status = "UNKNOWN"
    return {
        "status": status,
        "cnf": {
            "artifact": cnf_path.name,
            "bytes": len(cnf_text.encode()),
            "variables": max(
                (int(line.split()[2]) for line in cnf_text.splitlines()
                 if line.startswith("p cnf ")),
                default=0,
            ),
            "clauses": len(clauses),
            "sha256": sha256(cnf_text.encode()),
        },
        "z3": z3_result,
        "cvc5": cvc5_result,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("h1517", type=Path)
    parser.add_argument("h1522", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--timeout-ms", type=int, default=60_000)
    arguments = parser.parse_args()
    if arguments.output.exists():
        raise SystemExit(f"refusing to overwrite {arguments.output}")
    if z3.get_version_string() != "4.15.3" or cvc5.__version__ != "1.3.1":
        raise RuntimeError("validated solver versions changed")
    if digest(arguments.h1517) != EXPECTED_H1517_SHA256:
        raise RuntimeError("H1517 canonical report hash changed")
    if digest(arguments.h1522) != EXPECTED_H1522_SHA256:
        raise RuntimeError("H1522 report hash changed")

    h1517 = json.loads(arguments.h1517.read_text())
    h1522 = json.loads(arguments.h1522.read_text())
    retained = coordinate_set(h1517["reachable_state_support"])
    retained.add((h1522["candidate"]["field"], int(h1522["candidate"]["bit"])))
    if retained != expected_retained() or len(retained) != 63:
        raise RuntimeError("H1522 retained-coordinate set changed")
    if h1522["status"] != "EXACT_63_COORDINATE_MINIMUM":
        raise RuntimeError("H1522 theorem changed")

    layouts = {name: config for name, _, config in tree_variants()}
    pair_a = layouts[EXPECTED_A]
    pair_b = layouts[EXPECTED_B]
    original = free_state("original")
    completed = constructive_completion(original)

    validity_violation = z3.Not(z3.And(
        *canonical_validity_constraints(completed),
        *retained_equal(original, completed, retained),
    ))
    equivalence_violation = z3.And(
        *canonical_validity_constraints(original),
        defect(decode_state(original), pair_a, pair_b)
        != defect(decode_state(completed), pair_a, pair_b),
    )
    validity = prove(
        "totality", validity_violation, arguments.output, arguments.timeout_ms
    )
    equivalence = prove(
        "equivalence", equivalence_violation,
        arguments.output, arguments.timeout_ms,
    )
    status = (
        "EXACT_CONSTRUCTIVE_63_COORDINATE_DECODER"
        if validity["status"] == equivalence["status"] == "UNSAT"
        else "CONSTRUCTIVE_DECODER_NOT_PROVED"
    )
    report = {
        "experiment": "h1528_constructive_projection_decoder",
        "status": status,
        "z3_version": z3.get_version_string(),
        "cvc5_version": cvc5.__version__,
        "retained_coordinates": 63,
        "construction": {
            "ordered_groups": (
                "zero-fill omitted T/U coordinates in groups 0..3"
            ),
            "unordered_groups": {
                "g4": "T[3..7], P[2..3], carry seed at columns 1..2",
                "g5": "T[5..7], P[4..5], carry seed at columns 3..4",
            },
            "recurrence": (
                "c_k=T_k XOR P_k; seed c_k below k according to P_(k-1); "
                "for i=k..7 set P_i=T_i XOR c_i, G_i=0, and "
                "c_(i+1)=P_i AND c_i; finally T=P+(G<<1) mod 2^9"
            ),
            "decoder": (
                "apply the exact H1516 canonical state decoder and common "
                "pair-A/pair-B defect circuit to this completed state"
            ),
            "lookup_tables": "none",
            "decision_tree": "none",
        },
        "totality_and_projection_proof": validity,
        "valid_state_equivalence_proof": equivalence,
        "composition": (
            "The constructive completion is valid and preserves all 63 "
            "retained coordinates for every projected bit pattern. Its defect "
            "equals every valid original completion. This supplies the "
            "explicit decoder whose extraction remained UNKNOWN in H1523/H1524."
        ),
        "claim_boundary": (
            "This is an exact table-free decoder for the abstract H1516 "
            "pair-A/pair-B defect quotient. It does not select the physical "
            "Skylake orientation or by itself close the x87 emulator frontier."
        ),
        "dependencies": {
            "h1517_sha256": digest(arguments.h1517),
            "h1522_sha256": digest(arguments.h1522),
        },
        "execution": {
            "hardware": "none",
            "x87_instructions": "none",
            "capture_labels_opened": "none",
            "private_capture_ledger": "not accessed",
            "h1488_state": "FROZEN_UNOPENED",
            "emulator_change": "none",
            "paper_change": "none",
        },
    }
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(text)
    print(json.dumps({
        "output": str(arguments.output),
        "report_sha256": sha256(text.encode()),
        "status": status,
        "totality": validity["status"],
        "equivalence": equivalence["status"],
        "cnf": {
            "totality": validity["cnf"],
            "equivalence": equivalence["cnf"],
        },
    }, sort_keys=True))


if __name__ == "__main__":
    main()
