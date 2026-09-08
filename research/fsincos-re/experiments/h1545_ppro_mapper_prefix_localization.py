#!/usr/bin/env python3
"""Localize H1543's mapper contradiction to recovered row subsets.

The exact H1543 CSP is replayed on two positive controls and four joint-body
subsets.  Cases run in separate processes; concurrency affects wall time but
not SAT/UNSAT semantics.  The report is emitted only if every predeclared case
reaches its expected terminal result.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
from pathlib import Path

import h1543_ppro_hall_csp as h1543


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def solve_case(
    name: str,
    rows_611: tuple[tuple[int, ...], ...],
    rows_612: tuple[tuple[int, ...], ...],
    timeout_seconds: float,
) -> tuple[str, dict[str, object]]:
    result = h1543.solve(
        {"611": rows_611, "612": rows_612}, timeout_seconds
    )
    return name, result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("h1467", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--jobs", type=int, default=3)
    parser.add_argument("--terminal-timeout-seconds", type=float, default=900.0)
    arguments = parser.parse_args()
    if arguments.output.exists():
        raise SystemExit(f"refusing to overwrite {arguments.output}")
    if digest(arguments.h1467) != h1543.EXPECTED_H1467_SHA256:
        raise RuntimeError("H1467 report hash changed")
    if arguments.jobs < 1:
        raise ValueError("jobs must be positive")

    h1543.selftest()
    rows = h1543.load_rows(json.loads(arguments.h1467.read_text()))
    r611 = rows["611"]
    r612 = rows["612"]
    terminal = arguments.terminal_timeout_seconds
    specifications = (
        ("611_only", r611, (), 120.0, "SAT"),
        ("612_only", (), r612, 120.0, "SAT"),
        ("aligned_prefix_12", r611[:12], r612[:12], 120.0, "SAT"),
        ("aligned_prefix_18", r611[:18], r612[:18], terminal, "UNSAT"),
        ("drop_611_group_18", r611[:18], r612, terminal, "UNSAT"),
        ("drop_612_group_18", r611, r612[:18], terminal, "UNSAT"),
    )
    completed: dict[str, dict[str, object]] = {}
    with concurrent.futures.ProcessPoolExecutor(
        max_workers=arguments.jobs
    ) as executor:
        future_to_spec = {
            executor.submit(solve_case, name, left, right, timeout): (
                name, len(left), len(right), timeout, expected
            )
            for name, left, right, timeout, expected in specifications
        }
        for future in concurrent.futures.as_completed(future_to_spec):
            name, left_count, right_count, timeout, expected = (
                future_to_spec[future]
            )
            returned_name, result = future.result()
            if returned_name != name:
                raise RuntimeError("worker case identity changed")
            if result["status"] != expected:
                raise RuntimeError(
                    f"{name}: expected {expected}, got {result['status']}"
                )
            completed[name] = {
                "rows_611": left_count,
                "rows_612": right_count,
                "expected_status": expected,
                **result,
            }
            print(
                name,
                json.dumps({
                    "status": result["status"],
                    "elapsed_seconds": result["elapsed_seconds"],
                    "nodes": result["search"]["nodes"],
                    "maximum_depth": result["search"]["maximum_depth"],
                }, sort_keys=True),
                flush=True,
            )

    ordered_cases = {
        name: completed[name]
        for name, *_ in specifications
    }
    report = {
        "schema": "fsincos-h1545-ppro-mapper-prefix-localization-v1",
        "query": "localize_h1543_unsat_across_recovered_body_rows",
        "status": "complete",
        "cases": ordered_cases,
        "conclusion": {
            "each_body_alone": "SAT",
            "aligned_prefix_12": "SAT",
            "aligned_prefix_18": "UNSAT",
            "both_final_groups_jointly_necessary": False,
            "localization": (
                "cross-body incompatibility is already forced within aligned "
                "groups 0 through 17, but not within groups 0 through 11"
            ),
        },
        "dependencies": {
            "h1467_report_sha256": digest(arguments.h1467),
            "h1543_script_sha256": digest(Path(h1543.__file__)),
            "script_sha256": digest(Path(__file__)),
        },
        "claim_boundary": (
            "Row-subset results concern only H1543's injective fixed-polarity "
            "mapping into the current 459-value public-P6 opcode language."
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
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    arguments.output.write_text(text)
    print(json.dumps({
        "output": str(arguments.output),
        "report_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "status": report["status"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
