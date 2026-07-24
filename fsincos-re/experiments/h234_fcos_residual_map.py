#!/usr/bin/env python3
"""Map remaining standalone-FCOS misses to residual cells and output lanes.

A wrong trigonometric lookup word should concentrate failures in one table
cell and in uses of that cell's sine or cosine state.  This report separates
the direct six-term polynomial (which reads no lookup cell) from direct and
M66-reduced table paths, then groups the remaining mismatches by cell, lane,
rounding mode, and magnitude direction.
"""

from __future__ import annotations

import argparse
import collections
import pathlib
import subprocess

import h58_constraint_search as h58
import h60_round16_parity as h60


ROOT = pathlib.Path(__file__).resolve().parents[1]
INPUTS = ROOT / "capture-kit" / "inputs" / "dense_qn.txt"
CAPTURE = ROOT / "capture-kit-captures" / "skylake-fsin-h110"


def value(line: str) -> tuple[int, int]:
    fields = line.split()
    if fields[0] != "OK":
        raise ValueError(line)
    return int(fields[1], 16), int(fields[2], 16)


def magnitude_rank(result: tuple[int, int]) -> int:
    se, sig = result
    return ((se & 0x7FFF) << 63) + sig


def classify(se: int, sig: int) -> tuple[str, str, str, int | None]:
    reduced = h60.reduced_kernel_input(se, sig)
    if reduced is None:
        source = "direct"
        signed_n = 0
        r_se, r_sig = se, sig
    else:
        source = "reduced"
        signed_n, r_se, r_sig, _ = reduced
    exponent = (r_se & 0x7FFF) - 16383
    if r_sig == 0 or exponent < -32:
        family = "tiny"
    elif exponent < -2:
        family = "polynomial"
    elif exponent == -2:
        family = "narrow-table"
    else:
        family = "wide-table"
    lane = "cos-state" if ((signed_n + 1) & 1) else "sin-state"
    cell = (
        h58.cell_for(r_sig, exponent)
        if family.endswith("table")
        else None
    )
    return source, family, lane, cell


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", type=pathlib.Path)
    args = parser.parse_args()

    input_text = INPUTS.read_text()
    input_lines = input_text.splitlines()
    inputs = [
        tuple(int(field, 16) for field in line.split())
        for line in input_lines
    ]
    groups = collections.Counter()
    family_inputs: dict[tuple[str, str, str, int | None], set[int]] = (
        collections.defaultdict(set)
    )
    total_inputs: set[int] = set()
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
        ]
        if rc != "rn":
            command.append(f"--rc={rc}")
        actual = subprocess.run(
            command,
            input=input_text,
            text=True,
            stdout=subprocess.PIPE,
            check=True,
        ).stdout.splitlines()
        expected = (
            CAPTURE / f"dense_fcos_{rc}_status.txt"
        ).read_text().splitlines()
        for index, (model_line, hardware_line) in enumerate(
            zip(actual, expected)
        ):
            model = value(model_line)
            hardware = value(hardware_line)
            if model == hardware:
                continue
            path = classify(*inputs[index])
            delta = magnitude_rank(model) - magnitude_rank(hardware)
            direction = "model-high" if delta > 0 else "model-low"
            groups[path + (rc, direction)] += 1
            family_inputs[path].add(index)
            total_inputs.add(index)

    print("source family lane cell: modes inputs [mode/direction counts]")
    paths = sorted(
        family_inputs,
        key=lambda item: (item[0], item[1], item[2], item[3] or -1),
    )
    for path in paths:
        details = []
        modes = 0
        for rc in h58.RCS:
            for direction in ("model-low", "model-high"):
                count = groups[path + (rc, direction)]
                modes += count
                if count:
                    details.append(f"{rc}/{direction}={count}")
        cell = "-" if path[3] is None else str(path[3])
        print(
            f"{path[0]:7s} {path[1]:12s} {path[2]:9s} {cell:>2s}: "
            f"{modes:4d} {len(family_inputs[path]):4d} "
            + " ".join(details)
        )
    print(
        f"total: {sum(groups.values())} mode misses on "
        f"{len(total_inputs)} inputs"
    )


if __name__ == "__main__":
    main()
