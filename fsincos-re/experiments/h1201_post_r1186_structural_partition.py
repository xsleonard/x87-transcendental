#!/usr/bin/env python3
"""Test physical multiplier/CSA wires on the five post-R1186 conflicts.

R1186 leaves five terminal cells nonmonotone in the scalar M coordinate.
This cached-only audit asks a narrower structural question: does one named
wire from the literal P5 Booth tree, final CPA, fused terminal CSA, or
redundant R60 comparator make each cell monotone when carried as one extra
state bit?  The feature constructors are fixed circuit transcriptions from
h1100/h1128/h1129/h1172; no operand threshold or identity is introduced.

This is a localization experiment, not a correction rule.  A successful
partition still needs to be expressed as the operation's actual recurrence
and validated outside the discovery rows.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import defaultdict
from pathlib import Path

from h1101_p5_tree_mine import row_features as tree_features
from h1128_fused_terminal_csa_mine import row_features as fused_features
from h1129_r60_redundant_comparator_mine import (
    active_row_features as comparator_features,
)
from h1172_p5_cpa_predictor_mine import row_features as cpa_features
from h1178_round_history_state_audit import CELL, monotonicity, signed128
from h1196_reframed_history_partition import physical_deviation


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def base_conflicts(rows: list[dict[str, str]]) -> set[tuple[int, ...]]:
    groups = defaultdict(list)
    for row in rows:
        key = tuple(int(row[field]) for field in CELL)
        groups[key].append((signed128(row["Mreg"]), physical_deviation(row)))
    return {
        key for key, values in groups.items()
        if monotonicity({key: values})[1]
    }


def structural_features(row: dict[str, str]) -> dict[str, int]:
    banks = (
        ("tree", tree_features(row)),
        ("fused", fused_features(row)),
        ("cpa", cpa_features(row)),
        ("comparator", comparator_features(row) or {}),
    )
    result = {}
    for bank, values in banks:
        for name, value in values.items():
            result[f"{bank}.{name}"] = int(value)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("rows", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("--expected-cells", type=int, default=5)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    with args.rows.open(newline="") as source:
        rows = [
            row for row in csv.DictReader(source, delimiter="\t")
            if row["physical_status"] == "constraining"
        ]
    conflict_keys = base_conflicts(rows)
    conflicts = [
        row for row in rows
        if tuple(int(row[field]) for field in CELL) in conflict_keys
    ]
    if len(conflict_keys) != args.expected_cells:
        raise RuntimeError(
            f"expected {args.expected_cells} conflict cells, "
            f"got {len(conflict_keys)}"
        )

    records = []
    schema = None
    for index, row in enumerate(conflicts, 1):
        values = structural_features(row)
        if schema is None:
            schema = set(values)
        elif set(values) != schema:
            # Comparator features are absent on corner rows.  Normalize the
            # union after collection instead of giving absence a data-driven
            # meaning; the fixed default state is zero.
            schema |= set(values)
        records.append((row, values))
        if index % 50 == 0:
            print(f"features {index}/{len(conflicts)}", flush=True)
    if schema is None:
        raise RuntimeError("empty conflict corpus")

    scores = []
    for name in sorted(schema):
        groups = defaultdict(list)
        states = set()
        target_states = []
        for row, values in records:
            state = int(values.get(name, 0))
            states.add(state)
            if row["label"] == "POS":
                target_states.append((row["op"], state))
            key = tuple(int(row[field]) for field in CELL)
            groups[key + (state,)].append(
                (signed128(row["Mreg"]), physical_deviation(row))
            )
        mixed, nonmonotone, bad_rows = monotonicity(groups)
        scores.append((nonmonotone, bad_rows, mixed, len(states), name,
                       tuple(target_states)))
    scores.sort(key=lambda item: item[:5])
    exact = [score for score in scores if score[0] == 0]

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as target:
        target.write(f"rows_sha256\t{digest(args.rows)}\n")
        target.write(f"constraining_rows\t{len(rows)}\n")
        target.write(f"conflict_cells\t{len(conflict_keys)}\n")
        target.write(f"conflict_rows\t{len(conflicts)}\n")
        target.write(f"features\t{len(scores)}\n")
        target.write(f"zero_nonmonotone_features\t{len(exact)}\n")
        target.write("\n[ranking]\n")
        target.write(
            "nonmonotone\tbad_rows\tmixed\tstates\tfeature\t"
            "target_states\n"
        )
        for score in scores[:500]:
            nonmonotone, bad_rows, mixed, states, name, target_states = score
            rendered = ",".join(
                f"{operand}={state}" for operand, state in target_states
            )
            target.write(
                f"{nonmonotone}\t{bad_rows}\t{mixed}\t{states}\t{name}\t"
                f"{rendered}\n"
            )

    print(
        f"wrote {args.report} cells={len(conflict_keys)} "
        f"rows={len(conflicts)} features={len(scores)} exact={len(exact)} "
        f"best={scores[0][:5]}",
        flush=True,
    )


if __name__ == "__main__":
    main()
