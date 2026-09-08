#!/usr/bin/env python3
"""Refine the 65-bit power carrier with fixed Horner-product formats.

h1334's best global arithmetic schedule uses square=odd65 and
fourth=chop65, then the recovered Horner chain.  Holding that power carrier
fixed, this pass exhausts every independent 60--80-bit chop/RN/away/odd
representation for mul1 and mul2.  The two FADDs remain RN64.

Every candidate is one global arithmetic schedule.  Hardware labels are
immutable inputs and this program executes no x87 instruction.
"""

from __future__ import annotations

import argparse
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
    MODES,
    Candidate,
    recurrence,
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
    exact = []
    for mul1_width in range(60, 81):
        for mul1_mode in MODES:
            for mul2_width in range(60, 81):
                for mul2_mode in MODES:
                    widths = list(BASE_WIDTHS)
                    modes = list(BASE_MODES)
                    widths[0], modes[0] = 65, "odd"
                    widths[1], modes[1] = 65, "chop"
                    widths[2], modes[2] = mul1_width, mul1_mode
                    widths[4], modes[4] = mul2_width, mul2_mode
                    candidate = Candidate(
                        "horner_product_grid",
                        f"mul1.{mul1_mode}{mul1_width}."
                        f"mul2.{mul2_mode}{mul2_width}",
                        tuple(widths), tuple(modes))
                    counts = Counter()
                    for _, magnitude, baseline, wanted, bank in prepared:
                        delta = magnitude_delta(
                            recurrence(magnitude, candidate), baseline)
                        predicted = int(delta == -1)
                        wrong = predicted != wanted
                        counts["errors"] += wrong
                        counts[f"bank{bank}.errors"] += wrong
                        counts["positive_errors"] += wrong and wanted
                        counts["negative_errors"] += wrong and not wanted
                        counts["predicted_positives"] += predicted
                        counts[f"delta.{delta}"] += 1
                    item = (
                        counts["errors"], counts["bank1.errors"],
                        counts["bank0.errors"], counts["positive_errors"],
                        counts["negative_errors"],
                        counts["predicted_positives"],
                        counts["delta.-1"], counts["delta.0"],
                        len(prepared) - counts["delta.-1"] - counts["delta.0"],
                        mul1_width, mul1_mode, mul2_width, mul2_mode,
                    )
                    scores.append(item)
                    if not item[0]:
                        exact.append(item)
    scores.sort()

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as output:
        output.write(f"model_sha256\t{digest(args.model)}\n")
        for index, path in enumerate(args.direct_label):
            output.write(
                f"direct_labels_sha256.{index}\t{digest(path)}\n")
        output.write("hardware_policy\tfrozen_one_shot_labels_no_x87_execution\n")
        output.write(
            "candidate_policy\tfixed_odd65_chop65_power_plus_horner_product_grid\n")
        output.write(f"operands\t{len(prepared)}\n")
        output.write(f"positive_operands\t{sum(labels.values())}\n")
        output.write(f"candidates\t{len(scores)}\n")
        output.write(f"exact_candidates\t{len(exact)}\n")
        output.write("\n[ranking]\n")
        output.write(
            "errors\textension_errors\tolder_errors\tpositive_errors\t"
            "negative_errors\tpredicted_positives\tdelta_minus1\t"
            "delta_zero\tdelta_other\tmul1_width\tmul1_mode\t"
            "mul2_width\tmul2_mode\n")
        for item in scores[:1024]:
            output.write("\t".join(map(str, item)) + "\n")
        output.write("\n[exact candidates]\n")
        for item in exact:
            output.write("\t".join(map(str, item)) + "\n")

    print(
        f"wrote {args.report}: operands={len(prepared)} "
        f"candidates={len(scores)} exact={len(exact)} "
        f"best={scores[0]}",
        flush=True,
    )


if __name__ == "__main__":
    main()
