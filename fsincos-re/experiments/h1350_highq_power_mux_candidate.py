#!/usr/bin/env python3
"""Score the smallest completion suggested by the upstream power-tree audit.

h1346 found two independently zero-collateral, 16-of-19 terms after the
already measured cut-63 enable:

    A = low_product[69] AND NOT square_carry_in[29]
    B = low_product[69] XOR fourth_full_generate[5]

Their OR covers 18 of the 19 wider-factor operands and no predecessor
operand.  Algebraically it is a two-way mux: when low_product[69] is clear,
select fourth_full_generate[5]; otherwise select the NAND of the square carry
and fourth generate.  This script freezes and scores that expression and the
same expression using h1346's training-equivalent square-generate alias.

The coordinates are physically named but widely separated, so this is a
candidate for adversarial testing, not evidence that the mux exists on the
chip.  No additional term is fitted to the remaining operand.  Hardware
labels are immutable one-shot inputs and this program executes no x87
instruction.
"""

from __future__ import annotations

import argparse
import hashlib
from collections import Counter
from pathlib import Path

from h1210_stagea_residual_reframe import parse_dump, run
from h1296_faddword_deeper_tree import event
from h1316_highq_fixed_schedule_representations import load_direct
from h1346_highq_power_tree_wire_audit import power_features


LOW = "fourth.external.low_product.b69"
SQUARE_CARRY = "square.port.final.cin.b29"
SQUARE_GENERATE = "square.port.final.generate.b47"
FOURTH_GENERATE = "fourth.full.final.generate.b5"


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def predictions(values: dict[str, int], cut: int) -> dict[str, int]:
    low = values[LOW]
    square_carry = values[SQUARE_CARRY]
    square_generate = values[SQUARE_GENERATE]
    fourth_generate = values[FOURTH_GENERATE]
    enabled = int(cut == 63)
    term_a = low & (1 ^ square_carry)
    term_a_alias = low & (1 ^ square_generate)
    term_b = low ^ fourth_generate
    return {
        "term_a": enabled & term_a,
        "term_a_alias": enabled & term_a_alias,
        "term_b": enabled & term_b,
        "mux_union": enabled & (term_a | term_b),
        "mux_union_alias": enabled & (term_a_alias | term_b),
    }


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
    sources: dict[str, int] = {}
    for bank, path in enumerate(args.direct_label):
        bank_labels: dict[str, int] = {}
        load_direct(path, bank_labels)
        overlap = set(labels) & set(bank_labels)
        if overlap:
            raise RuntimeError(f"direct-label banks overlap: {sorted(overlap)}")
        labels.update(bank_labels)
        sources.update({operand: bank for operand in bank_labels})

    operands = sorted(labels)
    _, stderr = run(args.model, "rn", operands, dump=True)
    rows = parse_dump(stderr, operands)
    records = []
    names = None
    for row in rows:
        values = power_features(row)
        item = event(row, "negative.add2")
        cut = int(item["product"]).bit_length() - 67
        row_predictions = predictions(values, cut)
        if names is None:
            names = tuple(row_predictions)
        elif tuple(row_predictions) != names:
            raise RuntimeError("prediction schema changed")
        records.append((
            row["op"], labels[row["op"]], sources[row["op"]], cut,
            values[LOW], values[SQUARE_CARRY], values[SQUARE_GENERATE],
            values[FOURTH_GENERATE], row_predictions,
        ))
    if names is None:
        raise SystemExit("empty label set")

    scores = []
    for name in names:
        counts = Counter()
        for record in records:
            wanted = record[1]
            predicted = record[8][name]
            wrong = wanted != predicted
            counts["errors"] += wrong
            counts["positive_errors"] += wrong and wanted
            counts["negative_errors"] += wrong and not wanted
            counts["predicted_positives"] += predicted
            counts[f"bank{record[2]}.errors"] += wrong
        scores.append((
            counts["errors"], counts["positive_errors"],
            counts["negative_errors"], counts["predicted_positives"],
            counts["bank1.errors"], counts["bank0.errors"], name,
        ))
    scores.sort()

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as output:
        output.write(f"model_sha256\t{digest(args.model)}\n")
        for index, path in enumerate(args.direct_label):
            output.write(f"direct_labels_sha256.{index}\t{digest(path)}\n")
        output.write("hardware_policy\tfrozen_one_shot_labels_no_x87_execution\n")
        output.write("candidate_policy\tfixed_cut63_power_tree_mux_expression\n")
        output.write("candidate_status\tempirical_near_fit_requires_blind_test\n")
        output.write(f"operands\t{len(records)}\n")
        output.write(f"positive_operands\t{sum(labels.values())}\n")
        output.write(f"low_wire\t{LOW}\n")
        output.write(f"square_control\t{SQUARE_CARRY}\n")
        output.write(f"square_training_alias\t{SQUARE_GENERATE}\n")
        output.write(f"fourth_control\t{FOURTH_GENERATE}\n")
        output.write("\n[ranking]\n")
        output.write(
            "errors\tpositive_errors\tnegative_errors\t"
            "predicted_positives\textension_errors\tolder_errors\tname\n")
        for score in scores:
            output.write("\t".join(map(str, score)) + "\n")
        output.write("\n[mux disagreements]\n")
        output.write(
            "op\twanted_wide\tpredicted_wide\tbank\tcut\tlow69\t"
            "square_cin29\tsquare_generate47\tfourth_generate5\n")
        for record in records:
            predicted = record[8]["mux_union"]
            if predicted != record[1]:
                output.write("\t".join(map(str, (
                    record[0], record[1], predicted, record[2],
                    *record[3:8],
                ))) + "\n")
        output.write("\n[alias disagreements]\n")
        output.write("op\tmux_union\tmux_union_alias\tlabel\tcut\n")
        for record in records:
            direct = record[8]["mux_union"]
            alias = record[8]["mux_union_alias"]
            if direct != alias:
                output.write(
                    f"{record[0]}\t{direct}\t{alias}\t"
                    f"{record[1]}\t{record[3]}\n")

    print(
        f"wrote {args.report}: operands={len(records)} "
        f"best={scores[0][:6]} name={scores[0][6]}",
        flush=True,
    )


if __name__ == "__main__":
    main()
