#!/usr/bin/env python3
"""Stream-compare the million-input h349 FSINCOS capture with C outputs."""

from __future__ import annotations

import argparse
import collections
import contextlib
import pathlib


RCS = ("rn", "rd", "ru")


def parse_hardware(line: str):
    fields = line.split()
    if len(fields) != 7 or fields[0] != "OK" or fields[5] != "SW":
        raise ValueError(line)
    return (
        (int(fields[1], 16), int(fields[2], 16)),
        (int(fields[3], 16), int(fields[4], 16)),
        int(fields[6], 16),
    )


def parse_model(line: str):
    fields = line.split()
    if len(fields) != 5 or fields[0] != "OK":
        raise ValueError(line)
    return (
        (int(fields[1], 16), int(fields[2], 16)),
        (int(fields[3], 16), int(fields[4], 16)),
    )


def magnitude_rank(value):
    se, sig = value
    return se >> 15, ((se & 0x7FFF) << 64) + sig


def signed_step(predicted, expected):
    predicted_sign, predicted_rank = magnitude_rank(predicted)
    expected_sign, expected_rank = magnitude_rank(expected)
    if predicted_sign != expected_sign:
        return "sign"
    delta = predicted_rank - expected_rank
    return -delta if predicted_sign else delta


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", type=pathlib.Path)
    parser.add_argument("capture", type=pathlib.Path)
    parser.add_argument("model_outputs", type=pathlib.Path)
    parser.add_argument("--residuals", type=pathlib.Path)
    parser.add_argument("--mismatch-inputs", type=pathlib.Path)
    args = parser.parse_args()

    counts = collections.Counter()
    mismatching_inputs = set()
    with contextlib.ExitStack() as stack:
        inputs = stack.enter_context(args.inputs.open())
        hardware = {
            rc: stack.enter_context(
                (args.capture / f"fsincos_{rc}_status.txt").open()
            )
            for rc in RCS
        }
        models = {
            rc: stack.enter_context(
                (args.model_outputs / f"fsincos_{rc}.txt").open()
            )
            for rc in RCS
        }
        residuals = (
            stack.enter_context(args.residuals.open("w"))
            if args.residuals else None
        )
        if residuals:
            residuals.write(
                "# index se sig rc lane hw_se hw_sig model_se model_sig sw step\n"
            )
        for index, input_line in enumerate(inputs):
            se, sig = (int(field, 16) for field in input_line.split())
            for rc in RCS:
                hardware_pair = parse_hardware(hardware[rc].readline())
                model_pair = parse_model(models[rc].readline())
                for lane_index, lane in enumerate(("sin", "cos")):
                    expected = hardware_pair[lane_index]
                    predicted = model_pair[lane_index]
                    if predicted == expected:
                        continue
                    step = signed_step(predicted, expected)
                    counts["result"] += 1
                    counts["lane", lane] += 1
                    counts["rc", rc] += 1
                    counts["step", step] += 1
                    mismatching_inputs.add((se, sig))
                    if residuals:
                        step_text = str(step)
                        residuals.write(
                            f"{index} {se:04x} {sig:016x} {rc} {lane} "
                            f"{expected[0]:04x} {expected[1]:016x} "
                            f"{predicted[0]:04x} {predicted[1]:016x} "
                            f"{hardware_pair[2]:04x} {step_text}\n"
                        )
        total = index + 1
        for rc in RCS:
            if hardware[rc].readline() or models[rc].readline():
                raise SystemExit(f"h350 long {rc} result file")

    if args.mismatch_inputs:
        args.mismatch_inputs.write_text(
            "".join(
                f"{se:04x} {sig:016x}\n"
                for se, sig in sorted(mismatching_inputs)
            )
        )
    print(
        f"h350 Round-49 broad scan: result={counts['result']}/{total * 6} "
        f"affected-inputs={len(mismatching_inputs)}/{total}"
    )
    for prefix in ("lane", "rc", "step"):
        selected = {
            key[1]: value
            for key, value in counts.items()
            if isinstance(key, tuple) and key[0] == prefix
        }
        print(f"  {prefix}: {dict(sorted(selected.items(), key=lambda item: str(item[0])))}")


if __name__ == "__main__":
    main()
