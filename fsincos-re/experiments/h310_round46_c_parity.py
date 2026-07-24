#!/usr/bin/env python3
"""Prove C/Python parity for the Round-46 shared-sine carrier rule."""

from __future__ import annotations

import argparse
import pathlib
import subprocess

import h58_constraint_search as h58
import h228_p6_four_term_c_parity as h228
import h285_trig_sine_bias_discriminator as h285
import h307_trig_narrow_sine_fraction_discriminator as h307
import h309_trig_narrow_sine_fractional_rule as h309


ROOT = pathlib.Path(__file__).resolve().parents[1]
INPUTS = {
    **h228.INPUTS,
    "h285": ROOT / "capture-kit" / "inputs" / "constraint_trig_sine_bias_h285.txt",
    "h292": ROOT / "capture-kit" / "inputs" / "constraint_trig_sine_coordinates_h292.txt",
    "h301": ROOT / "capture-kit" / "inputs" / "constraint_trig_sine_fraction_h301.txt",
    "h307": ROOT / "capture-kit" / "inputs" / "constraint_trig_narrow_sine_fraction_h307.txt",
}
FLAGS = (
    *h228.FLAGS,
    "--round43-p6-sine-bias",
    "--round44-p6-sine-bias",
    "--round45-p6-sine-fraction",
    "--round46-p6-narrow-sine-fraction",
)


def points(name: str):
    if name not in ("h285", "h292", "h301", "h307"):
        return h228.points(name)
    operands = [
        tuple(int(field, 16) for field in line.split())
        for line in INPUTS[name].read_text().splitlines()
    ]
    result = []
    for index, (se, sig) in enumerate(operands):
        point = (
            h307.point_from_input(index, se, sig)
            if name == "h307"
            else h285.point_from_input(index, se, sig)
        )
        if point is None:
            raise SystemExit(f"{name} line {index + 1} is not a table point")
        result.append(point)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", type=pathlib.Path)
    parser.add_argument("--dataset", choices=tuple(INPUTS))
    parser.add_argument("--rc", choices=h58.RCS)
    args = parser.parse_args()
    model = args.model.resolve()
    checks = 0
    datasets = (
        ((args.dataset, INPUTS[args.dataset]),)
        if args.dataset
        else INPUTS.items()
    )
    for name, input_path in datasets:
        selected = points(name)
        by_index = {
            point.prepared.joint.observed.index: point
            for point in selected
        }
        input_text = input_path.read_text()
        for rc in ((args.rc,) if args.rc else h58.RCS):
            command = [str(model), "--batch", *FLAGS]
            if rc != "rn":
                command.append(f"--rc={rc}")
            lines = subprocess.run(
                command,
                input=input_text,
                text=True,
                stdout=subprocess.PIPE,
                check=True,
            ).stdout.splitlines()
            misses = 0
            first = None
            for index, point in by_index.items():
                actual = h228.parse_pair(lines[index])
                expected = tuple(
                    h58.x87_round(value, rc)
                    for value in h309.hidden_values(point)
                )
                if actual != expected:
                    misses += 1
                    if first is None:
                        first = (index, actual, expected)
                checks += 2
            print(f"{name} {rc}: {misses}/{len(selected)} pair mismatches")
            if misses:
                raise SystemExit(f"first mismatch: {first}")
    print(f"h310 Round-46 C/Python parity: {checks}/{checks} lane-mode checks")


if __name__ == "__main__":
    main()
