#!/usr/bin/env python3
"""Stream-compare a large one-mode hardware FPTAN scan with the C model."""

from __future__ import annotations

import argparse
import contextlib
import pathlib


def hardware_result(line: str) -> tuple[int, int] | None:
    fields = line.split()
    if fields[:2] == ["C2", "SW"]:
        return None
    if (
        len(fields) != 7
        or fields[0] != "OK"
        or fields[5] != "SW"
        or (int(fields[3], 16), int(fields[4], 16))
        != (0x3FFF, 0x8000000000000000)
    ):
        raise ValueError(line)
    return int(fields[1], 16), int(fields[2], 16)


def model_result(line: str) -> tuple[int, int] | None:
    fields = line.split()
    if fields == ["C2"]:
        return None
    if (
        len(fields) != 5
        or fields[0] != "OK"
        or (int(fields[3], 16), int(fields[4], 16))
        != (0x3FFF, 0x8000000000000000)
    ):
        raise ValueError(line)
    return int(fields[1], 16), int(fields[2], 16)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", type=pathlib.Path)
    parser.add_argument("hardware", type=pathlib.Path)
    parser.add_argument("model", type=pathlib.Path)
    parser.add_argument("--mismatch-inputs", type=pathlib.Path)
    args = parser.parse_args()

    total = 0
    misses = 0
    with (
        args.inputs.open() as inputs,
        args.hardware.open() as hardware,
        args.model.open() as model,
        contextlib.ExitStack() as stack,
    ):
        mismatch_stream = (
            stack.enter_context(args.mismatch_inputs.open("w"))
            if args.mismatch_inputs
            else None
        )
        for index, rows in enumerate(zip(inputs, hardware, model, strict=True)):
            input_line, hardware_line, model_line = (
                value.rstrip("\n") for value in rows
            )
            got = model_result(model_line)
            expected = hardware_result(hardware_line)
            total += 1
            if got == expected:
                continue
            misses += 1
            if mismatch_stream:
                print(input_line, file=mismatch_stream)
            print(
                f"{index}\t{input_line}\thw={expected}\tmodel={got}\t"
                f"status={hardware_line}"
            )
    print(f"h270 FPTAN scan: {misses}/{total} result mismatches")


if __name__ == "__main__":
    main()
