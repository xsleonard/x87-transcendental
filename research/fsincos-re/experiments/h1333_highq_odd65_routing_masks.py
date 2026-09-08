#!/usr/bin/env python3
"""Exhaust fixed routing masks for the h1332 odd65 product carrier.

h1332's strongest fixed arithmetic representation uses a 65-bit
round-to-odd carrier at all four negative-chain products and ordinary RN64
at both adds.  This pass isolates that result by routing the odd65 carrier at
each subset of ``square``, ``fourth``, ``mul1``, and ``mul2``.  The 16 masks
are architectural edge choices, not operand conditions.

Hardware labels are immutable inputs and this program executes no x87
instruction.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import Counter
from pathlib import Path

from h1184_upstream_halfway_audit import row_value
from h1191_grs_history_isomorphism import magnitude_delta
from h1210_stagea_residual_reframe import parse_dump, run
from h1316_highq_fixed_schedule_representations import load_direct
from h1332_highq_width_double_round_audit import (
    BASE_MODES,
    BASE_WIDTHS,
    Candidate,
    recurrence,
)


PRODUCT_STAGES = ((0, "square"), (1, "fourth"), (2, "mul1"), (4, "mul2"))


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument(
        "--direct-label", action="append", type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")
    if len(args.direct_label) != 2:
        raise SystemExit("supply the older bank and extension bank in order")

    labels: dict[str, int] = {}
    source_bank: dict[str, int] = {}
    for bank, path in enumerate(args.direct_label):
        bank_labels: dict[str, int] = {}
        load_direct(path, bank_labels)
        overlap = set(labels) & set(bank_labels)
        if overlap:
            raise RuntimeError(f"direct-label banks overlap: {sorted(overlap)}")
        labels.update(bank_labels)
        for operand in bank_labels:
            source_bank[operand] = bank
    operands = sorted(labels)
    _, stderr = run(args.model, "rn", operands, dump=True)
    rows = parse_dump(stderr, operands)
    prepared = [(
        row["op"], row_value(row, "mag"), row_value(row, "lf"),
        labels[row["op"]], source_bank[row["op"]],
    ) for row in rows]

    scores = []
    diagnostics_by_mask = {}
    for mask in range(16):
        widths = list(BASE_WIDTHS)
        modes = list(BASE_MODES)
        active = []
        for bit_index, (stage_index, stage_name) in enumerate(PRODUCT_STAGES):
            if mask & (1 << bit_index):
                widths[stage_index] = 65
                modes[stage_index] = "odd"
                active.append(stage_name)
        name = "+".join(active) if active else "baseline"
        candidate = Candidate(
            "odd65_mask", name, tuple(widths), tuple(modes))
        counts = Counter()
        diagnostics = []
        for operand, magnitude, baseline, wanted, bank in prepared:
            delta = magnitude_delta(recurrence(magnitude, candidate), baseline)
            predicted = int(delta == -1)
            wrong = predicted != wanted
            counts["errors"] += wrong
            counts[f"bank{bank}.errors"] += wrong
            counts["positive_errors"] += wrong and wanted
            counts["negative_errors"] += wrong and not wanted
            counts["predicted_positives"] += predicted
            counts[f"delta.{delta}"] += 1
            diagnostics.append((operand, wanted, predicted, delta, bank))
        scores.append((
            counts["errors"], counts["bank1.errors"],
            counts["bank0.errors"], counts["positive_errors"],
            counts["negative_errors"], counts["predicted_positives"],
            counts["delta.-1"], counts["delta.0"],
            len(prepared) - counts["delta.-1"] - counts["delta.0"],
            mask, name,
        ))
        diagnostics_by_mask[mask] = diagnostics
    scores.sort()
    best = scores[0]

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as output:
        output.write(f"model_sha256\t{digest(args.model)}\n")
        for index, path in enumerate(args.direct_label):
            output.write(
                f"direct_labels_sha256.{index}\t{digest(path)}\n")
        output.write("hardware_policy\tfrozen_one_shot_labels_no_x87_execution\n")
        output.write("candidate_policy\tfixed_odd65_product_routing_masks\n")
        output.write(f"operands\t{len(prepared)}\n")
        output.write(f"positive_operands\t{sum(labels.values())}\n")
        output.write(f"masks\t{len(scores)}\n")
        output.write(f"exact_masks\t{sum(not item[0] for item in scores)}\n")
        output.write("\n[ranking]\n")
        output.write(
            "errors\textension_errors\tolder_errors\tpositive_errors\t"
            "negative_errors\tpredicted_positives\tdelta_minus1\t"
            "delta_zero\tdelta_other\tmask_hex\trouting\n")
        for item in scores:
            rendered = (*item[:9], f"{item[9]:x}", item[10])
            output.write("\t".join(map(str, rendered)) + "\n")
        output.write("\n[best diagnostics]\n")
        output.write("op\twanted_wide\tpredicted_wide\tfactor_delta\tbank\n")
        for item in diagnostics_by_mask[best[9]]:
            output.write("\t".join(map(str, item)) + "\n")

    print(
        f"wrote {args.report}: operands={len(prepared)} "
        f"exact={sum(not item[0] for item in scores)} best={best}",
        flush=True,
    )


if __name__ == "__main__":
    main()
