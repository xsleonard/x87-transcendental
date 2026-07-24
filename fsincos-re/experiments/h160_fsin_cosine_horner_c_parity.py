#!/usr/bin/env python3
"""Prove C parity and independent scores for Round 32.

The rule was declared before h158 hardware capture: materialize the fifth
internal-cosine Horner sum with chop65 when its exact incoming product has
no high normalization bit and has nonzero sticky below the 65-bit guard.
This script checks C/Python parity and scope over the old sweep plus
h147/h148/h151/h158.
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


ROOT = pathlib.Path(__file__).resolve().parents[1]
SWEEP_INPUTS = (
    ROOT / "capture-kit" / "inputs" / "sweep_inputs.txt"
)
FLAGS = (
    "--fsin-standalone",
    "--round18-poly",
    "--round21-table-bias",
    "--round23-narrow-coefficient",
    "--round24-table-delta-rn67",
    "--round29-p5-fmul-route",
    "--round30-fsin-cosine-square",
    "--round31-fsin-cosine-tail",
)
CANDIDATE = next(
    candidate
    for candidate in h158.CANDIDATES
    if candidate.name == "sum65c-if-p5norm0-sticky"
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
    return h146.hidden_value(
        point,
        h158.schedule(
            point, CANDIDATE if candidate else None
        ),
    )


def run(
    model: pathlib.Path,
    inputs: pathlib.Path,
    rc: str,
    candidate: bool,
) -> list[tuple[int, int] | str]:
    command = [str(model), "--batch", *FLAGS]
    if candidate:
        command.append("--round32-fsin-cosine-horner")
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
            expected = point.observed.outputs[index]
            mismatch = output != expected
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
    for rc_index, rc in enumerate(h58.RCS):
        old = run(model, inputs, rc, False)
        new = run(model, inputs, rc, True)
        if len(new) != len(points):
            raise SystemExit(
                f"{name} C/point line counts differ"
            )
        for index, (before, after, point) in enumerate(
            zip(old, new, points)
        ):
            expected = h58.x87_round(
                hidden(point, True), rc
            )
            if after != expected:
                raise SystemExit(
                    f"{name} C/Python mismatch line "
                    f"{index + 1} {rc}: C={after} "
                    f"Python={expected}"
                )
            changed += before != after
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
    changed = 0
    checked = 0
    for rc_index, rc in enumerate(h58.RCS):
        before = run(model, SWEEP_INPUTS, rc, False)
        after = run(model, SWEEP_INPUTS, rc, True)
        for index, (left, right) in enumerate(
            zip(before, after)
        ):
            point = by_index.get(index)
            if left != right and point is None:
                raise SystemExit(
                    f"Round 32 changed non-internal-cosine "
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

    fresh147 = h147.load_capture(
        h147.DEFAULT_OUTPUT,
        ROOT / "capture-kit-captures" / "skylake-fsin-h147",
    )
    check_capture(
        model, "h147", h147.DEFAULT_OUTPUT, fresh147
    )
    fresh148 = h148.load_capture(
        h148.DEFAULT_OUTPUT,
        ROOT / "capture-kit-captures" / "skylake-fsin-h148",
    )
    check_capture(
        model, "h148", h148.DEFAULT_OUTPUT, fresh148
    )
    fresh151 = h151.load_capture(
        h151.DEFAULT_OUTPUT,
        ROOT / "capture-kit-captures" / "skylake-fsin-h151",
    )
    check_capture(
        model, "h151", h151.DEFAULT_OUTPUT, fresh151
    )
    fresh158 = h158.load_capture(
        h158.DEFAULT_OUTPUT,
        ROOT / "capture-kit-captures" / "skylake-fsin-h158",
    )
    check_capture(
        model, "h158", h158.DEFAULT_OUTPUT, fresh158
    )
    print("PASS: Round 32 C/Python parity and scope")


if __name__ == "__main__":
    main()
