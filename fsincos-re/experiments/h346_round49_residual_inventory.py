#!/usr/bin/env python3
"""Inventory every Round-49 paired-table residual in an existing corpus.

The structured sweep exposes only thirteen mismatching lane/mode results,
while the denser table corpus exposes a larger population.  This pass keeps
the arithmetic model fixed and reports the exact operand, lane, rounding
mode, path, cell, and one-step output direction for every residual.  It is
also the common seed source for the focused-neighborhood capture.
"""

from __future__ import annotations

import argparse
import collections
import dataclasses

import h58_constraint_search as h58
import h110_fsin_standalone as h110
import h228_p6_four_term_c_parity as h228
import h333_p6_carrier_metadata_semantics as h333


CANDIDATE = h333.CANDIDATES["interval-low1-last-interior"]


@dataclasses.dataclass(frozen=True)
class Residual:
    index: int
    se: int
    sig: int
    lane: str
    rc: str
    source: str
    family: str
    cell: int
    producer: str
    direction: int
    c1_mismatch: bool


def magnitude_rank(value: tuple[int, int]) -> tuple[int, int]:
    se, sig = value
    return se >> 15, ((se & 0x7FFF) << 64) + sig


def signed_step(
    predicted: tuple[int, int], expected: tuple[int, int]
) -> int:
    predicted_sign, predicted_rank = magnitude_rank(predicted)
    expected_sign, expected_rank = magnitude_rank(expected)
    if predicted_sign != expected_sign:
        raise AssertionError((predicted, expected))
    delta = predicted_rank - expected_rank
    return -delta if predicted_sign else delta


def inventory(scope: str) -> tuple[list, list[Residual]]:
    points = h228.points(scope)
    input_lines = h228.INPUTS[scope].read_text().splitlines()
    result: list[Residual] = []
    for point in points:
        observed = point.prepared.joint.observed
        prepared = observed.point
        se, sig = (
            int(field, 16)
            for field in input_lines[observed.index].split()
        )
        hidden = h333.hidden_values(point, CANDIDATE)
        outputs = (
            observed.outputs,
            point.prepared.joint.cosine_outputs,
        )
        c1_outputs = (
            observed.c1,
            point.prepared.joint.cosine_c1,
        )
        for lane_index, lane in enumerate(("sin", "cos")):
            for rc_index, rc in enumerate(h58.RCS):
                predicted = h58.x87_round(hidden[lane_index], rc)
                expected = outputs[lane_index][rc_index]
                predicted_c1 = (
                    h110.compare_magnitude(
                        predicted, hidden[lane_index]
                    )
                    > 0
                )
                c1_mismatch = (
                    predicted == expected
                    and predicted_c1 != c1_outputs[lane_index][rc_index]
                )
                if predicted == expected and not c1_mismatch:
                    continue
                producer = (
                    "cos-state"
                    if bool(observed.signed_n & 1) == (lane == "sin")
                    else "sin-state"
                )
                result.append(Residual(
                    observed.index,
                    se,
                    sig,
                    lane,
                    rc,
                    observed.source,
                    observed.family,
                    prepared.cell,
                    producer,
                    0 if predicted == expected else signed_step(predicted, expected),
                    c1_mismatch,
                ))
    return points, result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope", choices=tuple(h228.INPUTS), default="sweep")
    parser.add_argument("--details", action="store_true")
    args = parser.parse_args()

    points, records = inventory(args.scope)
    result_records = [record for record in records if record.direction]
    c1_records = [record for record in records if record.c1_mismatch]
    unique_inputs = {(record.se, record.sig) for record in records}
    print(
        f"h346 Round-49 inventory: scope={args.scope} points={len(points)} "
        f"result={len(result_records)} C1={len(c1_records)} "
        f"affected-inputs={len(unique_inputs)}"
    )

    fields = (
        ("lane", lambda record: record.lane),
        ("rc", lambda record: record.rc),
        ("source/family", lambda record: (record.source, record.family)),
        ("cell", lambda record: record.cell),
        ("producer", lambda record: record.producer),
        ("direction", lambda record: record.direction),
    )
    for name, key in fields:
        counts = collections.Counter(key(record) for record in result_records)
        print(f"  {name}: {dict(sorted(counts.items(), key=lambda item: str(item[0])))}")

    if args.details:
        for record in records:
            print(
                f"  index={record.index} input={record.se:04x}:{record.sig:016x} "
                f"lane={record.lane} rc={record.rc} "
                f"path={record.source}/{record.family}/cell{record.cell}/"
                f"{record.producer} step={record.direction:+d} "
                f"c1={int(record.c1_mismatch)}"
            )


if __name__ == "__main__":
    main()
