#!/usr/bin/env python3
"""Validate the C FPTAN model against every sibling-capture result.

The C batch path emits the FPTAN result followed by the architectural pushed
one.  This checker covers dense and sweep inputs under RN/RD/RU, including
zero and C2/no-writeback cases.  Python h260/h264 separately validate C1.
"""

from __future__ import annotations

import argparse
import pathlib
import subprocess

import h58_constraint_search as h58
import h245_fptan_shared_state as h245
import h264_fptan_polynomial_transfer as h264


def parse_model(line: str):
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
    parser.add_argument("model", type=pathlib.Path)
    args = parser.parse_args()
    model = args.model.resolve()

    total = 0
    misses = 0
    first = None
    for name in ("dense", "sweep"):
        input_text = h264.INPUTS[name].read_text()
        for rc in h58.RCS:
            command = [str(model), "--batch", "--fptan", f"--rc={rc}"]
            actual = [
                parse_model(line)
                for line in subprocess.run(
                    command,
                    input=input_text,
                    text=True,
                    stdout=subprocess.PIPE,
                    check=True,
                ).stdout.splitlines()
            ]
            expected = [
                h245.parse(line)[0]
                for line in (
                    h245.CAPTURE / f"{name}_fptan_{rc}_status.txt"
                ).read_text().splitlines()
            ]
            if len(actual) != len(expected):
                raise SystemExit(f"{name} {rc}: line-count mismatch")
            mode_misses = 0
            for index, (got, want) in enumerate(zip(actual, expected)):
                if got != want:
                    mode_misses += 1
                    if first is None:
                        first = name, rc, index, got, want
            print(f"{name} {rc}: {mode_misses}/{len(expected)} result misses")
            total += len(expected)
            misses += mode_misses
    print(f"h265 C FPTAN parity: {misses}/{total} result misses")
    if misses != 0:
        raise SystemExit(f"unexpected mismatch count; first={first}")


if __name__ == "__main__":
    main()
