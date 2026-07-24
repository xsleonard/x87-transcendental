#!/usr/bin/env python3
"""Score Round 43 and the next h291 coordinate on fresh h292 hardware."""

from __future__ import annotations

import collections
import pathlib

import h58_constraint_search as h58
import h228_p6_four_term_c_parity as h228
import h283_trig_sine_bias_selector as h283
import h285_trig_sine_bias_discriminator as h285
import h286_ingest_trig_sine_bias_capture as h286


ROOT = pathlib.Path(__file__).resolve().parents[1]
CAPTURE = ROOT / "capture-kit-captures" / "skylake-trig-h292"
META = ROOT / "capture-kit" / "inputs" / "constraint_trig_sine_coordinates_h292.meta.txt"


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


def classes():
    return [
        line.split()[1]
        for line in META.read_text().splitlines()
        if line and not line.startswith("#")
    ]


def main() -> None:
    operands = [
        tuple(int(field, 16) for field in line.split())
        for line in (CAPTURE / "inputs.txt").read_text().splitlines()
    ]
    labels = classes()
    if len(labels) != len(operands):
        raise SystemExit("h292 input/metadata line counts differ")
    points = []
    for index, (se, sig) in enumerate(operands):
        point = h285.point_from_input(index, se, sig)
        if point is None:
            raise SystemExit(f"h292 line {index + 1} is not a table point")
        points.append(point)
    hardware = captures()

    for label in ("round43-direct", "next-coordinate"):
        indexes = [index for index, value in enumerate(labels) if value == label]
        print(f"{label}: inputs={len(indexes)}")
        observations = {}
        for candidate_name, candidate in (
            ("baseline-bias5", h228.CANDIDATE),
            ("candidate-bias3", h283.BIAS3),
        ):
            counts = collections.Counter()
            per_observation = {}
            for instruction in ("fsin", "fcos", "fsincos"):
                for rc in h58.RCS:
                    for index in indexes:
                        predicted, predicted_c1 = h286.expected(
                            points[index], candidate, instruction, rc
                        )
                        actual, actual_c1 = h286.hardware_values(
                            hardware[instruction][rc][index], instruction
                        )
                        result_misses = sum(
                            got != want for got, want in zip(predicted, actual)
                        )
                        c1_miss = (
                            not result_misses and predicted_c1 != actual_c1
                        )
                        counts[instruction, "result"] += result_misses
                        counts[instruction, "c1"] += c1_miss
                        counts["total", "result"] += result_misses
                        counts["total", "c1"] += c1_miss
                        per_observation[instruction, rc, index] = (
                            result_misses, c1_miss
                        )
            observations[candidate_name] = per_observation
            print(
                f"  {candidate_name}: result="
                f"{counts['total', 'result']}/{len(indexes) * 12} "
                f"C1={counts['total', 'c1']}/{len(indexes) * 9}"
            )
            for instruction in ("fsin", "fcos", "fsincos"):
                result_total = len(indexes) * (6 if instruction == "fsincos" else 3)
                print(
                    f"    {instruction}: result="
                    f"{counts[instruction, 'result']}/{result_total} "
                    f"C1={counts[instruction, 'c1']}/{len(indexes) * 3}"
                )

        changes = collections.Counter()
        for key, old in observations["baseline-bias5"].items():
            new = observations["candidate-bias3"][key]
            old_total = old[0] + int(old[1])
            new_total = new[0] + int(new[1])
            if new_total < old_total:
                changes["improved"] += 1
                changes["removed"] += old_total - new_total
            elif new_total > old_total:
                changes["regressed"] += 1
                changes["added"] += new_total - old_total
            elif new != old:
                changes["mixed"] += 1
        print(f"  changes={dict(changes)}")

    for index in range(len(points)):
        for rc in h58.RCS:
            fsin = hardware["fsin"][rc][index][0]
            fcos = hardware["fcos"][rc][index][0]
            pair = hardware["fsincos"][rc][index][:2]
            if pair != (fsin, fcos):
                raise SystemExit(
                    f"standalone/paired mismatch line {index + 1} {rc}"
                )
    print("standalone/paired results agree on all 1,536 lane-mode checks")


if __name__ == "__main__":
    main()
