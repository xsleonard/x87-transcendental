#!/usr/bin/env python3
"""Validate the C standalone-FSIN path against Python and hardware.

The Python side is h110's complete-data survivor.  The hardware side is the
extended Skylake RN/RD/RU standalone capture, whose RN values are identical
to the Pentium II on all 240,000 dense inputs.
"""

from __future__ import annotations

import argparse
import pathlib
import subprocess

import h58_constraint_search as h58
import h110_fsin_standalone as h110


ROOT = pathlib.Path(__file__).resolve().parents[1]
INPUTS = ROOT / "capture-kit" / "inputs" / "dense_qn.txt"
CAPTURE = ROOT / "capture-kit-captures" / "skylake-fsin-h110"


def parse_single(line: str) -> tuple[int, int]:
    fields = line.split()
    if fields[0] != "OK":
        raise ValueError(line)
    return int(fields[1], 16), int(fields[2], 16)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", type=pathlib.Path)
    args = parser.parse_args()

    inputs = INPUTS.read_text()
    input_lines = inputs.splitlines()
    direct = {
        point.raw.index: point
        for point in h110.load_observed()
    }
    total_mode_misses = 0
    total_output_misses: set[int] = set()
    for rc_index, rc in enumerate(h58.RCS):
        command = [
            str(args.model.resolve()),
            "--batch",
            "--fsin-standalone",
            "--round21-table-bias",
            "--round23-narrow-coefficient",
            "--round24-table-delta-rn67",
        ]
        if rc != "rn":
            command.append(f"--rc={rc}")
        completed = subprocess.run(
            command,
            input=inputs,
            text=True,
            stdout=subprocess.PIPE,
            check=True,
        )
        actual_lines = completed.stdout.splitlines()
        hardware_lines = (
            CAPTURE / f"dense_fsin_{rc}_status.txt"
        ).read_text().splitlines()
        if len(actual_lines) != len(input_lines):
            raise SystemExit("C output line count differs")

        parity_misses = 0
        direct_hardware_misses = 0
        table_hardware_misses = 0
        for index, (actual_line, hardware_line) in enumerate(
            zip(actual_lines, hardware_lines)
        ):
            actual = parse_single(actual_line)
            hardware = parse_single(hardware_line)
            if index in direct:
                expected = h58.x87_round(
                    h110.hidden_value(
                        direct[index], h110.FSIN_SURVIVOR
                    ),
                    rc,
                )
                parity_misses += actual != expected
                direct_hardware_misses += actual != hardware
            else:
                table_hardware_misses += actual != hardware
            if actual != hardware:
                total_mode_misses += 1
                total_output_misses.add(index)
        print(
            f"{rc}: C/Python direct parity {parity_misses}/80000; "
            f"hardware direct {direct_hardware_misses}/80000; "
            f"hardware table {table_hardware_misses}/160000"
        )
        if parity_misses:
            raise SystemExit("C/Python standalone schedule differs")

    print(
        f"combined hardware: {total_mode_misses}/720000 mode results, "
        f"{len(total_output_misses)}/240000 inputs differ"
    )


if __name__ == "__main__":
    main()
