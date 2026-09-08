#!/usr/bin/env python3
"""Unroll H1528's carry completion into an exact closed-form decoder."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import cvc5
import z3

from h1517_quartet_state_bit_support import field_names, free_state
from h1528_constructive_projection_decoder import (
    UNORDERED_WINDOWS,
    WIDTH,
    bit,
    bit_word,
    constructive_completion,
    prove,
    zero_fill,
)


EXPECTED_H1528_SCRIPT_SHA256 = (
    "a5d2eb5f1786998e795eb4f566b78302c9533f22e8670d6a81b26d87dbe46ab2"
)
EXPECTED_H1528_REPORT_SHA256 = (
    "ea79668f6e3b27e26ec185bec16ff1e44f5b8d9c66f40be256b2fa6d1a60bb73"
)
EXPECTED_H1529_REPORT_SHA256 = (
    "f9ec0610978752712204f2d5fb5ddb5fca1c301f375fb0db6199d31d5931d478"
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def complete_unordered_closed(total, propagate, start: int):
    p_previous = bit(propagate, start - 1)
    initial_carry = z3.Xor(bit(total, start), bit(propagate, start))
    completed_p = bit_word(p_previous, start - 1)
    completed_g = (
        bit_word(z3.And(initial_carry, z3.Not(p_previous)), start - 1)
        | bit_word(z3.And(initial_carry, p_previous), start - 2)
    )
    for index in range(start, 8):
        carry = z3.And(
            initial_carry,
            *(z3.Not(bit(total, lower))
              for lower in range(start, index)),
        )
        completed_p = completed_p | bit_word(
            z3.Xor(bit(total, index), carry), index
        )
    completed_t = completed_p + (completed_g << 1)
    return completed_t, completed_p


def closed_form_completion(state):
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
        total, propagate = complete_unordered_closed(
            state[f"g{group}.T"], state[f"g{group}.P"], start
        )
        completed[f"g{group}.T"] = total
        completed[f"g{group}.P"] = propagate
    return completed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("h1528_script", type=Path)
    parser.add_argument("h1528_report", type=Path)
    parser.add_argument("h1529_report", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--timeout-ms", type=int, default=60_000)
    arguments = parser.parse_args()
    if arguments.output.exists():
        raise SystemExit(f"refusing to overwrite {arguments.output}")
    expected = {
        arguments.h1528_script: EXPECTED_H1528_SCRIPT_SHA256,
        arguments.h1528_report: EXPECTED_H1528_REPORT_SHA256,
        arguments.h1529_report: EXPECTED_H1529_REPORT_SHA256,
    }
    for path, expected_hash in expected.items():
        if digest(path) != expected_hash:
            raise RuntimeError(f"dependency hash changed: {path}")
    if z3.get_version_string() != "4.15.3" or cvc5.__version__ != "1.3.1":
        raise RuntimeError("validated solver versions changed")
    h1528 = json.loads(arguments.h1528_report.read_text())
    h1529 = json.loads(arguments.h1529_report.read_text())
    if h1528["status"] != "EXACT_CONSTRUCTIVE_63_COORDINATE_DECODER" \
            or h1529["status"] != "EXACT_H1528_CNF_REPLAY":
        raise RuntimeError("H1528/H1529 theorem boundary changed")

    state = free_state("closed_form")
    recurrent = constructive_completion(state)
    closed = closed_form_completion(state)
    disagreement = z3.Or(*(
        recurrent[field] != closed[field] for field in field_names()
    ))
    proof = prove(
        "recurrence_equivalence", disagreement,
        arguments.output, arguments.timeout_ms,
    )
    status = (
        "EXACT_CLOSED_FORM_63_COORDINATE_DECODER"
        if proof["status"] == "UNSAT"
        else "CLOSED_FORM_UNROLLING_NOT_PROVED"
    )
    report = {
        "experiment": "h1530_closed_form_projection_decoder",
        "status": status,
        "formula": {
            "initial_carry": "c_k = T_k XOR P_k",
            "unrolled_carry": (
                "c_i = c_k AND (AND over j=k..i-1 of NOT T_j), i>=k"
            ),
            "propagate": "P'_i = T_i XOR c_i, i=k..7",
            "low_seed": (
                "G'_(k-2)=c_k AND P_(k-1); "
                "G'_(k-1)=c_k AND NOT P_(k-1)"
            ),
            "total": "T' = P' + 2*G' mod 2^9",
            "groups": {"g4": "k=3", "g5": "k=5"},
            "lookup_tables": "none",
            "decision_tree": "none",
            "state_machine": "none",
        },
        "proof": proof,
        "composition": (
            "The closed expression is identical to H1528's constructive "
            "completion for every input state. H1528/H1529 already prove that "
            "completion total, projection-preserving, and defect-equivalent "
            "for every valid H1516 redundant state."
        ),
        "claim_boundary": (
            "This is a closed-form decoder for the abstract pair-A/pair-B "
            "defect quotient. It does not identify the physical Skylake pair "
            "orientation or close the remaining x87 emulator rows."
        ),
        "dependencies": {
            "h1528_script_sha256": digest(arguments.h1528_script),
            "h1528_report_sha256": digest(arguments.h1528_report),
            "h1529_report_sha256": digest(arguments.h1529_report),
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
        "report_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "status": status,
        "proof_status": proof["status"],
        "cnf": proof["cnf"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
