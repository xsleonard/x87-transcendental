#!/usr/bin/env python3
"""Replay H1505's immutable fixed-polarity CNF with CVC5 CaDiCaL.

H1507 used CVC5's default QF_SAT backend and timed out.  H1526 pins the input
hashes and selects the compiled CaDiCaL backend explicitly.  SAT models are
decoded and replayed through H1507's independent validator; UNSAT is a theorem
only for H1505's bounded recognized-opcode condition.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import cvc5

import h1507_cvc5_dimacs_crosscheck as h1507


EXPECTED_CNF_SHA256 = (
    "f4c39270dd3f3bd96211ca3c379ffdf838839c814df6384385d695032ecd373f"
)
EXPECTED_H1467_SHA256 = (
    "63d32e546726b602e0c55b87a6e89792dab2d9ad3ce8938dec123b023cb4fa74"
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("cnf", type=Path)
    parser.add_argument("h1467", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--timeout-ms", type=int, default=300_000)
    arguments = parser.parse_args()
    if arguments.output.exists():
        raise SystemExit(f"refusing to overwrite {arguments.output}")
    if cvc5.__version__ != "1.3.1":
        raise RuntimeError(f"validated CVC5 version changed: {cvc5.__version__}")

    cnf_sha256 = digest(arguments.cnf)
    h1467_sha256 = digest(arguments.h1467)
    if cnf_sha256 != EXPECTED_CNF_SHA256:
        raise RuntimeError(f"H1505 CNF hash changed: {cnf_sha256}")
    if h1467_sha256 != EXPECTED_H1467_SHA256:
        raise RuntimeError(f"H1467 report hash changed: {h1467_sha256}")

    solver = cvc5.Solver()
    solver.setLogic("QF_SAT")
    solver.setOption("produce-models", "true")
    solver.setOption("tlimit-per", str(arguments.timeout_ms))
    solver.setOption("sat-solver", "cadical")
    build_started = time.monotonic()
    variables, clause_count = h1507.load_dimacs(arguments.cnf, solver)
    build_seconds = time.monotonic() - build_started
    solve_started = time.monotonic()
    result = solver.checkSat()
    solve_seconds = time.monotonic() - solve_started
    status = (
        "SAT" if result.isSat() else
        "UNSAT" if result.isUnsat() else
        "UNKNOWN"
    )

    report: dict[str, object] = {
        "query": "h1505_exact_dimacs_cvc5_cadical",
        "status": status,
        "unknown_explanation": (
            result.getUnknownExplanation().name if result.isUnknown() else None
        ),
        "solver": {
            "name": "CVC5 QF_SAT CaDiCaL",
            "version": cvc5.__version__,
            "timeout_ms": arguments.timeout_ms,
            "cnf_construction_seconds": build_seconds,
            "solve_seconds": solve_seconds,
        },
        "cnf": {
            "variables": len(variables) - 1,
            "clauses": clause_count,
            "sha256": cnf_sha256,
        },
        "dependencies": {"h1467_report_sha256": h1467_sha256},
        "claim_boundary": (
            "SAT or UNSAT decides only H1505's injective fixed-polarity "
            "twelve-channel mapping under the current 459-value public P6 "
            "recognized-opcode condition; it is not a complete Pentium Pro "
            "decoder or a Skylake R59 selector."
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
    if result.isSat():
        report["model"] = h1507.decode_and_validate(
            solver, variables, arguments.h1467
        )

    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(text)
    print(json.dumps({
        "output": str(arguments.output),
        "report_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "status": status,
        "build_seconds": build_seconds,
        "solve_seconds": solve_seconds,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
