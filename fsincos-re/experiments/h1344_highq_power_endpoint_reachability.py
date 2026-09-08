#!/usr/bin/env python3
"""Diagnose per-operand reachability across fixed power representations.

h1343 finds three wider labels that no choice of adjacent lower/upper 65-bit
square and fourth endpoints can produce.  This audit identifies those rows
and, independently, enumerates the complete h1334 60--80-bit standard-mode
power grid to determine which global scalar representations can reach each
label.  Reachability is diagnostic only; per-operand schedule selection is
not a candidate model.

Hardware labels are immutable scoring inputs and this program executes no x87
instruction.
"""

from __future__ import annotations

import argparse
import hashlib
from collections import Counter
from pathlib import Path

from h1184_upstream_halfway_audit import multiply, row_value
from h1191_grs_history_isomorphism import magnitude_delta, quantize_mode
from h1210_stagea_residual_reframe import parse_dump, run
from h1316_highq_fixed_schedule_representations import load_direct
from h1332_highq_width_double_round_audit import MODES
from h1339_highq_custom_rounding_laws import factor_from_fourth
from h1342_highq_round_prefix_depth import quantize_forced


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

    reachability = {operand: [] for operand in operands}
    for square_width in range(60, 81):
        for square_mode in MODES:
            for fourth_width in range(60, 81):
                for fourth_mode in MODES:
                    schedule_name = (
                        f"{square_mode}{square_width}/"
                        f"{fourth_mode}{fourth_width}")
                    for operand, magnitude, baseline, _, _ in prepared:
                        square = quantize_mode(
                            multiply(magnitude, magnitude),
                            square_width, square_mode)
                        fourth = quantize_mode(
                            multiply(square, square),
                            fourth_width, fourth_mode)
                        delta = magnitude_delta(
                            factor_from_fourth(fourth), baseline)
                        if delta == -1:
                            reachability[operand].append(schedule_name)

    adjacent_rows = []
    impossible = []
    for operand, magnitude, baseline, wanted, bank in prepared:
        predictions = []
        deltas = []
        square_op = multiply(magnitude, magnitude)
        for square_increment in (0, 1):
            square = quantize_forced(square_op, 65, square_increment)
            fourth_op = multiply(square, square)
            for fourth_increment in (0, 1):
                fourth = quantize_forced(
                    fourth_op, 65, fourth_increment)
                delta = magnitude_delta(factor_from_fourth(fourth), baseline)
                predictions.append(int(delta == -1))
                deltas.append(delta)
        reachable = wanted in predictions
        if not reachable:
            impossible.append(operand)
        adjacent_rows.append((
            operand, wanted, bank, int(reachable),
            ",".join(map(str, predictions)),
            ",".join(map(str, deltas)),
            len(reachability[operand]),
            ",".join(reachability[operand][:16]) or "-",
        ))

    counts = Counter()
    for row in adjacent_rows:
        counts["adjacent65.impossible"] += not row[3]
        counts[f"adjacent65.impossible.label.{row[1]}"] += not row[3]
        counts[f"grid.reachable.label.{row[1]}"] += bool(row[6])

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as output:
        output.write(f"model_sha256\t{digest(args.model)}\n")
        for index, path in enumerate(args.direct_label):
            output.write(f"direct_labels_sha256.{index}\t{digest(path)}\n")
        output.write("hardware_policy\tfrozen_one_shot_labels_no_x87_execution\n")
        output.write("candidate_policy\tdiagnostic_power_endpoint_reachability\n")
        output.write(f"operands\t{len(prepared)}\n")
        output.write(f"positive_operands\t{sum(labels.values())}\n")
        output.write("standard_grid_schedules\t7056\n")
        for name, value in sorted(counts.items()):
            output.write(f"{name}\t{value}\n")
        output.write("\n[adjacent65 and standard-grid diagnostics]\n")
        output.write(
            "op\twanted_wide\tbank\tadjacent65_reachable\t"
            "predictions_s0f0_s0f1_s1f0_s1f1\t"
            "deltas_s0f0_s0f1_s1f0_s1f1\tgrid_wide_schedules\t"
            "first_grid_schedules\n")
        for item in adjacent_rows:
            output.write("\t".join(map(str, item)) + "\n")
        output.write("\n[adjacent65 impossible rows]\n")
        for operand in impossible:
            output.write(operand + "\n")

    print(
        f"wrote {args.report}: operands={len(prepared)} "
        f"adjacent65_impossible={len(impossible)} "
        f"grid_unreachable={sum(not reachability[operand] for operand in operands)}",
        flush=True,
    )


if __name__ == "__main__":
    main()
