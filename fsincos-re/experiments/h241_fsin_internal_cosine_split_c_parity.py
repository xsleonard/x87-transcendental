#!/usr/bin/env python3
"""Prove C/Python parity for Round 41's FSIN cosine split graph."""

from __future__ import annotations

import argparse
import pathlib
import subprocess

import h58_constraint_search as h58
import h121_fsin_internal_cosine as h121
import h124_fsin_cosine_c_parity as h124
import h147_fsin_cosine_boolean_discriminator as h147
import h148_fsin_cosine_boolean_crossvalidate as h148
import h151_fsin_cosine_tail_discriminator as h151
import h158_fsin_cosine_two_predicate_discriminator as h158
import h161_fsin_cosine_round32_composition as h161
import h163_fsin_cosine_product_discriminator as h163
import h168_fsin_cosine_round33_operation_discriminator as h168
import h239_round39_residual_census as h239
import h241_fsin_internal_cosine_split as h241


ROOT = pathlib.Path(__file__).resolve().parents[1]
CAPTURES = ROOT / "capture-kit-captures"
COMMAND_FLAGS = (
    *h239.BASE_FLAGS,
    "--fsin-standalone",
    "--round41-fsin-cosine-split",
)


def validate(
    model: pathlib.Path,
    label: str,
    inputs: pathlib.Path,
    points: list[h121.Point],
) -> None:
    input_text = inputs.read_text()
    mode_misses = 0
    hardware_misses = 0
    for rc_index, rc in enumerate(h58.RCS):
        command = [str(model.resolve()), *COMMAND_FLAGS]
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
            hidden = h241.split_hidden(
                point, h241.FSIN_SPLIT_SURVIVOR
            )
            expected = h58.x87_round(hidden, rc)
            output = h124.parse_single(
                actual[point.observed.raw.index]
            )
            mode_misses += output != expected
            hardware_misses += (
                output != point.observed.outputs[rc_index]
            )
    print(
        f"{label}: C/Python={mode_misses}/{3 * len(points)}; "
        f"hardware={hardware_misses}/{3 * len(points)}"
    )
    if mode_misses:
        raise SystemExit(f"Round-41 C/Python mismatch in {label}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", type=pathlib.Path)
    args = parser.parse_args()

    validate(
        args.model,
        "structured sweep",
        ROOT / "capture-kit" / "inputs" / "sweep_inputs.txt",
        h121.load_points(),
    )
    datasets = (
        (
            "h147",
            h147.DEFAULT_OUTPUT,
            h147.load_capture(
                h147.DEFAULT_OUTPUT, CAPTURES / "skylake-fsin-h147"
            ),
        ),
        (
            "h148",
            h148.DEFAULT_OUTPUT,
            h148.load_capture(
                h148.DEFAULT_OUTPUT, CAPTURES / "skylake-fsin-h148"
            ),
        ),
        (
            "h151",
            h151.DEFAULT_OUTPUT,
            h151.load_capture(
                h151.DEFAULT_OUTPUT, CAPTURES / "skylake-fsin-h151"
            ),
        ),
        (
            "h158",
            h158.DEFAULT_OUTPUT,
            h158.load_capture(
                h158.DEFAULT_OUTPUT, CAPTURES / "skylake-fsin-h158"
            ),
        ),
        (
            "h161",
            h161.DEFAULT_OUTPUT,
            h161.load_capture(
                h161.DEFAULT_OUTPUT, CAPTURES / "skylake-fsin-h161"
            ),
        ),
        (
            "h163",
            h163.DEFAULT_OUTPUT,
            h163.load_capture(
                h163.DEFAULT_OUTPUT, CAPTURES / "skylake-fsin-h163"
            ),
        ),
        (
            "h168",
            h168.DEFAULT_OUTPUT,
            h168.load_capture(
                h168.DEFAULT_OUTPUT, CAPTURES / "skylake-fsin-h168"
            ),
        ),
    )
    for label, inputs, points in datasets:
        validate(args.model, label, inputs, points)


if __name__ == "__main__":
    main()
