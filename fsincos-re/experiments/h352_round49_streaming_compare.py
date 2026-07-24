#!/usr/bin/env python3
"""Run and stream-compare Round 49 without materializing model outputs."""

from __future__ import annotations

import argparse
import collections
import contextlib
import pathlib
import subprocess

import h350_round49_broad_compare as h350


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
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", type=pathlib.Path)
    parser.add_argument("inputs", type=pathlib.Path)
    parser.add_argument("capture", type=pathlib.Path)
    parser.add_argument("--residuals", type=pathlib.Path)
    parser.add_argument("--mismatch-inputs", type=pathlib.Path)
    parser.add_argument("--extra-flag", action="append", default=[])
    args = parser.parse_args()

    counts = collections.Counter()
    mismatching_inputs = set()
    with contextlib.ExitStack() as stack:
        residuals = (
            stack.enter_context(args.residuals.open("w"))
            if args.residuals else None
        )
        if residuals:
            residuals.write(
                "# index se sig rc lane hw_se hw_sig model_se model_sig sw step\n"
            )
        total = None
        for rc in h350.RCS:
            input_stream = stack.enter_context(args.inputs.open())
            comparison_inputs = stack.enter_context(args.inputs.open())
            hardware_stream = stack.enter_context(
                (args.capture / f"fsincos_{rc}_status.txt").open()
            )
            command = [str(args.model.resolve()), *FLAGS, *args.extra_flag]
            if rc != "rn":
                command.append(f"--rc={rc}")
            process = subprocess.Popen(
                command,
                stdin=input_stream,
                stdout=subprocess.PIPE,
                text=True,
            )
            if process.stdout is None:
                raise AssertionError("missing model stdout")
            line_count = 0
            for index, (input_line, hardware_line, model_line) in enumerate(
                zip(
                    comparison_inputs,
                    hardware_stream,
                    process.stdout,
                )
            ):
                line_count += 1
                se, sig = (int(field, 16) for field in input_line.split())
                hardware_pair = h350.parse_hardware(hardware_line)
                model_pair = h350.parse_model(model_line)
                for lane_index, lane in enumerate(("sin", "cos")):
                    expected = hardware_pair[lane_index]
                    predicted = model_pair[lane_index]
                    if predicted == expected:
                        continue
                    step = h350.signed_step(predicted, expected)
                    counts["result"] += 1
                    counts["lane", lane] += 1
                    counts["rc", rc] += 1
                    counts["step", step] += 1
                    mismatching_inputs.add((se, sig))
                    if residuals:
                        residuals.write(
                            f"{index} {se:04x} {sig:016x} {rc} {lane} "
                            f"{expected[0]:04x} {expected[1]:016x} "
                            f"{predicted[0]:04x} {predicted[1]:016x} "
                            f"{hardware_pair[2]:04x} {step}\n"
                        )
            if process.wait() != 0:
                raise SystemExit(f"Round-49 model failed for {rc}")
            if total is None:
                total = line_count
            elif line_count != total:
                raise SystemExit(f"h352 line count changed for {rc}")

    if args.mismatch_inputs:
        args.mismatch_inputs.write_text(
            "".join(
                f"{se:04x} {sig:016x}\n"
                for se, sig in sorted(mismatching_inputs)
            )
        )
    if total is None:
        raise AssertionError("no rounding modes processed")
    print(
        f"h352 Round-49 streaming scan: result={counts['result']}/{total * 6} "
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
