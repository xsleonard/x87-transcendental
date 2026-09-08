#!/usr/bin/env python3
"""Independently test a second chop65 selector after Round 32.

h158 predeclared and validated both the Round 32 normalization+sticky rule
and a product-LSB/square-low-bits rule.  Their OR composition predicts a
further old-sweep gain, but was first evaluated after h158 hardware was
known.  This pass selects only inputs where Round 32 alone and that
composition predict different output/C1 observations; hardware is not
consulted during generation.
"""

from __future__ import annotations

import argparse
import collections
import dataclasses
import pathlib
import random
import sys

import h58_constraint_search as h58
import h110_fsin_standalone as h110
import h119_fcos_standalone as h119
import h121_fsin_internal_cosine as h121
import h146_fsin_cosine_boolean_search as h146
import h147_fsin_cosine_boolean_discriminator as h147
import h157_fsin_cosine_two_predicate as h157
import h158_fsin_cosine_two_predicate_discriminator as h158
import h159_fsin_cosine_two_predicate_union as h159


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = (
    ROOT
    / "capture-kit"
    / "inputs"
    / "constraint_fsin_cosine_round32_composition_h161.txt"
)
DEFAULT_METADATA = (
    ROOT
    / "capture-kit"
    / "inputs"
    / "constraint_fsin_cosine_round32_composition_h161.meta.txt"
)
SEED = 0xF161C5
ROUND32 = next(
    candidate
    for candidate in h158.CANDIDATES
    if candidate.name == "sum65c-if-p5norm0-sticky"
)
SECOND = next(
    candidate
    for candidate in h158.CANDIDATES
    if candidate.name == "sum65c-if-p5lsb0-ylo3"
)


def schedule(point: h121.Point, candidate: bool):
    return h159.schedule(
        point,
        (ROUND32, SECOND) if candidate else (ROUND32,),
    )


def profile(
    point: h121.Point, candidate: bool
) -> tuple[tuple[tuple[int, int], bool], ...]:
    value = h146.hidden_value(point, schedule(point, candidate))
    return profile_value(value)


def profile_value(
    value: h58.FP,
) -> tuple[tuple[tuple[int, int], bool], ...]:
    return tuple(
        (
            output := h58.x87_round(value, rc),
            h110.compare_magnitude(output, value) > 0,
        )
        for rc in h58.RCS
    )


def difference_mask(
    left: tuple[tuple[tuple[int, int], bool], ...],
    right: tuple[tuple[tuple[int, int], bool], ...],
) -> int:
    mask = 0
    for index, (old, new) in enumerate(zip(left, right)):
        if old[0] != new[0]:
            mask |= 1 << index
        if old[1] != new[1]:
            mask |= 1 << (index + 3)
    return mask


def generate(
    output: pathlib.Path,
    metadata: pathlib.Path,
    count: int,
    scan_limit: int,
) -> None:
    rng = random.Random(SEED)
    rows = []
    meta = []
    masks: collections.Counter[int] = collections.Counter()
    residuals = set()
    for scan_index in range(scan_limit):
        exponent = rng.randrange(0, 63)
        sig = rng.randrange(1 << 63, 1 << 64)
        sign = rng.getrandbits(1)
        se = (sign << 15) | (exponent + 16383)
        prepared = h147.point_from_input(scan_index, se, sig)
        if prepared is None:
            continue
        point, signed_n, r_se, r_sig = prepared
        key = signed_n & 3, r_se, r_sig
        if key in residuals:
            continue
        square_schedule, baseline_schedule, features = (
            h157.round31_schedule(point)
        )
        # The OR composition differs from Round 32 only on E && !D.
        if (
            h158.selected(features, ROUND32)
            or not h158.selected(features, SECOND)
        ):
            continue
        baseline = profile_value(
            h146.hidden_value(point, baseline_schedule)
        )
        altered = dataclasses.replace(
            square_schedule,
            sums=h110.replace_tuple(
                square_schedule.sums, 4, SECOND.sum5
            ),
        )
        altered_features = h146.trace(point, altered)
        candidate_schedule: h119.Schedule = (
            dataclasses.replace(
                altered, tail=h157.ROUND31_TAIL
            )
            if altered_features["tail.lsb"] == 1
            else altered
        )
        candidate = profile_value(
            h146.hidden_value(point, candidate_schedule)
        )
        mask = difference_mask(baseline, candidate)
        if not mask:
            continue
        residuals.add(key)
        masks[mask] += 1
        rows.append(f"{se:04x} {sig:016x}")
        meta.append(
            f"{scan_index} {signed_n} {r_se:04x} "
            f"{r_sig:016x} {mask:02x}"
        )
        if len(rows) >= count:
            break
    if len(rows) < count:
        raise SystemExit(
            f"h161 selected {len(rows)} inputs after "
            f"{scan_limit} scans; wanted {count}"
        )
    output.write_text("\n".join(rows) + "\n")
    metadata.write_text("\n".join(meta) + "\n")
    print(
        f"h161: selected {len(rows)} separators from "
        f"{scan_index + 1} scans; "
        f"masks={dict(sorted(masks.items()))}; "
        f"seed={SEED:#x}",
        file=sys.stderr,
    )


