#!/usr/bin/env python3
"""Bit-blast H1521's exact 63-coordinate candidate to immutable CNF.

The H1521 candidate remains UNKNOWN in QF_BV.  H1522 applies Z3's exact
simplify/solve-eqs/bit-blast/Tseitin pipeline once, preserves the resulting
DIMACS instance, and solves the pure clauses with Z3 SAT plus the compiled
CVC5 CaDiCaL and MiniSat Boolean backends.  A Z3 SAT model is converted back
through the tactic model converter and replayed on the original bit-vector
assertion before it is accepted.

No x87 instruction or hardware capture is executed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from concurrent.futures import ProcessPoolExecutor
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
from h1516_minimal_ordered_quartet_state import EXPECTED_A, EXPECTED_B
from h1521_width_reduced_valid_projection import (
    CANDIDATE,
    build_query,
    key,
    z3_counterexample_edge,
)


def sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def parse_dimacs(text: str, solver: cvc5.Solver):
    variables = None
    clause_count = None
    asserted = 0
    names = {}
    for line in text.splitlines():
        if not line:
            continue
        if line.startswith("c "):
            parts = line.split(maxsplit=2)
            if len(parts) == 3 and parts[1].isdigit():
                names[int(parts[1])] = parts[2]
            continue
        if line.startswith("p "):
            _, kind, variable_text, clause_text = line.split()
            if kind != "cnf" or variables is not None:
                raise RuntimeError("invalid DIMACS header")
            variables = [None] + [
                solver.mkConst(solver.getBooleanSort(), f"v{index}")
                for index in range(1, int(variable_text) + 1)
            ]
            clause_count = int(clause_text)
            continue
        if variables is None:
            raise RuntimeError("DIMACS clause precedes header")
        values = [int(value) for value in line.split()]
        if not values or values[-1] != 0:
            raise RuntimeError("unterminated DIMACS clause")
        literals = [
            variables[value] if value > 0 else solver.mkTerm(
                cvc5.Kind.NOT, variables[-value]
            )
            for value in values[:-1]
        ]
        if not literals:
            clause = solver.mkBoolean(False)
        elif len(literals) == 1:
            clause = literals[0]
        else:
            clause = solver.mkTerm(cvc5.Kind.OR, *literals)
        solver.assertFormula(clause)
        asserted += 1
    if variables is None or asserted != clause_count:
        raise RuntimeError("DIMACS clause count mismatch")
    return variables, names, asserted


def solve_cvc5(name: str, backend: str, cnf_text: str, timeout_ms: int):
    start = time.monotonic()
    solver = cvc5.Solver()
    solver.setLogic("QF_SAT")
    solver.setOption("produce-models", "true")
    solver.setOption("tlimit-per", str(timeout_ms))
    solver.setOption("sat-solver", backend)
    variables, names, clauses = parse_dimacs(cnf_text, solver)
    result = solver.checkSat()
    status = (
        "sat" if result.isSat() else
        "unsat" if result.isUnsat() else "unknown"
    )
    record = {
        "solver": f"cvc5 QF_SAT {backend}",
        "status": status,
        "elapsed_ms": round((time.monotonic() - start) * 1000),
        "clauses": clauses,
    }
    if result.isUnknown():
        record["reason_unknown"] = result.getUnknownExplanation().name
    elif result.isSat():
        record["named_model"] = {
            names[index]: solver.getValue(variables[index]).getBooleanValue()
            for index in sorted(names)
            if names[index].startswith("candidate_")
        }
    return record


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("h1517", type=Path)
    parser.add_argument("h1521", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--timeout-ms", type=int, default=300_000)
    arguments = parser.parse_args()
    if arguments.output.exists():
        raise SystemExit(f"refusing to overwrite {arguments.output}")
    cnf_path = arguments.output.with_name(arguments.output.stem + ".cnf")
    if cnf_path.exists():
        raise SystemExit(f"refusing to overwrite {cnf_path}")
    if z3.get_version_string() != "4.15.3" or cvc5.__version__ != "1.3.1":
        raise RuntimeError("validated solver versions changed")

    h1517 = json.loads(arguments.h1517.read_text())
    h1521 = json.loads(arguments.h1521.read_text())
    if h1517["status"] != "EXACT_EXTENSION_SUPPORT_WITH_REACHABILITY_GAP" \
            or h1521["status"] != "STOPPING_UNKNOWN":
        raise RuntimeError("H1517/H1521 boundary changed")
    extension = {key(row) for row in h1517["canonical_extension_support"]}
    mandatory = {key(row) for row in h1517["reachable_state_support"]}
    retained = mandatory | {CANDIDATE}
    optional = tuple(sorted(extension - mandatory))

    layouts = {name: config for name, _, config in tree_variants()}
    graph = build_query(
        "candidate", retained, extension,
        layouts[EXPECTED_A], layouts[EXPECTED_B]
    )
    goal = z3.Goal()
    goal.add(graph["assertion"])
    pipeline = z3.Then(
        "simplify", "propagate-values", "solve-eqs", "bit-blast",
        "tseitin-cnf"
    )
    started = time.monotonic()
    transformed = pipeline(goal)
    transform_ms = round((time.monotonic() - started) * 1000)
    if len(transformed) != 1:
        raise RuntimeError(f"bit-blast produced {len(transformed)} subgoals")
    clauses = transformed[0]
    cnf_text = clauses.dimacs()
    cnf_path.write_text(cnf_text)

    sat_solver = z3.Tactic("sat").solver()
    sat_solver.set(timeout=arguments.timeout_ms)
    sat_solver.add(*clauses)
    started = time.monotonic()
    z3_status = sat_solver.check()
    z3_ms = round((time.monotonic() - started) * 1000)
    z3_result = {
        "solver": f"z3 {z3.get_version_string()} propositional SAT",
        "status": str(z3_status),
        "elapsed_ms": z3_ms,
    }
    candidate_edge = None
    if z3_status == z3.unknown:
        z3_result["reason_unknown"] = sat_solver.reason_unknown()
    elif z3_status == z3.sat:
        original_model = clauses.convert_model(sat_solver.model())
        if not z3.is_true(original_model.eval(
                graph["assertion"], model_completion=True)):
            raise RuntimeError("converted SAT model failed original assertion")
        candidate_edge = z3_counterexample_edge(
            graph,
            {"status": "sat", "model": original_model},
            optional,
        )
        if not candidate_edge:
            raise RuntimeError("converted SAT model has empty optional edge")
        z3_result["converted_model_replay"] = "exact"
        z3_result["counterexample_edge"] = candidate_edge

    cvc5_results = []
    if z3_status == z3.unknown:
        with ProcessPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(
                    solve_cvc5, f"qf_sat_{backend}", backend,
                    cnf_text, arguments.timeout_ms
                )
                for backend in ("cadical", "minisat")
            ]
            cvc5_results = [future.result() for future in futures]

    statuses = [z3_result["status"]] + [
        result["status"] for result in cvc5_results
    ]
    decided = [status for status in statuses if status in ("sat", "unsat")]
    if len(set(decided)) > 1:
        status = "SOLVER_DISAGREEMENT"
    elif decided and decided[0] == "sat":
        status = "CANDIDATE_REFUTED"
    elif decided and decided[0] == "unsat":
        status = "EXACT_63_COORDINATE_MINIMUM"
    else:
        status = "STOPPING_UNKNOWN"
    report = {
        "experiment": "h1522_exact_cnf_projection",
        "status": status,
        "z3_version": z3.get_version_string(),
        "cvc5_version": cvc5.__version__,
        "candidate": {"field": CANDIDATE[0], "bit": CANDIDATE[1]},
        "pipeline": [
            "simplify", "propagate-values", "solve-eqs", "bit-blast",
            "tseitin-cnf",
        ],
        "transformation_ms": transform_ms,
        "cnf": {
            "artifact": cnf_path.name,
            "bytes": len(cnf_text.encode()),
            "sha256": sha256(cnf_text.encode()),
            "clauses": len(clauses),
        },
        "z3_result": z3_result,
        "cvc5_results": cvc5_results,
        **({"candidate_counterexample_edge": candidate_edge}
           if candidate_edge is not None else {}),
        "interpretation": (
            "SAT refutes H1518's g5.P[5] candidate; UNSAT proves the exact "
            "63-coordinate minimum by composition with H1518's hitting-set "
            "lower bound. UNKNOWN carries no semantic conclusion."
        ),
        "claim_boundary": (
            "This decides only the abstract H1518 projection candidate. It "
            "does not choose the physical Skylake orientation or validate a "
            "silicon selector."
        ),
        "hardware_execution": "none",
        "hardware_labels_opened": "none",
        "capture_manifest": "none",
        "emulator_change": "none",
        "paper_change": "none",
        "sha256": {
            "h1517": sha256(arguments.h1517.read_bytes()),
            "h1521": sha256(arguments.h1521.read_bytes()),
        },
    }
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(text)
    print(json.dumps({
        "output": str(arguments.output),
        "report_sha256": sha256(text.encode()),
        "status": status,
        "cnf_bytes": len(cnf_text.encode()),
        "cnf_clauses": len(clauses),
        "z3": z3_result["status"],
        "cvc5": [result["status"] for result in cvc5_results],
        **({"candidate_counterexample_edge": candidate_edge}
           if candidate_edge is not None else {}),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
