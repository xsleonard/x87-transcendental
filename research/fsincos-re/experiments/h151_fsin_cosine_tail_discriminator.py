#!/usr/bin/env python3
"""Build and score a targeted discriminator for h150's tail rules.

h150 leaves several one-bit selectors for the final internal-cosine
polynomial multiply.  This pass searches large architectural inputs whose
solved reducer reaches that path and for which each candidate changes an
FSIN result or C1 prediction relative to the Round 30 graph.
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
import h150_fsin_cosine_boolean_round30 as h150


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = (
    ROOT
    / "capture-kit"
    / "inputs"
    / "constraint_fsin_cosine_tail_h151.txt"
)
DEFAULT_METADATA = (
    ROOT
    / "capture-kit"
    / "inputs"
    / "constraint_fsin_cosine_tail_h151.meta.txt"
)
SEED = 0xF151C5


@dataclasses.dataclass(frozen=True)
class Conditional:
    name: str
    feature: str
    value: int
    tail: h110.Quant


CANDIDATES = (
    Conditional(
        "tail67c-if-ylo6",
        "tail.right-low3",
        6,
        h110.Quant(67, "chop"),
    ),
    Conditional(
        "tail67c-if-tz6",
        "tail.tz>=6",
        1,
        h110.Quant(67, "chop"),
    ),
    Conditional(
        "tail68c-if-ylo6",
        "tail.right-low3",
        6,
        h110.Quant(68, "chop"),
    ),
    Conditional(
        "tail71c-if-lsb1",
        "tail.lsb",
        1,
        h110.Quant(71, "chop"),
    ),
    Conditional(
        "tail68c-if-tz6",
        "tail.tz>=6",
        1,
        h110.Quant(68, "chop"),
    ),
    Conditional(
        "tail67c-if-xlo0",
        "tail.left-low3",
        0,
        h110.Quant(67, "chop"),
    ),
)


def hidden(
    point: h121.Point, candidate: Conditional | None
) -> h58.FP:
    schedule = h150.base_schedule(point)
    features = h146.trace(point, schedule)
    if (
        candidate is not None
        and features[candidate.feature] == candidate.value
    ):
        schedule = dataclasses.replace(
            schedule, tail=candidate.tail
        )
    value = h119.hidden_value(point.observed, schedule)
    return h58.neg(value) if point.negate else value


def profile(
    point: h121.Point, candidate: Conditional | None
) -> tuple[tuple[tuple[int, int], bool], ...]:
    value = hidden(point, candidate)
    return tuple(
        (
            output := h58.x87_round(value, rc),
            h110.compare_magnitude(output, value) > 0,
        )
        for rc in h58.RCS
    )


def profile_schedule(
    point: h121.Point, schedule: h119.Schedule
) -> tuple[tuple[tuple[int, int], bool], ...]:
    value = h119.hidden_value(point.observed, schedule)
    if point.negate:
        value = h58.neg(value)
    return tuple(
        (
            output := h58.x87_round(value, rc),
            h110.compare_magnitude(output, value) > 0,
        )
        for rc in h58.RCS
    )


def generate(
    output: pathlib.Path,
    metadata: pathlib.Path,
    per_candidate: int,
    scan_limit: int,
) -> None:
    rng = random.Random(SEED)
    rows = []
    meta = []
    counts: collections.Counter[str] = collections.Counter()
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
        schedule = h150.base_schedule(point)
        features = h146.trace(point, schedule)
        baseline = profile_schedule(point, schedule)
        separated = [
            candidate
            for candidate in CANDIDATES
            if counts[candidate.name] < per_candidate
            and features[candidate.feature] == candidate.value
            and profile_schedule(
                point,
                dataclasses.replace(
                    schedule, tail=candidate.tail
                ),
            )
            != baseline
        ]
        if not separated:
            continue
        residuals.add(key)
        rows.append(f"{se:04x} {sig:016x}")
        labels = ",".join(
            candidate.name for candidate in separated
        )
        meta.append(
            f"{scan_index} {signed_n} {r_se:04x} "
            f"{r_sig:016x} {labels}"
        )
        for candidate in separated:
            counts[candidate.name] += 1
        if all(
            counts[candidate.name] >= per_candidate
            for candidate in CANDIDATES
        ):
            break
    missing = {
        candidate.name: counts[candidate.name]
        for candidate in CANDIDATES
        if counts[candidate.name] < per_candidate
    }
    if missing:
        raise SystemExit(
            f"h151 stopped after {scan_limit} scans; "
            f"incomplete={missing}"
        )
    output.write_text("\n".join(rows) + "\n")
    metadata.write_text("\n".join(meta) + "\n")
    print(
        f"h151: selected {len(rows)} inputs from "
        f"{scan_index + 1} scans; "
        f"per-candidate={dict(sorted(counts.items()))}; "
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
            / f"constraint_fsin_cosine_tail_h151_{rc}_status.txt"
        ).read_text().splitlines()
        for rc in h58.RCS
    ]
    if any(len(lines) != len(input_rows) for lines in modes):
        raise SystemExit("h151 input/capture line counts differ")
    result = []
    for index, (se, sig) in enumerate(input_rows):
        prepared = h147.point_from_input(index, se, sig)
        if prepared is None:
            raise SystemExit(
                f"h151 input {index + 1} is not active"
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
    points: list[h121.Point], candidate: Conditional | None
) -> h110.Score:
    result = h110.Score()
    for point in points:
        value = hidden(point, candidate)
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--generate", action="store_true")
    parser.add_argument("--score", type=pathlib.Path)
    parser.add_argument("--per-candidate", type=int, default=128)
    parser.add_argument(
        "--scan-limit", type=int, default=20_000_000
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
            args.per_candidate,
            args.scan_limit,
        )
    if args.score is not None:
        points = load_capture(args.output, args.score)
        metadata = args.metadata.read_text().splitlines()
        if len(metadata) != len(points):
            raise SystemExit(
                "h151 metadata/capture line counts differ"
            )
        print(f"loaded {len(points)} fresh h151 separators")
        pooled = score(points, None)
        print(f"pooled baseline {pooled.describe()}")
        for candidate in CANDIDATES:
            selected = [
                point
                for point, line in zip(points, metadata)
                if candidate.name
                in line.split()[-1].split(",")
            ]
            baseline = score(selected, None)
            result = score(selected, candidate)
            status = (
                "PASS"
                if all(
                    left <= right
                    for left, right in zip(
                        result.rank(), baseline.rank()
                    )
                )
                else "FAIL"
            )
            print(
                f"{status:4s} {candidate.name:20s} "
                f"n={len(selected):3d} "
                f"{baseline.describe()} -> "
                f"{result.describe()}"
            )
    if not args.generate and args.score is None:
        parser.error(
            "select --generate and/or --score CAPTURE_DIRECTORY"
        )


if __name__ == "__main__":
    main()
