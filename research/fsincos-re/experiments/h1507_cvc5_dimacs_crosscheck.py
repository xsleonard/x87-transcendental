#!/usr/bin/env python3
"""Cross-check H1505's immutable exact DIMACS instance with CVC5.

The input CNF is not regenerated or modified.  CVC5 receives each DIMACS
clause as a Boolean assertion.  A SAT result is decoded through H1505's
documented variable order and independently replayed on all 38 patch rows.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import cvc5

import h1490_ppro_core_permutation_transfer as later
import h1504_ppro_opcode_permutation_smt as h1504


LOGICAL_BITS = 12
OPTIONS_PER_BIT = 496


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_dimacs(path: Path, solver: cvc5.Solver):
    variables = None
    declared_clauses = None
    asserted_clauses = 0
    for line in path.read_text().splitlines():
        if not line or line.startswith("c"):
            continue
        if line.startswith("p "):
            _, kind, variable_count, clause_count = line.split()
            if kind != "cnf" or variables is not None:
                raise RuntimeError(f"unsupported DIMACS header {line!r}")
            declared_clauses = int(clause_count)
            variables = [None] + [
                solver.mkConst(solver.getBooleanSort(), f"v{index}")
                for index in range(1, int(variable_count) + 1)
            ]
            continue
        if variables is None:
            raise RuntimeError("DIMACS clause appears before header")
        values = [int(token) for token in line.split()]
        if not values or values[-1] != 0:
            raise RuntimeError("unterminated DIMACS clause")
        literals = [
            variables[value] if value > 0 else solver.mkTerm(
                cvc5.Kind.NOT, variables[-value]
            )
            for value in values[:-1]
        ]
        if len(literals) == 1:
            clause = literals[0]
        else:
            clause = solver.mkTerm(cvc5.Kind.OR, *literals)
        solver.assertFormula(clause)
        asserted_clauses += 1
    if variables is None or asserted_clauses != declared_clauses:
        raise RuntimeError(
            f"DIMACS clause count {asserted_clauses} != {declared_clauses}"
        )
    return variables, asserted_clauses


def decode_and_validate(
    solver: cvc5.Solver,
    variables,
    h1467: Path,
) -> dict[str, object]:
    channels = h1504.physical_channels()
    mapping = []
    for logical_bit in range(LOGICAL_BITS):
        chosen = []
        for option in range(OPTIONS_PER_BIT):
            variable_index = 1 + logical_bit * OPTIONS_PER_BIT + option
            if solver.getValue(variables[variable_index]).getBooleanValue():
                chosen.append(option)
        if len(chosen) != 1:
            raise RuntimeError(
                f"logical bit {logical_bit} has {len(chosen)} selected options"
            )
        channel = chosen[0] // 2
        polarity = chosen[0] & 1
        dword, physical_bit = channels[channel]
        mapping.append(
            {
                "logical_opcode_bit": logical_bit,
                "physical_channel_index": channel,
                "dword": dword,
                "bit": physical_bit,
                "inverted": bool(polarity),
            }
        )
    if len({item["physical_channel_index"] for item in mapping}) != LOGICAL_BITS:
        raise RuntimeError("CVC5 model is not channel-injective")

    rows = h1504.load_rows(json.loads(h1467.read_text()))
    decoded = {}
    for signature in h1504.SIGNATURES:
        decoded[signature] = []
        for row in rows[signature]:
            opcode = sum(
                (
                    ((row[item["dword"]] >> item["bit"]) & 1)
                    ^ int(item["inverted"])
                )
                << item["logical_opcode_bit"]
                for item in mapping
            )
            if later.recognized_opcode(opcode) is None:
                raise RuntimeError(f"CVC5 model decoded unknown opcode {opcode:03X}")
            decoded[signature].append(f"{opcode:03X}")
    return {"mapping": mapping, "decoded_opcodes": decoded}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("cnf", type=Path)
    parser.add_argument("h1467", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--timeout-ms", type=int, default=300_000)
    arguments = parser.parse_args()
    if arguments.output.exists():
        raise SystemExit(f"refusing to overwrite {arguments.output}")

    solver = cvc5.Solver()
    solver.setLogic("QF_SAT")
    solver.setOption("produce-models", "true")
    solver.setOption("tlimit-per", str(arguments.timeout_ms))
    build_started = time.monotonic()
    variables, clause_count = load_dimacs(arguments.cnf, solver)
    build_seconds = time.monotonic() - build_started
    solve_started = time.monotonic()
    result = solver.checkSat()
    solve_seconds = time.monotonic() - solve_started
    status = "SAT" if result.isSat() else ("UNSAT" if result.isUnsat() else "UNKNOWN")

    report: dict[str, object] = {
        "query": "h1505_exact_dimacs_cvc5_crosscheck",
        "status": status,
        "unknown_explanation": result.getUnknownExplanation().name
        if result.isUnknown()
        else None,
        "solver": {
            "name": "CVC5 Boolean backend",
            "version": cvc5.__version__,
            "timeout_ms": arguments.timeout_ms,
            "cnf_construction_seconds": build_seconds,
            "solve_seconds": solve_seconds,
        },
        "cnf": {
            "variables": len(variables) - 1,
            "clauses": clause_count,
            "sha256": digest(arguments.cnf),
        },
        "dependencies": {"h1467_report_sha256": digest(arguments.h1467)},
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
        report["model"] = decode_and_validate(solver, variables, arguments.h1467)

    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    arguments.output.write_text(text)
    print(
        json.dumps(
            {
                "output": str(arguments.output),
                "report_sha256": hashlib.sha256(text.encode()).hexdigest(),
                "status": status,
                "build_seconds": build_seconds,
                "solve_seconds": solve_seconds,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
