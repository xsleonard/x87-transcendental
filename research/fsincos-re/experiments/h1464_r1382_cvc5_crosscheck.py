#!/usr/bin/env python3
"""Independently cross-check the H1463 QF_BV residue decomposition.

Each input is a complete standalone SMT-LIB query produced by H1463.  A
separate CVC5 solver parses and executes each query under an identical finite
per-check time limit.  UNKNOWN is preserved as UNKNOWN; this program does not
reinterpret a timeout as an unreachability result.  It executes no x87
instruction and changes no emulator behavior.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from concurrent.futures import ProcessPoolExecutor
from itertools import repeat
from pathlib import Path
from typing import Any

try:
    import cvc5
except ImportError as error:  # pragma: no cover
    raise SystemExit("cvc5 1.3.1 is required") from error


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def run_query(path: Path, timeout_ms: int) -> dict[str, Any]:
    content = path.read_bytes()
    text = content.decode()
    if "(set-logic QF_BV)" not in text:
        raise AssertionError(f"query lacks explicit QF_BV logic: {path}")

    solver = cvc5.Solver()
    solver.setOption("tlimit-per", str(timeout_ms))
    parser = cvc5.InputParser(solver)
    parser.setStringInput(cvc5.InputLanguage.SMT_LIB_2_6, text, str(path))
    symbols = parser.getSymbolManager()
    replies: list[str] = []
    commands = 0
    start = time.monotonic()
    while True:
        command = parser.nextCommand()
        if command.isNull():
            break
        reply = command.invoke(solver, symbols)
        commands += 1
        if reply:
            replies.append(reply.strip())
    elapsed_ms = round((time.monotonic() - start) * 1000)
    result_lines = [
        line
        for reply in replies
        for line in reply.splitlines()
        if line == "sat" or line == "unsat" or line.startswith("unknown")
    ]
    if len(result_lines) != 1:
        raise AssertionError(
            f"expected one solver result for {path}, got {result_lines}"
        )
    result = result_lines[0]
    return {
        "query": str(path),
        "query_bytes": len(content),
        "query_sha256": sha256_bytes(content),
        "commands_executed": commands,
        "result": result.upper(),
        "elapsed_ms": elapsed_ms,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--timeout-ms", type=int, default=60_000)
    parser.add_argument("query", nargs="+", type=Path)
    args = parser.parse_args()
    if args.timeout_ms <= 0:
        raise SystemExit("timeout must be positive")
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")
    for path in args.query:
        if not path.is_file():
            raise SystemExit(f"missing query {path}")

    # CVC5's time limit is solver-local CPU time.  Separate processes prevent
    # the Python extension's global state from serializing otherwise
    # independent residue branches and making that bound misleading in wall
    # time.
    with ProcessPoolExecutor(max_workers=len(args.query)) as executor:
        rows = list(executor.map(
            run_query, args.query, repeat(args.timeout_ms)
        ))
    report = {
        "experiment": "h1464_r1382_cvc5_crosscheck",
        "solver": f"cvc5 {cvc5.__version__}",
        "timeout_ms_per_check": args.timeout_ms,
        "queries": rows,
        "all_unknown": all(row["result"].startswith("UNKNOWN")
                           for row in rows),
        "interpretation": (
            "UNKNOWN remains a stopping result, not an unreachability proof"
        ),
        "hardware_execution": "none",
        "emulator_change": "none",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as target:
        json.dump(report, target, indent=2, sort_keys=True)
        target.write("\n")
    print(json.dumps({
        "output": str(args.output),
        "queries": len(rows),
        "all_unknown": report["all_unknown"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
