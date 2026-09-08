#!/usr/bin/env python3
"""Audit patent-motivated attached-history fields on forced high-q labels.

US 5,612,909 permits rounding history to describe more than a direction bit:
it may encode exact-half, all-ones, and other properties of discarded data.
This audit constructs those fields at every recovered producer on the negative
Horner path.  It tests their literal Boolean projections and fixed arithmetic
relations to the current three-bit half-distance q.  It also reports whether
the complete field tuples contain opposite-label collisions.

The search is diagnostic.  An exact expression would still require a physical
routing argument and a disjoint frozen challenge before promotion.  Hardware
labels are frozen inputs to scoring and no x87 instruction is executed.
"""

from __future__ import annotations

import argparse
import hashlib
from collections import Counter, defaultdict
from pathlib import Path

from h1184_upstream_halfway_audit import (
    STAGES,
    Value,
    quantize,
    row_value,
    schedule,
)
from h1191_grs_history_isomorphism import compare_values
from h1210_stagea_residual_reframe import parse_dump, run
from h1222_r1200_enable_state import cut_fields
from h1316_highq_fixed_schedule_representations import (
    load_causal,
    load_direct,
    load_siblings,
)


NATIVE = {
    "square": (67, False),
    "fourth": (67, False),
    "negative.mul1": (67, False),
    "negative.add1": (64, True),
    "negative.mul2": (67, False),
    "negative.add2": (64, True),
}
GATES = (
    ("and", lambda a, b: a & b),
    ("or", lambda a, b: a | b),
    ("xor", lambda a, b: a ^ b),
    ("a_and_not_b", lambda a, b: a & (1 - b)),
    ("not_a_and_b", lambda a, b: (1 - a) & b),
    ("xnor", lambda a, b: 1 - (a ^ b)),
)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def trailing_zeros(value: int) -> int:
    return (value & -value).bit_length() - 1 if value else 0


def history_fields(operation, bits: int, nearest: bool
                   ) -> tuple[dict[str, int], dict[int, tuple[int, int]]]:
    stored = quantize(operation, bits, nearest)
    shift = max(0, operation.magnitude.bit_length() - bits)
    denominator = 1 << shift if shift else 1
    remainder = operation.magnitude & (denominator - 1) if shift else 0
    retained = operation.magnitude >> shift
    half = denominator >> 1 if shift else 0
    increment = int(stored.significand != retained)
    exact_value = Value(operation.sign, operation.exponent, operation.magnitude)
    direction = compare_values(stored, exact_value)
    fields: dict[str, int] = {
        "discarded.any": int(bool(remainder)),
        "discarded.none": int(not remainder),
        "discarded.all_ones": int(bool(shift) and remainder == denominator - 1),
        "discarded.half": int(bool(shift) and remainder == half),
        "discarded.below_half": int(bool(shift) and remainder < half),
        "discarded.above_half": int(bool(shift) and remainder > half),
        "round.increment": increment,
        "round.direction.down": int(direction < 0),
        "round.direction.exact": int(direction == 0),
        "round.direction.up": int(direction > 0),
        "retained.lsb": retained & 1,
        "shift.parity": shift & 1,
        "remainder.tz.parity": trailing_zeros(remainder) & 1,
    }
    for offset, name in ((1, "guard"), (2, "round")):
        fields[f"discarded.{name}"] = (
            (remainder >> (shift - offset)) & 1 if shift >= offset else 0)
    fields["discarded.sticky"] = int(
        shift > 2 and bool(remainder & ((1 << (shift - 2)) - 1)))

    words: dict[int, tuple[int, int]] = {}
    for width in range(1, 13):
        if shift >= width:
            top = remainder >> (shift - width)
        else:
            top = remainder << (width - shift)
        bottom = remainder & ((1 << width) - 1)
        words[width] = top, bottom
        mask = (1 << width) - 1
        for orientation, word in (("top", top), ("bottom", bottom)):
            prefix = f"discarded.{orientation}{width}"
            fields[f"{prefix}.zero"] = int(word == 0)
            fields[f"{prefix}.ones"] = int(word == mask)
            fields[f"{prefix}.parity"] = word.bit_count() & 1
            fields[f"{prefix}.onehot"] = int(word.bit_count() == 1)
            for bit in range(width):
                fields[f"{prefix}.b{bit}"] = (word >> bit) & 1
    return fields, words


