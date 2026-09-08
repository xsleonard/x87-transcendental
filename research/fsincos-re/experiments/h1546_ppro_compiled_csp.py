#!/usr/bin/env python3
"""Build, cross-check, and run the compiled H1504 mapper CSP.

The C engine intentionally omits H1543's Hall pruning.  Its full-corpus tree
must reproduce H1544's status and exact node counters before prefix results are
accepted.  SAT witnesses are replayed independently in this Python driver.
All generated instances and the binary are retained and hashed.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import subprocess
from pathlib import Path

import h1543_ppro_hall_csp as h1543


EXPECTED_H1544_SHA256 = (
    "73364d48cc394ed6be9da14cc1a758107865f49f8c6b3cbf45f08d3d45a9f378"
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def instance_text(
    rows_611: tuple[tuple[int, ...], ...],
    rows_612: tuple[tuple[int, ...], ...],
    allowed: tuple[int, ...],
) -> str:
    labeled = tuple(
        (f"611_{index:02d}", row) for index, row in enumerate(rows_611)
    ) + tuple(
        (f"612_{index:02d}", row) for index, row in enumerate(rows_612)
    )
    lines = [
        "FSINCOS_H1546_CSP_V1",
        f"{len(labeled)} {len(allowed)}",
    ]
    lines.extend(
        label + " " + " ".join(f"{word:08x}" for word in row)
        for label, row in labeled
    )
    lines.extend(f"{opcode:03x}" for opcode in allowed)
    return "\n".join(lines) + "\n"


def run_case(
    binary: Path, instance: Path, timeout_seconds: float
) -> dict[str, object]:
    process = subprocess.run(
        [str(binary), str(instance), str(timeout_seconds)],
        check=True,
        capture_output=True,
        text=True,
        timeout=timeout_seconds + 60.0,
    )
    result = json.loads(process.stdout)
    if process.stderr:
        raise RuntimeError(f"compiled solver wrote stderr: {process.stderr}")
    if result["status"] not in ("SAT", "UNSAT", "UNKNOWN"):
        raise RuntimeError(f"bad compiled status {result['status']!r}")
    return result


def replay_sat(
    result: dict[str, object],
    rows: tuple[tuple[int, ...], ...],
    allowed: set[int],
) -> dict[str, object]:
    literals = result.get("solution_literals")
    if not isinstance(literals, list) or len(literals) != h1543.LOGICAL_BITS:
        raise RuntimeError("SAT result has no complete literal assignment")
    channels = h1543.physical_channels()
    selected_channels = [literal // 2 for literal in literals]
    if len(set(selected_channels)) != h1543.LOGICAL_BITS:
        raise RuntimeError("SAT result reuses a physical channel")
    decoded = []
    for row in rows:
        opcode = 0
        for logical_bit, literal in enumerate(literals):
            channel = literal // 2
            polarity = literal & 1
            dword, physical_bit = channels[channel]
            value = ((row[dword] >> physical_bit) & 1) ^ polarity
            opcode |= value << logical_bit
        if opcode not in allowed:
            raise RuntimeError(f"SAT replay found illegal opcode {opcode:03x}")
        decoded.append(f"{opcode:03X}")
    return {
        "result": "pass",
        "distinct_channels": True,
        "decoded_opcodes": decoded,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("h1467", type=Path)
    parser.add_argument("h1544", type=Path)
    parser.add_argument("c_source", type=Path)
    parser.add_argument("artifact_directory", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--jobs", type=int, default=3)
    parser.add_argument("--timeout-seconds", type=float, default=300.0)
    arguments = parser.parse_args()
    if arguments.output.exists():
        raise SystemExit(f"refusing to overwrite {arguments.output}")
    if digest(arguments.h1467) != h1543.EXPECTED_H1467_SHA256:
        raise RuntimeError("H1467 report hash changed")
    if digest(arguments.h1544) != EXPECTED_H1544_SHA256:
        raise RuntimeError("H1544 report hash changed")
    if arguments.artifact_directory.exists():
        raise SystemExit(
            f"refusing to overwrite {arguments.artifact_directory}"
        )
    if arguments.jobs < 1:
        raise ValueError("jobs must be positive")

    source = json.loads(arguments.h1467.read_text())
    rows = h1543.load_rows(source)
    allowed_tuple = h1543.recognized_values()
    allowed_set = set(allowed_tuple)
    r611 = rows["611"]
    r612 = rows["612"]
    cases = [
        ("611_only", r611, ()),
        ("612_only", (), r612),
        ("aligned_prefix_12", r611[:12], r612[:12]),
        ("aligned_prefix_13", r611[:13], r612[:13]),
        ("aligned_prefix_14", r611[:14], r612[:14]),
        ("aligned_prefix_15", r611[:15], r612[:15]),
        ("aligned_prefix_16", r611[:16], r612[:16]),
        ("aligned_prefix_17", r611[:17], r612[:17]),
        ("aligned_prefix_18", r611[:18], r612[:18]),
        ("full_38", r611, r612),
    ]

    arguments.artifact_directory.mkdir(parents=True)
    binary = arguments.artifact_directory / "h1546_ppro_opcode_csp"
    compiler = subprocess.run(
        ["cc", "--version"], check=True, capture_output=True, text=True
    ).stdout.splitlines()[0]
    subprocess.run(
        [
            "cc", "-O3", "-std=c11", "-Wall", "-Wextra", "-Werror",
            str(arguments.c_source), "-o", str(binary),
        ],
        check=True,
    )

    case_paths = {}
    case_rows = {}
    for name, left, right in cases:
        path = arguments.artifact_directory / f"{name}.csp"
        path.write_text(instance_text(left, right, allowed_tuple))
        case_paths[name] = path
        case_rows[name] = left + right

    completed = {}
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=arguments.jobs
    ) as executor:
        future_to_name = {
            executor.submit(
                run_case, binary, case_paths[name], arguments.timeout_seconds
            ): name
            for name, _, _ in cases
        }
        for future in concurrent.futures.as_completed(future_to_name):
            name = future_to_name[future]
            result = future.result()
            if result["status"] == "SAT":
                result["independent_python_replay"] = replay_sat(
                    result, case_rows[name], allowed_set
                )
            completed[name] = result
            print(
                name,
                json.dumps({
                    "status": result["status"],
                    "elapsed_seconds": result["elapsed_seconds"],
                    "nodes": result["nodes"],
                    "maximum_depth": result["maximum_depth"],
                }, sort_keys=True),
                flush=True,
            )

    h1544 = json.loads(arguments.h1544.read_text())
    full = completed["full_38"]
    expected_full = {
        "status": h1544["status"],
        "nodes": h1544["search"]["nodes"],
        "dead_ends": h1544["search"]["dead_ends"],
        "domain_failures": h1544["search"]["domain_failures"],
        "maximum_depth": h1544["search"]["maximum_depth"],
    }
    actual_full = {key: full[key] for key in expected_full}
    if actual_full != expected_full:
        raise RuntimeError(
            f"compiled full replay differs: {actual_full} != {expected_full}"
        )
    required = {
        "611_only": "SAT",
        "612_only": "SAT",
        "aligned_prefix_12": "SAT",
        "aligned_prefix_18": "UNSAT",
        "full_38": "UNSAT",
    }
    for name, expected in required.items():
        if completed[name]["status"] != expected:
            raise RuntimeError(
                f"{name}: expected {expected}, got {completed[name]['status']}"
            )

    ordered_results = {
        name: {
            "rows": len(case_rows[name]),
            "instance_sha256": digest(case_paths[name]),
            **completed[name],
        }
        for name, _, _ in cases
    }
    report = {
        "schema": "fsincos-h1546-ppro-compiled-csp-v1",
        "query": "independent_compiled_replay_and_aligned_prefix_census",
        "status": "complete",
        "full_h1544_counter_replay": {
            "result": "exact_match",
            **actual_full,
        },
        "cases": ordered_results,
        "compiler": {
            "identity": compiler,
            "flags": ["-O3", "-std=c11", "-Wall", "-Wextra", "-Werror"],
            "binary_sha256": digest(binary),
        },
        "dependencies": {
            "h1467_report_sha256": digest(arguments.h1467),
            "h1544_report_sha256": digest(arguments.h1544),
            "c_source_sha256": digest(arguments.c_source),
            "script_sha256": digest(Path(__file__)),
        },
        "claim_boundary": (
            "The compiled engine decides only H1504's injective fixed-polarity "
            "direct-selection mapper under the current 459-value public-P6 "
            "recognized-opcode condition."
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
        "prefix_statuses": {
            name: completed[name]["status"]
            for name, _, _ in cases
            if name.startswith("aligned_prefix_")
        },
    }, sort_keys=True))


if __name__ == "__main__":
    main()
