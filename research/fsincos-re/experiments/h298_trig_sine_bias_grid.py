#!/usr/bin/env python3
"""Measure every small shared-sine carrier bias on the h292 capture."""

from __future__ import annotations

import collections
import dataclasses

import h58_constraint_search as h58
import h228_p6_four_term_c_parity as h228
import h283_trig_sine_bias_selector as h283
import h285_trig_sine_bias_discriminator as h285
import h286_ingest_trig_sine_bias_capture as h286
import h293_ingest_trig_coordinate_capture as h293


BIASES = tuple(range(9))


def observation_error(point, hardware, index: int, bias: int):
    candidate = dataclasses.replace(h228.CANDIDATE, sine_bias=bias)
    result_errors = 0
    c1_errors = 0
    for instruction in ("fsin", "fcos", "fsincos"):
        for rc in h58.RCS:
            predicted, predicted_c1 = h286.expected(
                point, candidate, instruction, rc
            )
            actual, actual_c1 = h286.hardware_values(
                hardware[instruction][rc][index], instruction
            )
            misses = sum(
                got != want for got, want in zip(predicted, actual)
            )
            result_errors += misses
            c1_errors += int(not misses and predicted_c1 != actual_c1)
    return result_errors, c1_errors


def main() -> None:
    operands = [
        tuple(int(field, 16) for field in line.split())
        for line in (h293.CAPTURE / "inputs.txt").read_text().splitlines()
    ]
    labels = h293.classes()
    hardware = h293.captures()
    points = []
    for index, (se, sig) in enumerate(operands):
        point = h285.point_from_input(index, se, sig)
        if point is None:
            raise SystemExit(f"h292 line {index + 1} is not a table point")
        points.append(point)

    errors = {}
    for bias in BIASES:
        for index, point in enumerate(points):
            errors[bias, index] = observation_error(
                point, hardware, index, bias
            )

    for label in ("round43-direct", "next-coordinate"):
        indexes = [index for index, value in enumerate(labels) if value == label]
        print(f"{label}: inputs={len(indexes)}")
        for bias in BIASES:
            result_errors = sum(errors[bias, index][0] for index in indexes)
            c1_errors = sum(errors[bias, index][1] for index in indexes)
            print(
                f"  bias={bias}: result={result_errors}/1536 "
                f"C1={c1_errors}/1152 total={result_errors + c1_errors}"
            )

        winners = collections.Counter()
        unique = collections.Counter()
        for index in indexes:
            scores = {
                bias: sum(errors[bias, index]) for bias in BIASES
            }
            best = min(scores.values())
            best_biases = tuple(
                bias for bias, score in scores.items() if score == best
            )
            winners[best_biases] += 1
            if len(best_biases) == 1:
                unique[best_biases[0]] += 1
        print(f"  pointwise winner sets={dict(sorted(winners.items()))}")
        print(f"  unique winners={dict(sorted(unique.items()))}")


if __name__ == "__main__":
    main()
