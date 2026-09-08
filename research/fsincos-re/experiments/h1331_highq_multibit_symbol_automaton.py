#!/usr/bin/env python3
"""Test a one-bit history tag driven by literal two-bit rounding symbols.

h1328 exhausts one-bit state machines whose input is itself one bit.  The
rounding-history patent permits a wider description of discarded data, so
that audit does not rule out a one-bit carried decision updated from a
two-bit rounding class.  This pass exhausts the missing finite-state class:

    state_next = T_operation(state, two_bit_symbol)
    wide       = (product_cut == 63) AND (state XOR polarity).

Each FMUL/FADD transition is an arbitrary fixed 8-entry Boolean function;
all 256 laws, both seeds, and both output polarities are tested.  Symbols are
the predeclared literal attributes from h1330 and are extracted identically
at every stage.  The older 73-operand bank and its 116-operand extension are
also scored separately to expose non-transferring fits.

This is a small hardware automaton grammar, not an operand decision tree.
Any exact survivor would still require a disjoint frozen challenge and a
physical routing argument.  Hardware labels are immutable inputs and this
program executes no x87 instruction.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from pathlib import Path

import numpy as np

from h1184_upstream_halfway_audit import schedule
from h1210_stagea_residual_reframe import parse_dump, run
from h1296_faddword_deeper_tree import event
from h1330_highq_two_bit_history_recurrence import (
    KINDS,
    NATIVE,
    STAGES,
    SYMBOLS,
    rounding_symbols,
)


TRANSITIONS = np.asarray([
    [(law >> index) & 1 for index in range(8)]
    for law in range(256)
], dtype=np.uint8)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def load_labels(paths: list[Path]) -> tuple[dict[str, int], dict[str, int]]:
    labels: dict[str, int] = {}
    sources: dict[str, int] = {}
    for source_index, path in enumerate(paths):
        with path.open(newline="") as source:
            for row in csv.DictReader(source, delimiter="\t"):
                if row["verdict"] not in ("wide", "predecessor"):
                    raise RuntimeError(f"non-binary direct label: {row}")
                operand = row["op"].lower()
                wanted = int(row["verdict"] == "wide")
                previous = labels.setdefault(operand, wanted)
                if previous != wanted:
                    raise RuntimeError(f"factor-label conflict for {operand}")
                previous_source = sources.setdefault(operand, source_index)
                if previous_source != source_index:
                    raise RuntimeError(
                        f"operand occurs in more than one bank: {operand}")
    return labels, sources


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

    labels, sources = load_labels(args.direct_label)
    operands = sorted(labels)
    _, stderr = run(args.model, "rn", operands, dump=True)
    rows = parse_dump(stderr, operands)

    sequences = {name: [] for name in SYMBOLS}
    targets = []
    cuts = []
    source_indices = []
    for row in rows:
        operations = schedule(row)
        item = event(row, "negative.add2")
        q = int(item["q"])
        product = int(item["product"])
        cut = product.bit_length() - 67
        if not (
            5 <= q <= 7
            and int(item["increments"])
            and ((product >> 65) & 1) == ((q >> 2) & 1)
        ):
            raise RuntimeError(f"not a high-q separator: {row['op']}")
        stage_symbols = [
            rounding_symbols(operations[stage], *NATIVE[stage])
            for stage in STAGES
        ]
        for name in SYMBOLS:
            sequences[name].append(
                tuple(values[name] for values in stage_symbols))
        targets.append(labels[row["op"]])
        cuts.append(cut)
        source_indices.append(sources[row["op"]])
    if any(wanted and cut != 63 for wanted, cut in zip(targets, cuts)):
        raise RuntimeError("wider label exists outside cut 63")

    target = np.asarray(targets, dtype=np.uint8)
    enabled = np.asarray([cut == 63 for cut in cuts], dtype=np.uint8)
    source_index = np.asarray(source_indices, dtype=np.uint8)
    source_masks = tuple(source_index == index for index in range(2))
    scores = []
    exact = []
    candidate_count = 0

    for symbol_name in SYMBOLS:
        symbols = np.asarray(sequences[symbol_name], dtype=np.uint8)
        for mul_law in range(256):
            for add_law in range(256):
                laws = tuple(
                    mul_law if kind == "mul" else add_law
                    for kind in KINDS
                )
                for seed in (0, 1):
                    state = np.full(len(rows), seed, dtype=np.uint8)
                    for index, law in enumerate(laws):
                        state = TRANSITIONS[law][
                            4 * state + symbols[:, index]]
                    for polarity in (0, 1):
                        predicted = enabled & (state ^ polarity)
                        wrong = predicted != target
                        errors = int(np.count_nonzero(wrong))
                        positive_errors = int(np.count_nonzero(
                            wrong & target.astype(bool)))
                        negative_errors = errors - positive_errors
                        bank_errors = tuple(
                            int(np.count_nonzero(wrong & mask))
                            for mask in source_masks
                        )
                        item_score = (
                            errors, bank_errors[1], bank_errors[0],
                            positive_errors, negative_errors,
                            int(np.count_nonzero(predicted)),
                            symbol_name, seed, mul_law, add_law, polarity,
                        )
                        scores.append(item_score)
                        if len(scores) == 8192:
                            scores.sort()
                            del scores[1024:]
                        if errors == 0:
                            exact.append(item_score)
                        candidate_count += 1
    scores.sort()

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as output:
        output.write(f"model_sha256\t{digest(args.model)}\n")
        for index, path in enumerate(args.direct_label):
            output.write(
                f"direct_labels_sha256.{index}\t{digest(path)}\n")
        output.write("hardware_policy\tfrozen_one_shot_labels_no_x87_execution\n")
        output.write(
            "candidate_policy\tone_bit_state_arbitrary_two_bit_symbol_laws\n")
        output.write(f"operands\t{len(rows)}\n")
        output.write(f"positive_operands\t{sum(targets)}\n")
        output.write(f"cut63_operands\t{int(enabled.sum())}\n")
        output.write(f"symbol_encodings\t{len(SYMBOLS)}\n")
        output.write(f"candidates\t{candidate_count}\n")
        output.write(f"exact_candidates\t{len(exact)}\n")
        for index, mask in enumerate(source_masks):
            output.write(f"bank_operands.{index}\t{int(mask.sum())}\n")
        output.write("stage_order\t" + ",".join(STAGES) + "\n")
        output.write("\n[ranking]\n")
        output.write(
            "errors\textension_errors\tolder_errors\tpositive_errors\t"
            "negative_errors\tpredicted_positives\tsymbol\tseed\t"
            "mul_law_hex\tadd_law_hex\tpolarity\n")
        for item_score in scores[:1024]:
            rendered = (
                *item_score[:8], f"{item_score[8]:02x}",
                f"{item_score[9]:02x}", item_score[10],
            )
            output.write("\t".join(map(str, rendered)) + "\n")
        output.write("\n[exact candidates]\n")
        for item_score in exact:
            rendered = (
                *item_score[:8], f"{item_score[8]:02x}",
                f"{item_score[9]:02x}", item_score[10],
            )
            output.write("\t".join(map(str, rendered)) + "\n")

    print(
        f"wrote {args.report}: operands={len(rows)} "
        f"candidates={candidate_count} exact={len(exact)} "
        f"best={scores[0][:6]}",
        flush=True,
    )


if __name__ == "__main__":
    main()
