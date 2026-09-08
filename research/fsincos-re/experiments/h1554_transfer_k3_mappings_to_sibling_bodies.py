#!/usr/bin/env python3
"""Transfer H1553's exact K=3 feasibility mappings to held-out PPro bodies."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import h1543_ppro_hall_csp as h1543


EXPECTED_H1553_SHA256 = (
    "53f10035b4c579217cc1b15f83425a8a330463250255a46b7a3ec48d291c81c3"
)
TRAINING_SIGNATURES = ("611", "612")
HELD_OUT_SIGNATURES = ("617", "619")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_patch_rows(source: dict[str, object], signature: str) -> tuple[tuple[int, ...], ...]:
    recovery = source["patches"][signature]["recovery"]
    if recovery["status"] != "exact_continuous_physical_recovery":
        raise RuntimeError(f"0x{signature}: physical recovery status changed")
    groups = recovery["decrypted_body"]["physical_groups"]
    if len(groups) != h1543.DATA_GROUPS:
        raise RuntimeError(f"0x{signature}: physical group count changed")
    return tuple(
        tuple(int(word, 16) for word in group["physical_dwords"])
        for group in groups
    )


def decode_mapping(
    mapping: list[dict[str, object]],
    rows: tuple[tuple[int, ...], ...],
    allowed: set[int],
) -> dict[str, object]:
    decoded = []
    recognized = []
    for group, row in enumerate(rows):
        opcode = 0
        for item in mapping:
            value = ((row[item["dword"]] >> item["bit"]) & 1) ^ int(
                item["inverted"]
            )
            opcode |= value << item["logical_opcode_bit"]
        decoded.append(f"{opcode:03X}")
        if opcode in allowed:
            recognized.append(group)
    recognized_set = set(recognized)
    return {
        "decoded_opcodes": decoded,
        "recognized_count": len(recognized),
        "unrecognized_count": len(rows) - len(recognized),
        "recognized_groups": recognized,
        "unrecognized_groups": [
            group for group in range(len(rows)) if group not in recognized_set
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("h1467", type=Path)
    parser.add_argument("h1553", type=Path)
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args()
    if arguments.output.exists():
        raise SystemExit(f"refusing to overwrite {arguments.output}")
    if digest(arguments.h1467) != h1543.EXPECTED_H1467_SHA256:
        raise RuntimeError("H1467 hash changed")
    if digest(arguments.h1553) != EXPECTED_H1553_SHA256:
        raise RuntimeError("H1553 hash changed")

    source = json.loads(arguments.h1467.read_text())
    prior = json.loads(arguments.h1553.read_text())
    allowed = set(h1543.recognized_values())
    rows = {
        signature: load_patch_rows(source, signature)
        for signature in TRAINING_SIGNATURES + HELD_OUT_SIGNATURES
    }
    mappings = {}
    for name, replay in prior["replays"].items():
        mapping = replay["mapping"]
        if len({item["physical_channel_index"] for item in mapping}) != 12:
            raise RuntimeError(f"{name}: channel distinctness changed")
        patches = {
            signature: decode_mapping(mapping, rows[signature], allowed)
            for signature in TRAINING_SIGNATURES + HELD_OUT_SIGNATURES
        }
        training_decoded = (
            patches["611"]["decoded_opcodes"]
            + patches["612"]["decoded_opcodes"]
        )
        if training_decoded != replay["decoded_all_rows"]:
            raise RuntimeError(f"{name}: H1553 training replay changed")
        held_out_recognized = sum(
            patches[signature]["recognized_count"]
            for signature in HELD_OUT_SIGNATURES
        )
        mappings[name] = {
            "patches": patches,
            "training": {
                "rows": 38,
                "recognized_count": sum(
                    patches[signature]["recognized_count"]
                    for signature in TRAINING_SIGNATURES
                ),
                "unrecognized_count": sum(
                    patches[signature]["unrecognized_count"]
                    for signature in TRAINING_SIGNATURES
                ),
            },
            "held_out": {
                "rows": 38,
                "recognized_count": held_out_recognized,
                "unrecognized_count": 38 - held_out_recognized,
            },
        }

    report = {
        "schema": "fsincos-h1554-transfer-k3-mappings-to-sibling-bodies-v1",
        "query": "unchanged_h1553_mapping_transfer_to_617_619",
        "status": "complete",
        "training_signatures": list(TRAINING_SIGNATURES),
        "held_out_signatures": list(HELD_OUT_SIGNATURES),
        "public_recognized_opcode_count": len(allowed),
        "mappings": mappings,
        "dependencies": {
            "h1467_report_sha256": digest(arguments.h1467),
            "h1553_report_sha256": digest(arguments.h1553),
            "script_sha256": digest(Path(__file__)),
        },
        "claim_boundary": (
            "This is an unchanged-mapping transfer audit under the same current "
            "public-P6 recognized-opcode language. Poor transfer rejects treating "
            "an H1553 feasibility witness as a validated general decoder, but it "
            "cannot distinguish wrong wiring from an incomplete Pentium Pro "
            "opcode catalogue."
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
        "held_out_recognized_counts": {
            name: value["held_out"]["recognized_count"]
            for name, value in mappings.items()
        },
    }, sort_keys=True))


if __name__ == "__main__":
    main()
