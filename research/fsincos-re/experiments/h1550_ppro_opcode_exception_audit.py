#!/usr/bin/env python3
"""Build and audit the H1550 bounded-opcode-exception CSP.

The compiled engine searches mappings and necessarily unrecognized rows in one
exact recursion.  K=0 must reproduce H1544's no-Hall counters.  H1548/H1549
provide the independent K<=2 UNSAT lower bound.  A fixed four-exception witness
is used only as preferred value order, then replayed independently in Python.
K=3 remains SAT, UNSAT, or UNKNOWN according to its bounded exact run.
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
EXPECTED_H1548_SHA256 = (
    "f2603ddfd5ec56e074d919069372c4d4a51b2e4595c3455b0b2bd526d017034c"
)
EXPECTED_H1549_SHA256 = (
    "598a4966757d34acde0f780754ba101fbc332388b88a0e0213bbd80605a829be"
)
PREFERRED_K4 = (495, 63, 315, 477, 285, 115, 135, 142, 224, 368, 156, 239)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_bound(
    binary: Path,
    instance: Path,
    timeout_seconds: float,
    maximum_exceptions: int,
    preferred: tuple[int, ...] | None = None,
) -> dict[str, object]:
    command = [
        str(binary), str(instance), str(timeout_seconds),
        str(maximum_exceptions),
    ]
    if preferred is not None:
        command.append(",".join(map(str, preferred)))
    process = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        timeout=timeout_seconds + 60.0,
    )
    if process.stderr:
        raise RuntimeError(f"exception solver wrote stderr: {process.stderr}")
    result = json.loads(process.stdout)
    if result["status"] not in ("SAT", "UNSAT", "UNKNOWN"):
        raise RuntimeError(f"bad exception status {result['status']!r}")
    return result


def replay_sat(
    result: dict[str, object],
    rows: tuple[tuple[str, int, tuple[int, ...]], ...],
) -> dict[str, object]:
    literals = result.get("solution_literals")
    if not isinstance(literals, list) or len(literals) != h1543.LOGICAL_BITS:
        raise RuntimeError("SAT result lacks a complete mapping")
    if len({literal // 2 for literal in literals}) != h1543.LOGICAL_BITS:
        raise RuntimeError("SAT result reuses a channel")
    ignored = int(str(result["ignored_rows_hex"]), 16)
    allowed = set(h1543.recognized_values())
    channels = h1543.physical_channels()
    decoded = []
    unrecognized = []
    for row_index, (signature, group, row) in enumerate(rows):
        opcode = 0
        for logical_bit, literal in enumerate(literals):
            dword, physical_bit = channels[literal // 2]
            value = ((row[dword] >> physical_bit) & 1) ^ (literal & 1)
            opcode |= value << logical_bit
        recognized = opcode in allowed
        if recognized == bool((ignored >> row_index) & 1):
            raise RuntimeError("ignored-row mask disagrees with opcode replay")
        decoded.append(f"{opcode:03X}")
        if not recognized:
            unrecognized.append({
                "row_index": row_index,
                "signature": signature,
                "group": group,
                "opcode": f"{opcode:03X}",
            })
    if len(unrecognized) != result["ignored_row_count"]:
        raise RuntimeError("ignored-row count disagrees with replay")
    if len(unrecognized) > result["maximum_exceptions"]:
        raise RuntimeError("SAT result exceeds its exception bound")
    return {
        "result": "pass",
        "distinct_channels": True,
        "decoded_opcodes": decoded,
        "unrecognized_rows": unrecognized,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("h1467", type=Path)
    parser.add_argument("h1544", type=Path)
    parser.add_argument("h1548", type=Path)
    parser.add_argument("h1549", type=Path)
    parser.add_argument("instance", type=Path)
    parser.add_argument("c_source", type=Path)
    parser.add_argument("artifact_directory", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--k3-timeout-seconds", type=float, default=300.0)
    arguments = parser.parse_args()
    if arguments.output.exists():
        raise SystemExit(f"refusing to overwrite {arguments.output}")
    if arguments.artifact_directory.exists():
        raise SystemExit(
            f"refusing to overwrite {arguments.artifact_directory}"
        )
    expected = (
        (arguments.h1467, h1543.EXPECTED_H1467_SHA256, "H1467"),
        (arguments.h1544, EXPECTED_H1544_SHA256, "H1544"),
        (arguments.h1548, EXPECTED_H1548_SHA256, "H1548"),
        (arguments.h1549, EXPECTED_H1549_SHA256, "H1549"),
    )
    for path, expected_hash, name in expected:
        if digest(path) != expected_hash:
            raise RuntimeError(f"{name} hash changed")
    h1548 = json.loads(arguments.h1548.read_text())
    h1549 = json.loads(arguments.h1549.read_text())
    if h1548["counts"] != {"SAT": 0, "UNKNOWN": 0, "UNSAT": 38}:
        raise RuntimeError("H1548 lower bound changed")
    if h1549["counts"] != {"SAT": 0, "UNKNOWN": 0, "UNSAT": 703}:
        raise RuntimeError("H1549 lower bound changed")

    source = json.loads(arguments.h1467.read_text())
    rows_by_signature = h1543.load_rows(source)
    rows = tuple(
        (signature, group, row)
        for signature in h1543.SIGNATURES
        for group, row in enumerate(rows_by_signature[signature])
    )
    arguments.artifact_directory.mkdir(parents=True)
    binary = arguments.artifact_directory / "h1550_ppro_opcode_exception_csp"
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

    jobs = {
        "k0": (300.0, 0, None),
        "k1": (300.0, 1, None),
        "k3": (arguments.k3_timeout_seconds, 3, PREFERRED_K4),
        "k4": (300.0, 4, PREFERRED_K4),
    }
    completed = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        future_to_name = {
            executor.submit(
                run_bound,
                binary,
                arguments.instance,
                timeout,
                bound,
                preferred,
            ): name
            for name, (timeout, bound, preferred) in jobs.items()
        }
        for future in concurrent.futures.as_completed(future_to_name):
            name = future_to_name[future]
            result = future.result()
            if result["status"] == "SAT":
                result["independent_python_replay"] = replay_sat(result, rows)
            completed[name] = result
            print(name, json.dumps({
                "status": result["status"],
                "elapsed_seconds": result["elapsed_seconds"],
                "nodes": result["nodes"],
            }, sort_keys=True), flush=True)

    h1544 = json.loads(arguments.h1544.read_text())
    exact_k0 = {
        "status": h1544["status"],
        "nodes": h1544["search"]["nodes"],
        "dead_ends": h1544["search"]["dead_ends"],
        "domain_failures": h1544["search"]["domain_failures"],
        "maximum_depth": h1544["search"]["maximum_depth"],
    }
    if {key: completed["k0"][key] for key in exact_k0} != exact_k0:
        raise RuntimeError("K=0 did not reproduce H1544 exactly")
    if completed["k1"]["status"] != "UNSAT":
        raise RuntimeError("K=1 did not independently reproduce UNSAT")
    if completed["k4"]["status"] != "SAT":
        raise RuntimeError("K=4 witness did not reproduce")
    if completed["k4"]["ignored_row_count"] != 4:
        raise RuntimeError("K=4 witness does not use exactly four exceptions")

    k3_status = completed["k3"]["status"]
    if k3_status == "SAT":
        minimum = 3
        bracket = [3, 3]
    elif k3_status == "UNSAT":
        minimum = 4
        bracket = [4, 4]
    else:
        minimum = None
        bracket = [3, 4]
    report = {
        "schema": "fsincos-h1550-ppro-opcode-exception-audit-v1",
        "query": "minimum_unrecognized_rows_for_bounded_direct_mapper",
        "status": "complete_with_k3_unknown" if minimum is None else "complete",
        "minimum_exception_count": minimum,
        "exact_minimum_bracket": bracket,
        "bounds": {name: completed[name] for name in ("k0", "k1", "k3", "k4")},
        "external_exact_lower_bound": {
            "k1": "H1548 all 38 single omissions UNSAT",
            "k2": "H1549 all 703 double omissions UNSAT",
        },
        "k0_h1544_counter_replay": {"result": "exact_match", **exact_k0},
        "compiler": {
            "identity": compiler,
            "flags": ["-O3", "-std=c11", "-Wall", "-Wextra", "-Werror"],
            "binary_sha256": digest(binary),
        },
        "dependencies": {
            "h1467_report_sha256": digest(arguments.h1467),
            "h1544_report_sha256": digest(arguments.h1544),
            "h1548_report_sha256": digest(arguments.h1548),
            "h1549_report_sha256": digest(arguments.h1549),
            "instance_sha256": digest(arguments.instance),
            "c_source_sha256": digest(arguments.c_source),
            "script_sha256": digest(Path(__file__)),
        },
        "claim_boundary": (
            "The exception bracket concerns only an injective fixed-polarity "
            "direct-selection mapper into the current 459-value public-P6 "
            "recognized-opcode language. The K=4 mapping is an upper-bound "
            "witness, not a physical decoder."
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
        "minimum_exception_count": minimum,
        "exact_minimum_bracket": bracket,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
