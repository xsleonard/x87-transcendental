#!/usr/bin/env python3
"""Generate direct Round-43 and next-coordinate hardware separators.

h285 validates the Round-43 exponent/alignment rule on reduced entries.  This
hardware-blind set adds direct entries for that invariant rule and separately
tests h291's next non-regressing coordinate: wide local exponent -6,
alignment distance 15, bias 3 instead of 5.
"""

from __future__ import annotations

import argparse
import collections
import pathlib
import random
import sys

import h58_constraint_search as h58
import h135_fsin_table_terminal_discriminator as h135
import h171_fsin_table_correction_discriminator as h171
import h175_fsin_table_path_discriminator as h175
import h228_p6_four_term_c_parity as h228
import h283_trig_sine_bias_selector as h283
import h285_trig_sine_bias_discriminator as h285
import h291_trig_sine_bias_coordinate_scan as h291


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = (
    ROOT / "capture-kit" / "inputs" / "constraint_trig_sine_coordinates_h292.txt"
)
DEFAULT_METADATA = DEFAULT_OUTPUT.with_suffix(".meta.txt")
SEED = 0xF292C00D
CLASSES = ("round43-direct", "next-coordinate")


def classify(point):
    observed = point.prepared.joint.observed
    coord, _ = h291.coordinate(point)
    if observed.source == "direct" and coord == (-5, 13):
        return "round43-direct"
    if coord == (-6, 15):
        return "next-coordinate"
    return None


def random_operand(rng: random.Random):
    route = rng.randrange(3)
    if route == 0:
        return h135.direct_operand(rng, "wide")
    if route == 1:
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


def generate(output, metadata, per_class: int, per_stratum: int, scan_limit: int):
    rng = random.Random(SEED)
    rows = []
    meta = []
    counts = collections.Counter()
    strata = collections.Counter()
    seen = set()
    for scan_index in range(scan_limit):
        if scan_index and scan_index % 100_000 == 0:
            print(
                f"h292 scan={scan_index} counts={dict(counts)}",
                file=sys.stderr,
            )
        operand = random_operand(rng)
        if operand is None or operand in seen:
            continue
        se, sig = operand
        point = h285.point_from_input(scan_index, se, sig)
        if point is None:
            continue
        target = classify(point)
        if target is None or counts[target] >= per_class:
            continue
        old = h285.profile(point, h228.CANDIDATE)
        new = h285.profile(point, h283.BIAS3)
        mask = h285.difference_mask(old, new)
        if not mask:
            continue
        observed = point.prepared.joint.observed
        key = (
            target,
            observed.source,
            observed.point.cell,
            observed.signed_n & 3,
            observed.point.raw.sign,
        )
        if strata[key] >= per_stratum:
            continue
        seen.add(operand)
        strata[key] += 1
        counts[target] += 1
        rows.append(f"{se:04x} {sig:016x}")
        coord, _ = h291.coordinate(point)
        meta.append(
            f"{scan_index} {target} {observed.source} {observed.signed_n} "
            f"{observed.point.cell} sign={observed.point.raw.sign} "
            f"coord={coord[0]},{coord[1]} mask={mask:03x}"
        )
        if all(counts[name] >= per_class for name in CLASSES):
            break
    missing = {
        name: counts[name] for name in CLASSES if counts[name] < per_class
    }
    if missing:
        raise SystemExit(
            f"h292 incomplete after {scan_limit} scans: {missing}"
        )
    output.write_text("\n".join(rows) + "\n")
    metadata.write_text(
        "\n".join(
            (
                "# hardware-blind h292 shared-sine coordinate separators",
                f"# seed={SEED:#x}",
                f"# rows={len(rows)} scans={scan_index + 1}",
                "# columns: scan class source signed_n cell sign coord mask",
                *meta,
            )
        )
        + "\n"
    )
    print(
        f"h292 wrote {len(rows)} rows after {scan_index + 1} scans; "
        f"counts={dict(counts)} strata={len(strata)}"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=pathlib.Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--metadata", type=pathlib.Path, default=DEFAULT_METADATA)
    parser.add_argument("--per-class", type=int, default=128)
    parser.add_argument("--per-stratum", type=int, default=24)
    parser.add_argument("--scan-limit", type=int, default=3_000_000)
    args = parser.parse_args()
    generate(
        args.output.resolve(),
        args.metadata.resolve(),
        args.per_class,
        args.per_stratum,
        args.scan_limit,
    )


if __name__ == "__main__":
    main()
