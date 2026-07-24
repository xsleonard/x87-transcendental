#!/usr/bin/env python3
"""Validate C Round 38 against h235 and dense FCOS hardware captures."""

from __future__ import annotations

import argparse
import pathlib
import subprocess

import h58_constraint_search as h58
import h119_fcos_standalone as h119
import h120_fcos_c_parity as h120
import h235_fcos_p6_split_graph as h235


ROOT = pathlib.Path(__file__).resolve().parents[1]
INPUTS = ROOT / "capture-kit" / "inputs" / "dense_qn.txt"
CAPTURE = ROOT / "capture-kit-captures" / "skylake-fsin-h110"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", type=pathlib.Path)
    parser.add_argument(
        "--replay-dir",
        type=pathlib.Path,
        help="score precomputed dense_{rn,rd,ru}.txt output instead of running model",
    )
    parser.add_argument("--fcos-tiny", action="store_true")
    args = parser.parse_args()

    input_text = INPUTS.read_text()
    input_lines = input_text.splitlines()
    direct = {
        point.raw.index: point for point in h119.load_observed()
    }
    total_mode_misses = 0
    total_output_misses = set()
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
            "--round37-p6-four-term",
            "--round38-p6-cosine-split",
        ]
        if args.fcos_tiny:
            command.append("--round39-fcos-tiny")
        if rc != "rn":
            command.append(f"--rc={rc}")
        actual = (
            (args.replay_dir / f"dense_{rc}.txt").read_text().splitlines()
            if args.replay_dir
            else subprocess.run(
                command,
                input=input_text,
                text=True,
                stdout=subprocess.PIPE,
                check=True,
            ).stdout.splitlines()
        )
        hardware = (
            CAPTURE / f"dense_fcos_{rc}_status.txt"
        ).read_text().splitlines()
        parity_misses = 0
        direct_hardware_misses = 0
        other_hardware_misses = 0
        for index, (actual_line, hardware_line) in enumerate(
            zip(actual, hardware)
        ):
            actual_value = h120.parse_single(actual_line)
            hardware_value = h120.parse_single(hardware_line)
            if index in direct:
                expected = h58.x87_round(
                    h235.hidden_value(
                        direct[index], h235.P6_SURVIVOR
                    ),
                    rc,
                )
                parity_misses += actual_value != expected
                direct_hardware_misses += actual_value != hardware_value
            else:
                other_hardware_misses += actual_value != hardware_value
            if actual_value != hardware_value:
                total_mode_misses += 1
                total_output_misses.add(index)
        print(
            f"{rc}: C/Python direct parity {parity_misses}/80000; "
            f"hardware direct {direct_hardware_misses}/80000; "
            f"hardware other {other_hardware_misses}/160000"
        )
        if parity_misses:
            raise SystemExit("C/Python Round-38 schedule differs")

    print(
        f"combined hardware: {total_mode_misses}/720000 mode results, "
        f"{len(total_output_misses)}/240000 inputs differ"
    )


if __name__ == "__main__":
    main()
