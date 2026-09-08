#!/usr/bin/env python3
"""Score uniform retained-unit changes at the Round-49 correction output."""

from __future__ import annotations

import argparse
import collections
import contextlib
import pathlib
import subprocess

import h350_round49_broad_compare as h350
import h352_round49_streaming_compare as h352


def baseline_errors(path: pathlib.Path):
    result = set()
    for line in path.read_text().splitlines():
        if not line or line.startswith("#"):
            continue
        fields = line.split()
        result.add((int(fields[0]), fields[3], fields[4]))
    return result


def score(
    model: pathlib.Path,
    inputs: pathlib.Path,
    capture: pathlib.Path,
    old_errors,
    delta: int,
    output: pathlib.Path | None,
):
    counts = collections.Counter()
    with contextlib.ExitStack() as stack:
        stream = stack.enter_context(output.open("w")) if output else None
        if stream:
            stream.write(
                "# index se sig rc lane class hw_se hw_sig candidate_se "
                "candidate_sig sw\n"
            )
        total = None
        for rc in h350.RCS:
            model_input = stack.enter_context(inputs.open())
            comparison_inputs = stack.enter_context(inputs.open())
            hardware = stack.enter_context(
                (capture / f"fsincos_{rc}_status.txt").open()
            )
            command = [
                str(model.resolve()),
                *h352.FLAGS,
                f"--round49-correction-delta={delta}",
            ]
            if rc != "rn":
                command.append(f"--rc={rc}")
            process = subprocess.Popen(
                command,
                stdin=model_input,
                stdout=subprocess.PIPE,
                text=True,
            )
            if process.stdout is None:
                raise AssertionError("missing candidate stdout")
            line_count = 0
            for index, (input_line, hardware_line, candidate_line) in enumerate(
                zip(comparison_inputs, hardware, process.stdout, strict=True)
            ):
                line_count += 1
                se, sig = (int(field, 16) for field in input_line.split())
                expected = h350.parse_hardware(hardware_line)
                candidate = h350.parse_model(candidate_line)
                for lane_index, lane in enumerate(("sin", "cos")):
                    old_error = (index, rc, lane) in old_errors
                    new_error = candidate[lane_index] != expected[lane_index]
                    if old_error and not new_error:
                        category = "improves"
                    elif not old_error and new_error:
                        category = "regresses"
                    elif old_error:
                        category = "still-wrong"
                    else:
                        category = "unchanged-correct"
                    counts[category] += 1
                    if stream and category != "unchanged-correct":
                        stream.write(
                            f"{index} {se:04x} {sig:016x} {rc} {lane} "
                            f"{category} {expected[lane_index][0]:04x} "
                            f"{expected[lane_index][1]:016x} "
                            f"{candidate[lane_index][0]:04x} "
                            f"{candidate[lane_index][1]:016x} "
                            f"{expected[2]:04x}\n"
                        )
            if process.wait() != 0:
                raise SystemExit(f"candidate delta {delta} failed for {rc}")
            if total is None:
                total = line_count
            elif line_count != total:
                raise SystemExit("h355 line count changed between modes")
    if total is None:
        raise AssertionError("no candidate modes processed")
    print(
        f"delta={delta:+d}: baseline={len(old_errors)} "
        f"candidate={counts['regresses'] + counts['still-wrong']} "
        f"improves={counts['improves']} regressions={counts['regresses']} "
        f"still-wrong={counts['still-wrong']} observations={total * 6}"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", type=pathlib.Path)
    parser.add_argument("inputs", type=pathlib.Path)
    parser.add_argument("capture", type=pathlib.Path)
    parser.add_argument("baseline_residuals", type=pathlib.Path)
    parser.add_argument("--deltas", type=int, nargs="+", default=(-2, -1, 1, 2))
    parser.add_argument("--output-directory", type=pathlib.Path)
    args = parser.parse_args()
    errors = baseline_errors(args.baseline_residuals)
    if args.output_directory:
        args.output_directory.mkdir(parents=True, exist_ok=True)
    for delta in args.deltas:
        if delta < -8 or delta > 8 or delta == 0:
            raise SystemExit("deltas must be nonzero values in -8..8")
        output = (
            args.output_directory / f"correction_delta_{delta:+d}.tsv"
            if args.output_directory else None
        )
        score(args.model, args.inputs, args.capture, errors, delta, output)


if __name__ == "__main__":
    main()
