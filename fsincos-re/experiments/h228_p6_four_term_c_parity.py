#!/usr/bin/env python3
"""Prove C/Python parity for the P6 four-term all-cell table kernel."""

from __future__ import annotations

import argparse
import pathlib
import subprocess

import h58_constraint_search as h58
import h184_table_lookup_firc_routes as h184
import h188_table_stage_local_pairs as h188
import h207_tang_literal_fadd as h207
import h226_p6_full_sine_graph as h226
import h230_p6_microop_materialization_search as h230


ROOT = pathlib.Path(__file__).resolve().parents[1]
INPUTS = {
    "dense": ROOT / "capture-kit" / "inputs" / "dense_qn.txt",
    "sweep": ROOT / "capture-kit" / "inputs" / "sweep_inputs.txt",
}
FLAGS = (
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
    "--round37-p6-four-term",
)
CANDIDATE = h230.dataclasses.replace(
    h230.CURRENT,
    square="chop67",
    p_horner_product="chop67",
    q_horner_product="chop67",
    p_square="chop67",
    p_times_a="chop67",
)


def parse_pair(line: str) -> tuple[tuple[int, int], tuple[int, int]]:
    fields = line.split()
    if len(fields) != 5 or fields[0] != "OK":
        raise ValueError(line)
    return (
        (int(fields[1], 16), int(fields[2], 16)),
        (int(fields[3], 16), int(fields[4], 16)),
    )


def points(name: str) -> list[h207.Point]:
    return [
        h207.Point(h188.prepare(point), True)
        for point in h184.dataset(name)
    ]


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
        if len(by_index) != len(selected):
            raise SystemExit(f"duplicate {name} point index")
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
                actual = parse_pair(lines[index])
                expected = tuple(
                    h58.x87_round(value, rc)
                    for value in h230.hidden_values(point, CANDIDATE)
                )
                if actual != expected:
                    misses += 1
                    if first is None:
                        first = (index, actual, expected)
                checks += 2
            print(f"{name} {rc}: {misses}/{len(selected)} pair mismatches")
            if misses:
                raise SystemExit(f"first mismatch: {first}")
    print(f"h228 C/Python parity: {checks}/{checks} lane-mode checks")


if __name__ == "__main__":
    main()
