#!/usr/bin/env python3
"""Localize H1546's prefix-16/prefix-17 mapper transition.

The common base is aligned groups 0 through 15 from both recovered bodies.
Each remaining row 16 through 18 is added alone, then every cross-body pair is
added.  The compiled no-Hall solver decides each case and Python independently
replays every SAT mapping.
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
    parser.add_argument("--jobs", type=int, default=3)
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
    r611 = rows["611"]
    r612 = rows["612"]
    allowed_tuple = h1543.recognized_values()
    allowed_set = set(allowed_tuple)
    base_611 = r611[:16]
    base_612 = r612[:16]
    cases: list[
        tuple[str, tuple[tuple[int, ...], ...], tuple[tuple[int, ...], ...]]
    ] = [("base_prefix_16", base_611, base_612)]
    for group in range(16, 19):
        cases.append((
            f"single_611_g{group}",
            base_611 + (r611[group],),
            base_612,
        ))
        cases.append((
            f"single_612_g{group}",
            base_611,
            base_612 + (r612[group],),
        ))
    for left_group in range(16, 19):
        for right_group in range(16, 19):
            cases.append((
                f"pair_611_g{left_group}_612_g{right_group}",
                base_611 + (r611[left_group],),
                base_612 + (r612[right_group],),
            ))

    arguments.artifact_directory.mkdir(parents=True)
    case_paths = {}
    case_rows = {}
    for name, left, right in cases:
        path = arguments.artifact_directory / f"{name}.csp"
        path.write_text(h1546.instance_text(left, right, allowed_tuple))
        case_paths[name] = path
        case_rows[name] = left + right

    completed = {}
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=arguments.jobs
    ) as executor:
        future_to_name = {
            executor.submit(
                h1546.run_case,
                arguments.binary,
                case_paths[name],
                arguments.timeout_seconds,
            ): name
            for name, _, _ in cases
        }
        for future in concurrent.futures.as_completed(future_to_name):
            name = future_to_name[future]
            result = future.result()
            if result["status"] == "SAT":
                result["independent_python_replay"] = h1546.replay_sat(
                    result, case_rows[name], allowed_set
                )
            completed[name] = result
            print(
                name,
                json.dumps({
                    "status": result["status"],
                    "elapsed_seconds": result["elapsed_seconds"],
                    "nodes": result["nodes"],
                }, sort_keys=True),
                flush=True,
            )

    if completed["base_prefix_16"]["status"] != "SAT":
        raise RuntimeError("base prefix-16 control did not reproduce SAT")
    if completed["pair_611_g16_612_g16"]["status"] != "UNSAT":
        raise RuntimeError("aligned group-16 pair did not reproduce UNSAT")
    ordered = {
        name: {
            "rows": len(case_rows[name]),
            "instance_sha256": digest(case_paths[name]),
            **completed[name],
        }
        for name, _, _ in cases
    }
    singles = {
        name: completed[name]["status"]
        for name, _, _ in cases
        if name.startswith("single_")
    }
    pairs = {
        name: completed[name]["status"]
        for name, _, _ in cases
        if name.startswith("pair_")
    }
    report = {
        "schema": "fsincos-h1547-ppro-mapper-tail-pair-localization-v1",
        "query": "classify_tail_rows_relative_to_aligned_prefix_16",
        "status": "complete",
        "base": "aligned groups 0 through 15 from both bodies",
        "single_row_statuses": singles,
        "cross_body_pair_statuses": pairs,
        "cases": ordered,
        "dependencies": {
            "h1467_report_sha256": digest(arguments.h1467),
            "h1546_report_sha256": digest(arguments.h1546_report),
            "h1546_binary_sha256": digest(arguments.binary),
            "script_sha256": digest(Path(__file__)),
        },
        "claim_boundary": (
            "Tail-row classifications concern only H1546's injective fixed-"
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
        "single_row_statuses": singles,
        "cross_body_pair_statuses": pairs,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
