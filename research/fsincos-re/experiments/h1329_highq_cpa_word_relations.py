#!/usr/bin/env python3
"""Audit block-local CPA word relations on the complete high-q bank.

The P5 multiplier patent ends its radix-8/4:2 tree with four-bit
carry-select blocks.  R1290 tested only one muxed four-bit word against
``2*q``.  This pass exhausts the bounded structural generalization: every
near-cut physical four-bit block under P5, absolute, and cut-relative
alignment; its carry-zero, carry-one, exactly selected, sum-row, and
carry-row words; and fixed comparator/carry relations to literal four-bit
encodings of the current FADD distance ``q``.

The tested form is

    wide = (product_cut == 63) AND relation(CPA_word, encode(q)).

There are no operand identities or learned numeric thresholds.  An exact
survivor would still be a candidate circuit grammar requiring a disjoint
frozen challenge.  Hardware labels are immutable inputs and this program
executes no x87 instruction.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from pathlib import Path

from h1172_p5_cpa_predictor_mine import bit
from h1210_stagea_residual_reframe import parse_dump, run
from h1296_faddword_deeper_tree import event


WIDTH = 4
MASK = (1 << WIDTH) - 1
RELATIVES = range(-4, 5)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def load_labels(paths: list[Path]) -> dict[str, int]:
    labels: dict[str, int] = {}
    for path in paths:
        with path.open(newline="") as source:
            for row in csv.DictReader(source, delimiter="\t"):
                if row["verdict"] not in ("wide", "predecessor"):
                    raise RuntimeError(f"non-binary direct label: {row}")
                operand = row["op"].lower()
                wanted = int(row["verdict"] == "wide")
                previous = labels.setdefault(operand, wanted)
                if previous != wanted:
                    raise RuntimeError(f"factor-label conflict for {operand}")
    return labels


def carry_into(sum_vector: int, carry_vector: int, end: int) -> int:
    carry = 0
    for position in range(end):
        a = bit(sum_vector, position)
        b = bit(carry_vector, position)
        carry = (a & b) | ((a ^ b) & carry)
    return carry


def conditional_word(sum_vector: int, carry_vector: int,
                     start: int, assumed: int) -> tuple[int, int]:
    carry = assumed
    word = 0
    for offset, position in enumerate(range(start, start + WIDTH)):
        a = bit(sum_vector, position)
        b = bit(carry_vector, position)
        word |= (a ^ b ^ carry) << offset
        carry = (a & b) | ((a ^ b) & carry)
    return word, carry


def words(item: dict[str, object]) -> dict[str, int]:
    product = int(item["product"])
    cut = product.bit_length() - 67
    state = item["state"]
    sum_vector = int(state["sum"])
    carry_vector = int(state["carry"])
    values: dict[str, int] = {}
    for alignment, origin in (("p5", 2), ("abs", 0), ("cut", cut)):
        base = origin + ((cut - origin) // WIDTH) * WIDTH
        for relative in RELATIVES:
            start = base + relative * WIDTH
            if start < 0 or start + WIDTH > 131:
                continue
            stem = f"{alignment}.rel{relative:+d}"
            sum0, cout0 = conditional_word(
                sum_vector, carry_vector, start, 0)
            sum1, cout1 = conditional_word(
                sum_vector, carry_vector, start, 1)
            cin = carry_into(sum_vector, carry_vector, start)
            values[f"{stem}.sum0"] = sum0
            values[f"{stem}.sum1"] = sum1
            values[f"{stem}.selected"] = sum1 if cin else sum0
            values[f"{stem}.sumrow"] = (sum_vector >> start) & MASK
            values[f"{stem}.carryrow"] = (carry_vector >> start) & MASK
            values[f"{stem}.cout0"] = MASK if cout0 else 0
            values[f"{stem}.cout1"] = MASK if cout1 else 0
            values[f"{stem}.cin"] = MASK if cin else 0
    return values


def q_encodings(q: int) -> dict[str, int]:
    return {
        "q": q & MASK,
        "2q": (2 * q) & MASK,
        "2q-1": (2 * q - 1) & MASK,
        "2q+1": (2 * q + 1) & MASK,
        "-q": (-q) & MASK,
        "~q": (~q) & MASK,
    }


def relations(left: int, right: int) -> dict[str, int]:
    return {
        "equal": int(left == right),
        "greater_equal": int(left >= right),
        "greater": int(left > right),
        "same_half": int(((left ^ right) & 8) == 0),
        "same_half_ge": int(((left ^ right) & 8) == 0 and left >= right),
        "same_half_gt": int(((left ^ right) & 8) == 0 and left > right),
        "add_carry": int(left + right > MASK),
        "sub_borrow": int(left < right),
        "xor_parity": (left ^ right).bit_count() & 1,
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

    labels = load_labels(args.direct_label)
    operands = sorted(labels)
    _, stderr = run(args.model, "rn", operands, dump=True)
    rows = parse_dump(stderr, operands)

    records = []
    schema = None
    for row in rows:
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
        word_values = words(item)
        if schema is None:
            schema = tuple(sorted(word_values))
        elif tuple(sorted(word_values)) != schema:
            raise RuntimeError("word schema differs by operand")
        records.append((
            row["op"], labels[row["op"]], cut, q, word_values,
        ))
    if schema is None:
        raise SystemExit("empty label set")
    if any(wanted and cut != 63 for _, wanted, cut, _, _ in records):
        raise RuntimeError("wider label exists outside cut 63")

    scores = []
    exact = []
    candidate_count = 0
    for word_name in schema:
        for encoding_name in q_encodings(5):
            for relation_name in relations(0, 0):
                for invert in (0, 1):
                    errors = positive_errors = negative_errors = 0
                    predicted_positives = 0
                    for _, wanted, cut, q, values in records:
                        reference = q_encodings(q)[encoding_name]
                        predicate = relations(
                            values[word_name], reference)[relation_name]
                        predicted = int(cut == 63 and (predicate ^ invert))
                        wrong = predicted != wanted
                        errors += wrong
                        positive_errors += wrong and wanted
                        negative_errors += wrong and not wanted
                        predicted_positives += predicted
                    item_score = (
                        errors, positive_errors, negative_errors,
                        predicted_positives, relation_name, invert,
                        encoding_name, word_name,
                    )
                    scores.append(item_score)
                    candidate_count += 1
                    if errors == 0:
                        exact.append(item_score)
    scores.sort()

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as output:
        output.write(f"model_sha256\t{digest(args.model)}\n")
        for index, path in enumerate(args.direct_label):
            output.write(
                f"direct_labels_sha256.{index}\t{digest(path)}\n")
        output.write("hardware_policy\tfrozen_one_shot_labels_no_x87_execution\n")
        output.write(
            "candidate_policy\tcut63_AND_fixed_four_bit_CPA_word_relation\n")
        output.write(f"operands\t{len(records)}\n")
        output.write(f"positive_operands\t{sum(labels.values())}\n")
        output.write(
            f"cut63_operands\t{sum(cut == 63 for _, _, cut, _, _ in records)}\n")
        output.write(f"word_sources\t{len(schema)}\n")
        output.write(f"candidates\t{candidate_count}\n")
        output.write(f"exact_candidates\t{len(exact)}\n")
        output.write("\n[ranking]\n")
        output.write(
            "errors\tpositive_errors\tnegative_errors\t"
            "predicted_positives\trelation\tinvert\tq_encoding\tword\n")
        for item_score in scores[:1024]:
            output.write("\t".join(map(str, item_score)) + "\n")
        output.write("\n[exact candidates]\n")
        for item_score in exact:
            output.write("\t".join(map(str, item_score)) + "\n")

    print(
        f"wrote {args.report}: operands={len(records)} "
        f"words={len(schema)} candidates={candidate_count} "
        f"exact={len(exact)} best={scores[0][:4]}",
        flush=True,
    )


if __name__ == "__main__":
    main()
