#!/usr/bin/env python3
"""Build and score fresh separators for h157's old-improving rules.

h157 discovers several two-predicate selectors for the fifth cosine-Horner
sum.  This pass declares six distinct mechanisms, then searches only for
large architectural inputs whose solved reducer reaches the internal-cosine
path and for which a mechanism changes an output or C1 prediction relative
to Round 31.  Input selection is independent of hardware results.
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


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = (
    ROOT
    / "capture-kit"
    / "inputs"
    / "constraint_fsin_cosine_two_predicate_h158.txt"
)
DEFAULT_METADATA = (
    ROOT
    / "capture-kit"
    / "inputs"
    / "constraint_fsin_cosine_two_predicate_h158.meta.txt"
)
SEED = 0xF158C5


@dataclasses.dataclass(frozen=True)
class Conditional:
    name: str
    predicates: tuple[
        tuple[str, int], tuple[str, int]
    ]
    sum5: h110.Quant


CANDIDATES = (
    Conditional(
        "sum64c-if-p5norm0-tz4",
        (("product-5.norm2", 0), ("product-5.tz>=4", 1)),
        h110.Quant(64, "chop"),
    ),
    Conditional(
        "sum64c-if-p5lo1-sumlsb1",
        (("product-5.left-low3", 1), ("sum-5.lsb", 1)),
        h110.Quant(64, "chop"),
    ),
    Conditional(
        "sum64c-if-p5lo1-norm0",
        (("product-5.left-low3", 1), ("product-5.norm2", 0)),
        h110.Quant(64, "chop"),
    ),
    Conditional(
        "sum65c-if-p5norm0-sticky",
        (("product-5.norm2", 0), ("product-5.sticky", 1)),
        h110.Quant(65, "chop"),
    ),
    Conditional(
        "sum65c-if-p5lsb0-ylo3",
        (("product-5.lsb", 0), ("product-5.right-low3", 3)),
        h110.Quant(65, "chop"),
    ),
    Conditional(
        "sum65c-if-input2-p5lo0",
        (("global.input-low3", 2), ("product-5.left-low3", 0)),
        h110.Quant(65, "chop"),
    ),
)


def selected(
    features: dict[str, int], candidate: Conditional
) -> bool:
    return all(
        features[feature] == value
        for feature, value in candidate.predicates
    )


def schedule(
    point: h121.Point, candidate: Conditional | None
) -> h119.Schedule:
    square_schedule, baseline, features = (
        h157.round31_schedule(point)
    )
    if candidate is None or not selected(features, candidate):
        return baseline
    altered = dataclasses.replace(
        square_schedule,
        sums=h110.replace_tuple(
            square_schedule.sums, 4, candidate.sum5
        ),
    )
    altered_features = h146.trace(point, altered)
    return (
        dataclasses.replace(
            altered, tail=h157.ROUND31_TAIL
        )
        if altered_features["tail.lsb"] == 1
        else altered
    )


def profile(
    point: h121.Point, candidate: Conditional | None
) -> tuple[tuple[tuple[int, int], bool], ...]:
    value = h146.hidden_value(point, schedule(point, candidate))
    return tuple(
        (
            output := h58.x87_round(value, rc),
            h110.compare_magnitude(output, value) > 0,
        )
        for rc in h58.RCS
    )


def profile_schedule(
    point: h121.Point, value_schedule: h119.Schedule
) -> tuple[tuple[tuple[int, int], bool], ...]:
    value = h146.hidden_value(point, value_schedule)
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
        _, baseline_schedule, features = (
            h157.round31_schedule(point)
        )
        baseline = profile_schedule(point, baseline_schedule)
        separated = [
            candidate
            for candidate in CANDIDATES
            if counts[candidate.name] < per_candidate
            and selected(features, candidate)
            and profile_schedule(
                point,
                dataclasses.replace(
                    baseline_schedule,
                    sums=h110.replace_tuple(
                        baseline_schedule.sums,
                        4,
                        candidate.sum5,
                    ),
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
            f"h158 stopped after {scan_limit} scans; "
            f"incomplete={missing}"
        )
    output.write_text("\n".join(rows) + "\n")
    metadata.write_text("\n".join(meta) + "\n")
    print(
        f"h158: selected {len(rows)} inputs from "
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
            / f"constraint_fsin_cosine_two_predicate_h158_{rc}_status.txt"
        ).read_text().splitlines()
        for rc in h58.RCS
    ]
    if any(len(lines) != len(input_rows) for lines in modes):
        raise SystemExit("h158 input/capture line counts differ")
    result = []
    for index, (se, sig) in enumerate(input_rows):
        prepared = h147.point_from_input(index, se, sig)
        if prepared is None:
            raise SystemExit(
                f"h158 input {index + 1} is not active"
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
    parser.add_argument("--per-candidate", type=int, default=128)
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
            args.per_candidate,
            args.scan_limit,
        )
    if args.score is not None:
        points = load_capture(args.output, args.score)
        metadata = args.metadata.read_text().splitlines()
        if len(metadata) != len(points):
            raise SystemExit(
                "h158 metadata/capture line counts differ"
            )
        print(f"loaded {len(points)} fresh h158 separators")
        print(f"pooled baseline {score(points, None).describe()}")
        for candidate in CANDIDATES:
            selected_points = [
                point
                for point, line in zip(points, metadata)
                if candidate.name
                in line.split()[-1].split(",")
            ]
            baseline = score(selected_points, None)
            result = score(selected_points, candidate)
            status = (
                "PASS"
                if componentwise(result, baseline)
                else "FAIL"
            )
            print(
                f"{status:4s} {candidate.name:29s} "
                f"n={len(selected_points):3d} "
                f"{baseline.describe()} -> "
                f"{result.describe()}"
            )
    if not args.generate and args.score is None:
        parser.error(
            "select --generate and/or --score CAPTURE_DIRECTORY"
        )


if __name__ == "__main__":
    main()
