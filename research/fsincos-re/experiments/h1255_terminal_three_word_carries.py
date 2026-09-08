#!/usr/bin/env python3
"""Search fixed three-word carry equations for the terminal exception bit.

h1254 rules out a carry from the redundant square comparator by itself.
This pass tests the next circuit-sized hypothesis: a four-bit product-CPA
digit from each of two live arithmetic sources is combined with one natural
terminal digit, using an ordinary carry/borrow or one 3:2 compressor bit.

Product words are compared only at identical P5 alignment, relative block,
and conditional-sum form.  Constants are limited to the mandatory +1 per
two's-complement negated input, or its carry-in-absent physical control.  No
learned threshold, operand identity, or input interval is admitted.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import defaultdict
from itertools import combinations
from pathlib import Path

import numpy as np

from h1250_terminal_product_word_relations import (
    coordinate_words,
    product_words,
)


MASK4 = 15


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def terminal_words(row: dict[str, str]) -> dict[str, int]:
    values = coordinate_words(row)
    cut = int(row["k"])
    sources = {
        "S": int(row["S"], 16),
        "B": int(row["B"], 16),
        "SxorB": int(row["S"], 16) ^ int(row["B"], 16),
        "umag": int(row["umag"], 16),
    }
    for name, value in sources.items():
        for relative in range(-2, 3):
            start = cut + 4 * relative
            values[f"term.{name}.cut.rel{relative:+d}"] = (
                value >> max(0, start)
            ) & MASK4
    for name in ("tc_ud", "tc_u5d", "tc_rud"):
        values[f"term.{name}"] = int(row[name]) & MASK4
    right_discarded = int(row["tc_rdisc"], 16)
    for start in range(48, 65, 4):
        values[f"term.rdisc.nibble{start}"] = (
            right_discarded >> start
        ) & MASK4
    return values


def relation_arrays(a: np.ndarray, b: np.ndarray, c: np.ndarray):
    """Yield fixed carry/compressor predicates over three unsigned digits."""
    for signs in ((1, 1, 1), (1, 1, -1), (1, -1, 1), (-1, 1, 1)):
        words = (a, b, c)
        encoded = np.zeros_like(a, dtype=np.int16)
        negative_count = 0
        sign_text = ""
        for sign, word in zip(signs, words):
            sign_text += "+" if sign > 0 else "-"
            if sign > 0:
                encoded += word
            else:
                encoded += word ^ MASK4
                negative_count += 1
        for correction_name, correction in (
            ("raw", 0), ("twos", negative_count),
        ):
            total = encoded + correction
            stem = f"{sign_text}.{correction_name}"
            yield f"{stem}.carry_bit0", ((total >> 4) & 1).astype(np.uint8)
            yield f"{stem}.carry_bit1", ((total >> 5) & 1).astype(np.uint8)
            yield f"{stem}.carry_any", (total >= 16).astype(np.uint8)
            yield f"{stem}.carry_two", (total >= 32).astype(np.uint8)
            yield f"{stem}.sum_zero", ((total & MASK4) == 0).astype(np.uint8)
            yield f"{stem}.sum_one", ((total & MASK4) == 1).astype(np.uint8)
            yield f"{stem}.sum_allones", ((total & MASK4) == MASK4).astype(np.uint8)

    # Literal 3:2 compressor wires.  These are independent of operand order.
    csa_sum = a ^ b ^ c
    csa_carry = ((a & b) | (a & c) | (b & c)) << 1
    for bit in range(4):
        yield f"csa.sum.bit{bit}", ((csa_sum >> bit) & 1).astype(np.uint8)
        yield f"csa.carry.bit{bit}", ((csa_carry >> bit) & 1).astype(np.uint8)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("rows", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument(
        "--target", choices=("exception", "flip", "physical"),
        default="exception",
    )
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    with args.rows.open(newline="") as source:
        rows = [
            row for row in csv.DictReader(source, delimiter="\t")
            if row["physical_status"] == "constraining"
        ]
    product_records = []
    coordinate_records = []
    truth = []
    for index, row in enumerate(rows, 1):
        product_records.append(product_words(row))
        coordinate_records.append(terminal_words(row))
        if args.target == "exception":
            wanted = (
                int(row["physical_label"])
                ^ ((int(row["low3"]) >> 1) & 1)
            )
        elif args.target == "flip":
            wanted = int(row["label"] == "POS")
        else:
            wanted = int(row["physical_label"])
        truth.append(wanted)
        if index % 25 == 0:
            print(f"words {index}/{len(rows)}", flush=True)
    expected = np.asarray(truth, dtype=np.uint8)

    product_names = sorted(product_records[0])
    coordinate_names = sorted(coordinate_records[0])
    products = {
        name: np.asarray([record[name] for record in product_records],
                         dtype=np.int16)
        for name in product_names
    }
    coordinates = {
        name: np.asarray([record[name] for record in coordinate_records],
                         dtype=np.int16)
        for name in coordinate_names
    }

    by_layout: dict[tuple[str, str, str, str], list[str]] = defaultdict(list)
    for name in product_names:
        prefix, alignment, width, relative, form = name.split(".")
        by_layout[(alignment, width, relative, form)].append(name)

    scores = []
    exact = []
    candidates = 0
    for layout_index, (layout, names) in enumerate(sorted(by_layout.items()), 1):
        for left_name, right_name in combinations(sorted(names), 2):
            a, b = products[left_name], products[right_name]
            for coordinate_name in coordinate_names:
                c = coordinates[coordinate_name]
                for relation_name, prediction in relation_arrays(a, b, c):
                    candidates += 1
                    wrong = prediction ^ expected
                    errors = int(np.count_nonzero(wrong))
                    exception_miss = int(np.count_nonzero(
                        expected & (prediction ^ 1)
                    ))
                    control_fire = int(np.count_nonzero(
                        (expected ^ 1) & prediction
                    ))
                    score = (
                        errors, exception_miss, control_fire,
                        relation_name, left_name, right_name, coordinate_name,
                    )
                    if len(scores) < 5000:
                        scores.append(score)
                        scores.sort()
                    elif score < scores[-1]:
                        scores[-1] = score
                        scores.sort()
                    if errors == 0:
                        exact.append(score)
        if layout_index % 9 == 0:
            print(
                f"layouts {layout_index}/{len(by_layout)} "
                f"candidates={candidates} best={scores[0][:3]}",
                flush=True,
            )

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as target:
        target.write(f"rows_sha256\t{digest(args.rows)}\n")
        target.write(f"rows\t{len(rows)}\n")
        target.write(f"target\t{args.target}\n")
        target.write(f"target_ones\t{int(expected.sum())}\n")
        target.write(f"product_words\t{len(product_names)}\n")
        target.write(f"coordinate_words\t{len(coordinate_names)}\n")
        target.write(f"layouts\t{len(by_layout)}\n")
        target.write(f"candidates\t{candidates}\n")
        target.write(f"exact_candidates\t{len(exact)}\n")
        target.write("hardware_policy\tcached_labels_only_no_x87_execution\n")
        target.write("\n[ranking]\n")
        target.write(
            "errors\texception_miss\tcontrol_fire\trelation\t"
            "left\tright\tcoordinate\n"
        )
        for score in scores:
            target.write("\t".join(map(str, score)) + "\n")
        target.write("\n[exact candidates]\n")
        for score in exact:
            target.write("\t".join(map(str, score)) + "\n")

    print(
        f"wrote {args.report} candidates={candidates} "
        f"exact={len(exact)} best={scores[0]}",
        flush=True,
    )


if __name__ == "__main__":
    main()
