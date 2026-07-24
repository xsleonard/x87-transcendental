#!/usr/bin/env python3
"""Generate hardware-blind separators for the second narrow carrier leaf."""

from __future__ import annotations

import argparse
import collections
import pathlib
import random
import sys

import h285_trig_sine_bias_discriminator as h285
import h291_trig_sine_bias_coordinate_scan as h291
import h301_trig_sine_fractional_discriminator as h301
import h307_trig_narrow_sine_fraction_discriminator as h307


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = (
    ROOT / "capture-kit" / "inputs" /
    "constraint_trig_narrow_sine_fraction2_h314.txt"
)
DEFAULT_METADATA = DEFAULT_OUTPUT.with_suffix(".meta.txt")
SEED = 0xF314B17
TARGET_COORDINATE = (-8, 19)


def seed_operands():
    result = []
    for input_name in ("dense_qn.txt", "sweep_inputs.txt"):
        input_path = ROOT / "capture-kit" / "inputs" / input_name
        for index, line in enumerate(input_path.read_text().splitlines()):
            se, sig = (int(field, 16) for field in line.split())
            point = h307.point_from_input(index, se, sig)
            if point is None:
                continue
            coord, rn64 = h291.coordinate(point)
            if coord != TARGET_COORDINATE:
                continue
            baseline = h301.profile(point, rn64, 32)
            candidate = h301.profile(point, rn64, 30)
            if h285.difference_mask(baseline, candidate):
                result.append((se, sig))
    if not result:
        raise SystemExit("h314 found no dense/sweep model separators")
    return tuple(result)


def random_operand(rng: random.Random, seeds):
    route = rng.randrange(6)
    if route < 5:
        se, sig = rng.choice(seeds)
        span_bits = rng.randrange(1, 51)
        sig += rng.randrange(-(1 << span_bits), 1 << span_bits)
        if not (1 << 63) <= sig < (1 << 64):
            return None
        return se, sig
    return (
        (rng.getrandbits(1) << 15) | (16383 - 2),
        rng.randrange(1 << 63, 1 << 64),
    )


def generate(output, metadata, count: int, per_stratum: int, scan_limit: int):
    seeds = seed_operands()
    rng = random.Random(SEED)
    rows = []
    meta = []
    strata = collections.Counter()
    seen = set()
    for scan_index in range(scan_limit):
        if scan_index and scan_index % 100_000 == 0:
            print(
                f"h314 scan={scan_index} selected={len(rows)} "
                f"strata={len(strata)}",
                file=sys.stderr,
            )
        operand = random_operand(rng, seeds)
        if operand is None or operand in seen:
            continue
        se, sig = operand
        point = h307.point_from_input(scan_index, se, sig)
        if point is None:
            continue
        coord, rn64 = h291.coordinate(point)
        if coord != TARGET_COORDINATE:
            continue
        profile32 = h301.profile(point, rn64, 32)
        profile30 = h301.profile(point, rn64, 30)
        mask30_32 = h285.difference_mask(profile30, profile32)
        if not mask30_32:
            continue
        observed = point.prepared.joint.observed
        key = (
            observed.source,
            observed.point.cell,
            observed.signed_n & 3,
            observed.point.raw.sign,
        )
        if strata[key] >= per_stratum:
            continue
        profile29 = h301.profile(point, rn64, 29)
        seen.add(operand)
        strata[key] += 1
        rows.append(f"{se:04x} {sig:016x}")
        meta.append(
            f"{scan_index} {observed.source} {observed.signed_n} "
            f"{observed.point.cell} sign={observed.point.raw.sign} "
            f"mask30_32={mask30_32:03x} "
            f"mask29_30={h285.difference_mask(profile29, profile30):03x}"
        )
        if len(rows) >= count:
            break
    if len(rows) < count:
        raise SystemExit(
            f"h314 found only {len(rows)}/{count} separators in "
            f"{scan_limit} scans"
        )
    output.write_text("\n".join(rows) + "\n")
    metadata.write_text(
        "\n".join(
            (
                "# hardware-blind h314 second narrow carrier separators",
                f"# seed={SEED:#x}",
                f"# seed_rows={len(seeds)} rows={len(rows)} scans={scan_index + 1}",
                "# columns: scan source signed_n cell sign masks",
                *meta,
            )
        )
        + "\n"
    )
    print(
        f"h314 wrote {len(rows)} separators after {scan_index + 1} scans; "
        f"seeds={len(seeds)} strata={dict(sorted(strata.items()))}"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=pathlib.Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--metadata", type=pathlib.Path, default=DEFAULT_METADATA
    )
    parser.add_argument("--count", type=int, default=24)
    parser.add_argument("--per-stratum", type=int, default=16)
    parser.add_argument("--scan-limit", type=int, default=1_000_000)
    args = parser.parse_args()
    generate(
        args.output.resolve(),
        args.metadata.resolve(),
        args.count,
        args.per_stratum,
        args.scan_limit,
    )


if __name__ == "__main__":
    main()
