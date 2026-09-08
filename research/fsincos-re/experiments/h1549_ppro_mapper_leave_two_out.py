#!/usr/bin/env python3
"""Exact leave-two-rows-out census for the Pentium Pro mapper.

All C(38,2)=703 pairs of recovered rows are omitted from the full H1546
instance.  Every remaining 36-row problem is classified by the compiled exact
solver.  H1548 proves that no single omission suffices, so any SAT result here
would establish a minimum exception count of two; all UNSAT establishes a
lower bound of three.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import itertools
import json
from pathlib import Path

import h1543_ppro_hall_csp as h1543
import h1546_ppro_compiled_csp as h1546


EXPECTED_H1546_SHA256 = (
    "fab75758afd8551d2b4c0769f8b2bfd864c898b3679db3acacf432b7da2aa385"
)
EXPECTED_H1548_SHA256 = (
    "f2603ddfd5ec56e074d919069372c4d4a51b2e4595c3455b0b2bd526d017034c"
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("h1467", type=Path)
    parser.add_argument("h1546_report", type=Path)
    parser.add_argument("h1548_report", type=Path)
    parser.add_argument("binary", type=Path)
    parser.add_argument("artifact_directory", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--jobs", type=int, default=8)
    parser.add_argument("--timeout-seconds", type=float, default=300.0)
    arguments = parser.parse_args()
    if arguments.output.exists():
        raise SystemExit(f"refusing to overwrite {arguments.output}")
    if arguments.artifact_directory.exists():
        raise SystemExit(
            f"refusing to overwrite {arguments.artifact_directory}"
        )
    if digest(arguments.h1467) != h1543.EXPECTED_H1467_SHA256:
        raise RuntimeError("H1467 report hash changed")
    if digest(arguments.h1546_report) != EXPECTED_H1546_SHA256:
        raise RuntimeError("H1546 report hash changed")
    if digest(arguments.h1548_report) != EXPECTED_H1548_SHA256:
        raise RuntimeError("H1548 report hash changed")
    h1548_report = json.loads(arguments.h1548_report.read_text())
    if h1548_report["counts"] != {"SAT": 0, "UNKNOWN": 0, "UNSAT": 38}:
        raise RuntimeError("H1548 single-omission lower bound changed")
    h1546_report = json.loads(arguments.h1546_report.read_text())
    if digest(arguments.binary) != h1546_report["compiler"]["binary_sha256"]:
        raise RuntimeError("H1546 binary hash changed")

    source = json.loads(arguments.h1467.read_text())
    rows = h1543.load_rows(source)
    allowed_tuple = h1543.recognized_values()
    allowed_set = set(allowed_tuple)
    full = tuple(
        (signature, group, row)
        for signature in h1543.SIGNATURES
        for group, row in enumerate(rows[signature])
    )
    arguments.artifact_directory.mkdir(parents=True)
    cases = []
    for first, second in itertools.combinations(range(len(full)), 2):
        first_signature, first_group, _ = full[first]
        second_signature, second_group, _ = full[second]
        name = (
            f"drop_{first_signature}_g{first_group:02d}"
            f"__{second_signature}_g{second_group:02d}"
        )
        retained = tuple(
            item for index, item in enumerate(full)
            if index != first and index != second
        )
        retained_611 = tuple(row for sig, _, row in retained if sig == "611")
        retained_612 = tuple(row for sig, _, row in retained if sig == "612")
        path = arguments.artifact_directory / f"{name}.csp"
        path.write_text(
            h1546.instance_text(retained_611, retained_612, allowed_tuple)
        )
        cases.append((
            name,
            ((first_signature, first_group), (second_signature, second_group)),
            retained_611 + retained_612,
            path,
        ))
    if len(cases) != 703:
        raise RuntimeError(f"expected 703 row pairs, got {len(cases)}")

    completed = {}
    finished = 0
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=arguments.jobs
    ) as executor:
        future_to_case = {
            executor.submit(
                h1546.run_case,
                arguments.binary,
                path,
                arguments.timeout_seconds,
            ): (name, dropped, retained, path)
            for name, dropped, retained, path in cases
        }
        for future in concurrent.futures.as_completed(future_to_case):
            name, dropped, retained, path = future_to_case[future]
            result = future.result()
            if result["status"] == "SAT":
                result["independent_python_replay"] = h1546.replay_sat(
                    result, retained, allowed_set
                )
            completed[name] = {
                "dropped": [
                    {"signature": signature, "group": group}
                    for signature, group in dropped
                ],
                "instance_sha256": digest(path),
                **result,
            }
            finished += 1
            if finished % 25 == 0 or result["status"] != "UNSAT":
                print(json.dumps({
                    "finished": finished,
                    "total": len(cases),
                    "name": name,
                    "status": result["status"],
                    "elapsed_seconds": result["elapsed_seconds"],
                    "nodes": result["nodes"],
                }, sort_keys=True), flush=True)

    ordered = {name: completed[name] for name, *_ in cases}
    counts = {
        status: sum(result["status"] == status for result in ordered.values())
        for status in ("SAT", "UNSAT", "UNKNOWN")
    }
    if counts["UNKNOWN"]:
        classification = "incomplete_unknown_cases"
        minimum_omissions = None
    elif counts["SAT"]:
        classification = "two_row_omission_suffices"
        minimum_omissions = 2
    else:
        classification = "all_two_row_omissions_unsat"
        minimum_omissions = 3
    sat_pairs = [
        name for name, result in ordered.items() if result["status"] == "SAT"
    ]
    report = {
        "schema": "fsincos-h1549-ppro-mapper-leave-two-out-v1",
        "query": "omit_every_pair_of_recovered_rows_from_h1546_mapper",
        "status": "complete" if not counts["UNKNOWN"] else "bounded_unknown",
        "pair_count": len(cases),
        "counts": counts,
        "classification": classification,
        "minimum_omissions_required_if_model_retained": minimum_omissions,
        "sat_pairs": sat_pairs,
        "cases": ordered,
        "dependencies": {
            "h1467_report_sha256": digest(arguments.h1467),
            "h1546_report_sha256": digest(arguments.h1546_report),
            "h1548_report_sha256": digest(arguments.h1548_report),
            "h1546_binary_sha256": digest(arguments.binary),
            "script_sha256": digest(Path(__file__)),
        },
        "claim_boundary": (
            "The omission lower bound concerns only H1546's injective fixed-"
            "polarity direct-selection mapper under the current 459-value "
            "public-P6 recognized-opcode condition."
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
        "counts": counts,
        "classification": classification,
        "sat_pair_count": len(sat_pairs),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
