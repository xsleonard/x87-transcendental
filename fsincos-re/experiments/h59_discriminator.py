#!/usr/bin/env python3
"""Generate and score a fresh Skylake discriminator for h58's survivor.

Generation is host-FP-free: it samples raw x87 significands in each direct
table cell and retains only inputs for which the baseline and the candidate
micro-operation schedules predict different FSINCOS output bits.  Capture the
resulting inputs under RN/RD/RU on the x87 test host, then use ``score`` to
measure which schedule predicts the held-out silicon observations.
"""

from __future__ import annotations

import argparse
import pathlib
import random
import sys

import h58_constraint_search as h58


CELLS = (
    # cell, unbiased exponent, inclusive significand start, exclusive end
    (18, -2, 0x8000000000000000, 0xA000000000000000),
    (22, -2, 0xA000000000000000, 0xC000000000000000),
    (26, -2, 0xC000000000000000, 0xE000000000000000),
    (30, -2, 0xE000000000000000, 0x10000000000000000),
    (36, -1, 0x8000000000000000, 0xA000000000000000),
    (44, -1, 0xA000000000000000, 0xC000000000000000),
    (52, -1, 0xC000000000000000, 0xC90FDAA22168C234),
)
DUMMY_HW = (((0, 0), (0, 0)),) * 3


def candidate_config(
    profile: str, raw: h58.RawPoint | None = None
) -> tuple[h58.ProducerConfig, h58.TailConfig]:
    if profile == "narrow":
        if raw is not None and raw.exponent != -2:
            return h58.BASE_PRODUCER, h58.BASE
        return h58.BASE_PRODUCER, h58.NARROW_TAIL
    if profile == "wide":
        if raw is not None and raw.exponent != -1:
            return h58.BASE_PRODUCER, h58.BASE
        return h58.BASE_PRODUCER, h58.WIDE_TAIL
    if profile == "global":
        return h58.CANDIDATE_PRODUCER, h58.NEAR_TAIL
    raise ValueError(profile)


def predictions(
    raw: h58.RawPoint, profile: str
) -> tuple[
    tuple[tuple[tuple[int, int], tuple[int, int]], ...],
    tuple[tuple[tuple[int, int], tuple[int, int]], ...],
]:
    baseline_values = h58.table_tail(h58.prepare(raw), h58.BASE)
    producer, tail = candidate_config(profile, raw)
    candidate_values = h58.table_tail(h58.prepare(raw, producer), tail)
    baseline = tuple(
        tuple(h58.x87_round(value, rc) for value in baseline_values)
        for rc in h58.RCS
    )
    candidate = tuple(
        tuple(h58.x87_round(value, rc) for value in candidate_values)
        for rc in h58.RCS
    )
    return baseline, candidate


def generate(count: int, seed: int, scan_limit: int, profile: str) -> None:
    rng = random.Random(seed)
    cells = CELLS[:4] if profile == "narrow" else CELLS[4:]
    if profile == "global":
        cells = CELLS
    found = 0
    for scan_index in range(scan_limit):
        _, exponent, start, end = cells[scan_index % len(cells)]
        sig = rng.randrange(start, end)
        sign = rng.randrange(2)
        raw = h58.RawPoint(
            index=found,
            sign=sign,
            exponent=exponent,
            sig=sig,
            hw=DUMMY_HW,
        )
        baseline, candidate = predictions(raw, profile)
        if baseline == candidate:
            continue
        se = (sign << 15) | (exponent + 16383)
        print(f"{se:04x} {sig:016x}")
        found += 1
        if found == count:
            print(
                f"selected {found} disagreements from {scan_index + 1} "
                f"raw inputs (seed {seed:#x})",
                file=sys.stderr,
            )
            return
    raise SystemExit(
        f"found only {found} disagreements in {scan_limit} raw inputs"
    )


def load_score_points(
    inputs: pathlib.Path, captures: pathlib.Path, capture_prefix: str
) -> list[h58.RawPoint]:
    input_lines = inputs.read_text().splitlines()
    output_lines = [
        (captures / f"{capture_prefix}_{rc}.txt").read_text().splitlines()
        for rc in h58.RCS
    ]
    if any(len(lines) != len(input_lines) for lines in output_lines):
        raise SystemExit("input/capture line counts differ")
    points = []
    for index, line in enumerate(input_lines):
        se_text, sig_text = line.split()
        se, sig = int(se_text, 16), int(sig_text, 16)
        points.append(
            h58.RawPoint(
                index=index,
                sign=se >> 15,
                exponent=(se & 0x7FFF) - 16383,
                sig=sig,
                hw=tuple(
                    h58.parse_sincos(lines[index]) for lines in output_lines
                ),
            )
        )
    return points


