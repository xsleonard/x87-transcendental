#!/usr/bin/env python3
"""Build fresh separators for h167's adjacent operation rules.

h167 finds several old-improving product/sum/tail/final mechanisms after
Rounds 30 through 33.  This pass predeclares six distinct rules, constructs
large odd-quadrant inputs without consulting hardware, and balances inputs
where each rule changes an architectural output or C1 prediction.
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
import h121_fsin_internal_cosine as h121
import h146_fsin_cosine_boolean_search as h146
import h147_fsin_cosine_boolean_discriminator as h147
import h163_fsin_cosine_product_discriminator as h163
import h167_fsin_cosine_round33_operation_search as h167


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = (
    ROOT
    / "capture-kit"
    / "inputs"
    / "constraint_fsin_cosine_round33_operation_h168.txt"
)
DEFAULT_METADATA = (
    ROOT
    / "capture-kit"
    / "inputs"
    / "constraint_fsin_cosine_round33_operation_h168.meta.txt"
)
SEED = 0xF168C5


@dataclasses.dataclass(frozen=True)
class Conditional:
    name: str
    operation: h167.Operation
    predicates: tuple[
        tuple[str, int], tuple[str, int]
    ]


CANDIDATES = (
    Conditional(
        "sum64c-if-ylo5-sumlsb0",
        h167.Operation("sum-5", h110.Quant(64, "chop")),
        (
            ("product-5.right-low3", 5),
            ("sum-5.lsb", 0),
        ),
    ),
    Conditional(
        "sum64c-if-xlo2-ylo5",
        h167.Operation("sum-5", h110.Quant(64, "chop")),
        (
            ("product-5.left-low3", 2),
            ("product-5.right-low3", 5),
        ),
    ),
    Conditional(
        "tail66c-if-xlo6-tlo4",
        h167.Operation("tail", h110.Quant(66, "chop")),
        (
            ("product-5.left-low3", 6),
            ("tail.left-low3", 4),
        ),
    ),
    Conditional(
        "tail66c-if-p5tz3-tlo0",
        h167.Operation("tail", h110.Quant(66, "chop")),
        (
            ("product-5.tz>=3", 1),
            ("tail.left-low3", 0),
        ),
    ),
    Conditional(
        "tail66c-if-xlo2-sumlsb0",
        h167.Operation("tail", h110.Quant(66, "chop")),
        (
            ("product-5.left-low3", 2),
            ("sum-5.lsb", 0),
        ),
    ),
    Conditional(
        "final72a-if-input4-guard0",
        h167.Operation("final-sum", h110.Quant(72, "away")),
        (
            ("global.input-low3", 4),
            ("final-sum.guard", 0),
        ),
    ),
)


def selected(
    features: dict[str, int], candidate: Conditional
) -> bool:
    return all(
        features[name] == value
        for name, value in candidate.predicates
    )


def schedule(
    point: h121.Point,
    candidate: Conditional | None,
):
    baseline = h167.current_schedule(point)
    if candidate is None:
        return baseline
    features = h146.trace(point, baseline)
    if not selected(features, candidate):
        return baseline
    return h167.apply_operation(
        point, baseline, candidate.operation
    )


def profile(
    point: h121.Point,
    candidate: Conditional | None,
) -> tuple[tuple[tuple[int, int], bool], ...]:
    value = h146.hidden_value(
        point, schedule(point, candidate)
    )
    return h163.profile_value(value)


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
        prepared = h163.construct_input(rng, scan_index)
        if prepared is None:
            continue
        se, sig, point, signed_n, r_se, r_sig = prepared
        key = signed_n & 3, r_se, r_sig
        if key in residuals:
            continue
        baseline_schedule = h167.current_schedule(point)
        features = h146.trace(
            point, baseline_schedule
        )
        baseline_value = h146.hidden_value(
            point, baseline_schedule
        )
        baseline = h163.profile_value(baseline_value)
        separated = []
        masks = []
        for candidate in CANDIDATES:
            if (
                counts[candidate.name] >= per_candidate
                or not selected(features, candidate)
            ):
                continue
            candidate_schedule = h167.apply_operation(
                point,
                baseline_schedule,
                candidate.operation,
            )
            value = h146.hidden_value(
                point, candidate_schedule
            )
            mask = h147.difference_mask(
                baseline, h163.profile_value(value)
            )
            if mask:
                separated.append(candidate)
                masks.append(mask)
        if not separated:
            continue
        residuals.add(key)
        rows.append(f"{se:04x} {sig:016x}")
        labels = ",".join(
            f"{candidate.name}:{mask:02x}"
            for candidate, mask in zip(separated, masks)
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
            f"h168 stopped after {scan_limit} scans; "
            f"incomplete={missing}"
        )
    output.write_text("\n".join(rows) + "\n")
    metadata.write_text("\n".join(meta) + "\n")
    print(
        f"h168: selected {len(rows)} inputs from "
        f"{scan_index + 1} constructed scans; "
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
            / f"constraint_fsin_cosine_round33_operation_h168_{rc}_status.txt"
        ).read_text().splitlines()
        for rc in h58.RCS
    ]
    if any(len(lines) != len(input_rows) for lines in modes):
        raise SystemExit("h168 input/capture line counts differ")
    result = []
    for index, (se, sig) in enumerate(input_rows):
        prepared = h147.point_from_input(index, se, sig)
        if prepared is None:
            raise SystemExit(
                f"h168 input {index + 1} is not active"
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
        result.append(
            dataclasses.replace(
                point,
                observed=dataclasses.replace(
                    point.observed,
                    outputs=tuple(outputs),
                    c1=tuple(c1),
                ),
            )
        )
    return result


def score(
    points: list[h121.Point],
    candidate: Conditional | None,
) -> h110.Score:
    result = h110.Score()
    for point in points:
        value = h146.hidden_value(
            point, schedule(point, candidate)
        )
        result.total += 1
        any_miss = False
        for index, rc in enumerate(h58.RCS):
            output = h58.x87_round(value, rc)
            mismatch = output != point.observed.outputs[index]
            result.mode_misses += mismatch
            any_miss |= mismatch
            if not mismatch:
                c1 = h110.compare_magnitude(output, value) > 0
                result.c1_misses += (
                    c1 != point.observed.c1[index]
                )
        result.output_misses += any_miss
    return result


def componentwise(
    value: h110.Score, baseline: h110.Score
) -> bool:
    return all(
        candidate <= old
        for candidate, old in zip(
            value.rank(), baseline.rank()
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--generate", action="store_true")
    parser.add_argument("--score", type=pathlib.Path)
    parser.add_argument("--per-candidate", type=int, default=64)
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
        print(
            f"loaded {len(points)} fresh h168 separators"
        )
        for candidate in CANDIDATES:
            targeted = [
                point
                for point, line in zip(points, metadata)
                if any(
                    item.split(":", 1)[0]
                    == candidate.name
                    for item in line.split()[-1].split(",")
                )
            ]
            baseline = score(targeted, None)
            value = score(targeted, candidate)
            status = (
                "PASS"
                if componentwise(value, baseline)
                else "FAIL"
            )
            print(
                f"{status} {candidate.name:30s} "
                f"n={len(targeted):3d} "
                f"{baseline.describe()} -> "
                f"{value.describe()}"
            )
    if not args.generate and args.score is None:
        parser.error(
            "select --generate and/or --score CAPTURE_DIRECTORY"
        )


if __name__ == "__main__":
    main()
