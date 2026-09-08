#!/usr/bin/env python3
"""Separate the Round-16 candidate's observationally-equivalent m widths.

The complete dense capture and h59 cannot distinguish m=RN68(P*a^2) from
m=RN69 or m=chop69 once u=chop68(1+m) is formed.  This host-FP-free search
first detects differences in the shared S carrier, then retains only raw x87
inputs whose final RN/RD/RU predictions distinguish the schedules.
"""

from __future__ import annotations

import argparse
import dataclasses
import pathlib
import random
import sys

import h58_constraint_search as h58
import h59_discriminator as h59


VARIANTS = (
    (
        "m68rn",
        dataclasses.replace(h58.NARROW_TAIL, m_bits=68, m_mode="rn"),
    ),
    (
        "m69rn",
        h58.NARROW_TAIL,
    ),
    (
        "m69chop",
        dataclasses.replace(h58.NARROW_TAIL, m_bits=69, m_mode="chop"),
    ),
)
DUMMY_HW = (((0, 0), (0, 0)),) * 3


def sine_a(point: h58.PreparedPoint, cfg: h58.TailConfig) -> h58.FP:
    m = h58.fmul(point.p, point.asq, cfg.m_bits, cfg.m_mode)
    u = h58.fadd(h58.ONE, m, cfg.mid_bits, cfg.mid_mode)
    return h58.fmul(point.a, u, cfg.s_bits, cfg.s_mode)


def rounded_prediction(
    point: h58.PreparedPoint, cfg: h58.TailConfig
) -> tuple[tuple[tuple[int, int], tuple[int, int]], ...]:
    values = h58.table_tail(point, cfg)
    return tuple(
        tuple(h58.x87_round(value, rc) for value in values)
        for rc in h58.RCS
    )


def generate(
    count: int, seed: int, scan_limit: int, carrier_only: bool
) -> None:
    rng = random.Random(seed)
    found = 0
    s_disagreements = 0
    variant_hits = {name: 0 for name, _ in VARIANTS[1:]}
    for scan_index in range(scan_limit):
        cell_index = scan_index & 3
        start = 0x8000000000000000 + cell_index * 0x2000000000000000
        raw = h58.RawPoint(
            index=found,
            sign=rng.randrange(2),
            exponent=-2,
            sig=rng.randrange(start, start + 0x2000000000000000),
            hw=DUMMY_HW,
        )
        point = h58.prepare(raw, h58.BASE_PRODUCER)
        s_values = tuple(sine_a(point, cfg) for _, cfg in VARIANTS)
        if len(set(s_values)) == 1:
            continue
        s_disagreements += 1
        if carrier_only:
            se = (raw.sign << 15) | 0x3FFD
            print(f"{se:04x} {raw.sig:016x}")
            found += 1
            if found == count:
                print(
                    f"selected {found} S-carrier disagreements from "
                    f"{scan_index + 1} raw inputs; seed={seed:#x}",
                    file=sys.stderr,
                )
                return
            continue
        predictions = tuple(
            rounded_prediction(point, cfg) for _, cfg in VARIANTS
        )
        if len(set(predictions)) == 1:
            continue
        reference = predictions[0]
        for (name, _), prediction in zip(VARIANTS[1:], predictions[1:]):
            variant_hits[name] += prediction != reference
        se = (raw.sign << 15) | 0x3FFD
        print(f"{se:04x} {raw.sig:016x}")
        found += 1
        if found == count:
            print(
                f"selected {found} final-output disagreements from "
                f"{scan_index + 1} raw inputs; "
                f"{s_disagreements} S-carrier disagreements; "
                f"hits={variant_hits}; seed={seed:#x}",
                file=sys.stderr,
            )
            return
    raise SystemExit(
        f"found {found}/{count} final-output disagreements in {scan_limit} "
        f"raw inputs; {s_disagreements} S-carrier disagreements; "
        f"hits={variant_hits}; seed={seed:#x}"
    )


def compare(inputs: pathlib.Path) -> None:
    points = [
        h58.prepare(raw, h58.BASE_PRODUCER)
        for raw in h59.load_input_points(inputs)
    ]
    reference = [
        rounded_prediction(point, VARIANTS[0][1]) for point in points
    ]
    print(f"loaded {len(points)} inputs")
    for name, cfg in VARIANTS:
        predictions = [rounded_prediction(point, cfg) for point in points]
        differing_inputs = sum(
            prediction != expected
            for prediction, expected in zip(predictions, reference)
        )
        differing_mode_outputs = sum(
            actual != expected
            for predictions_by_rc, reference_by_rc in zip(
                predictions, reference
            )
            for actual_rc, expected_rc in zip(
                predictions_by_rc, reference_by_rc
            )
            for actual, expected in zip(actual_rc, expected_rc)
        )
        print(
            f"{name:8s} differing inputs={differing_inputs}, "
            f"mode-outputs={differing_mode_outputs}"
        )


def score(
    inputs: pathlib.Path, captures: pathlib.Path, capture_prefix: str
) -> None:
    raw = h59.load_score_points(inputs, captures, capture_prefix)
    points = [h58.prepare(point, h58.BASE_PRODUCER) for point in raw]
    print(f"loaded {len(points)} captured m-width discriminator inputs")
    for name, cfg in VARIANTS:
        result = h58.score_config(points, cfg)
        print(f"{name:8s} {result.describe()}")


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    generating = sub.add_parser("generate")
    generating.add_argument("--count", type=int, default=1)
    generating.add_argument(
        "--seed", type=lambda value: int(value, 0), default=0xF623
    )
    generating.add_argument("--scan-limit", type=int, default=10_000_000)
    generating.add_argument(
        "--carrier-only",
        action="store_true",
        help="emit internal S disagreements even when final x87 bits agree",
    )
    comparing = sub.add_parser("compare")
    comparing.add_argument("inputs", type=pathlib.Path)
    scoring = sub.add_parser("score")
    scoring.add_argument("inputs", type=pathlib.Path)
    scoring.add_argument("captures", type=pathlib.Path)
    scoring.add_argument("--capture-prefix", default="constraint_mwidth")
    args = parser.parse_args()

    if args.command == "generate":
        generate(args.count, args.seed, args.scan_limit, args.carrier_only)
    elif args.command == "compare":
        compare(args.inputs)
    else:
        score(args.inputs, args.captures, args.capture_prefix)


if __name__ == "__main__":
    main()
