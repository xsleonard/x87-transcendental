#!/usr/bin/env python3
"""Prove C parity on the seven shared-FMUL FPTAN residuals."""

from __future__ import annotations

import argparse
import pathlib
import subprocess

import h58_constraint_search as h58
import h265_fptan_c_parity as h265
import h271_fptan_scan_residuals as h271


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", type=pathlib.Path)
    args = parser.parse_args()
    model = args.model.resolve()
    input_text = h271.INPUTS.read_text()
    hardware = h271.captures()
    total = 0
    for rc in h58.RCS:
        actual = [
            h265.parse_model(line)
            for line in subprocess.run(
                [str(model), "--batch", "--fptan", f"--rc={rc}"],
                input=input_text,
                text=True,
                stdout=subprocess.PIPE,
                check=True,
            ).stdout.splitlines()
        ]
        expected = [value for value, _ in hardware[rc]]
        misses = sum(got != want for got, want in zip(actual, expected))
        print(f"h269 {rc}: {misses}/{len(expected)} result misses")
        if misses:
            raise SystemExit("focused FPTAN C parity failed")
        total += len(expected)
    print(f"h276 focused FPTAN C parity: {total}/{total} checks")


if __name__ == "__main__":
    main()
