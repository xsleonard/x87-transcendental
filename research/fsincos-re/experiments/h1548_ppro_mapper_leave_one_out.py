#!/usr/bin/env python3
"""Exact leave-one-row-out census for the rejected Pentium Pro mapper.

Each of the 38 recovered rows is omitted once while all other rows remain.
The H1546 compiled no-Hall solver classifies every resulting 37-row instance.
If all are UNSAT, no single unsupported/padding row can explain the full mapper
failure under the bounded public-opcode model.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
from pathlib import Path

import h1543_ppro_hall_csp as h1543
import h1546_ppro_compiled_csp as h1546


EXPECTED_H1546_SHA256 = (
    "fab75758afd8551d2b4c0769f8b2bfd864c898b3679db3acacf432b7da2aa385"
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("h1467", type=Path)
    parser.add_argument("h1546_report", type=Path)
    parser.add_argument("binary", type=Path)
    parser.add_argument("artifact_directory", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--jobs", type=int, default=4)
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
    for dropped_index, (signature, group, _) in enumerate(full):
        name = f"drop_{signature}_g{group:02d}"
        retained = tuple(
            item for index, item in enumerate(full) if index != dropped_index
        )
        retained_611 = tuple(row for sig, _, row in retained if sig == "611")
        retained_612 = tuple(row for sig, _, row in retained if sig == "612")
        path = arguments.artifact_directory / f"{name}.csp"
        path.write_text(
            h1546.instance_text(retained_611, retained_612, allowed_tuple)
        )
        cases.append((name, signature, group, retained_611 + retained_612, path))

    completed = {}
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=arguments.jobs
    ) as executor:
        future_to_case = {
            executor.submit(
                h1546.run_case,
                arguments.binary,
                path,
                arguments.timeout_seconds,
            ): (name, signature, group, retained, path)
            for name, signature, group, retained, path in cases
        }
        for future in concurrent.futures.as_completed(future_to_case):
            name, signature, group, retained, path = future_to_case[future]
            result = future.result()
            if result["status"] == "SAT":
                result["independent_python_replay"] = h1546.replay_sat(
                    result, retained, allowed_set
                )
            completed[name] = {
                "dropped_signature": signature,
                "dropped_group": group,
                "instance_sha256": digest(path),
                **result,
            }
            print(
                name,
                json.dumps({
                    "status": result["status"],
                    "elapsed_seconds": result["elapsed_seconds"],
                    "nodes": result["nodes"],
                }, sort_keys=True),
                flush=True,
            )

    ordered = {name: completed[name] for name, *_ in cases}
    counts = {
        status: sum(result["status"] == status for result in ordered.values())
        for status in ("SAT", "UNSAT", "UNKNOWN")
    }
    if counts["UNKNOWN"]:
        classification = "incomplete_unknown_cases"
        minimum_omissions = None
    elif counts["SAT"]:
        classification = "one_row_omission_suffices"
        minimum_omissions = 1
    else:
        classification = "all_single_row_omissions_unsat"
        minimum_omissions = 2
    report = {
        "schema": "fsincos-h1548-ppro-mapper-leave-one-out-v1",
        "query": "omit_each_recovered_row_once_from_h1546_mapper",
        "status": "complete" if not counts["UNKNOWN"] else "bounded_unknown",
        "counts": counts,
        "classification": classification,
        "minimum_omissions_required_if_model_retained": minimum_omissions,
        "cases": ordered,
        "dependencies": {
            "h1467_report_sha256": digest(arguments.h1467),
            "h1546_report_sha256": digest(arguments.h1546_report),
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
    }, sort_keys=True))


if __name__ == "__main__":
    main()
