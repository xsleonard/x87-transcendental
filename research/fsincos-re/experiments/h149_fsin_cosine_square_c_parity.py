#!/usr/bin/env python3
"""Validate and prove C parity for Round 30's square-normalization rule.

The selected rule keeps h121's away67 square when the exact product has the
high normalization bit, but retains away68 in the lower 127-bit case.  This
script proves the C implementation against the conditional Python graph over
all 12,249 old sweep points, proves every changed full-sweep output belongs
to that subpath, and reports both fresh h147/h148 scores.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

import h58_constraint_search as h58
import h110_fsin_standalone as h110
import h119_fcos_standalone as h119
import h121_fsin_internal_cosine as h121
import h146_fsin_cosine_boolean_search as h146
import h147_fsin_cosine_boolean_discriminator as h147
import h148_fsin_cosine_boolean_crossvalidate as h148


ROOT = pathlib.Path(__file__).resolve().parents[1]
INPUTS = ROOT / "capture-kit" / "inputs" / "sweep_inputs.txt"
FLAGS = (
    "--fsin-standalone",
    "--round18-poly",
    "--round21-table-bias",
    "--round23-narrow-coefficient",
    "--round24-table-delta-rn67",
    "--round29-p5-fmul-route",
)
CANDIDATE = h148.with_square(68, "away")


def parse(line: str) -> tuple[int, int] | str:
    fields = line.split()
    if fields[0] == "C2":
        return "C2"
    if fields[0] != "OK":
        raise ValueError(line)
    return int(fields[1], 16), int(fields[2], 16)


def hidden(point: h121.Point) -> h58.FP:
    schedule = (
        CANDIDATE
        if h146.trace(point)["square.norm2"] == 0
        else h121.FSIN_INTERNAL_COSINE
    )
    value = h119.hidden_value(point.observed, schedule)
    return h58.neg(value) if point.negate else value


def run(
    model: pathlib.Path,
    inputs: str,
    rc: str,
    candidate: bool,
) -> list[tuple[int, int] | str]:
    command = [str(model), "--batch", *FLAGS]
    if candidate:
        command.append("--round30-fsin-cosine-square")
    if rc != "rn":
        command.append(f"--rc={rc}")
    completed = subprocess.run(
        command,
        input=inputs,
        text=True,
        stdout=subprocess.PIPE,
        check=True,
    )
    return [parse(line) for line in completed.stdout.splitlines()]


def python_score(points: list[h121.Point]) -> h110.Score:
    result = h110.Score()
    for point in points:
        value = hidden(point)
        result.total += 1
        any_miss = False
        for index, rc in enumerate(h58.RCS):
            output = h58.x87_round(value, rc)
            expected = point.observed.outputs[index]
            mismatch = output != expected
            result.mode_misses += mismatch
            any_miss |= mismatch
            if not mismatch:
                c1 = h110.compare_magnitude(output, value) > 0
                result.c1_misses += c1 != point.observed.c1[index]
        result.output_misses += any_miss
    return result


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(f"usage: {sys.argv[0]} MODEL")
    model = pathlib.Path(sys.argv[1]).resolve()
    inputs = INPUTS.read_text()
    points = h121.load_points()
    by_index = {point.observed.raw.index: point for point in points}
    checked = 0
    changed = 0
    old_misses = 0
    new_misses = 0
    for rc_index, rc in enumerate(h58.RCS):
        baseline = run(model, inputs, rc, False)
        candidate = run(model, inputs, rc, True)
        for index, (old, new) in enumerate(zip(baseline, candidate)):
            point = by_index.get(index)
            if old != new and point is None:
                raise SystemExit(
                    f"Round 30 changed non-internal-cosine line "
                    f"{index + 1} under {rc}"
                )
            if point is None:
                continue
            expected = h58.x87_round(hidden(point), rc)
            if new != expected:
                raise SystemExit(
                    f"C/Python mismatch line {index + 1} {rc}: "
                    f"C={new} Python={expected}"
                )
            hardware = point.observed.outputs[rc_index]
            old_misses += old != hardware
            new_misses += new != hardware
            changed += old != new
            checked += 1
    print(
        f"old sweep: checked={checked} changed={changed} "
        f"hardware={old_misses}->{new_misses}; "
        f"Python={python_score(points).describe()}"
    )

    fresh147 = h147.load_capture(
        h147.DEFAULT_OUTPUT,
        ROOT / "capture-kit-captures" / "skylake-fsin-h147",
    )
    round30 = next(
        candidate
        for candidate in h148.CANDIDATES
        if candidate.name == "square68a-if-norm0"
    )
    print(
        "h147: "
        f"{h148.score(fresh147, None).describe()} -> "
        f"{h148.score(fresh147, round30).describe()}"
    )
    fresh148 = h148.load_capture(
        h148.DEFAULT_OUTPUT,
        ROOT / "capture-kit-captures" / "skylake-fsin-h148",
    )
    print(
        "h148 pooled: "
        f"{h148.score(fresh148, None).describe()} -> "
        f"{h148.score(fresh148, round30).describe()}"
    )
    print("PASS: Round 30 C/Python parity and scope")


if __name__ == "__main__":
    main()
