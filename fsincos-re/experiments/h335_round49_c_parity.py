#!/usr/bin/env python3
"""Prove C/Python parity for the Round-49 carrier-interval rule."""

from __future__ import annotations

import argparse
import pathlib
import subprocess

import h58_constraint_search as h58
import h228_p6_four_term_c_parity as h228
import h323_round48_c_parity as h323
import h333_p6_carrier_metadata_semantics as h333


FLAGS = (*h323.FLAGS, "--round49-p6-carrier-interval")
CANDIDATE = h333.CANDIDATES["interval-low1-last-interior"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", type=pathlib.Path)
    parser.add_argument("--dataset", choices=tuple(h323.INPUTS))
    parser.add_argument("--rc", choices=h58.RCS)
    args = parser.parse_args()
    model = args.model.resolve()
    checks = 0
    datasets = (
        ((args.dataset, h323.INPUTS[args.dataset]),)
        if args.dataset
        else h323.INPUTS.items()
    )
    for name, input_path in datasets:
        selected = h323.points(name)
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
                    for value in h333.hidden_values(point, CANDIDATE)
                )
                if actual != expected:
                    misses += 1
                    if first is None:
                        first = (index, actual, expected)
                checks += 2
            print(f"{name} {rc}: {misses}/{len(selected)} pair mismatches")
            if misses:
                raise SystemExit(f"first mismatch: {first}")
    print(f"h335 Round-49 C/Python parity: {checks}/{checks} lane-mode checks")


if __name__ == "__main__":
    main()
