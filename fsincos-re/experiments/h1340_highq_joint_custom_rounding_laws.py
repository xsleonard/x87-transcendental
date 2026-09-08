#!/usr/bin/env python3
"""Exhaust joint fixed 65-bit LSB/guard/sticky laws at square and fourth.

h1339 varies either power edge alone.  This pass completes that compact
round-controller grammar by varying both edges together.  Each edge has one
fixed eight-entry Boolean truth table over retained LSB, guard, and sticky;
exact results are preserved.  All 65,536 operation-level law pairs are
tested, with equivalent value and prediction signatures cached explicitly.

No condition reads an operand identity or hardware label.  Hardware labels
are immutable scoring inputs and this program executes no x87 instruction.
"""

from __future__ import annotations

import argparse
import hashlib
from collections import Counter, defaultdict
from pathlib import Path

from h1184_upstream_halfway_audit import multiply, row_value
from h1191_grs_history_isomorphism import magnitude_delta
from h1210_stagea_residual_reframe import parse_dump, run
from h1316_highq_fixed_schedule_representations import load_direct
from h1339_highq_custom_rounding_laws import (
    factor_from_fourth,
    quantize_law,
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

    square_groups = defaultdict(list)
    for square_law in range(256):
        squares = tuple(
            quantize_law(multiply(magnitude, magnitude), 65, square_law)
            for _, magnitude, _, _, _ in prepared)
        square_groups[squares].append(square_law)

    prediction_groups = defaultdict(list)
    for squares, square_laws in square_groups.items():
        for fourth_law in range(256):
            prediction = []
            deltas = []
            for square, (_, _, baseline, _, _) in zip(squares, prepared):
                fourth = quantize_law(
                    multiply(square, square), 65, fourth_law)
                delta = magnitude_delta(factor_from_fourth(fourth), baseline)
                deltas.append(delta)
                prediction.append(int(delta == -1))
            signature = (tuple(prediction), tuple(deltas))
            prediction_groups[signature].append(
                (tuple(square_laws), fourth_law))

    scores = []
    exact = []
    for (prediction, deltas), aliases in prediction_groups.items():
        counts = Counter()
        for predicted, delta, (_, _, _, wanted, bank) in zip(
                prediction, deltas, prepared):
            wrong = predicted != wanted
            counts["errors"] += wrong
            counts[f"bank{bank}.errors"] += wrong
            counts["positive_errors"] += wrong and wanted
            counts["negative_errors"] += wrong and not wanted
            counts["predicted_positives"] += predicted
            counts[f"delta.{delta}"] += 1
        pair_aliases = sum(len(square_laws) for square_laws, _ in aliases)
        first_square_laws, first_fourth_law = aliases[0]
        item = (
            counts["errors"], counts["bank1.errors"],
            counts["bank0.errors"], counts["positive_errors"],
            counts["negative_errors"], counts["predicted_positives"],
            counts["delta.-1"], counts["delta.0"],
            len(prepared) - counts["delta.-1"] - counts["delta.0"],
            pair_aliases, first_square_laws[0], first_fourth_law,
        )
        scores.append(item)
        if not item[0]:
            exact.append((item, aliases))
    scores.sort()

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as output:
        output.write(f"model_sha256\t{digest(args.model)}\n")
        for index, path in enumerate(args.direct_label):
            output.write(f"direct_labels_sha256.{index}\t{digest(path)}\n")
        output.write("hardware_policy\tfrozen_one_shot_labels_no_x87_execution\n")
        output.write("candidate_policy\tjoint_fixed_65bit_lsb_guard_sticky_laws\n")
        output.write(f"operands\t{len(prepared)}\n")
        output.write(f"positive_operands\t{sum(labels.values())}\n")
        output.write("law_pairs\t65536\n")
        output.write(f"distinct_square_value_signatures\t{len(square_groups)}\n")
        output.write(
            f"distinct_factor_prediction_signatures\t{len(prediction_groups)}\n")
        output.write(
            f"exact_prediction_signatures\t{len(exact)}\n")
        output.write("\n[ranking]\n")
        output.write(
            "errors\textension_errors\tolder_errors\tpositive_errors\t"
            "negative_errors\tpredicted_positives\tdelta_minus1\t"
            "delta_zero\tdelta_other\tpair_aliases\t"
            "first_square_law_hex\tfirst_fourth_law_hex\n")
        for item in scores:
            rendered = (*item[:-2], f"{item[-2]:02x}", f"{item[-1]:02x}")
            output.write("\t".join(map(str, rendered)) + "\n")
        output.write("\n[exact law-pair aliases]\n")
        for item, aliases in exact:
            output.write("score\t" + "\t".join(map(str, item)) + "\n")
            for square_laws, fourth_law in aliases:
                output.write(
                    "laws\t" + ",".join(f"{law:02x}" for law in square_laws)
                    + f"\t{fourth_law:02x}\n")

    print(
        f"wrote {args.report}: operands={len(prepared)} "
        f"square_signatures={len(square_groups)} "
        f"prediction_signatures={len(prediction_groups)} "
        f"exact={len(exact)} best={scores[0]}",
        flush=True,
    )


if __name__ == "__main__":
    main()
