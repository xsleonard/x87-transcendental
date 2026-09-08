#!/usr/bin/env python3
"""Score H1487 pair A/B on the already-opened H1400 transfer bank.

H1486 reduced the surviving selector spellings using 28 direct FCOS labels,
but did not consume the later-reconciled H1400 high-quotient transfer labels.
This audit verifies the frozen identities against the immutable raw FXSAVE
capture, replays the incumbent and default-off R1382 behaviors for all 100
core rows, and evaluates pair A/B wherever the two endpoints are distinct.

No x87 instruction or fresh hardware capture is executed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path

from h1405_score_single_shot_state import (
    expected_identity,
    parse_state,
    read_tsv,
    target_value,
    verify_identity,
)
from h1486_surviving_propagate_class import candidate_values
from h1510_existing_targeted_pair_audit import configs, digest


def parse_model_line(line: str, instruction: str, target_lane: str) -> str:
    fields = line.lower().split()
    if fields == ["c2"]:
        return "c2"
    expected = 5 if instruction == "fsincos" else 3
    if len(fields) != expected or fields[0] != "ok":
        raise RuntimeError(f"bad {instruction} model output: {line!r}")
    if instruction == "fsincos":
        offset = 1 if target_lane == "sin" else 3
    else:
        offset = 1
    return f"{int(fields[offset], 16):04x}:{int(fields[offset + 1], 16):016x}"


def run_model(
    model: Path,
    instruction: str,
    mode: str,
    target_lane: str,
    operand: str,
    dump: bool = False,
) -> tuple[str, str]:
    command = [str(model), "--batch", f"--rc={mode}"]
    if instruction == "fsin":
        command.append("--fsin-standalone")
    elif instruction == "fcos":
        command.append("--fcos-standalone")
    elif instruction != "fsincos":
        raise RuntimeError(f"unsupported core instruction {instruction!r}")
    if dump:
        command.append("--dump-internals")
    process = subprocess.run(
        command,
        input=operand + "\n",
        text=True,
        capture_output=True,
        check=True,
    )
    output_lines = process.stdout.splitlines()
    if len(output_lines) != 1:
        raise RuntimeError(
            f"{instruction}/{mode}/{operand}: {len(output_lines)} output rows"
        )
    return (
        parse_model_line(output_lines[0], instruction, target_lane),
        process.stderr,
    )


def terminal_patterns(stderr: str, candidate_configs) -> list[str]:
    patterns = []
    expression = re.compile(
        r"\brf=[01]:-?\d+:([0-9a-f]+)\s+"
        r"f4=[01]:-?\d+:([0-9a-f]+)\b"
    )
    for line in stderr.splitlines():
        if not line.startswith("DI_TC "):
            continue
        match = expression.search(line.lower())
        if not match:
            raise RuntimeError(f"cannot parse terminal operands: {line!r}")
        right_factor, fourth = match.groups()
        patterns.append(candidate_values(
            int(fourth, 16), int(right_factor, 16), candidate_configs
        ))
    return patterns


def select_pattern(
    instruction: str, target_lane: str, patterns: list[str]
) -> tuple[str | None, str]:
    if instruction != "fsincos":
        if len(patterns) != 1:
            return None, f"standalone_terminal_count_{len(patterns)}"
        return patterns[0], "standalone_terminal"
    if len(patterns) == 2:
        return patterns[0 if target_lane == "sin" else 1], "paired_lane_order"
    return None, f"paired_terminal_count_{len(patterns)}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("incumbent", type=Path)
    parser.add_argument("r1382", type=Path)
    parser.add_argument("core_manifest", type=Path)
    parser.add_argument("architecture_manifest", type=Path)
    parser.add_argument("identity_manifest", type=Path)
    parser.add_argument("raw_state", type=Path)
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args()
    if arguments.output.exists():
        raise SystemExit(f"refusing to overwrite {arguments.output}")

    core = read_tsv(arguments.core_manifest)
    architecture = read_tsv(arguments.architecture_manifest)
    identity = read_tsv(arguments.identity_manifest)
    expected = expected_identity(core, architecture)
    verify_identity(expected, identity)
    raw = parse_state(arguments.raw_state)
    if len(raw) != len(expected):
        raise RuntimeError(
            f"raw row count {len(raw)} != identity count {len(expected)}"
        )
    state_by_case = {
        expected_row["case_id"]: state
        for expected_row, state in zip(expected, raw)
    }
    if len(state_by_case) != len(expected):
        raise RuntimeError("duplicate identity case")

    signal_order, candidate_configs = configs()
    counts = Counter()
    rows = []
    for source_row in core:
        case_id = source_row["case_id"]
        instruction = source_row["instruction"]
        mode = source_row["mode"]
        target_lane = source_row["target_lane"]
        operand = source_row["operand"].lower()
        hardware = target_value(source_row, state_by_case[case_id])
        incumbent, _ = run_model(
            arguments.incumbent,
            instruction,
            mode,
            target_lane,
            operand,
        )
        r1382, _ = run_model(
            arguments.r1382,
            instruction,
            mode,
            target_lane,
            operand,
        )
        if hardware == incumbent:
            endpoint = "incumbent"
        elif hardware == r1382 and incumbent != r1382:
            endpoint = "r1382"
        else:
            endpoint = "other"

        pattern = None
        pattern_source = "not_endpoint_visible"
        pair_discriminator = False
        pair_a = None
        pair_b = None
        pair_a_exact = None
        pair_b_exact = None
        if incumbent != r1382:
            _, stderr = run_model(
                arguments.incumbent,
                instruction,
                mode,
                target_lane,
                operand,
                dump=True,
            )
            pattern, pattern_source = select_pattern(
                instruction,
                target_lane,
                terminal_patterns(stderr, candidate_configs),
            )
            if pattern is not None:
                if pattern[0] != pattern[1] or pattern[2] != pattern[3]:
                    raise RuntimeError(
                        f"{case_id}: H1487 within-pair equivalence changed"
                    )
                pair_discriminator = pattern[0] != pattern[2]
                pair_a = incumbent if pattern[0] == "1" else r1382
                pair_b = incumbent if pattern[2] == "1" else r1382
                pair_a_exact = pair_a == hardware
                pair_b_exact = pair_b == hardware

        row = {
            "case_id": case_id,
            "family": source_row["family"],
            "transfer_kind": source_row["transfer_kind"],
            "instruction": instruction,
            "target_lane": target_lane,
            "mode": mode,
            "operand": operand.replace(" ", ":"),
            "hardware": hardware,
            "incumbent": incumbent,
            "r1382": r1382,
            "endpoint": endpoint,
            "endpoint_visible": incumbent != r1382,
            "candidate_pattern": pattern,
            "candidate_pattern_source": pattern_source,
            "pair_discriminator": pair_discriminator,
            "pair_a": pair_a,
            "pair_b": pair_b,
            "pair_a_exact": pair_a_exact,
            "pair_b_exact": pair_b_exact,
        }
        rows.append(row)
        counts[f"instruction.{instruction}.rows"] += 1
        counts[f"hardware_endpoint.{endpoint}"] += 1
        counts[f"endpoint_visible.{str(incumbent != r1382).lower()}"] += 1
        if pattern is not None:
            counts[f"candidate_pattern.{pattern}"] += 1
            counts[
                f"pair_discriminator.{str(pair_discriminator).lower()}"
            ] += 1

    visible = [row for row in rows if row["endpoint_visible"]]
    discriminators = [row for row in rows if row["pair_discriminator"]]
    ambiguous_patterns = [
        row for row in visible if row["candidate_pattern"] is None
    ]
    if ambiguous_patterns:
        verdict = "OPENED_TRANSFER_ENDPOINTS_HAVE_AMBIGUOUS_PAIR_TRACE"
    elif discriminators:
        a_exact = all(row["pair_a_exact"] for row in discriminators)
        b_exact = all(row["pair_b_exact"] for row in discriminators)
        if a_exact and not b_exact:
            verdict = "OPENED_TRANSFER_LABELS_FAVOR_PAIR_A"
        elif b_exact and not a_exact:
            verdict = "OPENED_TRANSFER_LABELS_FAVOR_PAIR_B"
        else:
            verdict = "OPENED_TRANSFER_LABELS_FALSIFY_OR_FAIL_TO_CHOOSE_PAIRS"
    else:
        verdict = "NO_OPENED_TRANSFER_PAIR_DISCRIMINATOR"

    report = {
        "experiment": "h1512_opened_transfer_pair_audit",
        "status": verdict,
        "identity_reconciliation": "EXACT",
        "core_rows": len(core),
        "architecture_rows_reconciled": len(architecture),
        "endpoint_visible_rows": len(visible),
        "pair_discriminator_rows": len(discriminators),
        "ambiguous_pair_trace_rows": len(ambiguous_patterns),
        "counts": dict(sorted(counts.items())),
        "candidate_signal_order": signal_order,
        "rows": rows,
        "claim_boundary": (
            "the immutable already-opened H1400 100-row core transfer bank; "
            "pair scoring requires a current/R1382 endpoint separator whose "
            "exact H1487 pair functions disagree"
        ),
        "sha256": {
            "incumbent": digest(arguments.incumbent),
            "r1382": digest(arguments.r1382),
            "core_manifest": digest(arguments.core_manifest),
            "architecture_manifest": digest(arguments.architecture_manifest),
            "identity_manifest": digest(arguments.identity_manifest),
            "raw_state": digest(arguments.raw_state),
        },
        "execution": {
            "hardware": "none; immutable opened capture read only",
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
        "core_rows": len(core),
        "endpoint_visible_rows": len(visible),
        "pair_discriminator_rows": len(discriminators),
        "ambiguous_pair_trace_rows": len(ambiguous_patterns),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
