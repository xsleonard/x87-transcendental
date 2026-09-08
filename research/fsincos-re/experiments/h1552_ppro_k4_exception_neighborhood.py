#!/usr/bin/env python3
"""Exact K=3 row-omission neighborhood around H1550's K=4 witness.

The census covers every three-row omission set sharing at least two rows with
H1550's independently replayed four-row exception set.  H1546's compiled exact
solver classifies all 208 remaining 35-row instances.  A SAT case, combined
with H1549's global K<=2 UNSAT theorem, proves a minimum of three.  An all-UNSAT
result excludes only this declared neighborhood and is not global K=3 UNSAT.
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
EXPECTED_H1549_SHA256 = (
    "598a4966757d34acde0f780754ba101fbc332388b88a0e0213bbd80605a829be"
)
EXPECTED_H1550_SHA256 = (
    "2cfe114c702701476062ae2a652a5406ac3f78b668aa4dac82a32ad39187589c"
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("h1467", type=Path)
    parser.add_argument("h1546_report", type=Path)
    parser.add_argument("h1549_report", type=Path)
    parser.add_argument("h1550_report", type=Path)
    parser.add_argument("binary", type=Path)
    parser.add_argument("artifact_directory", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--jobs", type=int, default=12)
    parser.add_argument("--timeout-seconds", type=float, default=300.0)
    arguments = parser.parse_args()
    if arguments.output.exists():
        raise SystemExit(f"refusing to overwrite {arguments.output}")
    if arguments.artifact_directory.exists():
        raise SystemExit(
            f"refusing to overwrite {arguments.artifact_directory}"
        )
    expected = (
        (arguments.h1467, h1543.EXPECTED_H1467_SHA256, "H1467"),
        (arguments.h1546_report, EXPECTED_H1546_SHA256, "H1546"),
        (arguments.h1549_report, EXPECTED_H1549_SHA256, "H1549"),
        (arguments.h1550_report, EXPECTED_H1550_SHA256, "H1550"),
    )
    for path, expected_hash, name in expected:
        if digest(path) != expected_hash:
            raise RuntimeError(f"{name} hash changed")

    h1546_report = json.loads(arguments.h1546_report.read_text())
    if digest(arguments.binary) != h1546_report["compiler"]["binary_sha256"]:
        raise RuntimeError("H1546 binary hash changed")
    h1549_report = json.loads(arguments.h1549_report.read_text())
    if h1549_report["counts"] != {"SAT": 0, "UNKNOWN": 0, "UNSAT": 703}:
        raise RuntimeError("H1549 global K<=2 lower bound changed")
    h1550_report = json.loads(arguments.h1550_report.read_text())
    replay = h1550_report["bounds"]["k4"]["independent_python_replay"]
    if replay["result"] != "pass":
        raise RuntimeError("H1550 K=4 replay changed")
    witness_rows = tuple(
        sorted(int(item["row_index"]) for item in replay["unrecognized_rows"])
    )
    if witness_rows != (2, 11, 19, 35):
        raise RuntimeError(f"H1550 K=4 exception set changed: {witness_rows}")

    source = json.loads(arguments.h1467.read_text())
    rows_by_signature = h1543.load_rows(source)
    allowed_tuple = h1543.recognized_values()
    allowed_set = set(allowed_tuple)
    full = tuple(
        (signature, group, row)
        for signature in h1543.SIGNATURES
        for group, row in enumerate(rows_by_signature[signature])
    )
    witness_set = frozenset(witness_rows)
    triples = tuple(
        triple
        for triple in itertools.combinations(range(len(full)), 3)
        if len(witness_set.intersection(triple)) >= 2
    )
    if len(triples) != 208:
        raise RuntimeError(f"expected 208 neighborhood triples, got {len(triples)}")

    arguments.artifact_directory.mkdir(parents=True)
    cases = []
    for triple in triples:
        dropped = tuple((full[index][0], full[index][1]) for index in triple)
        name = "drop_" + "__".join(
            f"{signature}_g{group:02d}" for signature, group in dropped
        )
        retained = tuple(
            item for index, item in enumerate(full) if index not in triple
        )
        retained_611 = tuple(row for sig, _, row in retained if sig == "611")
        retained_612 = tuple(row for sig, _, row in retained if sig == "612")
        path = arguments.artifact_directory / f"{name}.csp"
        path.write_text(
            h1546.instance_text(retained_611, retained_612, allowed_tuple)
        )
        cases.append((name, triple, dropped, retained_611 + retained_612, path))

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
            ): (name, triple, dropped, retained, path)
            for name, triple, dropped, retained, path in cases
        }
        for future in concurrent.futures.as_completed(future_to_case):
            name, triple, dropped, retained, path = future_to_case[future]
            result = future.result()
            if result["status"] == "SAT":
                result["independent_python_replay"] = h1546.replay_sat(
                    result, retained, allowed_set
                )
            completed[name] = {
                "dropped_row_indices": list(triple),
                "dropped": [
                    {"signature": signature, "group": group}
                    for signature, group in dropped
                ],
                "instance_sha256": digest(path),
                **result,
            }
            finished += 1
            if finished % 10 == 0 or result["status"] != "UNSAT":
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
    sat_cases = [name for name, result in ordered.items()
                 if result["status"] == "SAT"]
    if counts["UNKNOWN"]:
        classification = "bounded_neighborhood_has_unknown_cases"
        exact_minimum = None
    elif sat_cases:
        classification = "three_exception_mapping_found"
        exact_minimum = 3
    else:
        classification = "declared_k4_neighborhood_all_unsat"
        exact_minimum = None
    report = {
        "schema": "fsincos-h1552-ppro-k4-exception-neighborhood-v1",
        "query": "all_k3_omission_sets_intersecting_h1550_k4_set_twice",
        "status": "complete" if not counts["UNKNOWN"] else "bounded_unknown",
        "h1550_k4_row_indices": list(witness_rows),
        "minimum_intersection": 2,
        "case_count": len(cases),
        "counts": counts,
        "classification": classification,
        "exact_minimum_exception_count": exact_minimum,
        "sat_cases": sat_cases,
        "cases": ordered,
        "dependencies": {
            "h1467_report_sha256": digest(arguments.h1467),
            "h1546_report_sha256": digest(arguments.h1546_report),
            "h1549_report_sha256": digest(arguments.h1549_report),
            "h1550_report_sha256": digest(arguments.h1550_report),
            "h1546_binary_sha256": digest(arguments.binary),
            "script_sha256": digest(Path(__file__)),
        },
        "claim_boundary": (
            "If SAT, H1549 makes minimum=3 exact. If all UNSAT, this excludes "
            "only K=3 omission sets sharing at least two rows with H1550's "
            "K=4 witness; it is not global K=3 UNSAT or a physical decoder."
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
        "exact_minimum_exception_count": exact_minimum,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
