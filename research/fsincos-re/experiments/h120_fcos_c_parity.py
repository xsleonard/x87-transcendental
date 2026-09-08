#!/usr/bin/env python3
"""Validate the C standalone-FCOS producer against Python and hardware."""

from __future__ import annotations

import argparse
import pathlib
import subprocess

import h58_constraint_search as h58
import h119_fcos_standalone as h119


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
    parser.add_argument("--p6-four-term", action="store_true")
    args = parser.parse_args()

    inputs = INPUTS.read_text()
    input_lines = inputs.splitlines()
    direct = {
        point.raw.index: point for point in h119.load_observed()
    }
    total_mode_misses = 0
    total_output_misses: set[int] = set()
    for rc in h58.RCS:
        command = [
            str(args.model.resolve()),
            "--batch",
            "--fcos-standalone",
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
        ]
        if args.p6_four_term:
            command.append("--round37-p6-four-term")
        if rc != "rn":
            command.append(f"--rc={rc}")
        actual_lines = subprocess.run(
            command,
            input=inputs,
            text=True,
            stdout=subprocess.PIPE,
            check=True,
        ).stdout.splitlines()
        hardware_lines = (
            CAPTURE / f"dense_fcos_{rc}_status.txt"
        ).read_text().splitlines()
        if len(actual_lines) != len(input_lines):
            raise SystemExit("C output line count differs")

        parity_misses = 0
        direct_hardware_misses = 0
        other_hardware_misses = 0
        for index, (actual_line, hardware_line) in enumerate(
            zip(actual_lines, hardware_lines)
        ):
            actual = parse_single(actual_line)
            hardware = parse_single(hardware_line)
            if index in direct:
                expected = h58.x87_round(
                    h119.hidden_value(
                        direct[index], h119.FCOS_SURVIVOR
                    ),
                    rc,
                )
                parity_misses += actual != expected
                direct_hardware_misses += actual != hardware
            else:
                other_hardware_misses += actual != hardware
            if actual != hardware:
                total_mode_misses += 1
                total_output_misses.add(index)
        print(
            f"{rc}: C/Python direct parity {parity_misses}/80000; "
            f"hardware direct {direct_hardware_misses}/80000; "
            f"hardware other {other_hardware_misses}/160000"
        )
        if parity_misses:
            raise SystemExit("C/Python standalone schedule differs")

    print(
        f"combined hardware: {total_mode_misses}/720000 mode results, "
        f"{len(total_output_misses)}/240000 inputs differ"
    )


if __name__ == "__main__":
    main()
