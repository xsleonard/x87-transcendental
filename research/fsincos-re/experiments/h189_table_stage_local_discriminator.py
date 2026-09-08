#!/usr/bin/env python3
"""Generate and score fresh separators for h188's terminal-P survivors.

h188 finds three old-corpus profiles that improve both standalone FSIN and
the paired FSINCOS cosine lane without regressing any complete partition.
All three materialize the final P coefficient with 64-bit away rounding;
their second, individually latent operation differs.  This generator is
hardware-blind and requires pairwise separators among the current Round 34
model and all three profiles.
"""

from __future__ import annotations

import argparse
import collections
import dataclasses
import itertools
import pathlib
import random
import sys

import h58_constraint_search as h58
import h110_fsin_standalone as h110
import h135_fsin_table_terminal_discriminator as h135
import h170_fsin_table_correction_search as h170
import h171_fsin_table_correction_discriminator as h171
import h175_fsin_table_path_discriminator as h175
import h182_table_joint_terminal_edges as h182
import h188_table_stage_local_pairs as h188


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = (
    ROOT
    / "capture-kit"
    / "inputs"
    / "constraint_table_stage_local_h189.txt"
)
DEFAULT_METADATA = (
    ROOT
    / "capture-kit"
    / "inputs"
    / "constraint_table_stage_local_h189.meta.txt"
)
SEED = 0xF189C5

BASELINE = h188.CURRENT_P
CANDIDATES = (
    BASELINE,
    h188.Override(
        "p",
        coefficient=h110.Quant(64, "away"),
        sum=h110.Quant(65, "chop"),
    ),
    h188.Override(
        "p",
        coefficient=h110.Quant(64, "away"),
        product=h110.Quant(64, "away"),
    ),
    h188.Override(
        "p",
        coefficient=h110.Quant(64, "away"),
        sum=h110.Quant(65, "rn"),
    ),
)
NAMES = {
    CANDIDATES[0]: "current",
    CANDIDATES[1]: "pc64a_ps65c",
    CANDIDATES[2]: "pc64a_pp64a",
    CANDIDATES[3]: "pc64a_ps65r",
}


def name(candidate: h188.Override) -> str:
    return NAMES[candidate]


def blank(point) -> h182.Point:
    return h182.Point(
        point,
        ((0, 0),) * len(h58.RCS),
        (False,) * len(h58.RCS),
    )


def profile(
    point: h188.Point, candidate: h188.Override
) -> tuple[tuple[tuple[tuple[int, int], bool], ...], ...]:
    return tuple(
        tuple(
            (
                output := h58.x87_round(value, rc),
                h110.compare_magnitude(output, value) > 0,
            )
            for rc in h58.RCS
        )
        for value in h188.values(point, candidate)
    )


def difference_mask(left, right) -> int:
    mask = 0
    for lane, (old_lane, new_lane) in enumerate(zip(left, right)):
        for index, (old, new) in enumerate(zip(old_lane, new_lane)):
            bit = lane * 6 + index
            if old[0] != new[0]:
                mask |= 1 << bit
            if old[1] != new[1]:
                mask |= 1 << (bit + 3)
    return mask


def pair_name(left: h188.Override, right: h188.Override) -> str:
    return f"{name(left)}~{name(right)}"


def generate(
    output: pathlib.Path,
    metadata: pathlib.Path,
    per_pair: int,
    scan_limit: int,
) -> None:
    rng = random.Random(SEED)
    pairs = tuple(itertools.combinations(CANDIDATES, 2))
    counts: collections.Counter[str] = collections.Counter()
    rows = []
    meta = []
    states = set()
    for scan_index in range(scan_limit):
        if scan_index and scan_index % 100_000 == 0:
            print(
                f"h189 scan={scan_index} "
                f"counts={dict(sorted(counts.items()))}",
                file=sys.stderr,
            )
        constructed = None
        if rng.getrandbits(1):
            se, sig = h135.direct_operand(rng, "wide")
        else:
            constructed = h175.construct_table_input(rng)
            if constructed is None:
                continue
            se, sig = constructed[:2]
        observed = h171.observed_from_input(scan_index, se, sig)
        if observed is None or observed.family != "wide":
            continue
        if (
            constructed is not None
            and abs(observed.signed_n) != constructed[2]
        ):
            continue
        key = (
            observed.source,
            observed.signed_n & 3,
            observed.point.cell,
            observed.point.a,
        )
        if key in states:
            continue
        point = h188.prepare(blank(observed))
        profiles = {
            candidate: profile(point, candidate)
            for candidate in CANDIDATES
        }
        separated = []
        for left, right in pairs:
            label = pair_name(left, right)
            if counts[label] >= per_pair:
                continue
            mask = difference_mask(profiles[left], profiles[right])
            if mask:
                separated.append((left, right, label, mask))
        if not separated:
            continue
        states.add(key)
        rows.append(f"{se:04x} {sig:016x}")
        meta.append(
            f"{scan_index} {observed.source} "
            f"{observed.signed_n} {observed.point.cell} "
            + ",".join(
                f"{label}:{mask:03x}"
                for _, _, label, mask in separated
            )
        )
        for _, _, label, _ in separated:
            counts[label] += 1
        if all(counts[pair_name(*pair)] >= per_pair for pair in pairs):
            break
    missing = {
        pair_name(*pair): counts[pair_name(*pair)]
        for pair in pairs
        if counts[pair_name(*pair)] < per_pair
    }
    if missing:
        raise SystemExit(
            f"h189 stopped after {scan_limit} scans; incomplete={missing}"
        )
    output.write_text("\n".join(rows) + "\n")
    metadata.write_text("\n".join(meta) + "\n")
    print(
        f"h189: selected {len(rows)} inputs from {scan_index + 1} scans; "
        f"per-pair={dict(sorted(counts.items()))}; seed={SEED:#x}",
        file=sys.stderr,
    )


