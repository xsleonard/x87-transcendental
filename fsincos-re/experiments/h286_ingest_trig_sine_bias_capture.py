#!/usr/bin/env python3
"""Score the h284 sine-bias rule on the fresh h285 Skylake capture."""

from __future__ import annotations

import collections
import pathlib

import h58_constraint_search as h58
import h110_fsin_standalone as h110
import h228_p6_four_term_c_parity as h228
import h230_p6_microop_materialization_search as h230
import h283_trig_sine_bias_selector as h283
import h285_trig_sine_bias_discriminator as h285


ROOT = pathlib.Path(__file__).resolve().parents[1]
CAPTURE = ROOT / "capture-kit-captures" / "skylake-trig-h285"


def parse_single(line: str):
    fields = line.split()
    if len(fields) != 5 or fields[0] != "OK" or fields[3] != "SW":
        raise ValueError(line)
    return (
        (int(fields[1], 16), int(fields[2], 16)),
        bool(int(fields[4], 16) & 0x0200),
    )


def parse_pair(line: str):
    fields = line.split()
    if len(fields) != 7 or fields[0] != "OK" or fields[5] != "SW":
        raise ValueError(line)
    return (
        (int(fields[1], 16), int(fields[2], 16)),
        (int(fields[3], 16), int(fields[4], 16)),
        bool(int(fields[6], 16) & 0x0200),
    )


def captures():
    result = {}
    for instruction in ("fsin", "fcos", "fsincos"):
        parser = parse_pair if instruction == "fsincos" else parse_single
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


def expected(point, candidate, instruction: str, rc: str):
    hidden = h230.hidden_values(point, candidate)
    rounded = tuple(h58.x87_round(value, rc) for value in hidden)
    increments = tuple(
        h110.compare_magnitude(output, value) > 0
        for output, value in zip(rounded, hidden)
    )
    if instruction == "fsin":
        return (rounded[0],), increments[0]
    if instruction == "fcos":
        return (rounded[1],), increments[1]
    return rounded, increments[1]


def hardware_values(record, instruction: str):
    if instruction == "fsincos":
        return record[:2], record[2]
    return (record[0],), record[1]


def main() -> None:
    operands = [
        tuple(int(field, 16) for field in line.split())
        for line in (CAPTURE / "inputs.txt").read_text().splitlines()
    ]
    points = []
    for index, (se, sig) in enumerate(operands):
        point = h285.point_from_input(index, se, sig)
        if point is None or not h285.selected(point):
            raise SystemExit(f"h285 input {index + 1} is not selected")
        points.append(point)
    hardware = captures()
    if any(
        len(records) != len(points)
        for instruction in hardware.values()
        for records in instruction.values()
    ):
        raise SystemExit("h285 input/capture line counts differ")

    candidates = (
        ("baseline-bias5", h228.CANDIDATE),
        ("candidate-bias3", h283.BIAS3),
    )
    scores = {}
    observation = {}
    for name, candidate in candidates:
        counts = collections.Counter()
        observations = {}
        for instruction in ("fsin", "fcos", "fsincos"):
            for rc in h58.RCS:
                for index, point in enumerate(points):
                    predicted, predicted_c1 = expected(
                        point, candidate, instruction, rc
                    )
                    actual, actual_c1 = hardware_values(
                        hardware[instruction][rc][index], instruction
                    )
                    result_misses = sum(
                        got != want for got, want in zip(predicted, actual)
                    )
                    c1_miss = not result_misses and predicted_c1 != actual_c1
                    counts[instruction, "result"] += result_misses
                    counts[instruction, "c1"] += c1_miss
                    counts["total", "result"] += result_misses
                    counts["total", "c1"] += c1_miss
                    observations[instruction, rc, index] = (
                        result_misses, c1_miss
                    )
        scores[name] = counts
        observation[name] = observations
        print(
            f"{name}: total result={counts['total', 'result']}/2304 "
            f"C1={counts['total', 'c1']}/1728"
        )
        for instruction in ("fsin", "fcos", "fsincos"):
            denominator = 1152 if instruction == "fsincos" else 576
            print(
                f"  {instruction}: result="
                f"{counts[instruction, 'result']}/{denominator} "
                f"C1={counts[instruction, 'c1']}/576"
            )

    changes = collections.Counter()
    for key, old in observation["baseline-bias5"].items():
        new = observation["candidate-bias3"][key]
        old_total = old[0] + int(old[1])
        new_total = new[0] + int(new[1])
        if new_total < old_total:
            changes["improved-observations"] += 1
            changes["removed-errors"] += old_total - new_total
        elif new_total > old_total:
            changes["regressed-observations"] += 1
            changes["added-errors"] += new_total - old_total
        elif new != old:
            changes["mixed-observations"] += 1
    print(f"candidate changes={dict(changes)}")

    for index in range(len(points)):
        for rc in h58.RCS:
            fsin = hardware["fsin"][rc][index][0]
            fcos = hardware["fcos"][rc][index][0]
            pair = hardware["fsincos"][rc][index][:2]
            if pair != (fsin, fcos):
                raise SystemExit(
                    f"standalone/paired result mismatch line {index + 1} {rc}"
                )
    print("standalone/paired results agree on all 1,152 lane-mode checks")


if __name__ == "__main__":
    main()
