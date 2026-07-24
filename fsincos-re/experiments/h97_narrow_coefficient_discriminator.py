#!/usr/bin/env python3
"""Generate a held-out discriminator for the narrow P5S4_1 ROM bits.

The h96 follow-up found that increasing the magnitude of the negative
leading sine coefficient improves every existing narrow-family dataset and
the untouched master.  This generator selects direct narrow inputs where
candidate low-ROM-unit corrections predict different architectural results.
It does not consult hardware.
"""

from __future__ import annotations

import argparse
import collections
import dataclasses
import pathlib
import random
import sys

import h58_constraint_search as h58
import h78_paired_table_tomography as h78
import h79_table_state_bias as h79


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = (
    ROOT
    / "capture-kit"
    / "inputs"
    / "constraint_narrow_coefficient_h97.txt"
)
SEED = 0xF971C05
DELTAS = (
    -4096,
    -2048,
    0,
    1024,
    2048,
    3072,
    4096,
    5120,
    6144,
    7168,
    8192,
    10240,
    12288,
)


def alter_p(
    point: h58.PreparedPoint,
    delta: int,
) -> h58.PreparedPoint:
    rows = h58.S4
    value = h58.coefficient(rows[0], h58.BASE_PRODUCER)
    for row in rows[1:-1]:
        value = h58.fadd(
            h58.fmul(value, point.asq, 64, "rn"),
            h58.coefficient(row, h58.BASE_PRODUCER),
            64,
            "rn",
        )
    constant = h58.ROM[rows[-1]]
    constant = (
        constant[0],
        constant[1] + delta,
        constant[2],
    )
    value = h58.fadd(
        h58.fmul(value, point.asq, 64, "rn"),
        constant,
        64,
        "rn",
    )
    return dataclasses.replace(point, p=value)


def predictions(
    se: int,
    sig: int,
    delta: int,
    bias_numerator: int = 4,
    bias_denominator_bits: int = 5,
) -> tuple[tuple[tuple[int, int], tuple[int, int]], ...]:
    raw = h58.RawPoint(
        index=0,
        sign=se >> 15,
        exponent=(se & 0x7FFF) - 16383,
        sig=sig,
        hw=h78.DUMMY_HW,
    )
    point = alter_p(h58.prepare(raw), delta)
    values = h79.values(
        point,
        h79.BASE,
        bias_numerator,
        bias_denominator_bits,
    )
    return tuple(
        tuple(h58.x87_round(value, rc) for value in values)
        for rc in h58.RCS
    )


def signature(
    profiles: tuple[
        tuple[tuple[tuple[int, int], tuple[int, int]], ...],
        ...,
    ],
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    lanes = []
    for lane in (0, 1):
        classes: dict[
            tuple[tuple[int, int], ...], int
        ] = {}
        lanes.append(
            tuple(
                classes.setdefault(
                    tuple(result[lane] for result in profile),
                    len(classes),
                )
                for profile in profiles
            )
        )
    return tuple(lanes)  # type: ignore[return-value]


def load_capture(
    inputs: pathlib.Path,
    capture: pathlib.Path,
) -> list[tuple[int, int, tuple[tuple[tuple[int, int], tuple[int, int]], ...]]]:
    input_lines = inputs.read_text().splitlines()
    outputs = [
        (capture / f"constraint_narrow_coefficient_{rc}.txt")
        .read_text()
        .splitlines()
        for rc in h58.RCS
    ]
    if any(len(lines) != len(input_lines) for lines in outputs):
        raise SystemExit(
            "h97 input/capture line counts differ: "
            f"inputs={len(input_lines)}, "
            f"outputs={[len(lines) for lines in outputs]}"
        )
    result = []
    for index, line in enumerate(input_lines):
        se_text, sig_text = line.split()
        result.append(
            (
                int(se_text, 16),
                int(sig_text, 16),
                tuple(
                    h58.parse_sincos(lines[index])
                    for lines in outputs
                ),
            )
        )
    return result


def score_capture(
    inputs: pathlib.Path,
    capture: pathlib.Path,
    deltas: tuple[int, ...],
) -> None:
    raw = load_capture(inputs, capture)
    ranked = []
    for delta in deltas:
        mode_misses = 0
        rn_misses = 0
        lane_misses = [0, 0]
        input_misses = 0
        for se, sig, hardware in raw:
            predicted = predictions(se, sig, delta)
            missed_input = False
            for rc_index, (expected_lanes, actual_lanes) in enumerate(
                zip(predicted, hardware)
            ):
                for lane, (expected, actual) in enumerate(
                    zip(expected_lanes, actual_lanes)
                ):
                    mismatch = expected != actual
                    mode_misses += mismatch
                    rn_misses += mismatch if rc_index == 0 else 0
                    lane_misses[lane] += mismatch
                    missed_input |= mismatch
            input_misses += missed_input
        rank = (mode_misses, input_misses, rn_misses, *lane_misses)
        ranked.append((rank, delta))
    print(
        f"h97: scored {len(raw)} inputs / {len(raw) * 6} "
        "output-mode checks"
    )
    for rank, delta in sorted(ranked):
        mode_misses, input_misses, rn_misses, sine_misses, cosine_misses = rank
        print(
            f"  delta={delta:+6d}: mode={mode_misses:4d} "
            f"inputs={input_misses:4d} rn={rn_misses:4d} "
            f"sin={sine_misses:4d} cos={cosine_misses:4d}"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=pathlib.Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--count", type=int, default=1536)
    parser.add_argument("--scan-limit", type=int, default=2_000_000)
    parser.add_argument(
        "--score",
        type=pathlib.Path,
        metavar="CAPTURE",
        help="score candidate deltas against a returned h97 capture directory",
    )
    parser.add_argument(
        "--fine-low",
        type=int,
        help="replace the coarse delta set with every delta in [LOW, HIGH]",
    )
    parser.add_argument("--fine-high", type=int)
    args = parser.parse_args()

    if args.score is not None:
        if (args.fine_low is None) != (args.fine_high is None):
            parser.error("--fine-low and --fine-high must be supplied together")
        deltas = DELTAS
        if args.fine_low is not None:
            if args.fine_low > args.fine_high:
                parser.error("--fine-low must not exceed --fine-high")
            deltas = tuple(range(args.fine_low, args.fine_high + 1))
        score_capture(args.output, args.score, deltas)
        return

    rng = random.Random(SEED)
    selected: list[tuple[int, int]] = []
    counts: collections.Counter[
        tuple[tuple[int, ...], tuple[int, ...]]
    ] = collections.Counter()
    for scan_index in range(args.scan_limit):
        sign = rng.getrandbits(1)
        se = (sign << 15) | 0x3FFD
        sig = rng.randrange(1 << 63, 1 << 64)
        profiles = tuple(
            predictions(se, sig, delta) for delta in DELTAS
        )
        if len(set(profiles)) == 1:
            continue
        key = signature(profiles)
        if counts[key] >= 64:
            continue
        counts[key] += 1
        selected.append((se, sig))
        if len(selected) >= args.count:
            break

    args.output.write_text(
        "".join(f"{se:04x} {sig:016x}\n" for se, sig in selected)
    )
    print(
        f"h97: selected {len(selected)} inputs from "
        f"{scan_index + 1} scans across {len(counts)} signatures; "
        f"seed={SEED:#x}; deltas={DELTAS}",
        file=sys.stderr,
    )
    if len(selected) < args.count:
        print(
            f"h97: requested {args.count}, exhausted scan limit",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
