#!/usr/bin/env python3
"""Audit H1487 pair A/B against pre-existing targeted FCOS captures.

H1509 found no endpoint separator in the 240,000-operand dense capture.  This
follow-up covers the older targeted adversarial suites whose inputs remain
exactly aligned with their cached Skylake standalone-FCOS RN/RD/RU outputs.
Only rows where the incumbent and default-off R1382 builds differ can reveal
the hidden merge choice.  On those rows, replay the exact H1486 pair functions
and ask whether an already-opened hardware result chooses pair A or pair B.

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


SUITES = (
    (
        "h363",
        "capture-kit/inputs/constraint_fcos_terminal_neighbors_h363.txt",
        "capture-kit-captures/skylake-fcos-h363",
        229_404,
    ),
    (
        "h372",
        "capture-kit/inputs/constraint_fcos_scaled_tail_h372.txt",
        "capture-kit-captures/skylake-fcos-h372",
        10_684,
    ),
    (
        "h380",
        "capture-kit/inputs/constraint_fcos_payload_h380.txt",
        "capture-kit-captures/skylake-fcos-h380",
        13_866,
    ),
    (
        "h384",
        "capture-kit/inputs/constraint_fcos_payload_h384.txt",
        "capture-kit-captures/skylake-fcos-h384",
        27_074,
    ),
    (
        "h388",
        "capture-kit/inputs/constraint_fcos_tail_gate_h388.txt",
        "capture-kit-captures/skylake-fcos-h388",
        16_516,
    ),
    (
        "h389",
        "capture-kit/inputs/constraint_fcos_tail_gate_h389.txt",
        "capture-kit-captures/skylake-fcos-h389",
        16_586,
    ),
    (
        "h391",
        "capture-kit/inputs/constraint_fcos_csa_gate_h391.txt",
        "capture-kit-captures/skylake-fcos-h391",
        16_418,
    ),
    (
        "h392",
        "capture-kit/inputs/constraint_fcos_csa_bit_h392.txt",
        "capture-kit-captures/skylake-fcos-h392",
        16_552,
    ),
    (
        "h393",
        "capture-kit/inputs/constraint_fcos_square_tail_h393.txt",
        "capture-kit-captures/skylake-fcos-h393",
        16_486,
    ),
    (
        "h394",
        "capture-kit/inputs/constraint_fcos_square_bit_h394.txt",
        "capture-kit-captures/skylake-fcos-h394",
        16_554,
    ),
    (
        "h395",
        "capture-kit/inputs/constraint_fcos_d7_lane_h395.txt",
        "capture-kit-captures/skylake-fcos-h395",
        16_418,
    ),
    (
        "h397",
        "capture-kit/inputs/constraint_fcos_d7_lane_h397.txt",
        "capture-kit-captures/skylake-fcos-h397",
        16_656,
    ),
    (
        "h285",
        "capture-kit/inputs/constraint_trig_sine_bias_h285.txt",
        "capture-kit-captures/skylake-trig-h285",
        192,
    ),
    (
        "h292",
        "capture-kit/inputs/constraint_trig_sine_coordinates_h292.txt",
        "capture-kit-captures/skylake-trig-h292",
        256,
    ),
    (
        "h301",
        "capture-kit/inputs/constraint_trig_sine_fraction_h301.txt",
        "capture-kit-captures/skylake-trig-h301",
        32,
    ),
    (
        "h307",
        "capture-kit/inputs/constraint_trig_narrow_sine_fraction_h307.txt",
        "capture-kit-captures/skylake-trig-h307",
        64,
    ),
    (
        "h314",
        "capture-kit/inputs/constraint_trig_narrow_sine_fraction2_h314.txt",
        "capture-kit-captures/skylake-trig-h314",
        24,
    ),
    (
        "h320",
        "capture-kit/inputs/constraint_trig_narrow_sine_fraction3_h320.txt",
        "capture-kit-captures/skylake-trig-h320",
        24,
    ),
    (
        "h347",
        "capture-kit/inputs/constraint_round49_residual_neighbors_h347.txt",
        "capture-kit-captures/skylake-trig-h347",
        197_044,
    ),
)


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
    parser.add_argument("repository", type=Path)
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args()
    if arguments.output.exists():
        raise SystemExit(f"refusing to overwrite {arguments.output}")

    signal_order, candidate_configs = configs()
    rows = []
    counts = Counter()
    suite_reports = []
    input_rows = 0
    capture_hashes = {}
    input_hashes = {}

    for tag, relative_input, relative_capture, expected_rows in SUITES:
        input_path = arguments.repository / relative_input
        capture_directory = arguments.repository / relative_capture
        operands = [
            line.strip().lower()
            for line in input_path.read_text().splitlines()
            if line.strip()
        ]
        if len(operands) != expected_rows:
            raise RuntimeError(
                f"{tag}: input count {len(operands)} != frozen {expected_rows}"
            )
        input_rows += len(operands)
        input_hashes[tag] = digest(input_path)
        suite_counts = Counter()
        suite_rows = []
        capture_hashes[tag] = {}

        for mode in MODES:
            capture_path = capture_directory / f"fcos_{mode}_status.txt"
            capture_lines = capture_path.read_text().splitlines()
            if len(capture_lines) != expected_rows:
                raise RuntimeError(
                    f"{tag}/{mode}: capture count {len(capture_lines)} "
                    f"!= frozen {expected_rows}"
                )
            capture_hashes[tag][mode] = digest(capture_path)
            incumbent_values, _ = run(arguments.incumbent, mode, operands)
            r1382_values, _ = run(arguments.r1382, mode, operands)
            different = [
                index
                for index, (incumbent, candidate) in enumerate(
                    zip(incumbent_values, r1382_values)
                )
                if incumbent != candidate
            ]
            suite_counts[f"mode.{mode}.endpoint_separators"] = len(different)
            counts[f"mode.{mode}.endpoint_separators"] += len(different)
            if not different:
                continue

            selected_operands = [operands[index] for index in different]
            _, stderr = run(
                arguments.incumbent, mode, selected_operands, dump=True
            )
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
                    "suite": tag,
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
                suite_rows.append(row)
                for target in (counts, suite_counts):
                    target[f"endpoint.{endpoint}"] += 1
                    target[f"pattern.{pattern}"] += 1
                    target[
                        f"pair_a.{'exact' if row['pair_a_exact'] else 'miss'}"
                    ] += 1
                    target[
                        f"pair_b.{'exact' if row['pair_b_exact'] else 'miss'}"
                    ] += 1
                    target[
                        "pair_discriminator."
                        + str(row["pair_discriminator"]).lower()
                    ] += 1

        suite_reports.append({
            "suite": tag,
            "input": relative_input,
            "capture_directory": relative_capture,
            "operands": expected_rows,
            "architectural_rows_scored": expected_rows * len(MODES),
            "endpoint_separator_rows": len(suite_rows),
            "pair_discriminator_rows": sum(
                row["pair_discriminator"] for row in suite_rows
            ),
            "counts": dict(sorted(suite_counts.items())),
        })

    discriminator_rows = [row for row in rows if row["pair_discriminator"]]
    if discriminator_rows:
        a_exact = all(row["pair_a_exact"] for row in discriminator_rows)
        b_exact = all(row["pair_b_exact"] for row in discriminator_rows)
        if a_exact and not b_exact:
            verdict = "EXISTING_TARGETED_CAPTURES_FAVOR_PAIR_A"
        elif b_exact and not a_exact:
            verdict = "EXISTING_TARGETED_CAPTURES_FAVOR_PAIR_B"
        else:
            verdict = "EXISTING_TARGETED_CAPTURES_FALSIFY_OR_FAIL_TO_CHOOSE_PAIRS"
    else:
        verdict = "NO_EXISTING_TARGETED_PAIR_DISCRIMINATOR"

    report = {
        "experiment": "h1510_existing_targeted_pair_audit",
        "status": verdict,
        "suites": suite_reports,
        "suite_count": len(SUITES),
        "input_rows": input_rows,
        "architectural_rows_scored": input_rows * len(MODES),
        "modes": list(MODES),
        "endpoint_separator_rows": len(rows),
        "pair_discriminator_rows": len(discriminator_rows),
        "counts": dict(sorted(counts.items())),
        "candidate_signal_order": signal_order,
        "rows": rows,
        "claim_boundary": (
            "the 19 listed pre-existing standalone-FCOS RN/RD/RU targeted "
            "captures only; a pair choice requires an endpoint-visible row "
            "where the exact H1487 pair functions disagree"
        ),
        "sha256": {
            "incumbent": digest(arguments.incumbent),
            "r1382": digest(arguments.r1382),
            "inputs": input_hashes,
            "captures": capture_hashes,
        },
        "execution": {
            "hardware": "none; cached captures read only",
            "x87_instructions": "none",
            "fresh_capture_labels_opened": "none",
            "private_capture_ledger": "not accessed",
            "h1488_state": "FROZEN_UNOPENED",
            "emulator_change": "none",
            "paper_change": "none",
        },
    }
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(text)
    print(json.dumps({
        "output": str(arguments.output),
        "report_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "status": verdict,
        "suite_count": len(SUITES),
        "input_rows": input_rows,
        "architectural_rows_scored": input_rows * len(MODES),
        "endpoint_separator_rows": len(rows),
        "pair_discriminator_rows": len(discriminator_rows),
        "pair_a_exact": counts["pair_a.exact"],
        "pair_b_exact": counts["pair_b.exact"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
