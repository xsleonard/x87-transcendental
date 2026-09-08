#!/usr/bin/env python3
"""Test literal 64+G+R+S encodings of the recovered 67-bit carriers.

The current arithmetic model treats an internal 67-bit product carrier as
67 ordinary value bits.  Intel's contemporary FADD documentation instead
describes a 68-bit FAMUBUS containing overflow, a 64-bit significand, and
guard/round/sticky fields.  Those representations agree in their first 66
value bits but differ in the last one: the bus S field is the OR of every
remaining exact product bit.

This audit tests that fixed representation directly.  It first replaces only
the negative.mul2 producer consumed by the open high-q FADD, then enumerates
which of the four earlier product materializations use the same literal bus
encoding.  The enumeration is over architectural routing points, not operand
identities, thresholds, or learned predicates.  Frozen factor labels are used
only for scoring; no x87 instruction is executed.
"""

from __future__ import annotations

import argparse
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
from h1210_stagea_residual_reframe import parse_dump, run
from h1316_highq_fixed_schedule_representations import (
    load_causal,
    load_direct,
    load_siblings,
)


PRODUCT_STAGES = ("square", "fourth", "negative.mul1", "negative.mul2")


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def famubus_grs(operation: ExactOperation) -> Value:
    """Encode exact product as 64 value bits, exact G/R, and OR-reduced S."""
    shift = max(0, operation.magnitude.bit_length() - 67)
    if not shift:
        return Value(operation.sign, operation.exponent, operation.magnitude)
    retained = operation.magnitude >> shift
    # The ordinary 67th bit is replaced by sticky over itself and everything
    # below it.  Equivalently, keep the leading 66 bits and append S.
    leading66 = retained >> 1
    discarded = operation.magnitude & ((1 << (shift + 1)) - 1)
    encoded = (leading66 << 1) | int(bool(discarded))
    return Value(operation.sign, operation.exponent + shift, encoded)


def materialize_product(operation: ExactOperation, use_grs: bool) -> Value:
    return famubus_grs(operation) if use_grs else quantize(operation, 67, False)


def negative_factor(row: dict[str, str], grs_mask: int) -> Value:
    """Replay the negative Horner chain under a fixed GRS routing mask."""
    magnitude = row_value(row, "mag")
    square_op = multiply(magnitude, magnitude)
    square = materialize_product(square_op, bool(grs_mask & 1))
    fourth_op = multiply(square, square)
    fourth = materialize_product(fourth_op, bool(grs_mask & 2))

    mul1_op = multiply(fourth, Value(*CONSTANTS[5]))
    mul1 = materialize_product(mul1_op, bool(grs_mask & 4))
    add1_op = add_same_sign(Value(*CONSTANTS[3]), mul1)
    add1 = quantize(add1_op, 64, True)

    mul2_op = multiply(fourth, add1)
    mul2 = materialize_product(mul2_op, bool(grs_mask & 8))
    add2_op = add_same_sign(Value(*CONSTANTS[1]), mul2)
    return quantize(add2_op, 64, True)


def mask_name(mask: int) -> str:
    active = [stage for index, stage in enumerate(PRODUCT_STAGES)
              if mask & (1 << index)]
    return "+".join(active) if active else "literal67"


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

    scores = []
    diagnostics = []
    for mask in range(1 << len(PRODUCT_STAGES)):
        counts = Counter()
        deltas = []
        for row in rows:
            # Assert that the source dump still follows the recovered graph.
            schedule(row)
            baseline = row_value(row, "lf")
            candidate = negative_factor(row, mask)
            delta = magnitude_delta(candidate, baseline)
            predicted = int(delta == -1)
            wanted = labels[row["op"]]
            counts["errors"] += predicted != wanted
            counts["positive_errors"] += wanted and not predicted
            counts["negative_errors"] += not wanted and predicted
            counts[f"delta.{delta}"] += 1
            deltas.append((row["op"], wanted, delta))
        scores.append((
            counts["errors"], counts["positive_errors"],
            counts["negative_errors"], counts["delta.-1"],
            counts["delta.0"], counts["delta.1"], mask_name(mask), mask,
        ))
        if mask in (8, 15):
            diagnostics.extend((mask_name(mask),) + item for item in deltas)
    scores.sort()

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as target:
        for name, path in (
            ("model", args.model),
            ("causal_legs", args.causal_legs),
            ("sibling_labels", args.sibling_labels),
            ("direct_labels", args.direct_labels),
        ):
            target.write(f"{name}_sha256\t{digest(path)}\n")
        target.write("hardware_policy\tfrozen_factor_labels_no_x87_execution\n")
        target.write("candidate_policy\tliteral_64_plus_GRS_bus_routing_masks\n")
        target.write(f"operands\t{len(rows)}\n")
        target.write(f"positive_operands\t{sum(labels.values())}\n")
        target.write(f"routing_masks\t{len(scores)}\n")
        target.write(f"exact_masks\t{sum(score[0] == 0 for score in scores)}\n")
        target.write("\n[ranking]\n")
        target.write(
            "errors\tpositive_errors\tnegative_errors\tdelta_minus1\t"
            "delta_zero\tdelta_plus1\trouting\tmask\n")
        for score in scores:
            target.write("\t".join(map(str, score)) + "\n")
        target.write("\n[local-and-recursive diagnostics]\n")
        target.write("routing\top\twanted_wide\tfactor_delta\n")
        for item in diagnostics:
            target.write("\t".join(map(str, item)) + "\n")

    print(
        f"wrote {args.report}: operands={len(rows)} exact="
        f"{sum(score[0] == 0 for score in scores)} best={scores[0]}",
        flush=True,
    )


if __name__ == "__main__":
    main()
