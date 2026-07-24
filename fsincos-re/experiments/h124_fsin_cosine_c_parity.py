#!/usr/bin/env python3
"""Prove C/Python parity for FSIN's odd-quadrant cosine survivor."""

from __future__ import annotations

import argparse
import pathlib
import subprocess

import h58_constraint_search as h58
import h119_fcos_standalone as h119
import h121_fsin_internal_cosine as h121


ROOT = pathlib.Path(__file__).resolve().parents[1]
INPUTS = ROOT / "capture-kit" / "inputs" / "sweep_inputs.txt"


def parse_single(line: str) -> tuple[int, int] | str:
    fields = line.split()
    if fields[0] == "C2":
        return "C2"
    if fields[0] != "OK":
        raise ValueError(line)
    return int(fields[1], 16), int(fields[2], 16)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", type=pathlib.Path)
    args = parser.parse_args()
    inputs = INPUTS.read_text()
    points = h121.load_points()

    for rc in h58.RCS:
        command = [
            str(args.model.resolve()),
            "--batch",
            "--fsin-standalone",
            "--round18-poly",
            "--round21-table-bias",
            "--round23-narrow-coefficient",
            "--round24-table-delta-rn67",
        ]
        if rc != "rn":
            command.append(f"--rc={rc}")
        actual = subprocess.run(
            command,
            input=inputs,
            text=True,
            stdout=subprocess.PIPE,
            check=True,
        ).stdout.splitlines()
        misses = 0
        for point in points:
            hidden = h119.hidden_value(
                point.observed, h121.FSIN_INTERNAL_COSINE
            )
            if point.negate:
                hidden = h58.neg(hidden)
            predicted = parse_single(
                actual[point.observed.raw.index]
            )
            expected = h58.x87_round(hidden, rc)
            misses += predicted != expected
        print(
            f"{rc}: C/Python internal-cosine parity "
            f"{misses}/{len(points)}"
        )
        if misses:
            raise SystemExit("C/Python internal cosine schedule differs")


if __name__ == "__main__":
    main()
