#!/usr/bin/env python3
"""Cross-check the exact H1463 queries with Bitwuzla.

The queries are complete standalone QF_BV artifacts.  Each is executed in an
independent Bitwuzla process with a finite per-check time limit.  SAT, UNSAT,
and UNKNOWN are preserved literally; in particular, a timeout is never
reported as an unreachability result.  No x87 instruction is executed and no
emulator behavior is changed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def run_query(binary: Path, path: Path, timeout_ms: int) -> dict[str, Any]:
    content = path.read_text()
    if "(set-logic QF_BV)" not in content:
        raise AssertionError(f"query lacks explicit QF_BV logic: {path}")
    command = [
        str(binary), "-T", str(timeout_ms), "--print-model",
        "--bv-output-format", "16", str(path),
    ]
    start = time.monotonic()
    process = subprocess.run(
        command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        check=False,
    )
    elapsed_ms = round((time.monotonic() - start) * 1000)
    stdout = process.stdout.strip()
    stderr = process.stderr.strip()
    if process.returncode != 0:
        raise RuntimeError(
            f"Bitwuzla failed for {path}: rc={process.returncode} {stderr}"
        )
    first_line = stdout.splitlines()[0] if stdout else ""
    if first_line not in ("sat", "unsat", "unknown"):
        raise AssertionError(
            f"unrecognized Bitwuzla result for {path}: {first_line!r}"
        )
    return {
        "query": str(path),
        "query_bytes": path.stat().st_size,
        "query_sha256": sha256(path),
        "result": first_line.upper(),
        "elapsed_ms": elapsed_ms,
        "model_printed": first_line == "sat" and len(stdout.splitlines()) > 1,
        "stderr": stderr,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--binary", default=Path("/opt/homebrew/bin/bitwuzla"),
                        type=Path)
    parser.add_argument("--timeout-ms", default=60_000, type=int)
    parser.add_argument("query", nargs="+", type=Path)
    args = parser.parse_args()
    if args.timeout_ms <= 0:
        raise SystemExit("timeout must be positive")
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")
    if not args.binary.is_file():
        raise SystemExit(f"missing Bitwuzla binary {args.binary}")
    for path in args.query:
        if not path.is_file():
            raise SystemExit(f"missing query {path}")

    version = subprocess.run(
        [str(args.binary), "--version"], text=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, check=True,
    ).stdout.strip()
    with ThreadPoolExecutor(max_workers=len(args.query)) as executor:
        rows = list(executor.map(
            lambda path: run_query(args.binary, path, args.timeout_ms),
            args.query,
        ))
    report = {
        "experiment": "h1465_r1382_bitwuzla_crosscheck",
        "solver": f"Bitwuzla {version}",
        "solver_binary": str(args.binary),
        "solver_binary_sha256": sha256(args.binary.resolve()),
        "configuration": "default bitblast/abstraction/CaDiCaL",
        "timeout_ms_per_check": args.timeout_ms,
        "queries": rows,
        "all_unknown": all(row["result"] == "UNKNOWN" for row in rows),
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