def q_relations(prefix: str, q: int, words: dict[int, tuple[int, int]]
                ) -> dict[str, int]:
    result = {}
    for width, pair in words.items():
        mask = (1 << width) - 1
        scaled_q = q << max(0, width - 3)
        if width < 3:
            scaled_q = q >> (3 - width)
        scaled_q &= mask
        for orientation, word in (("top", pair[0]), ("bottom", pair[1])):
            name = f"{prefix}.{orientation}{width}.q"
            result[f"{name}.equal"] = int(word == scaled_q)
            result[f"{name}.ge"] = int(word >= scaled_q)
            result[f"{name}.same_half"] = int(
                ((word ^ scaled_q) & (1 << (width - 1))) == 0)
            result[f"{name}.add_carry"] = int(word + scaled_q > mask)
            result[f"{name}.sub_borrow"] = int(word < scaled_q)
            result[f"{name}.xor_parity"] = (word ^ scaled_q).bit_count() & 1
    return result


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

    records = []
    schema = None
    tuple_groups: dict[tuple[int, ...], list[int]] = defaultdict(list)
    for row in rows:
        operations = schedule(row)
        q = int(cut_fields(operations["negative.add2"], 64)["half_delta"])
        if not 5 <= q <= 7:
            raise RuntimeError(f"not a high-q row: {row['op']} q={q}")
        signals: dict[str, int] = {
            "current.q.b0": q & 1,
            "current.q.b1": (q >> 1) & 1,
            "current.q.b2": (q >> 2) & 1,
            "current.q.eq5": int(q == 5),
            "current.q.eq6": int(q == 6),
            "current.q.eq7": int(q == 7),
        }
        tuple_values = []
        for stage, (bits, nearest) in NATIVE.items():
            fields, words = history_fields(operations[stage], bits, nearest)
            for name, value in fields.items():
                signals[f"{stage}.{name}"] = value
            signals.update(q_relations(stage, q, words))
            tuple_values.extend(fields[name] for name in sorted(fields))
        if schema is None:
            schema = tuple(sorted(signals))
        elif tuple(sorted(signals)) != schema:
            raise RuntimeError("signal schema changed")
        wanted = labels[row["op"]]
        records.append((row["op"], wanted, signals))
        tuple_groups[tuple(tuple_values)].append(wanted)
    if schema is None:
        raise SystemExit("empty label set")

    target = tuple(record[1] for record in records)
    rankings = []
    exact_unary = []
    signatures: dict[tuple[int, ...], list[str]] = defaultdict(list)
    for name in schema:
        signature = tuple(record[2][name] for record in records)
        signatures[signature].append(name)
        for invert in (0, 1):
            prediction = tuple(value ^ invert for value in signature)
            errors = sum(a != b for a, b in zip(prediction, target))
            positive_errors = sum(
                wanted and predicted != wanted
                for predicted, wanted in zip(prediction, target))
            negative_errors = errors - positive_errors
            rankings.append((errors, positive_errors, negative_errors,
                             invert, name))
            if not errors:
                exact_unary.append((invert, name))
    rankings.sort()

    signature_items = list(signatures.items())
    exact_pairs = []
    pair_best = []
    for left_index, (left, left_names) in enumerate(signature_items):
        for right, right_names in signature_items[left_index:]:
            for gate_name, gate in GATES:
                prediction = tuple(gate(a, b) for a, b in zip(left, right))
                errors = sum(a != b for a, b in zip(prediction, target))
                item = (errors, gate_name, left_names[0], right_names[0])
                if errors == 0:
                    exact_pairs.append(item[1:])
                if len(pair_best) < 32 or item < pair_best[-1]:
                    pair_best.append(item)
                    pair_best.sort()
                    del pair_best[32:]

    collision_groups = sum(
        len(set(values)) > 1 for values in tuple_groups.values())
    collision_operands = sum(
        len(values) for values in tuple_groups.values()
        if len(set(values)) > 1)

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as output:
        for name, path in (
            ("model", args.model),
            ("causal_legs", args.causal_legs),
            ("sibling_labels", args.sibling_labels),
            ("direct_labels", args.direct_labels),
        ):
            output.write(f"{name}_sha256\t{digest(path)}\n")
        output.write("hardware_policy\tfrozen_factor_labels_no_x87_execution\n")
        output.write("candidate_policy\tpatent_motivated_attached_history_fields\n")
        output.write(f"operands\t{len(records)}\n")
        output.write(f"positive_operands\t{sum(target)}\n")
        output.write(f"boolean_signals\t{len(schema)}\n")
        output.write(f"distinct_signatures\t{len(signatures)}\n")
        output.write(f"exact_unary\t{len(exact_unary)}\n")
        output.write(f"exact_two_input\t{len(exact_pairs)}\n")
        output.write(f"complete_tuple_collision_groups\t{collision_groups}\n")
        output.write(f"complete_tuple_collision_operands\t{collision_operands}\n")
        output.write("\n[best unary]\n")
        output.write("errors\tpositive_errors\tnegative_errors\tinvert\tsignal\n")
        for item in rankings[:64]:
            output.write("\t".join(map(str, item)) + "\n")
        output.write("\n[exact unary]\n")
        for item in exact_unary:
            output.write("\t".join(map(str, item)) + "\n")
        output.write("\n[best two-input primitives]\n")
        output.write("errors\tgate\tleft\tright\n")
        for item in pair_best:
            output.write("\t".join(map(str, item)) + "\n")
        output.write("\n[exact two-input primitives]\n")
        for item in exact_pairs[:4096]:
            output.write("\t".join(map(str, item)) + "\n")
        if len(exact_pairs) > 4096:
            output.write(f"truncated\t{len(exact_pairs) - 4096}\n")

    print(
        f"wrote {args.report}: operands={len(records)} signals={len(schema)} "
        f"unary_exact={len(exact_unary)} pair_exact={len(exact_pairs)} "
        f"best_unary={rankings[0][0]} best_pair={pair_best[0][0]}",
        flush=True,
    )


if __name__ == "__main__":
    main()
