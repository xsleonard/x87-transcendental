#!/usr/bin/env python3
"""Exhaust a bounded two-bit attached-history recurrence grammar.

The one-bit audit h1328 rules out every Boolean history recurrence over the
recovered six-operation negative Horner chain.  Intel's rounding-history
patent explicitly permits multiple bits describing discarded data.  This
pass therefore tests the smallest wider arithmetic state without introducing
operand identities or thresholds:

    state_next = (a_op*state + b_op*symbol + c_op) mod 4
    wide       = (product_cut == 63) AND decode(state).

FMUL and FADD have independent fixed ``(a,b,c)`` triples.  ``symbol`` is one
of a predeclared set of literal two-bit rounding attributes extracted in the
same way at every stage.  All four seeds and all 16 decoders of the final
two-bit state are exhausted.  A decoder is a four-entry hardware truth table,
not an operand table; any exact survivor would still need a disjoint frozen
challenge and a physical routing argument.

Hardware labels are immutable inputs and this program executes no x87
instruction.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
from pathlib import Path

import numpy as np

from h1184_upstream_halfway_audit import quantize, schedule
from h1191_grs_history_isomorphism import compare_values
from h1210_stagea_residual_reframe import parse_dump, run
from h1296_faddword_deeper_tree import event


STAGES = (
    "square", "fourth", "negative.mul1", "negative.add1",
    "negative.mul2", "negative.add2",
)
KINDS = ("mul", "mul", "mul", "add", "mul", "add")
NATIVE = {
    "square": (67, False),
    "fourth": (67, False),
    "negative.mul1": (67, False),
    "negative.add1": (64, True),
    "negative.mul2": (67, False),
    "negative.add2": (64, True),
}
SYMBOLS = (
    "discarded.top2",
    "discarded.bottom2",
    "discarded.grs2",
    "discarded.class4",
    "discarded.tz_mod4",
    "retained.low2",
    "shift.mod4",
    "round.increment_inexact",
    "round.direction_increment",
)


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


def trailing_zeros(value: int) -> int:
    return (value & -value).bit_length() - 1 if value else 0


def rounding_symbols(operation, bits: int, nearest: bool) -> dict[str, int]:
    stored = quantize(operation, bits, nearest)
    shift = max(0, operation.magnitude.bit_length() - bits)
    denominator = 1 << shift if shift else 1
    remainder = operation.magnitude & (denominator - 1) if shift else 0
    retained = operation.magnitude >> shift
    half = denominator >> 1 if shift else 0
    increment = int(stored.significand != retained)
    inexact = int(bool(remainder))
    if not remainder:
        class4 = 0
    elif remainder < half:
        class4 = 1
    elif remainder == half:
        class4 = 2
    else:
        class4 = 3
    if shift >= 2:
        top2 = remainder >> (shift - 2)
    else:
        top2 = remainder << (2 - shift)
    bottom2 = remainder & 3
    guard = (remainder >> (shift - 1)) & 1 if shift else 0
    sticky = int(
        shift > 1 and bool(remainder & ((1 << (shift - 1)) - 1)))
    exact_value = type(stored)(
        operation.sign, operation.exponent, operation.magnitude)
    direction = compare_values(stored, exact_value)
    direction_code = {-1: 0, 0: 1, 1: 2}[direction]
    return {
        "discarded.top2": top2 & 3,
        "discarded.bottom2": bottom2,
        "discarded.grs2": ((guard << 1) | sticky) & 3,
        "discarded.class4": class4,
        "discarded.tz_mod4": trailing_zeros(remainder) & 3,
        "retained.low2": retained & 3,
        "shift.mod4": shift & 3,
        "round.increment_inexact": increment | (inexact << 1),
        "round.direction_increment": direction_code | (increment << 1),
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

    sequences = {name: [] for name in SYMBOLS}
    targets = []
    cuts = []
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
    if any(wanted and cut != 63 for wanted, cut in zip(targets, cuts)):
        raise RuntimeError("wider label exists outside cut 63")

    target = np.asarray(targets, dtype=np.uint8)
    enabled = np.asarray([cut == 63 for cut in cuts], dtype=bool)
    positive = target.astype(bool)
    negative = enabled & ~positive
    coefficients = tuple(itertools.product(range(4), repeat=3))
    scores = []
    exact = []
    candidate_count = 0

    for symbol_name in SYMBOLS:
        symbols = np.asarray(sequences[symbol_name], dtype=np.uint8)
        for mul_coefficients in coefficients:
            for add_coefficients in coefficients:
                stage_coefficients = tuple(
                    mul_coefficients if kind == "mul" else add_coefficients
                    for kind in KINDS
                )
                for seed in range(4):
                    state = np.full(len(rows), seed, dtype=np.uint8)
                    for index, (a, b, c) in enumerate(stage_coefficients):
                        state = (a * state + b * symbols[:, index] + c) & 3
                    positive_by_state = np.bincount(
                        state[positive], minlength=4)
                    negative_by_state = np.bincount(
                        state[negative], minlength=4)
                    for decoder in range(16):
                        positive_errors = sum(
                            int(positive_by_state[value])
                            for value in range(4)
                            if not ((decoder >> value) & 1)
                        )
                        negative_errors = sum(
                            int(negative_by_state[value])
                            for value in range(4)
                            if (decoder >> value) & 1
                        )
                        predicted_positives = sum(
                            int(positive_by_state[value]
                                + negative_by_state[value])
                            for value in range(4)
                            if (decoder >> value) & 1
                        )
                        errors = positive_errors + negative_errors
                        item_score = (
                            errors, positive_errors, negative_errors,
                            predicted_positives, symbol_name, seed,
                            *mul_coefficients, *add_coefficients, decoder,
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
            "candidate_policy\tfixed_two_bit_affine_history_recurrences\n")
        output.write(f"operands\t{len(rows)}\n")
        output.write(f"positive_operands\t{sum(targets)}\n")
        output.write(f"cut63_operands\t{int(enabled.sum())}\n")
        output.write(f"symbol_encodings\t{len(SYMBOLS)}\n")
        output.write(f"candidates\t{candidate_count}\n")
        output.write(f"exact_candidates\t{len(exact)}\n")
        output.write("stage_order\t" + ",".join(STAGES) + "\n")
        output.write("\n[ranking]\n")
        output.write(
            "errors\tpositive_errors\tnegative_errors\t"
            "predicted_positives\tsymbol\tseed\t"
            "mul_a\tmul_b\tmul_c\tadd_a\tadd_b\tadd_c\tdecoder_hex\n")
        for item_score in scores[:1024]:
            rendered = (*item_score[:-1], f"{item_score[-1]:x}")
            output.write("\t".join(map(str, rendered)) + "\n")
        output.write("\n[exact candidates]\n")
        for item_score in exact:
            rendered = (*item_score[:-1], f"{item_score[-1]:x}")
            output.write("\t".join(map(str, rendered)) + "\n")

    print(
        f"wrote {args.report}: operands={len(rows)} "
        f"candidates={candidate_count} exact={len(exact)} "
        f"best={scores[0][:4]}",
        flush=True,
    )


if __name__ == "__main__":
    main()
