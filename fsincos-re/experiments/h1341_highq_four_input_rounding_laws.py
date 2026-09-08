#!/usr/bin/env python3
"""Test a second discarded bit in the 65-bit power round controller.

h1340's best fixed two-edge controller copies a guard relation into the
65-bit square endpoint and then applies the observed RN65 fourth endpoint,
but misses six wider-factor labels.  The three-input grammar collapses every
bit below guard into one sticky flag.  This pass adds the conventional round
bit explicitly and moves sticky below it, exhausting all 65,536 fixed truth
tables over retained-LSB/guard/round/sticky at one power edge at a time while
holding the other at h1340's best law.

Equivalent value signatures are evaluated once.  No condition reads an
operand identity or hardware label; labels are immutable scoring inputs and
this program executes no x87 instruction.
"""

from __future__ import annotations

import argparse
import hashlib
from collections import Counter, defaultdict
from pathlib import Path

from h1184_upstream_halfway_audit import (
    ExactOperation,
    Value,
    multiply,
    row_value,
)
from h1191_grs_history_isomorphism import magnitude_delta
from h1210_stagea_residual_reframe import parse_dump, run
from h1316_highq_fixed_schedule_representations import load_direct
from h1339_highq_custom_rounding_laws import factor_from_fourth, quantize_law


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def quantize_law4(operation: ExactOperation, bits: int, law: int) -> Value:
    shift = max(0, operation.magnitude.bit_length() - bits)
    retained = operation.magnitude >> shift
    remainder = operation.magnitude & ((1 << shift) - 1) if shift else 0
    if remainder:
        guard = (remainder >> (shift - 1)) & 1
        round_bit = (remainder >> (shift - 2)) & 1 if shift >= 2 else 0
        sticky = int(
            shift > 2 and bool(remainder & ((1 << (shift - 2)) - 1)))
        index = (
            (retained & 1) | (guard << 1) | (round_bit << 2) | (sticky << 3))
        retained += (law >> index) & 1
    if retained == 1 << bits:
        retained >>= 1
        shift += 1
    return Value(operation.sign, operation.exponent + shift, retained)


def law_index(operation: ExactOperation, bits: int) -> int | None:
    shift = max(0, operation.magnitude.bit_length() - bits)
    remainder = operation.magnitude & ((1 << shift) - 1) if shift else 0
    if not remainder:
        return None
    retained = operation.magnitude >> shift
    guard = (remainder >> (shift - 1)) & 1
    round_bit = (remainder >> (shift - 2)) & 1 if shift >= 2 else 0
    sticky = int(
        shift > 2 and bool(remainder & ((1 << (shift - 2)) - 1)))
    return (
        (retained & 1) | (guard << 1) | (round_bit << 2) | (sticky << 3))


def equivalent_laws(operations: tuple[ExactOperation, ...]):
    indices = tuple(law_index(operation, 65) for operation in operations)
    groups = defaultdict(list)
    for law in range(1 << 16):
        decisions = tuple(
            0 if index is None else (law >> index) & 1
            for index in indices)
        groups[decisions].append(law)
    return groups


def score(prediction, deltas, prepared):
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
    return (
        counts["errors"], counts["bank1.errors"], counts["bank0.errors"],
        counts["positive_errors"], counts["negative_errors"],
        counts["predicted_positives"], counts["delta.-1"],
        counts["delta.0"],
        len(prepared) - counts["delta.-1"] - counts["delta.0"],
    )


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

    square_operations = tuple(
        multiply(magnitude, magnitude)
        for _, magnitude, _, _, _ in prepared)
    signature_aliases = defaultdict(list)

    square_law_groups = equivalent_laws(square_operations)
    for laws in square_law_groups.values():
        law = laws[0]
        prediction = []
        deltas = []
        for square_op, (_, _, baseline, _, _) in zip(
                square_operations, prepared):
            square = quantize_law4(square_op, 65, law)
            fourth = quantize_law(multiply(square, square), 65, 0x40)
            delta = magnitude_delta(factor_from_fourth(fourth), baseline)
            deltas.append(delta)
            prediction.append(int(delta == -1))
        signature_aliases[
            ("square_law4", tuple(prediction), tuple(deltas))
        ].extend(laws)

    fixed_squares = tuple(
        quantize_law(operation, 65, 0x60) for operation in square_operations)
    fourth_operations = tuple(
        multiply(square, square) for square in fixed_squares)
    fourth_law_groups = equivalent_laws(fourth_operations)
    for laws in fourth_law_groups.values():
        law = laws[0]
        prediction = []
        deltas = []
        for fourth_op, (_, _, baseline, _, _) in zip(
                fourth_operations, prepared):
            fourth = quantize_law4(fourth_op, 65, law)
            delta = magnitude_delta(factor_from_fourth(fourth), baseline)
            deltas.append(delta)
            prediction.append(int(delta == -1))
        signature_aliases[
            ("fourth_law4", tuple(prediction), tuple(deltas))
        ].extend(laws)

    scores = []
    exact = []
    best_rows = None
    for (family, prediction, deltas), laws in signature_aliases.items():
        base = score(prediction, deltas, prepared)
        item = (*base, family, len(laws), laws[0])
        scores.append(item)
        if not base[0]:
            exact.append((item, laws))
    scores.sort()
    best = scores[0]
    for (family, prediction, deltas), laws in signature_aliases.items():
        if family == best[9] and laws[0] == best[11]:
            best_rows = tuple(zip(prediction, deltas))
            break
    if best_rows is None:
        raise AssertionError("best signature not found")

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as output:
        output.write(f"model_sha256\t{digest(args.model)}\n")
        for index, path in enumerate(args.direct_label):
            output.write(f"direct_labels_sha256.{index}\t{digest(path)}\n")
        output.write("hardware_policy\tfrozen_one_shot_labels_no_x87_execution\n")
        output.write("candidate_policy\tfixed_65bit_lsb_guard_round_sticky_laws\n")
        output.write(f"operands\t{len(prepared)}\n")
        output.write(f"positive_operands\t{sum(labels.values())}\n")
        output.write("laws_per_edge\t65536\n")
        output.write("edge_families\t2\n")
        output.write(f"distinct_signatures\t{len(signature_aliases)}\n")
        output.write(f"exact_signatures\t{len(exact)}\n")
        output.write(
            "law_index\tretained_lsb|(guard<<1)|(round<<2)|(sticky<<3)\n")
        output.write("\n[ranking]\n")
        output.write(
            "errors\textension_errors\tolder_errors\tpositive_errors\t"
            "negative_errors\tpredicted_positives\tdelta_minus1\t"
            "delta_zero\tdelta_other\tfamily\tlaw_aliases\tfirst_law_hex\n")
        for item in scores:
            rendered = (*item[:-1], f"{item[-1]:04x}")
            output.write("\t".join(map(str, rendered)) + "\n")
        output.write("\n[best diagnostics]\n")
        output.write("op\twanted_wide\tpredicted_wide\tfactor_delta\tbank\n")
        for (operand, _, _, wanted, bank), (predicted, delta) in zip(
                prepared, best_rows):
            output.write(
                f"{operand}\t{wanted}\t{predicted}\t{delta}\t{bank}\n")
        output.write("\n[exact law aliases]\n")
        for item, laws in exact:
            output.write("score\t" + "\t".join(map(str, item)) + "\n")
            output.write("laws\t" + ",".join(f"{law:04x}" for law in laws) + "\n")

    print(
        f"wrote {args.report}: operands={len(prepared)} "
        f"signatures={len(signature_aliases)} exact={len(exact)} best={best}",
        flush=True,
    )


if __name__ == "__main__":
    main()
