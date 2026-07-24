#!/usr/bin/env python3
"""Prove C parity, scope, and transfer for Round 33.

h163 independently localizes h161's secondary signal to the fifth cosine
Horner product.  The selected physical representative is a 67-bit
round-to-odd carrier when product-5's retained 65-bit LSB is zero, the
square low three bits are three, and the Round-32 selector is inactive.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

import h58_constraint_search as h58
import h110_fsin_standalone as h110
import h121_fsin_internal_cosine as h121
import h146_fsin_cosine_boolean_search as h146
import h147_fsin_cosine_boolean_discriminator as h147
import h148_fsin_cosine_boolean_crossvalidate as h148
import h151_fsin_cosine_tail_discriminator as h151
import h158_fsin_cosine_two_predicate_discriminator as h158
import h160_fsin_cosine_horner_c_parity as h160
import h161_fsin_cosine_round32_composition as h161
import h162_fsin_cosine_round32_residual_search as h162
import h163_fsin_cosine_product_discriminator as h163


ROOT = pathlib.Path(__file__).resolve().parents[1]
SWEEP_INPUTS = (
    ROOT / "capture-kit" / "inputs" / "sweep_inputs.txt"
)
FLAGS = (
    *h160.FLAGS,
    "--round32-fsin-cosine-horner",
)
P67_ODD = next(
    candidate
    for candidate in h163.CANDIDATES
    if candidate.name == "product5-67o"
)


def parse(line: str) -> tuple[int, int] | str:
    fields = line.split()
    if fields[0] == "C2":
        return "C2"
    if fields[0] != "OK":
        raise ValueError(line)
    return int(fields[1], 16), int(fields[2], 16)


def hidden(
    point: h121.Point, candidate: bool
) -> h58.FP:
    schedule = (
        h162.variant_schedule(point, P67_ODD.variant)
        if candidate
        else h162.baseline_schedule(point)
    )
    return h146.hidden_value(point, schedule)


def run(
    model: pathlib.Path,
    inputs: pathlib.Path,
    rc: str,
    candidate: bool,
) -> list[tuple[int, int] | str]:
    command = [str(model), "--batch", *FLAGS]
    if candidate:
        command.append("--round33-fsin-cosine-product")
    if rc != "rn":
        command.append(f"--rc={rc}")
    completed = subprocess.run(
        command,
        input=inputs.read_text(),
        text=True,
        stdout=subprocess.PIPE,
        check=True,
    )
    return [
        parse(line) for line in completed.stdout.splitlines()
    ]


def score(
    points: list[h121.Point], candidate: bool
) -> h110.Score:
    result = h110.Score()
    for point in points:
        value = hidden(point, candidate)
        result.total += 1
        any_miss = False
        for index, rc in enumerate(h58.RCS):
            output = h58.x87_round(value, rc)
            mismatch = output != point.observed.outputs[index]
            result.mode_misses += mismatch
            any_miss |= mismatch
            if not mismatch:
                c1 = (
                    h110.compare_magnitude(output, value) > 0
                )
                result.c1_misses += (
                    c1 != point.observed.c1[index]
                )
        result.output_misses += any_miss
    return result


def check_capture(
    model: pathlib.Path,
    name: str,
    inputs: pathlib.Path,
    points: list[h121.Point],
) -> None:
    checked = 0
    changed = 0
    for rc in h58.RCS:
        before = run(model, inputs, rc, False)
        after = run(model, inputs, rc, True)
        if len(after) != len(points):
            raise SystemExit(
                f"{name} C/point line counts differ"
            )
        for index, (left, right, point) in enumerate(
            zip(before, after, points)
        ):
            expected = h58.x87_round(
                hidden(point, True), rc
            )
            if right != expected:
                raise SystemExit(
                    f"{name} C/Python mismatch line "
                    f"{index + 1} {rc}: C={right} "
                    f"Python={expected}"
                )
            changed += left != right
            checked += 1
    print(
        f"{name}: checked={checked} changed={changed}; "
        f"hardware {score(points, False).describe()} -> "
        f"{score(points, True).describe()}"
    )


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(f"usage: {sys.argv[0]} MODEL")
    model = pathlib.Path(sys.argv[1]).resolve()
    old = h121.load_points()
    by_index = {
        point.observed.raw.index: point for point in old
    }
    checked = 0
    changed = 0
    for rc in h58.RCS:
        before = run(model, SWEEP_INPUTS, rc, False)
        after = run(model, SWEEP_INPUTS, rc, True)
        for index, (left, right) in enumerate(
            zip(before, after)
        ):
            point = by_index.get(index)
            if left != right and point is None:
                raise SystemExit(
                    f"Round 33 changed non-internal-cosine "
                    f"line {index + 1} under {rc}"
                )
            if point is None:
                continue
            expected = h58.x87_round(
                hidden(point, True), rc
            )
            if right != expected:
                raise SystemExit(
                    f"old C/Python mismatch line "
                    f"{index + 1} {rc}: C={right} "
                    f"Python={expected}"
                )
            changed += left != right
            checked += 1
    print(
        f"old sweep: checked={checked} changed={changed}; "
        f"hardware {score(old, False).describe()} -> "
        f"{score(old, True).describe()}"
    )

    datasets = (
        (
            "h147",
            h147.DEFAULT_OUTPUT,
            h147.load_capture(
                h147.DEFAULT_OUTPUT,
                ROOT
                / "capture-kit-captures"
                / "skylake-fsin-h147",
            ),
        ),
        (
            "h148",
            h148.DEFAULT_OUTPUT,
            h148.load_capture(
                h148.DEFAULT_OUTPUT,
                ROOT
                / "capture-kit-captures"
                / "skylake-fsin-h148",
            ),
        ),
        (
            "h151",
            h151.DEFAULT_OUTPUT,
            h151.load_capture(
                h151.DEFAULT_OUTPUT,
                ROOT
                / "capture-kit-captures"
                / "skylake-fsin-h151",
            ),
        ),
        (
            "h158",
            h158.DEFAULT_OUTPUT,
            h158.load_capture(
                h158.DEFAULT_OUTPUT,
                ROOT
                / "capture-kit-captures"
                / "skylake-fsin-h158",
            ),
        ),
        (
            "h161",
            h161.DEFAULT_OUTPUT,
            h161.load_capture(
                h161.DEFAULT_OUTPUT,
                ROOT
                / "capture-kit-captures"
                / "skylake-fsin-h161",
            ),
        ),
        (
            "h163",
            h163.DEFAULT_OUTPUT,
            h163.load_capture(
                h163.DEFAULT_OUTPUT,
                ROOT
                / "capture-kit-captures"
                / "skylake-fsin-h163",
            ),
        ),
    )
    for name, inputs, points in datasets:
        check_capture(model, name, inputs, points)
    print("PASS: Round 33 C/Python parity and scope")


if __name__ == "__main__":
    main()
