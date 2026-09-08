#!/usr/bin/env python3
"""Compare the standalone-FSIN C model with an FSIN hardware capture."""

from __future__ import annotations

import argparse
import collections
import pathlib
import subprocess


RCS = ("rn", "rd", "ru")
FLAGS = (
    "--batch",
    "--round18-poly",
    "--round21-table-bias",
    "--round23-narrow-coefficient",
    "--round24-table-delta-rn67",
    "--round29-p5-fmul-route",
    "--round30-fsin-cosine-square",
    "--round31-fsin-cosine-tail",
    "--round32-fsin-cosine-horner",
    "--round33-fsin-cosine-product",
    "--round34-table-lookup-firc",
    "--round35-table-p-terminal",
    "--round36-table-fadd-microcontrol",
    "--round37-p6-four-term",
    "--round38-p6-cosine-split",
    "--round39-fcos-tiny",
    "--round40-fsincos-tiny",
    "--round41-fsin-cosine-split",
    "--round42-p6-sine-split",
    "--round43-p6-sine-bias",
    "--round44-p6-sine-bias",
    "--round45-p6-sine-fraction",
    "--round46-p6-narrow-sine-fraction",
    "--round47-p6-narrow-sine-fraction",
    "--round48-p6-narrow-sine-fraction",
    "--round49-p6-carrier-interval",
    "--fsin-standalone",
)


def parse_value(line: str, hardware: bool) -> tuple[int, int] | tuple[str]:
    fields = line.split()
    if fields[0] == "C2":
        if hardware and (len(fields) != 3 or fields[1] != "SW"):
            raise ValueError(line)
        if not hardware and len(fields) != 1:
            raise ValueError(line)
        return ("C2",)
    expected = 5 if hardware else 3
    if len(fields) != expected or fields[0] != "OK":
        raise ValueError(line)
    if hardware and fields[3] != "SW":
        raise ValueError(line)
    return int(fields[1], 16), int(fields[2], 16)


def signed_step(predicted: tuple[int, int], expected: tuple[int, int]):
    predicted_se, predicted_sig = predicted
    expected_se, expected_sig = expected
    predicted_sign = predicted_se >> 15
    expected_sign = expected_se >> 15
    if predicted_sign != expected_sign:
        return "sign"
    predicted_rank = ((predicted_se & 0x7FFF) << 64) + predicted_sig
    expected_rank = ((expected_se & 0x7FFF) << 64) + expected_sig
    delta = predicted_rank - expected_rank
    return -delta if predicted_sign else delta


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", type=pathlib.Path)
    parser.add_argument("inputs", type=pathlib.Path)
    parser.add_argument("capture", type=pathlib.Path)
    parser.add_argument("--capture-stem", default="fsin")
    parser.add_argument("--model-output-directory", type=pathlib.Path)
    parser.add_argument("--extra-flag", action="append", default=[])
    parser.add_argument("--show-misses", type=int, default=0)
    args = parser.parse_args()

    input_text = args.inputs.read_text()
    total_inputs = len(input_text.splitlines())
    counts: collections.Counter[object] = collections.Counter()
    affected: set[int] = set()

    for rc in RCS:
        if args.model_output_directory:
            model_lines = (
                args.model_output_directory / f"fsin_{rc}.txt"
            ).read_text().splitlines()
        else:
            command = [str(args.model.resolve()), *FLAGS, *args.extra_flag]
            if rc != "rn":
                command.append(f"--rc={rc}")
            model_lines = subprocess.run(
                command,
                input=input_text,
                text=True,
                stdout=subprocess.PIPE,
                check=True,
            ).stdout.splitlines()
        hardware_lines = (
            args.capture / f"{args.capture_stem}_{rc}_status.txt"
        ).read_text().splitlines()
        if len(model_lines) != total_inputs or len(hardware_lines) != total_inputs:
            raise SystemExit(
                f"{rc}: expected {total_inputs} lines, got "
                f"model={len(model_lines)} hardware={len(hardware_lines)}"
            )
        for index, (model_line, hardware_line) in enumerate(
            zip(model_lines, hardware_lines)
        ):
            predicted = parse_value(model_line, False)
            expected = parse_value(hardware_line, True)
            if predicted == expected:
                continue
            step = (
                signed_step(predicted, expected)
                if len(predicted) == len(expected) == 2
                else "class"
            )
            counts["result"] += 1
            counts[("rc", rc)] += 1
            counts[("step", step)] += 1
            affected.add(index)
            if counts["result"] <= args.show_misses:
                predicted_text = (
                    "C2"
                    if len(predicted) == 1
                    else f"{predicted[0]:04x}:{predicted[1]:016x}"
                )
                expected_text = (
                    "C2"
                    if len(expected) == 1
                    else f"{expected[0]:04x}:{expected[1]:016x}"
                )
                print(
                    f"miss index={index} rc={rc} "
                    f"predicted={predicted_text} "
                    f"expected={expected_text} "
                    f"step={step}"
                )

    print(
        f"h356 standalone FSIN C gate: result={counts['result']}/{total_inputs * 3} "
        f"affected-inputs={len(affected)}/{total_inputs}"
    )
    for prefix in ("rc", "step"):
        selected = {
            key[1]: value
            for key, value in counts.items()
            if isinstance(key, tuple) and key[0] == prefix
        }
        print(f"  {prefix}: {dict(sorted(selected.items(), key=lambda item: str(item[0])))}")


if __name__ == "__main__":
    main()
