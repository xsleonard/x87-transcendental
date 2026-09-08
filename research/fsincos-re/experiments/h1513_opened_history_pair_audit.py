#!/usr/bin/env python3
"""Score H1487 pair A/B on 437 opened history/prelude observations.

H1414 is the corrected authoritative score for the immutable H1406, H1408,
H1410, and H1412 campaigns.  All rows execute direct standalone FCOS after a
producer or instruction-history variant.  This audit replays the two endpoint
models on each row and evaluates pair A/B wherever their outputs differ.

No x87 instruction or fresh hardware capture is executed.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

from h1510_existing_targeted_pair_audit import configs, digest
from h1512_opened_transfer_pair_audit import (
    run_model,
    select_pattern,
    terminal_patterns,
)


EXPECTED_CAMPAIGNS = {
    "h1406": 33,
    "h1408": 24,
    "h1410": 133,
    "h1412": 247,
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("incumbent", type=Path)
    parser.add_argument("r1382", type=Path)
    parser.add_argument("h1414_score", type=Path)
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args()
    if arguments.output.exists():
        raise SystemExit(f"refusing to overwrite {arguments.output}")

    with arguments.h1414_score.open(newline="") as source:
        source_rows = list(csv.DictReader(source, delimiter="\t"))
    required = {
        "campaign", "case_id", "population", "mode", "operand", "variant",
        "corrected_model", "corrected_hardware", "observed", "endpoint",
    }
    if len(source_rows) != 437 or not source_rows:
        raise RuntimeError(f"H1414 row count changed: {len(source_rows)}")
    if not required.issubset(source_rows[0]):
        raise RuntimeError(
            f"H1414 score missing columns: {sorted(required-set(source_rows[0]))}"
        )
    campaign_counts = Counter(row["campaign"] for row in source_rows)
    if dict(campaign_counts) != EXPECTED_CAMPAIGNS:
        raise RuntimeError(f"H1414 campaign census changed: {campaign_counts}")
    if any(
        row["observed"] != row["corrected_hardware"]
        for row in source_rows
    ):
        raise RuntimeError("H1414 corrected hardware reconciliation changed")

    signal_order, candidate_configs = configs()
    counts = Counter()
    rows = []
    replay_cache = {}
    for source_row in source_rows:
        mode = source_row["mode"].lower()
        operand = source_row["operand"].lower()
        key = mode, operand
        if key not in replay_cache:
            incumbent, _ = run_model(
                arguments.incumbent, "fcos", mode, "cos", operand
            )
            r1382, _ = run_model(
                arguments.r1382, "fcos", mode, "cos", operand
            )
            pattern = None
            pattern_source = "not_endpoint_visible"
            if incumbent != r1382:
                _, stderr = run_model(
                    arguments.incumbent,
                    "fcos",
                    mode,
                    "cos",
                    operand,
                    dump=True,
                )
                pattern, pattern_source = select_pattern(
                    "fcos",
                    "cos",
                    terminal_patterns(stderr, candidate_configs),
                )
            replay_cache[key] = incumbent, r1382, pattern, pattern_source

        incumbent, r1382, pattern, pattern_source = replay_cache[key]
        hardware = source_row["observed"].lower()
        if hardware == incumbent:
            endpoint = "incumbent"
        elif hardware == r1382 and incumbent != r1382:
            endpoint = "r1382"
        else:
            endpoint = "other"
        pair_discriminator = False
        pair_a = None
        pair_b = None
        pair_a_exact = None
        pair_b_exact = None
        if pattern is not None:
            if pattern[0] != pattern[1] or pattern[2] != pattern[3]:
                raise RuntimeError(
                    f"{key}: H1487 within-pair equivalence changed"
                )
            pair_discriminator = pattern[0] != pattern[2]
            pair_a = incumbent if pattern[0] == "1" else r1382
            pair_b = incumbent if pattern[2] == "1" else r1382
            pair_a_exact = pair_a == hardware
            pair_b_exact = pair_b == hardware

        row = {
            **source_row,
            "replay_incumbent": incumbent,
            "replay_r1382": r1382,
            "replay_endpoint": endpoint,
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
        counts[f"campaign.{source_row['campaign']}.rows"] += 1
        counts[f"population.{source_row['population']}.rows"] += 1
        counts[f"endpoint_visible.{str(incumbent != r1382).lower()}"] += 1
        counts[f"hardware_endpoint.{endpoint}"] += 1
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
        verdict = "OPENED_HISTORY_ENDPOINTS_HAVE_AMBIGUOUS_PAIR_TRACE"
    elif discriminators:
        a_exact = all(row["pair_a_exact"] for row in discriminators)
        b_exact = all(row["pair_b_exact"] for row in discriminators)
        if a_exact and not b_exact:
            verdict = "OPENED_HISTORY_LABELS_FAVOR_PAIR_A"
        elif b_exact and not a_exact:
            verdict = "OPENED_HISTORY_LABELS_FAVOR_PAIR_B"
        else:
            verdict = "OPENED_HISTORY_LABELS_FALSIFY_OR_FAIL_TO_CHOOSE_PAIRS"
    else:
        verdict = "NO_OPENED_HISTORY_PAIR_DISCRIMINATOR"

    report = {
        "experiment": "h1513_opened_history_pair_audit",
        "status": verdict,
        "h1414_reconciliation": "EXACT",
        "rows_scored": len(rows),
        "unique_mode_operands": len(replay_cache),
        "endpoint_visible_rows": len(visible),
        "endpoint_visible_unique_mode_operands": len({
            (row["mode"], row["operand"]) for row in visible
        }),
        "pair_discriminator_rows": len(discriminators),
        "ambiguous_pair_trace_rows": len(ambiguous_patterns),
        "counts": dict(sorted(counts.items())),
        "candidate_signal_order": signal_order,
        "rows": rows,
        "claim_boundary": (
            "the immutable H1414-corrected H1406/H1408/H1410/H1412 direct-"
            "FCOS history and prelude observations; pair scoring requires a "
            "current/R1382 endpoint separator where pair A and pair B differ"
        ),
        "sha256": {
            "incumbent": digest(arguments.incumbent),
            "r1382": digest(arguments.r1382),
            "h1414_score": digest(arguments.h1414_score),
        },
        "execution": {
            "hardware": "none; corrected immutable capture score read only",
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
        "rows_scored": len(rows),
        "unique_mode_operands": len(replay_cache),
        "endpoint_visible_rows": len(visible),
        "pair_discriminator_rows": len(discriminators),
        "ambiguous_pair_trace_rows": len(ambiguous_patterns),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