def load_input_points(inputs: pathlib.Path) -> list[h58.RawPoint]:
    points = []
    for index, line in enumerate(inputs.read_text().splitlines()):
        se_text, sig_text = line.split()
        se, sig = int(se_text, 16), int(sig_text, 16)
        points.append(
            h58.RawPoint(
                index=index,
                sign=se >> 15,
                exponent=(se & 0x7FFF) - 16383,
                sig=sig,
                hw=DUMMY_HW,
            )
        )
    return points


def emit(inputs: pathlib.Path, profile: str, rc: str, which: str) -> None:
    rc_index = h58.RCS.index(rc)
    for point in load_input_points(inputs):
        baseline, candidate = predictions(point, profile)
        outputs = baseline if which == "baseline" else candidate
        sine, cosine = outputs[rc_index]
        print(
            f"OK {sine[0]:04x} {sine[1]:016x} "
            f"{cosine[0]:04x} {cosine[1]:016x}"
        )


def score(
    inputs: pathlib.Path,
    captures: pathlib.Path,
    capture_prefix: str,
    profile: str,
) -> None:
    points = load_score_points(inputs, captures, capture_prefix)
    candidate_producer, candidate_tail = candidate_config(profile)
    configs = (
        ("baseline", h58.BASE_PRODUCER, h58.BASE),
        (profile, candidate_producer, candidate_tail),
    )
    for name, producer, tail in configs:
        prepared = [h58.prepare(point, producer) for point in points]
        result = h58.score_config(prepared, tail)
        print(f"{name:9s} {producer.short():30s} {tail.short():46s}")
        print(f"          {result.describe()}")
        for key in sorted(result.by_region):
            if result.by_region[key]:
                print(
                    f"          {key[0]:6s} {key[1]}: "
                    f"{result.by_region[key]:.0f}"
                )


def search(
    inputs: pathlib.Path,
    captures: pathlib.Path,
    capture_prefix: str,
    keep: int,
) -> None:
    print(
        "warning: discriminator-conditioned fits must be rechecked on the "
        "complete capture"
    )
    raw = load_score_points(inputs, captures, capture_prefix)
    points = [h58.prepare(point) for point in raw]
    weights = {point.raw.index: 1.0 for point in points}
    print(f"loaded {len(points)} captured discriminator inputs")
    print(f"baseline: {h58.score_config(points, h58.BASE).describe()}")
    s_configs = h58.search_tail(points, weights, keep)
    t_configs = h58.search_t(points, weights, keep)
    finalists = h58.cross_search(
        points, weights, s_configs, t_configs, keep
    )
    print("discriminator verification:")
    for tail in (h58.BASE, *finalists):
        result = h58.score_config(points, tail)
        print(f"  {tail.short():46s} {result.describe()}")


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    gen = sub.add_parser("generate")
    gen.add_argument("--count", type=int, default=5000)
    gen.add_argument("--seed", type=lambda value: int(value, 0), default=0xF59C)
    gen.add_argument("--scan-limit", type=int, default=5_000_000)
    gen.add_argument(
        "--profile", choices=("narrow", "wide", "global"), default="narrow"
    )
    scoring = sub.add_parser("score")
    scoring.add_argument("inputs", type=pathlib.Path)
    scoring.add_argument("captures", type=pathlib.Path)
    scoring.add_argument("--capture-prefix", default="discriminator")
    scoring.add_argument(
        "--profile", choices=("narrow", "wide", "global"), default="narrow"
    )
    searching = sub.add_parser("search")
    searching.add_argument("inputs", type=pathlib.Path)
    searching.add_argument("captures", type=pathlib.Path)
    searching.add_argument("--capture-prefix", default="discriminator")
    searching.add_argument("--keep", type=int, default=12)
    emitting = sub.add_parser("emit")
    emitting.add_argument("inputs", type=pathlib.Path)
    emitting.add_argument(
        "--profile", choices=("narrow", "wide", "global"), default="narrow"
    )
    emitting.add_argument("--rc", choices=h58.RCS, default="rn")
    emitting.add_argument(
        "--which", choices=("baseline", "candidate"), default="candidate"
    )
    args = parser.parse_args()
    if args.command == "generate":
        generate(args.count, args.seed, args.scan_limit, args.profile)
    elif args.command == "score":
        score(
            args.inputs, args.captures, args.capture_prefix, args.profile
        )
    elif args.command == "search":
        search(
            args.inputs, args.captures, args.capture_prefix, args.keep
        )
    else:
        emit(args.inputs, args.profile, args.rc, args.which)


if __name__ == "__main__":
    main()
