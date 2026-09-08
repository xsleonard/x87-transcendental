#!/usr/bin/env python3
"""Cross-check H1518 with available MiniSat and preprocessing variants.

H1519 established that this CVC5 build lacks Kissat and CryptoMiniSat support
and that eager CaDiCaL times out.  H1520 tests the remaining compiled MiniSat
backend in eager and lazy bit-blast modes, plus two materially different
CaDiCaL preprocessing configurations.  UNKNOWN remains UNKNOWN.

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
    ("eager_minisat", {
        "bitblast": "eager", "bv-sat-solver": "minisat",
    }),
    ("lazy_minisat", {
        "bitblast": "lazy", "bv-sat-solver": "minisat",
    }),
    ("lazy_cadical_bv_to_bool", {
        "bitblast": "lazy", "bv-sat-solver": "cadical",
        "bv-to-bool": "true",
    }),
    ("lazy_cadical_gauss", {
        "bitblast": "lazy", "bv-sat-solver": "cadical",
        "bv-gauss-elim": "true",
    }),
)


def sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def run_variant(name: str, options, query_text: str, timeout_ms: int):
    start = time.monotonic()
    try:
        solver = cvc5.Solver()
        solver.setOption("produce-models", "true")
        solver.setOption("tlimit-per", str(timeout_ms))
        for option, value in options.items():
            solver.setOption(option, value)
        parser = cvc5.InputParser(solver)
        parser.setStringInput(
            cvc5.InputLanguage.SMT_LIB_2_6, query_text, name
        )
        symbols = parser.getSymbolManager()
        response_text = ""
        while not parser.done():
            command = parser.nextCommand()
            if command.isNull():
                break
            response = command.invoke(solver, symbols)
            if command.getCommandName() == "check-sat":
                response_text = str(response).strip()
        if not response_text:
            raise RuntimeError("parser executed no check-sat command")
        status = response_text.split(" ", 1)[0]
        result = {
            "variant": name,
            "options": options,
            "status": status,
            "response": response_text,
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
    except Exception as error:
        return {
            "variant": name,
            "options": options,
            "status": "error",
            "error": f"{type(error).__name__}: {error}",
            "elapsed_ms": round((time.monotonic() - start) * 1000),
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("h1518", type=Path)
    parser.add_argument("h1519", type=Path)
    parser.add_argument("query", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--timeout-ms", type=int, default=180_000)
    arguments = parser.parse_args()
    if arguments.output.exists():
        raise SystemExit(f"refusing to overwrite {arguments.output}")
    if cvc5.__version__ != "1.3.1":
        raise RuntimeError(f"unexpected CVC5 version {cvc5.__version__}")

    h1518 = json.loads(arguments.h1518.read_text())
    h1519 = json.loads(arguments.h1519.read_text())
    query_bytes = arguments.query.read_bytes()
    query_text = query_bytes.decode()
    if h1518["status"] != "STOPPING_UNKNOWN" \
            or h1519["status"] != "ALL_BACKENDS_UNKNOWN_OR_UNAVAILABLE":
        raise RuntimeError("H1518/H1519 stopping status changed")
    if sha256(query_bytes) != h1518["stopping_query"]["sha256"]:
        raise RuntimeError("H1518 terminal query changed")

    with ProcessPoolExecutor(max_workers=len(VARIANTS)) as executor:
        futures = [
            executor.submit(
                run_variant, name, options, query_text, arguments.timeout_ms
            )
            for name, options in VARIANTS
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
        status = "ALL_BACKENDS_UNKNOWN_OR_ERROR"
    report = {
        "experiment": "h1520_terminal_minisat_crosscheck",
        "status": status,
        "cvc5_version": cvc5.__version__,
        "timeout_ms_per_backend": arguments.timeout_ms,
        "query": {
            "bytes": len(query_bytes),
            "sha256": sha256(query_bytes),
            "h1518_candidate": [{"field": "g5.P", "bit": 5}],
        },
        "variants": results,
        "interpretation": (
            "SAT rejects the one-coordinate H1518 candidate; UNSAT proves it "
            "sufficient and completes the CEGIS minimum; UNKNOWN and errors "
            "carry no semantic conclusion."
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
        "sha256": {
            "h1518": sha256(arguments.h1518.read_bytes()),
            "h1519": sha256(arguments.h1519.read_bytes()),
        },
    }
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(text)
    print(json.dumps({
        "output": str(arguments.output),
        "report_sha256": sha256(text.encode()),
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
