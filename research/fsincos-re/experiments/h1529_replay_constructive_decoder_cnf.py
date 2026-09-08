#!/usr/bin/env python3
"""Independently replay H1528's immutable proof CNFs with CVC5 CaDiCaL."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import cvc5

from h1522_exact_cnf_projection import parse_dimacs


EXPECTED = {
    "totality": {
        "sha256": "d2c2b18432663b0f6fbc5934c420e7e802b04c4ac0e4fa439ccd74a0a1d57e45",
        "variables": 50,
        "clauses": 193,
    },
    "equivalence": {
        "sha256": "34db421d4fadc71b4b74bace1b7c56b052b7c8b9f2f76dfe6ffb4a4e0c3f8f38",
        "variables": 620,
        "clauses": 3276,
    },
}
EXPECTED_H1528_SHA256 = (
    "ea79668f6e3b27e26ec185bec16ff1e44f5b8d9c66f40be256b2fa6d1a60bb73"
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replay(name: str, path: Path, timeout_ms: int):
    expected = EXPECTED[name]
    actual_hash = digest(path)
    if actual_hash != expected["sha256"]:
        raise RuntimeError(f"{name} CNF hash changed: {actual_hash}")
    solver = cvc5.Solver()
    solver.setLogic("QF_SAT")
    solver.setOption("tlimit-per", str(timeout_ms))
    solver.setOption("sat-solver", "cadical")
    variables, _, clauses = parse_dimacs(path.read_text(), solver)
    if len(variables) - 1 != expected["variables"]:
        raise RuntimeError(f"{name} variable count changed")
    if clauses != expected["clauses"]:
        raise RuntimeError(f"{name} clause count changed")
    started = time.monotonic()
    result = solver.checkSat()
    status = (
        "UNSAT" if result.isUnsat() else
        "SAT" if result.isSat() else
        "UNKNOWN"
    )
    return {
        "status": status,
        "solver": f"cvc5 {cvc5.__version__} QF_SAT CaDiCaL",
        "elapsed_ms": round((time.monotonic() - started) * 1000),
        "variables": len(variables) - 1,
        "clauses": clauses,
        "sha256": actual_hash,
        **({"reason_unknown": result.getUnknownExplanation().name}
           if result.isUnknown() else {}),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("h1528", type=Path)
    parser.add_argument("totality_cnf", type=Path)
    parser.add_argument("equivalence_cnf", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--timeout-ms", type=int, default=60_000)
    arguments = parser.parse_args()
    if arguments.output.exists():
        raise SystemExit(f"refusing to overwrite {arguments.output}")
    if cvc5.__version__ != "1.3.1":
        raise RuntimeError("validated CVC5 version changed")
    if digest(arguments.h1528) != EXPECTED_H1528_SHA256:
        raise RuntimeError("H1528 report hash changed")

    results = {
        "totality": replay(
            "totality", arguments.totality_cnf, arguments.timeout_ms
        ),
        "equivalence": replay(
            "equivalence", arguments.equivalence_cnf, arguments.timeout_ms
        ),
    }
    status = (
        "EXACT_H1528_CNF_REPLAY"
        if all(result["status"] == "UNSAT" for result in results.values())
        else "H1528_CNF_REPLAY_UNRESOLVED"
    )
    report = {
        "experiment": "h1529_replay_constructive_decoder_cnf",
        "status": status,
        "h1528_sha256": digest(arguments.h1528),
        "results": results,
        "claim_boundary": (
            "This reproduces H1528's immutable totality and equivalence "
            "proof obligations. It does not select a physical Skylake tree "
            "orientation or close the remaining x87 frontier."
        ),
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
        "results": {
            name: result["status"] for name, result in results.items()
        },
    }, sort_keys=True))


if __name__ == "__main__":
    main()
