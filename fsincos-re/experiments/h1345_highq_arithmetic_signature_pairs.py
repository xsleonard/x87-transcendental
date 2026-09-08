#!/usr/bin/env python3
"""Test Boolean compositions of complete power-carrier representations.

The 65-bit endpoint family cannot reach three wider labels, while every label
is reachable somewhere in the fixed 60--80-bit power grid.  A carry-save or
dual-path implementation can expose two arithmetic representatives rather
than one scalar value.  This audit therefore treats each global square/fourth
schedule as one complete Boolean response signature and exhausts the standard
two-input gates over distinct signatures.  It also includes the strongest
custom round-controller representatives from h1340/h1341.

This is an isomorphism search over global arithmetic recurrences, not an
operand table.  Any exact composition still requires a physical meaning and
a disjoint frozen challenge.  Hardware labels are immutable scoring inputs
and this program executes no x87 instruction.
"""

from __future__ import annotations

import argparse
import hashlib
from collections import defaultdict
from pathlib import Path

from h1184_upstream_halfway_audit import multiply, row_value
from h1191_grs_history_isomorphism import magnitude_delta, quantize_mode
from h1210_stagea_residual_reframe import parse_dump, run
from h1316_highq_fixed_schedule_representations import load_direct
from h1332_highq_width_double_round_audit import MODES
from h1339_highq_custom_rounding_laws import factor_from_fourth, quantize_law
from h1341_highq_four_input_rounding_laws import quantize_law4


GATES = (
    ("and", lambda a, b, mask: a & b),
    ("or", lambda a, b, mask: a | b),
    ("xor", lambda a, b, mask: a ^ b),
    ("a_and_not_b", lambda a, b, mask: a & (~b & mask)),
    ("not_a_and_b", lambda a, b, mask: (~a & mask) & b),
    ("nand", lambda a, b, mask: ~(a & b) & mask),
    ("nor", lambda a, b, mask: ~(a | b) & mask),
    ("xnor", lambda a, b, mask: ~(a ^ b) & mask),
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

    signature_names = defaultdict(list)
    for square_width in range(60, 81):
        for square_mode in MODES:
            squares = [
                quantize_mode(multiply(magnitude, magnitude),
                              square_width, square_mode)
                for _, magnitude, _, _, _ in prepared]
            for fourth_width in range(60, 81):
                for fourth_mode in MODES:
                    signature = 0
                    for index, (square, row) in enumerate(
                            zip(squares, prepared)):
                        fourth = quantize_mode(
                            multiply(square, square),
                            fourth_width, fourth_mode)
                        delta = magnitude_delta(
                            factor_from_fourth(fourth), row[2])
                        signature |= int(delta == -1) << index
                    signature_names[signature].append(
                        f"square.{square_mode}{square_width}."
                        f"fourth.{fourth_mode}{fourth_width}")

    custom_schedules = (
        ("custom3.square60.fourth40",
         lambda operation: quantize_law(operation, 65, 0x60),
         lambda operation: quantize_law(operation, 65, 0x40)),
        ("custom4.square60.fourth4000",
         lambda operation: quantize_law(operation, 65, 0x60),
         lambda operation: quantize_law4(operation, 65, 0x4000)),
    )
    for name, square_round, fourth_round in custom_schedules:
        signature = 0
        for index, (_, magnitude, baseline, _, _) in enumerate(prepared):
            square = square_round(multiply(magnitude, magnitude))
            fourth = fourth_round(multiply(square, square))
            delta = magnitude_delta(factor_from_fourth(fourth), baseline)
            signature |= int(delta == -1) << index
        signature_names[signature].append(name)

    signatures = sorted(signature_names)
    target = sum(row[3] << index for index, row in enumerate(prepared))
    mask = (1 << len(prepared)) - 1
    scores = []
    exact = []
    for left_index, left in enumerate(signatures):
        for right in signatures[left_index:]:
            for gate_name, gate in GATES:
                predicted = gate(left, right, mask)
                errors = (predicted ^ target).bit_count()
                false_negatives = (target & ~predicted & mask).bit_count()
                false_positives = (predicted & ~target & mask).bit_count()
                item = (
                    errors, false_negatives, false_positives,
                    predicted.bit_count(), gate_name,
                    len(signature_names[left]), signature_names[left][0],
                    len(signature_names[right]), signature_names[right][0],
                )
                if not errors:
                    exact.append(item[4:])
                if len(scores) < 1024 or item < scores[-1]:
                    scores.append(item)
                    scores.sort()
                    del scores[1024:]

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as output:
        output.write(f"model_sha256\t{digest(args.model)}\n")
        for index, path in enumerate(args.direct_label):
            output.write(f"direct_labels_sha256.{index}\t{digest(path)}\n")
        output.write("hardware_policy\tfrozen_one_shot_labels_no_x87_execution\n")
        output.write("candidate_policy\ttwo_global_arithmetic_signature_gates\n")
        output.write(f"operands\t{len(prepared)}\n")
        output.write(f"positive_operands\t{sum(labels.values())}\n")
        output.write("standard_schedules\t7056\n")
        output.write(f"custom_schedules\t{len(custom_schedules)}\n")
        output.write(f"distinct_signatures\t{len(signatures)}\n")
        output.write(f"exact_gates\t{len(exact)}\n")
        output.write("\n[best gates]\n")
        output.write(
            "errors\tfalse_negatives\tfalse_positives\t"
            "predicted_positives\tgate\tleft_aliases\tleft\t"
            "right_aliases\tright\n")
        for item in scores:
            output.write("\t".join(map(str, item)) + "\n")
        output.write("\n[exact gates]\n")
        output.write(
            "gate\tleft_aliases\tleft\tright_aliases\tright\n")
        for item in exact[:4096]:
            output.write("\t".join(map(str, item)) + "\n")
        if len(exact) > 4096:
            output.write(f"truncated\t{len(exact) - 4096}\n")

    print(
        f"wrote {args.report}: operands={len(prepared)} "
        f"signatures={len(signatures)} exact={len(exact)} "
        f"best={scores[0][:5]}",
        flush=True,
    )


if __name__ == "__main__":
    main()