def load_capture(
    inputs: pathlib.Path, capture: pathlib.Path
) -> list[h121.Point]:
    input_rows = [
        tuple(int(field, 16) for field in line.split())
        for line in inputs.read_text().splitlines()
    ]
    modes = [
        (
            capture
            / f"constraint_fsin_cosine_round32_composition_h161_{rc}_status.txt"
        ).read_text().splitlines()
        for rc in h58.RCS
    ]
    if any(len(lines) != len(input_rows) for lines in modes):
        raise SystemExit("h161 input/capture line counts differ")
    result = []
    for index, (se, sig) in enumerate(input_rows):
        prepared = h147.point_from_input(index, se, sig)
        if prepared is None:
            raise SystemExit(
                f"h161 input {index + 1} is not active"
            )
        point = prepared[0]
        outputs = []
        c1 = []
        for lines in modes:
            fields = lines[index].split()
            if (
                len(fields) != 5
                or fields[0] != "OK"
                or fields[3] != "SW"
            ):
                raise ValueError(lines[index])
            outputs.append(
                (int(fields[1], 16), int(fields[2], 16))
            )
            c1.append(bool(int(fields[4], 16) & 0x0200))
        observed = dataclasses.replace(
            point.observed,
            outputs=tuple(outputs),
            c1=tuple(c1),
        )
        result.append(
            dataclasses.replace(point, observed=observed)
        )
    return result


def score(
    points: list[h121.Point], candidate: bool
) -> h110.Score:
    result = h110.Score()
    for point in points:
        value = h146.hidden_value(
            point, schedule(point, candidate)
        )
        result.total += 1
        any_miss = False
        for index, rc in enumerate(h58.RCS):
            expected = point.observed.outputs[index]
            output = h58.x87_round(value, rc)
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


def componentwise(
    candidate: h110.Score, baseline: h110.Score
) -> bool:
    return all(
        left <= right
        for left, right in zip(
            candidate.rank(), baseline.rank()
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--generate", action="store_true")
    parser.add_argument("--score", type=pathlib.Path)
    parser.add_argument("--count", type=int, default=256)
    parser.add_argument(
        "--scan-limit", type=int, default=30_000_000
    )
    parser.add_argument(
        "--output", type=pathlib.Path, default=DEFAULT_OUTPUT
    )
    parser.add_argument(
        "--metadata",
        type=pathlib.Path,
        default=DEFAULT_METADATA,
    )
    args = parser.parse_args()
    if args.generate:
        generate(
            args.output,
            args.metadata,
            args.count,
            args.scan_limit,
        )
    if args.score is not None:
        points = load_capture(args.output, args.score)
        baseline = score(points, False)
        candidate = score(points, True)
        status = (
            "PASS"
            if componentwise(candidate, baseline)
            else "FAIL"
        )
        print(f"loaded {len(points)} fresh h161 separators")
        print(f"baseline  {baseline.describe()}")
        print(f"candidate {candidate.describe()} {status}")
    if not args.generate and args.score is None:
        parser.error(
            "select --generate and/or --score CAPTURE_DIRECTORY"
        )


if __name__ == "__main__":
    main()
