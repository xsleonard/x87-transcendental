#!/usr/bin/env python3
"""Prove C/Python parity for Round 42's standalone sine split graph."""

from __future__ import annotations

import argparse
import pathlib
import subprocess

import h58_constraint_search as h58
import h64_poly_constraints as h64
import h110_fsin_standalone as h110
import h122_fsin_reduced_sine as h122
import h124_fsin_cosine_c_parity as h124
import h239_round39_residual_census as h239
import h242_fsin_sine_split_graph as h242
import h242_sine_split_sibling_gate as sibling


ROOT = pathlib.Path(__file__).resolve().parents[1]
FLAGS = (
    *h239.BASE_FLAGS,
    "--round40-fsincos-tiny",
    "--round41-fsin-cosine-split",
    "--round42-p6-sine-split",
)


def load_direct() -> list[h110.Observed]:
    inputs = [
        tuple(int(field, 16) for field in line.split())
        for line in (
            ROOT / "capture-kit" / "inputs" / "dense_qn.txt"
        ).read_text().splitlines()
    ]
    modes = [
        (
            ROOT
            / "capture-kit-captures"
            / "skylake-fsin-h110"
            / f"dense_fsin_{rc}_status.txt"
        ).read_text().splitlines()
        for rc in h58.RCS
    ]
    result = []
    for index, (se, sig) in enumerate(inputs):
        exponent = (se & 0x7FFF) - 16383
        if exponent != -3:
            continue
        outputs = []
        c1 = []
        for lines in modes:
            fields = lines[index].split()
            outputs.append((int(fields[1], 16), int(fields[2], 16)))
            c1.append(bool(int(fields[4], 16) & 0x0200))
        raw = h64.PolyRaw(
            index=index,
            sign=se >> 15,
            exponent=exponent,
            sig=sig,
            sincos=(((0, 0), (0, 0)),) * 3,
            standalone=((0, 0), (0, 0)),
        )
        result.append(h110.Observed(raw, tuple(outputs), tuple(c1)))
    return result


def validate(
    model: pathlib.Path,
    label: str,
    inputs: pathlib.Path,
    points: list[h110.Observed],
    coefficients: h110.Schedule,
    instruction: str,
) -> None:
    input_text = inputs.read_text()
    parity_misses = 0
    hardware_misses = 0
    for rc_index, rc in enumerate(h58.RCS):
        command = [
            str(model.resolve()),
            *FLAGS,
            f"--{instruction}-standalone",
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
        for point in points:
            hidden = h242.hidden_value(
                point,
                h242.FSIN_SINE_SPLIT_SURVIVOR,
                coefficients,
            )
            expected = h58.x87_round(hidden, rc)
            output = h124.parse_single(actual[point.raw.index])
            parity_misses += output != expected
            hardware_misses += output != point.outputs[rc_index]
    total = 3 * len(points)
    print(
        f"{label}: C/Python={parity_misses}/{total}; "
        f"hardware={hardware_misses}/{total}"
    )
    if parity_misses:
        raise SystemExit(f"Round-42 C/Python mismatch in {label}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", type=pathlib.Path)
    args = parser.parse_args()

    validate(
        args.model,
        "FSIN direct",
        ROOT / "capture-kit" / "inputs" / "dense_qn.txt",
        load_direct(),
        h110.FSIN_SURVIVOR,
        "fsin",
    )
    validate(
        args.model,
        "FSIN reduced",
        sibling.INPUTS,
        h122.load_points(),
        h122.FSIN_REDUCED_SINE,
        "fsin",
    )
    fcos_reduced, _, _ = sibling.load_points()
    validate(
        args.model,
        "FCOS reduced sine state",
        sibling.INPUTS,
        fcos_reduced,
        h122.FSIN_REDUCED_SINE,
        "fcos",
    )


if __name__ == "__main__":
    main()
