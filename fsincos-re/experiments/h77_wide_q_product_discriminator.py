#!/usr/bin/env python3
"""Fresh discriminator for final-product chop67 in the baseline wide q chain."""

from __future__ import annotations

import argparse
import dataclasses
import pathlib
import random
import sys
from collections import Counter

import h58_constraint_search as h58
import h59_discriminator as h59
import h76_wide_horner_product_search as h76


START = 0x8000000000000000
END = 0xC90FDAA22168C234
DUMMY_HW = (((0, 0), (0, 0)),) * 3
CANDIDATE = h76.Variant(5, 67, "chop")


def rounded(
    raw: h58.RawPoint,
    candidate: bool,
) -> tuple[tuple[tuple[int, int], tuple[int, int]], ...]:
    point = h58.prepare(raw, h58.BASE_PRODUCER)
    if candidate:
        point = dataclasses.replace(
            point, q=h76.horner(h58.C6, point.asq, CANDIDATE)
        )
    values = h58.table_tail(point, h58.BASE)
    return tuple(
        tuple(h58.x87_round(value, rc) for value in values)
        for rc in h58.RCS
    )


def rounded_point(
    point: h58.PreparedPoint,
) -> tuple[tuple[tuple[int, int], tuple[int, int]], ...]:
    values = h58.table_tail(point, h58.BASE)
    return tuple(
        tuple(h58.x87_round(value, rc) for value in values)
        for rc in h58.RCS
    )


def generate(count: int, seed: int, scan_limit: int) -> None:
    rng = random.Random(seed)
    found = 0
    q_differences = 0
    categories: Counter[tuple[bool, bool]] = Counter()
    for scan_index in range(scan_limit):
        raw = h58.RawPoint(
            index=found,
            sign=rng.randrange(2),
            exponent=-1,
            sig=rng.randrange(START, END),
            hw=DUMMY_HW,
        )
        point = h58.prepare(raw, h58.BASE_PRODUCER)
        candidate_q = h76.horner(h58.C6, point.asq, CANDIDATE)
        if candidate_q == point.q:
            continue
        q_differences += 1
        baseline = rounded_point(point)
        candidate = rounded_point(
            dataclasses.replace(point, q=candidate_q)
        )
        if baseline == candidate:
            continue
        sine_diff = any(
            base[0] != alternate[0]
            for base, alternate in zip(baseline, candidate)
        )
        cosine_diff = any(
            base[1] != alternate[1]
            for base, alternate in zip(baseline, candidate)
        )
        categories[(sine_diff, cosine_diff)] += 1
        se = (raw.sign << 15) | 0x3FFE
        print(f"{se:04x} {raw.sig:016x}")
        found += 1
        if found == count:
            print(
                f"selected {found} disagreements from {scan_index + 1} "
                f"raw inputs; categories={dict(categories)}; "
                f"q-differences={q_differences}; seed={seed:#x}",
                file=sys.stderr,
            )
            return
    print(
        f"scan exhausted: architectural={found}/{count}, "
        f"q-differences={q_differences}, "
        f"categories={dict(categories)}, inputs={scan_limit}, "
        f"seed={seed:#x}",
        file=sys.stderr,
    )


def score(
    inputs: pathlib.Path,
    capture: pathlib.Path,
    prefix: str,
) -> None:
    raw = h59.load_score_points(inputs, capture, prefix)
    print(f"loaded {len(raw)} captured h77 inputs")
    for name, use_candidate in (
        ("baseline", False),
        ("q-product", True),
    ):
        result = h58.Score(total_outputs=2 * len(raw))
        for point in raw:
            predicted = rounded(point, use_candidate)
            for side in range(2):
                output_missed = False
                for rc_index, rc in enumerate(h58.RCS):
                    mismatch = (
                        predicted[rc_index][side]
                        != point.hw[rc_index][side]
                    )
                    result.mode_misses += mismatch
                    result.rn_misses += mismatch if rc == "rn" else 0
                    output_missed |= mismatch
                result.constrained_output_misses += output_missed
        print(f"{name:9s} {result.describe()}")


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    generating = sub.add_parser("generate")
    generating.add_argument("--count", type=int, default=256)
    generating.add_argument(
        "--seed", type=lambda value: int(value, 0), default=0xF770
    )
    generating.add_argument("--scan-limit", type=int, default=20_000_000)
    scoring = sub.add_parser("score")
    scoring.add_argument("inputs", type=pathlib.Path)
    scoring.add_argument("capture", type=pathlib.Path)
    scoring.add_argument("--prefix", default="constraint_wide_q_product")
    args = parser.parse_args()
    if args.command == "generate":
        generate(args.count, args.seed, args.scan_limit)
    else:
        score(args.inputs, args.capture, args.prefix)


if __name__ == "__main__":
    main()
