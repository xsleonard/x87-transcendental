#!/usr/bin/env python3
"""Generate hardware-blind separators for the h284 sine-bias rule.

The candidate selects wide shared-sine bias 3 instead of 5 only when the
FADD alignment distance is 13 and the local residual's top exponent is -5.
Inputs
are selected solely where the frozen baseline and candidate predict different
RN/RD/RU result or C1 profiles.  Hardware output is never consulted.
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
import h171_fsin_table_correction_discriminator as h171
import h175_fsin_table_path_discriminator as h175
import h188_table_stage_local_pairs as h188
import h207_tang_literal_fadd as h207
import h216_fadd_microcontrol_discriminator as h216
import h228_p6_four_term_c_parity as h228
import h230_p6_microop_materialization_search as h230
import h283_trig_sine_bias_selector as h283


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = (
    ROOT / "capture-kit" / "inputs" / "constraint_trig_sine_bias_h285.txt"
)
DEFAULT_METADATA = DEFAULT_OUTPUT.with_suffix(".meta.txt")
SEED = 0xF285B1A5


def point_from_input(index: int, se: int, sig: int):
    observed = h171.observed_from_input(index, se, sig)
    if observed is None or observed.family != "wide":
        return None
    return h207.Point(h188.prepare(h216.blank(observed)), True)


def selected(point) -> bool:
    values = h283.features(point)
    return (
        values["align.difference"] == 13
        and values["a.top-exponent"] == -5
    )


def profile(point, candidate):
    values = h230.hidden_values(point, candidate)
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


def difference_mask(left, right) -> int:
    mask = 0
    for rc_index, (old_modes, new_modes) in enumerate(zip(left, right)):
        for lane, (old, new) in enumerate(zip(old_modes, new_modes)):
            bit = rc_index * 4 + lane * 2
            if old[0] != new[0]:
                mask |= 1 << bit
            if old[1] != new[1]:
                mask |= 1 << (bit + 1)
    return mask


def random_operand(rng: random.Random):
    if rng.getrandbits(1):
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
        if scan_index and scan_index % 100_000 == 0:
            print(
                f"h285 scan={scan_index} selected={len(rows)} "
                f"strata={len(strata)}",
                file=sys.stderr,
            )
        operand = random_operand(rng)
        if operand is None or operand in seen:
            continue
        se, sig = operand
        point = point_from_input(scan_index, se, sig)
        if point is None or not selected(point):
            continue
        old = profile(point, h228.CANDIDATE)
        new = profile(point, h283.BIAS3)
        mask = difference_mask(old, new)
        if not mask:
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
        seen.add(operand)
        strata[key] += 1
        rows.append(f"{se:04x} {sig:016x}")
        meta.append(
            f"{scan_index} {observed.source} {observed.signed_n} "
            f"{observed.point.cell} sign={observed.point.raw.sign} "
            f"mask={mask:03x}"
        )
        if len(rows) >= count:
            break
    if len(rows) < count:
        raise SystemExit(
            f"h285 found only {len(rows)}/{count} separators in "
            f"{scan_limit} scans"
        )
    output.write_text("\n".join(rows) + "\n")
    metadata.write_text(
        "\n".join(
            (
                "# hardware-blind h285 shared-sine bias separators",
                f"# seed={SEED:#x}",
                f"# rows={len(rows)} scans={scan_index + 1}",
                "# columns: scan source signed_n cell sign difference-mask",
                *meta,
            )
        )
        + "\n"
    )
    print(
        f"h285 wrote {len(rows)} separators after {scan_index + 1} scans; "
        f"strata={dict(sorted(strata.items()))}"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=pathlib.Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--metadata", type=pathlib.Path, default=DEFAULT_METADATA
    )
    parser.add_argument("--count", type=int, default=192)
    parser.add_argument("--per-stratum", type=int, default=16)
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
