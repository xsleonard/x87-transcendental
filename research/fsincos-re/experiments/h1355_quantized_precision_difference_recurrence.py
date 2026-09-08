#!/usr/bin/env python3
"""Test finite signed precision-difference registers on the high-q graph.

US 5,612,909 allows an attached history to encode a multi-bit precision
difference, not just a direction.  The exact recursive difference tested in
h1320 never crosses the final midpoint, but a finite hardware register need
not retain that exact dyadic value.  This audit models every dependency as

    (stored numeric value, quantized signed difference from that value).

The stored values follow the recovered chop67/RN64 schedule exactly.  The
difference is propagated through multiplication/addition, rounded to a fixed
fractional-ulp grid, optionally saturated to a fixed ulp range, and attached
to the stored result.  The final negative FADD rounds the value corrected by
the incoming difference.  FMUL and FADD may use independent, globally fixed
register formats.  No operand predicate, lookup table, or learned threshold
is present.

This exhausts a bounded structural grammar.  An exact recurrence would still
require a physical encoding argument and frozen blind validation.  Hardware
labels are immutable inputs; no x87 instruction is executed.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
from collections import Counter
from pathlib import Path

from h1184_upstream_halfway_audit import (
    CONSTANTS,
    ExactOperation,
    Value,
    add_same_sign,
    multiply,
    quantize,
    row_value,
    schedule,
)
from h1191_grs_history_isomorphism import magnitude_delta
from h1192_precision_difference_recurrence import (
    Dyad,
    difference,
    dyad_add,
    dyad_mul,
    dyad_quantize,
    dyad_value,
)
from h1210_stagea_residual_reframe import parse_dump, run
from h1353_upstream_cpa_word_relations import load_labels


ROUND_MODES = ("floor", "ceil", "trunc", "away", "rn")
FRACTION_BITS = range(0, 9)
RANGE_ULPS = (0, 1, 2, 4)


@dataclasses.dataclass(frozen=True)
class TagFormat:
    fraction_bits: int
    mode: str
    range_ulps: int

    def name(self) -> str:
        limit = "unbounded" if self.range_ulps == 0 else f"sat{self.range_ulps}u"
        return f"q{self.fraction_bits}.{self.mode}.{limit}"


@dataclasses.dataclass(frozen=True)
class HistoryValue:
    value: Value
    difference: Dyad


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def round_ratio(numerator: int, denominator: int, mode: str) -> int:
    if denominator <= 0:
        raise ValueError("denominator must be positive")
    if numerator % denominator == 0:
        return numerator // denominator
    if mode == "floor":
        return numerator // denominator
    if mode == "ceil":
        return -((-numerator) // denominator)
    sign = -1 if numerator < 0 else 1
    quotient, remainder = divmod(abs(numerator), denominator)
    if mode == "trunc":
        increment = 0
    elif mode == "away":
        increment = 1
    elif mode == "rn":
        doubled = 2 * remainder
        increment = int(
            doubled > denominator
            or (doubled == denominator and quotient & 1))
    else:
        raise ValueError(mode)
    return sign * (quotient + increment)


def quantize_difference(
        value: Dyad, stored: Value, fmt: TagFormat) -> Dyad:
    grid_exponent = stored.exponent - fmt.fraction_bits
    shift = value.exponent - grid_exponent
    if shift >= 0:
        code = value.numerator << shift
    else:
        code = round_ratio(value.numerator, 1 << -shift, fmt.mode)
    if fmt.range_ulps:
        limit = fmt.range_ulps << fmt.fraction_bits
        code = max(-limit, min(limit, code))
    return Dyad(code, grid_exponent)


def estimated(source: HistoryValue) -> Dyad:
    return dyad_add(dyad_value(source.value), source.difference)


def exact_source(value: Value) -> HistoryValue:
    return HistoryValue(value, Dyad(0, value.exponent))


def materialize(
        operation: ExactOperation, estimate: Dyad, bits: int, nearest: bool,
        fmt: TagFormat) -> HistoryValue:
    stored = quantize(operation, bits, nearest)
    raw_difference = difference(estimate, dyad_value(stored))
    return HistoryValue(
        stored, quantize_difference(raw_difference, stored, fmt))


def multiply_history(
        left: HistoryValue, right: HistoryValue, bits: int,
        nearest: bool, fmt: TagFormat) -> HistoryValue:
    operation = multiply(left.value, right.value)
    estimate = dyad_mul(estimated(left), estimated(right))
    return materialize(operation, estimate, bits, nearest, fmt)


def add_history(
        left: HistoryValue, right: HistoryValue, bits: int,
        nearest: bool, fmt: TagFormat) -> HistoryValue:
    operation = add_same_sign(left.value, right.value)
    estimate = dyad_add(estimated(left), estimated(right))
    return materialize(operation, estimate, bits, nearest, fmt)


def candidate_factor(
        magnitude: Value, mul_format: TagFormat,
        add_format: TagFormat) -> tuple[Value, Dyad]:
    mag = exact_source(magnitude)
    c1 = exact_source(Value(*CONSTANTS[1]))
    c3 = exact_source(Value(*CONSTANTS[3]))
    c5 = exact_source(Value(*CONSTANTS[5]))

    square = multiply_history(mag, mag, 67, False, mul_format)
    fourth = multiply_history(square, square, 67, False, mul_format)
    mul1 = multiply_history(fourth, c5, 67, False, mul_format)
    add1 = add_history(c3, mul1, 64, True, add_format)
    mul2 = multiply_history(fourth, add1, 67, False, mul_format)
    corrected_add2 = dyad_add(estimated(c1), estimated(mul2))
    return dyad_quantize(corrected_add2, 64, True), mul2.difference


def formats() -> tuple[TagFormat, ...]:
    return tuple(
        TagFormat(fraction_bits, mode, range_ulps)
        for fraction_bits in FRACTION_BITS
        for mode in ROUND_MODES
        for range_ulps in RANGE_ULPS
    )


def score(prepared, mul_format: TagFormat, add_format: TagFormat):
    counts = Counter()
    diagnostics = []
    for operand, magnitude, baseline, wanted, bank in prepared:
        candidate, incoming_difference = candidate_factor(
            magnitude, mul_format, add_format)
        delta = magnitude_delta(candidate, baseline)
        predicted = int(delta == -1)
        wrong = predicted != wanted
        counts["errors"] += wrong
        counts["positive_errors"] += wrong and wanted
        counts["negative_errors"] += wrong and not wanted
        counts["predicted_positives"] += predicted
        counts[f"bank{bank}.errors"] += wrong
        counts[f"delta.{delta}"] += 1
        diagnostics.append((
            operand, wanted, predicted, delta, bank,
            incoming_difference.numerator, incoming_difference.exponent,
        ))
    item = (
        counts["errors"], counts["positive_errors"],
        counts["negative_errors"], counts["predicted_positives"],
        *(counts[f"bank{bank}.errors"] for bank in range(3)),
        counts["delta.-1"], counts["delta.0"],
        len(prepared) - counts["delta.-1"] - counts["delta.0"],
        mul_format.name(), add_format.name(),
    )
    return item, diagnostics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument(
        "--direct-label", action="append", type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    labels, banks = load_labels(args.direct_label)
    operands = sorted(labels)
    _, stderr = run(args.model, "rn", operands, dump=True)
    rows = parse_dump(stderr, operands)
    prepared = []
    for row in rows:
        schedule(row)
        prepared.append((
            row["op"], row_value(row, "mag"), row_value(row, "lf"),
            labels[row["op"]], banks[row["op"]],
        ))

    format_list = formats()
    uniform_scores = []
    uniform_diagnostics = {}
    for fmt in format_list:
        item, diagnostics = score(prepared, fmt, fmt)
        uniform_scores.append(item)
        uniform_diagnostics[fmt.name()] = diagnostics
    uniform_scores.sort()

    # Cross the eight best distinct FMUL and FADD formats from the uniform
    # census.  This keeps the independent-format refinement bounded and fixed
    # without exploding into an operand-conditioned program search.
    format_by_name = {fmt.name(): fmt for fmt in format_list}
    refinement_names = []
    for item in uniform_scores:
        name = item[-1]
        if name not in refinement_names:
            refinement_names.append(name)
        if len(refinement_names) == 8:
            break
    refinement_formats = [format_by_name[name] for name in refinement_names]
    refined_scores = []
    refined_diagnostics = {}
    for mul_format in refinement_formats:
        for add_format in refinement_formats:
            item, diagnostics = score(prepared, mul_format, add_format)
            refined_scores.append(item)
            refined_diagnostics[(mul_format.name(), add_format.name())] = diagnostics
    refined_scores.sort()
    best = min(uniform_scores[0], refined_scores[0])
    if best in refined_scores:
        best_diagnostics = refined_diagnostics[(best[-2], best[-1])]
    else:
        best_diagnostics = uniform_diagnostics[best[-1]]

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as output:
        output.write(f"model_sha256\t{digest(args.model)}\n")
        for index, path in enumerate(args.direct_label):
            output.write(f"direct_labels_sha256.{index}\t{digest(path)}\n")
        output.write("hardware_policy\tfrozen_one_shot_labels_no_x87_execution\n")
        output.write(
            "candidate_policy\tfinite_signed_precision_difference_recurrence\n")
        output.write(f"operands\t{len(prepared)}\n")
        output.write(f"positive_operands\t{sum(labels.values())}\n")
        output.write(f"uniform_formats\t{len(format_list)}\n")
        output.write(f"refinement_formats\t{len(refinement_formats)}\n")
        output.write(f"refined_pairs\t{len(refined_scores)}\n")
        output.write(
            f"exact_candidates\t"
            f"{sum(not item[0] for item in uniform_scores + refined_scores)}\n")
        output.write("difference_sign\tsigned_numeric_estimate_minus_stored\n")
        output.write("\n[uniform ranking]\n")
        output.write(
            "errors\tpositive_errors\tnegative_errors\t"
            "predicted_positives\tbank0_errors\tbank1_errors\t"
            "bank2_errors\tdelta_minus1\tdelta_zero\tdelta_other\t"
            "mul_format\tadd_format\n")
        for item in uniform_scores:
            output.write("\t".join(map(str, item)) + "\n")
        output.write("\n[refined ranking]\n")
        for item in refined_scores:
            output.write("\t".join(map(str, item)) + "\n")
        output.write("\n[best diagnostics]\n")
        output.write(
            "op\twanted_wide\tpredicted_wide\tfactor_delta\tbank\t"
            "incoming_difference_code\tincoming_difference_exponent\n")
        for diagnostic in best_diagnostics:
            output.write("\t".join(map(str, diagnostic)) + "\n")

    print(
        f"wrote {args.report}: operands={len(prepared)} "
        f"uniform={len(uniform_scores)} refined={len(refined_scores)} "
        f"exact={sum(not item[0] for item in uniform_scores + refined_scores)} "
        f"best={best}",
        flush=True,
    )


if __name__ == "__main__":
    main()
