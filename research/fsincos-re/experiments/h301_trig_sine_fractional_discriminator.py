#!/usr/bin/env python3
"""Generate hardware-blind separators for 21/256 versus 22/256 ulp.

The h300 cross-validation leaves both fractional carriers tied at the
`(-6, 15)` shared-sine coordinate.  This set contains only inputs whose full
RN/RD/RU result-or-C1 profiles distinguish those two values.  The older
19/256 profile is recorded as a secondary separator without consulting any
hardware output.
"""

from __future__ import annotations

import argparse
import collections
import pathlib
import random
import sys

import h58_constraint_search as h58
import h79_table_state_bias as h79
import h110_fsin_standalone as h110
import h175_fsin_table_path_discriminator as h175
import h283_trig_sine_bias_selector as h283
import h285_trig_sine_bias_discriminator as h285
import h291_trig_sine_bias_coordinate_scan as h291
import h293_ingest_trig_coordinate_capture as h293


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = (
    ROOT / "capture-kit" / "inputs" / "constraint_trig_sine_fraction_h301.txt"
)
DEFAULT_METADATA = DEFAULT_OUTPUT.with_suffix(".meta.txt")
SEED = 0xF301B17
DENOMINATOR_BITS = 8


def seed_operands():
    labels = h293.classes()
    operands = [
        tuple(int(field, 16) for field in line.split())
        for line in (
            ROOT / "capture-kit" / "inputs" /
            "constraint_trig_sine_coordinates_h292.txt"
        ).read_text().splitlines()
    ]
    return tuple(
        operand
        for operand, label in zip(operands, labels)
        if label == "next-coordinate"
    )


SEED_OPERANDS = seed_operands()


def profile(point, rn64, numerator: int):
    sine = h79.bias_toward_zero(
        rn64, numerator, DENOMINATOR_BITS
    )
    values = h291.hidden_values(point, sine)
    result = []
    for rc in h58.RCS:
        lanes = []
        for value in values:
            output = h58.x87_round(value, rc)
            lanes.append(
                (output, h110.compare_magnitude(output, value) > 0)
            )
        result.append(tuple(lanes))
    return tuple(result)


def random_operand(rng: random.Random):
    route = rng.randrange(6)
    if route < 4:
        se, sig = rng.choice(SEED_OPERANDS)
        span_bits = rng.randrange(1, 53)
        sig += rng.randrange(-(1 << span_bits), 1 << span_bits)
        if not (1 << 63) <= sig < (1 << 64):
            return None
        return se, sig
    if route == 4:
        constructed = h175.construct_table_input(rng)
        if constructed is None:
            return None
        se, sig = constructed[:2]
        if rng.getrandbits(1):
            se ^= 0x8000
        return se, sig
    exponent = rng.randrange(0, 63)
    return (
        (rng.getrandbits(1) << 15) | (exponent + 16383),
        rng.randrange(1 << 63, 1 << 64),
    )


def generate(output, metadata, count: int, per_stratum: int, scan_limit: int):
    rng = random.Random(SEED)
    rows = []
    meta = []
    strata = collections.Counter()
    seen = set()
    for scan_index in range(scan_limit):
        if scan_index and scan_index % 250_000 == 0:
            print(
                f"h301 scan={scan_index} selected={len(rows)} "
                f"strata={len(strata)}",
                file=sys.stderr,
            )
        operand = random_operand(rng)
        if operand is None or operand in seen:
            continue
        se, sig = operand
        point = h285.point_from_input(scan_index, se, sig)
        if point is None:
            continue
        coord, rn64 = h291.coordinate(point)
        if coord != (-6, 15):
            continue
        profile21 = profile(point, rn64, 21)
        profile22 = profile(point, rn64, 22)
        mask21_22 = h285.difference_mask(profile21, profile22)
        if not mask21_22:
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
        profile19 = profile(point, rn64, 19)
        seen.add(operand)
        strata[key] += 1
        rows.append(f"{se:04x} {sig:016x}")
        meta.append(
            f"{scan_index} {observed.source} {observed.signed_n} "
            f"{observed.point.cell} sign={observed.point.raw.sign} "
            f"mask21_22={mask21_22:03x} "
            f"mask19_21={h285.difference_mask(profile19, profile21):03x}"
        )
        if len(rows) >= count:
            break
    if len(rows) < count:
        raise SystemExit(
            f"h301 found only {len(rows)}/{count} separators in "
            f"{scan_limit} scans"
        )
    output.write_text("\n".join(rows) + "\n")
    metadata.write_text(
        "\n".join(
            (
                "# hardware-blind h301 fractional shared-sine separators",
                f"# seed={SEED:#x}",
                f"# rows={len(rows)} scans={scan_index + 1}",
                "# columns: scan source signed_n cell sign masks",
                *meta,
            )
        )
        + "\n"
    )
    print(
        f"h301 wrote {len(rows)} separators after {scan_index + 1} scans; "
        f"strata={dict(sorted(strata.items()))}"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=pathlib.Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--metadata", type=pathlib.Path, default=DEFAULT_METADATA
    )
    parser.add_argument("--count", type=int, default=32)
    parser.add_argument("--per-stratum", type=int, default=8)
    parser.add_argument("--scan-limit", type=int, default=5_000_000)
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
