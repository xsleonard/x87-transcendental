#!/usr/bin/env python3
"""Cross-check H1518's terminal query with independent CVC5 BV backends.

The H1518 CEGIS candidate retained g5.P[5] in addition to H1517's 62
mandatory coordinates, but default lazy CVC5 and Z3 both timed out.  This
experiment executes the frozen portable SMT2 query under four distinct CVC5
bit-blast/SAT-backend configurations.  UNKNOWN remains UNKNOWN.

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
    import cvc5
except ImportError as error:
    raise SystemExit("cvc5 1.3.1 is required") from error


VARIANTS = (
    ("eager_cadical", "eager", "cadical"),
    ("eager_kissat", "eager", "kissat"),
    ("eager_cryptominisat", "eager", "cryptominisat"),
    ("lazy_kissat", "lazy", "kissat"),
)


def digest_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def run_variant(name: str, bitblast: str, sat_backend: str,
                query_text: str, timeout_ms: int):
    start = time.monotonic()
    try:
        solver = cvc5.Solver()
        solver.setOption("produce-models", "true")
        solver.setOption("tlimit-per", str(timeout_ms))
        solver.setOption("bitblast", bitblast)
        solver.setOption("bv-sat-solver", sat_backend)
        parser = cvc5.InputParser(solver)
        parser.setStringInput(
            cvc5.InputLanguage.SMT_LIB_2_6, query_text, name
        )
        symbols = parser.getSymbolManager()
        result_text = ""
        while not parser.done():
            command = parser.nextCommand()
            if command.isNull():
                break
            response = command.invoke(solver, symbols)
            if command.getCommandName() == "check-sat":
                result_text = str(response).strip()
        if not result_text:
            raise RuntimeError("parser executed no check-sat command")
        status = result_text.split(" ", 1)[0]
        result = {
            "variant": name,
            "bitblast": bitblast,
            "bv_sat_solver": sat_backend,
            "status": status,
            "response": result_text,
            "elapsed_ms": round((time.monotonic() - start) * 1000),
        }
        if status == "sat":
            result["state_model"] = {
                str(term): str(solver.getValue(term))
                for term in symbols.getDeclaredTerms()
                if str(term).startswith("projection_left_")
                or str(term).startswith("projection_right_")
            }
        return result
    except Exception as error:  # backend availability is configuration-specific
        return {
            "variant": name,
            "bitblast": bitblast,
            "bv_sat_solver": sat_backend,
            "status": "error",
            "error": f"{type(error).__name__}: {error}",
            "elapsed_ms": round((time.monotonic() - start) * 1000),
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("h1518", type=Path)
    parser.add_argument("query", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--timeout-ms", type=int, default=300_000)
    arguments = parser.parse_args()
    if arguments.output.exists():
        raise SystemExit(f"refusing to overwrite {arguments.output}")
    if cvc5.__version__ != "1.3.1":
        raise RuntimeError(f"unexpected CVC5 version {cvc5.__version__}")

    h1518 = json.loads(arguments.h1518.read_text())
    query_bytes = arguments.query.read_bytes()
    query_text = query_bytes.decode()
    if h1518["status"] != "STOPPING_UNKNOWN":
        raise RuntimeError("H1518 stopping status changed")
    if h1518["unresolved_candidate_optional"] != [
        {"bit": 5, "field": "g5.P"}
    ]:
        raise RuntimeError("H1518 unresolved candidate changed")
    if digest_bytes(query_bytes) != h1518["stopping_query"]["sha256"]:
        raise RuntimeError("H1518 query hash changed")
    if "(set-logic QF_BV)" not in query_text:
        raise RuntimeError("terminal query lacks explicit QF_BV logic")

    with ProcessPoolExecutor(max_workers=len(VARIANTS)) as executor:
        futures = [
            executor.submit(
                run_variant, name, bitblast, backend,
                query_text, arguments.timeout_ms
            )
            for name, bitblast, backend in VARIANTS
        ]
        results = [future.result() for future in futures]

    decided = [row["status"] for row in results if row["status"] in ("sat", "unsat")]
    if len(set(decided)) > 1:
        status = "SOLVER_DISAGREEMENT"
    elif decided:
        status = (
            "TERMINAL_QUERY_SAT" if decided[0] == "sat"
            else "TERMINAL_QUERY_UNSAT"
        )
    else:
        status = "ALL_BACKENDS_UNKNOWN_OR_UNAVAILABLE"
    report = {
        "experiment": "h1519_terminal_bv_backend_crosscheck",
        "status": status,
        "cvc5_version": cvc5.__version__,
        "timeout_ms_per_backend": arguments.timeout_ms,
        "query": {
            "bytes": len(query_bytes),
            "sha256": digest_bytes(query_bytes),
            "h1518_candidate": [{"field": "g5.P", "bit": 5}],
        },
        "variants": results,
        "interpretation": (
            "SAT rejects the one-coordinate H1518 candidate; UNSAT proves it "
            "sufficient and completes the CEGIS minimum; UNKNOWN and backend "
            "errors carry no semantic conclusion."
        ),
        "claim_boundary": (
            "This cross-checks one frozen abstract-state quotient query. It "
            "does not choose the physical Skylake orientation or validate a "
            "silicon selector."
        ),
        "hardware_execution": "none",
        "hardware_labels_opened": "none",
        "capture_manifest": "none",
        "emulator_change": "none",
        "paper_change": "none",
        "sha256": {"h1518": digest_bytes(arguments.h1518.read_bytes())},
    }
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(text)
    print(json.dumps({
        "output": str(arguments.output),
        "report_sha256": digest_bytes(text.encode()),
        "status": status,
        "variants": [
            {
                "variant": row["variant"],
                "status": row["status"],
                "elapsed_ms": row["elapsed_ms"],
            }
            for row in results
        ],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
