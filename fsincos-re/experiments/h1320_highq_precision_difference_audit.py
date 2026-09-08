#!/usr/bin/env python3
"""Test exact one-hop and recursive precision differences on high-q labels.

US 5,612,909 permits an attached history to encode a multi-bit precision
difference.  The strongest arithmetic interpretation available from the
recovered graph is the exact dyadic difference between the materialized
operand and either (a) its immediate pre-round product or (b) the recursively
unmaterialized polynomial state.  This pass projects both fixed recurrences
through the final negative Horner FADD and scores the resulting adjacent
factor choice.  It does not tune a threshold or inspect operand identities.
"""

from __future__ import annotations

import argparse
import hashlib
from collections import Counter
from pathlib import Path

from h1184_upstream_halfway_audit import CONSTANTS, Value, row_value, schedule
from h1191_grs_history_isomorphism import magnitude_delta
from h1192_precision_difference_recurrence import (
    difference,
    dyad_operation,
    dyad_quantize,
    dyad_scaled_numerator,
    recurrence,
)
from h1210_stagea_residual_reframe import parse_dump, run
from h1316_highq_fixed_schedule_representations import (
    load_causal,
    load_direct,
    load_siblings,
)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", type=Path)
    parser.add_argument("causal_legs", type=Path)
    parser.add_argument("sibling_labels", type=Path)
    parser.add_argument("direct_labels", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    labels: dict[str, int] = {}
    load_causal(args.causal_legs, labels)
    load_siblings(args.sibling_labels, labels)
    load_direct(args.direct_labels, labels)
    operands = sorted(labels)
    _, stderr = run(args.model, "rn", operands, dump=True)
    rows = parse_dump(stderr, operands)

    counts = Counter()
    diagnostics = []
    for row in rows:
        operations = schedule(row)
        graph = recurrence(row)
        baseline = row_value(row, "lf")
        local_add = dyad_operation(operations["negative.add2"])
        local_source = dyad_operation(operations["negative.mul2"])
        candidates = {
            "onehop": graph["onehop.negative.add2"],
            "recursive": graph["recursive.negative.add2"],
        }
        deltas = {
            name: magnitude_delta(dyad_quantize(value, 64, True), baseline)
            for name, value in candidates.items()
        }
        wanted = labels[row["op"]]
        for name, delta in deltas.items():
            predicted = int(delta == -1)
            counts[f"{name}.errors"] += predicted != wanted
            counts[f"{name}.positive_errors"] += wanted and not predicted
            counts[f"{name}.negative_errors"] += not wanted and predicted
            counts[f"{name}.delta.{delta}"] += 1

        recursive_source = graph["recursive.negative.mul2"]
        fine = min(
            local_add.exponent,
            local_source.exponent,
            recursive_source.exponent,
            candidates["recursive"].exponent,
        )
        source_error = dyad_scaled_numerator(
            difference(recursive_source, local_source), fine)
        add_error = dyad_scaled_numerator(
            difference(candidates["recursive"], local_add), fine)
        diagnostics.append((
            row["op"], wanted, deltas["onehop"], deltas["recursive"],
            fine, source_error, add_error,
        ))

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as target:
        for name, path in (
            ("model", args.model),
            ("causal_legs", args.causal_legs),
            ("sibling_labels", args.sibling_labels),
            ("direct_labels", args.direct_labels),
        ):
            target.write(f"{name}_sha256\t{digest(path)}\n")
        target.write("hardware_policy\tfrozen_factor_labels_no_x87_execution\n")
        target.write("candidate_policy\texact_onehop_and_recursive_dyadic_recurrences\n")
        target.write(f"operands\t{len(rows)}\n")
        target.write(f"positive_operands\t{sum(labels.values())}\n")
        target.write("\n[counts]\n")
        for name, count in sorted(counts.items()):
            target.write(f"{name}\t{count}\n")
        target.write("\n[diagnostics]\n")
        target.write(
            "op\twanted_wide\tonehop_factor_delta\t"
            "recursive_factor_delta\terror_scale\t"
            "recursive_source_minus_local\trecursive_add_minus_local\n")
        for diagnostic in diagnostics:
            target.write("\t".join(map(str, diagnostic)) + "\n")

    print(
        f"wrote {args.report}: operands={len(rows)} "
        f"onehop_errors={counts['onehop.errors']} "
        f"recursive_errors={counts['recursive.errors']}",
        flush=True,
    )


if __name__ == "__main__":
    main()