def load_capture(
    inputs: pathlib.Path, capture: pathlib.Path
) -> list[h188.Point]:
    operands = [
        tuple(int(field, 16) for field in line.split())
        for line in inputs.read_text().splitlines()
    ]
    sine_modes = [
        (
            capture
            / f"constraint_table_stage_local_h189_fsin_{rc}_status.txt"
        ).read_text().splitlines()
        for rc in h58.RCS
    ]
    pair_modes = [
        (
            capture
            / f"constraint_table_stage_local_h189_fsincos_{rc}_status.txt"
        ).read_text().splitlines()
        for rc in h58.RCS
    ]
    if any(
        len(lines) != len(operands)
        for lines in (*sine_modes, *pair_modes)
    ):
        raise SystemExit("h189 input/capture line counts differ")
    result = []
    for index, (se, sig) in enumerate(operands):
        observed = h171.observed_from_input(index, se, sig)
        if observed is None or observed.family != "wide":
            raise SystemExit(f"h189 input {index + 1} is not wide table")
        sine_outputs = []
        sine_c1 = []
        cosine_outputs = []
        cosine_c1 = []
        for sine_lines, pair_lines in zip(sine_modes, pair_modes):
            sine_fields = sine_lines[index].split()
            pair_fields = pair_lines[index].split()
            if (
                len(sine_fields) != 5
                or sine_fields[0] != "OK"
                or sine_fields[3] != "SW"
                or len(pair_fields) != 7
                or pair_fields[0] != "OK"
                or pair_fields[5] != "SW"
            ):
                raise ValueError((sine_lines[index], pair_lines[index]))
            sine_outputs.append(
                (int(sine_fields[1], 16), int(sine_fields[2], 16))
            )
            sine_c1.append(bool(int(sine_fields[4], 16) & 0x0200))
            cosine_outputs.append(
                (int(pair_fields[3], 16), int(pair_fields[4], 16))
            )
            cosine_c1.append(bool(int(pair_fields[6], 16) & 0x0200))
        joint = h182.Point(
            dataclasses.replace(
                observed,
                outputs=tuple(sine_outputs),
                c1=tuple(sine_c1),
            ),
            tuple(cosine_outputs),
            tuple(cosine_c1),
        )
        result.append(h188.prepare(joint))
    return result


def score(
    points: list[h188.Point], candidate: h188.Override
) -> tuple[h188.Metric, h188.Metric]:
    value = ((0, 0, 0), (0, 0, 0))
    for point in points:
        point_value = h188.point_score(point, candidate)
        value = tuple(
            h170.add(old, new)
            for old, new in zip(value, point_value)
        )
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--generate", action="store_true")
    parser.add_argument("--score", type=pathlib.Path)
    parser.add_argument("--per-pair", type=int, default=16)
    parser.add_argument("--scan-limit", type=int, default=30_000_000)
    parser.add_argument("--output", type=pathlib.Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--metadata", type=pathlib.Path, default=DEFAULT_METADATA
    )
    args = parser.parse_args()
    if args.generate:
        generate(args.output, args.metadata, args.per_pair, args.scan_limit)
    if args.score is not None:
        points = load_capture(args.output, args.score)
        print(f"loaded {len(points)} fresh h189 pairwise separators")
        baseline = score(points, BASELINE)
        for candidate in CANDIDATES:
            value = score(points, candidate)
            print(
                f"{name(candidate):16s} "
                f"sine {baseline[0]}->{value[0]} "
                f"cosine {baseline[1]}->{value[1]}"
            )
    if not args.generate and args.score is None:
        parser.error("select --generate and/or --score CAPTURE_DIRECTORY")


if __name__ == "__main__":
    main()
