#!/usr/bin/env python3
"""Test closed product-CPA boundary representations on forced high-q labels.

The post-h1309 labels distinguish an upstream negative.add2 factor change
from every terminal carry endpoint.  A single product-tree wire is already
falsified.  This audit instead tests arithmetic representations: cut or force
one carry at a fixed column of the documented final product CPA, then allow
the resulting borrow/propagate chain to flow normally through product
materialization and the RN64 FADD.  The column is fixed across all operands;
no operand thresholds or learned decision tree are used.

Two carry-select interfaces are also tested.  They replace one fixed four-bit
conditional-sum word (and optionally its carry-out) with the precomputed
carry-zero or carry-one alternative while preserving every other product bit.
These are literal projections of the P5 four-bit carry-select final adder.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import Counter, defaultdict
from pathlib import Path

from h1100_p5_multiplier_tree import multiplier_tree
from h1184_upstream_halfway_audit import (
    CONSTANTS,
    ExactOperation,
    Value,
    add_same_sign,
    quantize,
    schedule,
)
from h1191_grs_history_isomorphism import magnitude_delta
from h1210_stagea_residual_reframe import parse_dump, run
from h1222_r1200_enable_state import cut_fields


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def causal_labels(path: Path) -> dict[str, int | None]:
    by_operand: dict[str, list[dict[str, str]]] = defaultdict(list)
    with path.open(newline="") as source:
        for row in csv.DictReader(source, delimiter="\t"):
            by_operand[row["op"].lower()].append(row)
    labels = {}
    for operand, rows in by_operand.items():
        if any(row["causal_class"] == "wide_factor_required" for row in rows):
            labels[operand] = 1
        elif any(row["wide_allowed_carries"] == "-" for row in rows):
            labels[operand] = 0
        else:
            labels[operand] = None
    return labels


def add_sibling_labels(labels: dict[str, int | None], path: Path) -> None:
    with path.open(newline="") as source:
        for row in csv.DictReader(source, delimiter="\t"):
            operand = f"3ffc {row['residual66'].lower()}"
            verdict = row["verdict"]
            if verdict not in ("wide", "predecessor"):
                raise RuntimeError(f"non-binary sibling verdict: {row}")
            value = int(verdict == "wide")
            previous = labels.setdefault(operand, value)
            if previous is not None and previous != value:
                raise RuntimeError(f"factor-label conflict for {operand}")


def cpa_carries(sum_vector: int, carry_vector: int, width: int = 131
                ) -> list[int]:
    carries = [0]
    carry = 0
    for position in range(width):
        a = (sum_vector >> position) & 1
        b = (carry_vector >> position) & 1
        carry = (a & b) | ((a ^ b) & carry)
        carries.append(carry)
    return carries


def conditional_word(
        sum_vector: int, carry_vector: int, start: int, assumed: int,
        width: int = 4) -> tuple[int, int]:
    word = 0
    carry = assumed
    for offset, position in enumerate(range(start, start + width)):
        a = (sum_vector >> position) & 1
        b = (carry_vector >> position) & 1
        word |= (a ^ b ^ carry) << offset
        carry = (a & b) | ((a ^ b) & carry)
    return word, carry


def factor_from_product(operation: ExactOperation, magnitude: int) -> Value:
    source = quantize(
        ExactOperation(operation.sign, operation.exponent, magnitude),
        67,
        False,
    )
    return quantize(
        add_same_sign(Value(*CONSTANTS[1]), source), 64, True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", type=Path)
    parser.add_argument("causal_legs", type=Path)
    parser.add_argument("sibling_labels", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    labels = causal_labels(args.causal_legs)
    add_sibling_labels(labels, args.sibling_labels)
    forced_labels = {
        operand: value for operand, value in labels.items()
        if value is not None
    }
    operands = sorted(forced_labels)
    _, stderr = run(args.model, "rn", operands, dump=True)
    dump_rows = parse_dump(stderr, operands)

    records = []
    candidate_values: dict[str, list[int | None]] = defaultdict(list)
    for dump_row in dump_rows:
        operand = dump_row["op"]
        operations = schedule(dump_row)
        product_operation = operations["negative.mul2"]
        product = product_operation.magnitude
        fourth = quantize(operations["fourth"], 67, False)
        first_factor = quantize(operations["negative.add1"], 64, True)
        tree = multiplier_tree(fourth.significand, first_factor.significand)
        sum_vector = int(tree["sum"])
        carry_vector = int(tree["carry"])
        mask131 = (1 << 131) - 1
        if (sum_vector + carry_vector) & mask131 != product:
            raise RuntimeError(f"tree/product mismatch for {operand}")
        carries = cpa_carries(sum_vector, carry_vector)
        baseline = factor_from_product(product_operation, product)
        product_fields = cut_fields(product_operation, 67)
        add_fields = cut_fields(operations["negative.add2"], 64)
        cut = int(product_fields["shift"])

        representations: dict[str, int] = {"baseline": product}
        for position in range(131):
            carry_in = carries[position]
            representations[f"drop_carry.abs{position:03d}"] = (
                product - (carry_in << position))
            representations[f"force_carry.abs{position:03d}"] = (
                product + ((1 - carry_in) << position))

        starts = set()
        for origin_name, origin in (("p5", 2), ("abs", 0)):
            for start in range(origin, 128, 4):
                if start + 4 <= 131:
                    starts.add((origin_name, start))
        for relative in range(-8, 9):
            start = cut + relative
            if 0 <= start and start + 4 <= 131:
                starts.add((f"cut{relative:+d}", start))
        for name, start in sorted(starts):
            field_mask = 15 << start
            field5_mask = 31 << start
            for assumed in (0, 1):
                word, carry_out = conditional_word(
                    sum_vector, carry_vector, start, assumed)
                local = (product & ~field_mask) | (word << start)
                local5 = (
                    (product & ~field5_mask)
                    | (word << start)
                    | (carry_out << (start + 4))
                )
                representations[
                    f"csel4.{name}.b{start:03d}.cin{assumed}.word"
                ] = local
                representations[
                    f"csel4.{name}.b{start:03d}.cin{assumed}.word_cout"
                ] = local5

        for name, magnitude in representations.items():
            if magnitude <= 0:
                delta = None
            else:
                value = factor_from_product(product_operation, magnitude)
                delta = magnitude_delta(value, baseline)
            candidate_values[name].append(delta)
        records.append({
            "op": operand,
            "wanted": int(forced_labels[operand]),
            "q": int(add_fields["half_delta"]),
            "cut": cut,
            "product": product,
            "sum": sum_vector,
            "carry": carry_vector,
        })

    scores = []
    for name, deltas in candidate_values.items():
        errors = positive_errors = negative_errors = 0
        changed = Counter()
        for record, delta in zip(records, deltas):
            prediction = int(delta == -1)
            wrong = prediction != record["wanted"]
            errors += wrong
            positive_errors += wrong and record["wanted"] == 1
            negative_errors += wrong and record["wanted"] == 0
            changed[str(delta)] += 1
        scores.append((
            errors, positive_errors, negative_errors,
            changed.get("-1", 0), changed.get("0", 0),
            changed.get("None", 0), name,
        ))
    scores.sort()
    exact = [score for score in scores if score[0] == 0]

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as target:
        target.write(f"model_sha256\t{digest(args.model)}\n")
        target.write(f"causal_legs_sha256\t{digest(args.causal_legs)}\n")
        target.write(
            f"sibling_labels_sha256\t{digest(args.sibling_labels)}\n")
        target.write("hardware_policy\tfrozen_forced_factor_labels_only\n")
        target.write(f"forced_operands\t{len(records)}\n")
        target.write(
            f"positive_operands\t{sum(row['wanted'] for row in records)}\n")
        target.write(f"representations\t{len(scores)}\n")
        target.write(f"exact_representations\t{len(exact)}\n")
        target.write("\n[ranking]\n")
        target.write(
            "errors\tpositive_errors\tnegative_errors\tdelta_minus1\t"
            "delta_zero\tdelta_other\trepresentation\n")
        for score in scores[:1000]:
            target.write("\t".join(map(str, score)) + "\n")
        target.write("\n[exact representations]\n")
        for score in exact:
            target.write("\t".join(map(str, score)) + "\n")
        target.write("\n[best diagnostics]\n")
        target.write("op\twanted\tq\tcut\tpredicted_delta\n")
        best_name = scores[0][-1]
        for record, delta in zip(records, candidate_values[best_name]):
            target.write("\t".join(map(str, (
                record["op"], record["wanted"], record["q"],
                record["cut"], delta,
            ))) + "\n")

    print(
        f"wrote {args.report}: operands={len(records)} "
        f"representations={len(scores)} exact={len(exact)} "
        f"best={scores[0]}",
        flush=True,
    )


if __name__ == "__main__":
    main()
