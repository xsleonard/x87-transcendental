#!/usr/bin/env python3
"""Audit H1487 pair A/B against the existing 240k-row FCOS capture.

The dense Skylake capture predates the H1487 candidates.  This audit first
finds rows where the current incumbent and default-off R1382 builds produce
different architectural FCOS endpoints.  Only those rows can label the hidden
merge choice.  It then replays the exact H1486 pair functions on the internal
multiplier operands and checks whether any existing endpoint separator also
distinguishes pair A from pair B.

No x87 instruction or fresh hardware capture is executed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from h1210_stagea_residual_reframe import parse_dump, run
from h1400_p5_representation_audit import tree_variants
from h1474_score_r1382_lattice import parse_hardware_line
from h1479_r1475_topology_isomorphism import MODES
from h1486_surviving_propagate_class import EXPECTED_SIGNALS, candidate_values


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def configs():
    available = {
        name: config
        for name, _, config in tree_variants()
        if config.stage_width >= 131
    }
    order = sorted(EXPECTED_SIGNALS)
    result = [available[signal.split(".final.")[0]] for signal in order]
    if len(result) != 4:
        raise RuntimeError("H1486 four-layout class changed")
    return order, result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("incumbent", type=Path)
    parser.add_argument("r1382", type=Path)
    parser.add_argument("inputs", type=Path)
    parser.add_argument("capture_directory", type=Path)
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args()
    if arguments.output.exists():
        raise SystemExit(f"refusing to overwrite {arguments.output}")

    operands = [
        line.strip().lower()
        for line in arguments.inputs.read_text().splitlines()
        if line.strip()
    ]
    if len(operands) != 240_000 or len(set(operands)) != len(operands):
        raise RuntimeError("dense operand census changed")

    signal_order, candidate_configs = configs()
    rows = []
    counts = Counter()
    capture_hashes = {}
    for mode in MODES[:3]:
        capture_path = arguments.capture_directory / f"dense_fcos_{mode}_status.txt"
        capture_lines = capture_path.read_text().splitlines()
        if len(capture_lines) != len(operands):
            raise RuntimeError(f"{capture_path}: dense row count changed")
        capture_hashes[mode] = digest(capture_path)
        incumbent_values, _ = run(arguments.incumbent, mode, operands)
        r1382_values, _ = run(arguments.r1382, mode, operands)
        different = [
            index
            for index, (incumbent, candidate) in enumerate(
                zip(incumbent_values, r1382_values)
            )
            if incumbent != candidate
        ]
        counts[f"mode.{mode}.endpoint_separators"] = len(different)
        if not different:
            continue

        selected_operands = [operands[index] for index in different]
        _, stderr = run(arguments.incumbent, mode, selected_operands, dump=True)
        dumps = parse_dump(stderr, selected_operands)
        for index, dump in zip(different, dumps):
            hardware, status = parse_hardware_line(
                capture_lines[index], capture_path, index + 1
            )
            incumbent = incumbent_values[index]
            r1382 = r1382_values[index]
            if hardware == incumbent:
                endpoint = "incumbent"
            elif hardware == r1382:
                endpoint = "r1382"
            else:
                endpoint = "other"
            pattern = candidate_values(
                int(dump["tc_f4_sig"], 16),
                int(dump["tc_rf_sig"], 16),
                candidate_configs,
            )
            if pattern[0] != pattern[1] or pattern[2] != pattern[3]:
                raise RuntimeError("H1487 within-pair equivalence changed")
            pair_a = incumbent if pattern[0] == "1" else r1382
            pair_b = incumbent if pattern[2] == "1" else r1382
            row = {
                "index": index,
                "mode": mode,
                "operand": operands[index].replace(" ", ":"),
                "hardware": hardware,
                "hardware_status": status,
                "incumbent": incumbent,
                "r1382": r1382,
                "endpoint": endpoint,
                "candidate_pattern": pattern,
                "pair_discriminator": pattern[0] != pattern[2],
                "pair_a": pair_a,
                "pair_b": pair_b,
                "pair_a_exact": pair_a == hardware,
                "pair_b_exact": pair_b == hardware,
                "s4": dump.get("s4"),
                "theta": dump.get("theta"),
                "low3": dump.get("low3"),
                "tc_f4_sig": dump["tc_f4_sig"],
                "tc_rf_sig": dump["tc_rf_sig"],
            }
            rows.append(row)
            counts[f"endpoint.{endpoint}"] += 1
            counts[f"pattern.{pattern}"] += 1
            counts[f"pair_a.{'exact' if row['pair_a_exact'] else 'miss'}"] += 1
            counts[f"pair_b.{'exact' if row['pair_b_exact'] else 'miss'}"] += 1
            counts[
                f"pair_discriminator.{str(row['pair_discriminator']).lower()}"
            ] += 1

    discriminator_rows = [row for row in rows if row["pair_discriminator"]]
    if discriminator_rows:
        a_exact = all(row["pair_a_exact"] for row in rows)
        b_exact = all(row["pair_b_exact"] for row in rows)
        if a_exact and not b_exact:
            verdict = "EXISTING_DENSE_CAPTURE_FAVORS_PAIR_A"
        elif b_exact and not a_exact:
            verdict = "EXISTING_DENSE_CAPTURE_FAVORS_PAIR_B"
        else:
            verdict = "EXISTING_DENSE_CAPTURE_FALSIFIES_OR_FAILS_TO_CHOOSE_PAIRS"
    else:
        verdict = "NO_EXISTING_DENSE_PAIR_DISCRIMINATOR"

    report = {
        "experiment": "h1509_existing_dense_pair_audit",
        "status": verdict,
        "dense_operands": len(operands),
        "modes": list(MODES[:3]),
        "architectural_rows_scored": len(operands) * 3,
        "endpoint_separator_rows": len(rows),
        "pair_discriminator_rows": len(discriminator_rows),
        "counts": dict(sorted(counts.items())),
        "candidate_signal_order": signal_order,
        "rows": rows,
        "claim_boundary": (
            "complete pre-existing 240000-operand standalone-FCOS RN/RD/RU "
            "capture only; a pair choice requires an endpoint-visible row "
            "where the exact H1487 pair functions disagree"
        ),
        "sha256": {
            "incumbent": digest(arguments.incumbent),
            "r1382": digest(arguments.r1382),
            "inputs": digest(arguments.inputs),
            "captures": capture_hashes,
        },
        "execution": {
            "hardware": "none; cached capture read only",
            "x87_instructions": "none",
            "fresh_capture_labels_opened": "none",
            "private_capture_ledger": "not accessed",
            "h1488_state": "FROZEN_UNOPENED",
            "emulator_change": "none",
            "paper_change": "none",
        },
    }
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    arguments.output.write_text(text)
    print(
        json.dumps(
            {
                "output": str(arguments.output),
                "report_sha256": hashlib.sha256(text.encode()).hexdigest(),
                "status": verdict,
                "endpoint_separator_rows": len(rows),
                "pair_discriminator_rows": len(discriminator_rows),
                "pair_a_exact": counts["pair_a.exact"],
                "pair_b_exact": counts["pair_b.exact"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
