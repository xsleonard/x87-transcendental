#!/usr/bin/env python3
"""Independently replay H1552's K=3 mappings over all 38 physical rows."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import h1543_ppro_hall_csp as h1543


EXPECTED_H1549_SHA256 = (
    "598a4966757d34acde0f780754ba101fbc332388b88a0e0213bbd80605a829be"
)
EXPECTED_H1552_SHA256 = (
    "3da9b1017bc76d5f6474cc86bda6c852e20df5af3e8ba2ad387847a67b14637b"
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("h1467", type=Path)
    parser.add_argument("h1549", type=Path)
    parser.add_argument("h1552", type=Path)
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args()
    if arguments.output.exists():
        raise SystemExit(f"refusing to overwrite {arguments.output}")
    expected = (
        (arguments.h1467, h1543.EXPECTED_H1467_SHA256, "H1467"),
        (arguments.h1549, EXPECTED_H1549_SHA256, "H1549"),
        (arguments.h1552, EXPECTED_H1552_SHA256, "H1552"),
    )
    for path, expected_hash, name in expected:
        if digest(path) != expected_hash:
            raise RuntimeError(f"{name} hash changed")

    h1549_report = json.loads(arguments.h1549.read_text())
    if h1549_report["counts"] != {"SAT": 0, "UNKNOWN": 0, "UNSAT": 703}:
        raise RuntimeError("H1549 exact K<=2 lower bound changed")
    h1552_report = json.loads(arguments.h1552.read_text())
    if h1552_report["counts"] != {"SAT": 2, "UNKNOWN": 0, "UNSAT": 206}:
        raise RuntimeError("H1552 classification changed")

    source = json.loads(arguments.h1467.read_text())
    rows_by_signature = h1543.load_rows(source)
    rows = tuple(
        (signature, group, row)
        for signature in h1543.SIGNATURES
        for group, row in enumerate(rows_by_signature[signature])
    )
    channels = h1543.physical_channels()
    allowed = set(h1543.recognized_values())
    replays = {}
    for name in h1552_report["sat_cases"]:
        case = h1552_report["cases"][name]
        literals = tuple(int(value) for value in case["solution_literals"])
        if len(literals) != h1543.LOGICAL_BITS:
            raise RuntimeError(f"{name}: mapping width changed")
        selected_channels = tuple(literal // 2 for literal in literals)
        if len(set(selected_channels)) != h1543.LOGICAL_BITS:
            raise RuntimeError(f"{name}: mapping reuses a physical channel")

        decoded = []
        unrecognized = []
        retained_decoded = []
        dropped_indices = set(int(value) for value in case["dropped_row_indices"])
        for row_index, (signature, group, row) in enumerate(rows):
            opcode = 0
            for logical_bit, literal in enumerate(literals):
                dword, physical_bit = channels[literal // 2]
                value = ((row[dword] >> physical_bit) & 1) ^ (literal & 1)
                opcode |= value << logical_bit
            decoded.append(f"{opcode:03X}")
            if opcode not in allowed:
                unrecognized.append({
                    "row_index": row_index,
                    "signature": signature,
                    "group": group,
                    "opcode": f"{opcode:03X}",
                })
            else:
                retained_decoded.append(f"{opcode:03X}")

        unrecognized_indices = {item["row_index"] for item in unrecognized}
        if unrecognized_indices != dropped_indices:
            raise RuntimeError(
                f"{name}: full replay exceptions {sorted(unrecognized_indices)} "
                f"do not equal omissions {sorted(dropped_indices)}"
            )
        previous = case["independent_python_replay"]["decoded_opcodes"]
        if retained_decoded != previous:
            raise RuntimeError(f"{name}: retained-row replay changed")
        mapping = []
        for logical_bit, literal in enumerate(literals):
            dword, physical_bit = channels[literal // 2]
            mapping.append({
                "logical_opcode_bit": logical_bit,
                "literal": literal,
                "physical_channel_index": literal // 2,
                "dword": dword,
                "bit": physical_bit,
                "inverted": bool(literal & 1),
            })
        replays[name] = {
            "result": "pass",
            "mapping": mapping,
            "decoded_all_rows": decoded,
            "unrecognized_rows": unrecognized,
            "unrecognized_row_count": len(unrecognized),
            "all_selected_channels_distinct": True,
        }

    report = {
        "schema": "fsincos-h1553-replay-k3-exception-mappings-v1",
        "query": "full_38_row_replay_of_h1552_sat_mappings",
        "status": "complete",
        "replay_count": len(replays),
        "replays": replays,
        "exact_minimum_exception_count": 3,
        "proof": {
            "lower_bound": "H1549 exhaustively proves all 703 K=2 omissions UNSAT",
            "upper_bound": "H1552 supplies two mappings with exactly three full-replay exceptions",
        },
        "dependencies": {
            "h1467_report_sha256": digest(arguments.h1467),
            "h1549_report_sha256": digest(arguments.h1549),
            "h1552_report_sha256": digest(arguments.h1552),
            "script_sha256": digest(Path(__file__)),
        },
        "claim_boundary": (
            "The exact minimum of three applies only to the injective fixed-"
            "polarity direct-selection mapper into the current 459-value "
            "public-P6 opcode language. The mappings are feasibility witnesses, "
            "not recovered physical decoders."
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
        "replay_count": len(replays),
        "exact_minimum_exception_count": 3,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
