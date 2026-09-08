#!/usr/bin/env python3
"""Map the remaining full-sweep FSIN misses to recovered kernel paths."""

from __future__ import annotations

import argparse
import collections
import pathlib
import subprocess

import h60_round16_parity as h60


ROOT = pathlib.Path(__file__).resolve().parents[1]
INPUTS = ROOT / "capture-kit" / "inputs" / "sweep_inputs.txt"
CAPTURE = ROOT / "capture-kit-captures" / "skylake-fsin-h110"


def value(line: str) -> tuple[str, ...]:
    fields = line.split()
    if fields[0] == "C2":
        return ("C2",)
    if fields[0] != "OK":
        raise ValueError(line)
    return "OK", fields[1], fields[2]


def classify(se: int, sig: int) -> tuple[str, str, int]:
    reduced = h60.reduced_kernel_input(se, sig)
    if reduced is None:
        source = "direct"
        quadrant = 0
        r_se, r_sig = se, sig
    else:
        signed_n, r_se, r_sig, _ = reduced
        source = "reduced"
        quadrant = signed_n & 3
    exponent = (r_se & 0x7FFF) - 16383
    if r_sig == 0 or exponent < -32:
        family = "tiny"
    elif exponent < -2:
        family = "polynomial"
    elif exponent == -2:
        family = "narrow-table"
    else:
        family = "wide-table"
    return source, family, quadrant


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", type=pathlib.Path)
    args = parser.parse_args()
    input_lines = INPUTS.read_text().splitlines()
    inputs = [
        tuple(int(field, 16) for field in line.split())
        for line in input_lines
    ]
    mode_counts: collections.Counter[tuple[str, str, int]] = (
        collections.Counter()
    )
    input_sets: dict[tuple[str, str, int], set[int]] = (
        collections.defaultdict(set)
    )
    for rc in ("rn", "rd", "ru"):
        command = [
            str(args.model.resolve()),
            "--batch",
            "--fsin-standalone",
            "--round18-poly",
            "--round21-table-bias",
            "--round23-narrow-coefficient",
            "--round24-table-delta-rn67",
            "--round29-p5-fmul-route",
            "--round30-fsin-cosine-square",
            "--round31-fsin-cosine-tail",
            "--round32-fsin-cosine-horner",
            "--round33-fsin-cosine-product",
        ]
        if rc != "rn":
            command.append(f"--rc={rc}")
        actual = subprocess.run(
            command,
            input="\n".join(input_lines) + "\n",
            text=True,
            stdout=subprocess.PIPE,
            check=True,
        ).stdout.splitlines()
        expected = (
            CAPTURE / f"sweep_fsin_{rc}_status.txt"
        ).read_text().splitlines()
        for index, (left, right) in enumerate(zip(actual, expected)):
            if value(left) == value(right):
                continue
            key = classify(*inputs[index])
            mode_counts[key] += 1
            input_sets[key].add(index)

    print("source family quadrant: mode_misses input_misses")
    for key in sorted(mode_counts):
        print(
            f"{key[0]:7s} {key[1]:12s} q{key[2]}: "
            f"{mode_counts[key]:3d} {len(input_sets[key]):3d}"
        )
    polynomial = sum(
        count
        for (_, family, _), count in mode_counts.items()
        if family == "polynomial"
    )
    table = sum(
        count
        for (_, family, _), count in mode_counts.items()
        if family.endswith("table")
    )
    tiny = sum(
        count
        for (_, family, _), count in mode_counts.items()
        if family == "tiny"
    )
    print(
        f"totals: polynomial={polynomial}, table={table}, tiny={tiny}, "
        f"all={polynomial + table + tiny}"
    )


if __name__ == "__main__":
    main()
