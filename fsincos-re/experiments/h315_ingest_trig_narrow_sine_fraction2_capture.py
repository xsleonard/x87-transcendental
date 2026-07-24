#!/usr/bin/env python3
"""Score the second narrow carrier fraction on fresh h314 hardware."""

from __future__ import annotations

import pathlib

import h58_constraint_search as h58
import h286_ingest_trig_sine_bias_capture as h286
import h299_trig_sine_fractional_bias_grid as h299
import h307_trig_narrow_sine_fraction_discriminator as h307


ROOT = pathlib.Path(__file__).resolve().parents[1]
CAPTURE = ROOT / "capture-kit-captures" / "skylake-trig-h314"
CANDIDATES = tuple(range(16, 35))


def captures():
    result = {}
    for instruction in ("fsin", "fcos", "fsincos"):
        parser = h286.parse_pair if instruction == "fsincos" else h286.parse_single
        result[instruction] = {
            rc: [
                parser(line)
                for line in (
                    CAPTURE / f"{instruction}_{rc}_status.txt"
                ).read_text().splitlines()
            ]
            for rc in h58.RCS
        }
    return result


def point_error(point, hardware, index: int, numerator: int):
    result_errors = 0
    c1_errors = 0
    for instruction in ("fsin", "fcos", "fsincos"):
        for rc in h58.RCS:
            values, c1 = h299.predicted(point, numerator, instruction, rc)
            actual, actual_c1 = h286.hardware_values(
                hardware[instruction][rc][index], instruction
            )
            misses = sum(got != want for got, want in zip(values, actual))
            result_errors += misses
            c1_errors += int(not misses and c1 != actual_c1)
    return result_errors, c1_errors


def main() -> None:
    operands = [
        tuple(int(field, 16) for field in line.split())
        for line in (CAPTURE / "inputs.txt").read_text().splitlines()
    ]
    hardware = captures()
    points = []
    for index, (se, sig) in enumerate(operands):
        point = h307.point_from_input(index, se, sig)
        if point is None:
            raise SystemExit(f"h314 line {index + 1} is not narrow-table")
        points.append(point)
    if any(
        len(records) != len(points)
        for instruction in hardware.values()
        for records in instruction.values()
    ):
        raise SystemExit("h314 input/capture line counts differ")

    print(f"h315 second narrow fractional capture: inputs={len(points)}")
    for numerator in CANDIDATES:
        result_errors = 0
        c1_errors = 0
        for index, point in enumerate(points):
            result, c1 = point_error(point, hardware, index, numerator)
            result_errors += result
            c1_errors += c1
        print(
            f"  bias={numerator}/256: result={result_errors}/{len(points) * 12} "
            f"C1={c1_errors}/{len(points) * 9} "
            f"total={result_errors + c1_errors}"
        )

    for index in range(len(points)):
        for rc in h58.RCS:
            fsin = hardware["fsin"][rc][index][0]
            fcos = hardware["fcos"][rc][index][0]
            pair = hardware["fsincos"][rc][index][:2]
            if pair != (fsin, fcos):
                raise SystemExit(
                    f"standalone/paired mismatch line {index + 1} {rc}"
                )
    print(
        f"standalone/paired results agree on all {len(points) * 6} "
        "lane-mode checks"
    )


if __name__ == "__main__":
    main()
