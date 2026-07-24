#!/usr/bin/env python3
"""Separate the narrow P5S4_1 correction from the shared-S bias.

h97 independently confirms that increasing the magnitude of the row-169
coefficient improves Skylake, but a one-dimensional fit moves depending on
the dataset because Round 21's constant shared-S bias is still a proxy.  This
pass jointly fits:

    P5S4_1 significand += delta
    S' = S - sign(S) * bias/256 * ulp64(S)

against the exact paired-cell S intervals from h78 and h95.  The best
interval candidates are then scored against h97's held-out architectural
outputs.  This is a diagnostic parameter separation, not evidence that
either fitted number is itself a physical micro-operation.
"""

from __future__ import annotations

import argparse
import dataclasses
import fractions
import pathlib

import h58_constraint_search as h58
import h59_discriminator as h59
import h78_paired_table_tomography as h78
import h79_table_state_bias as h79
import h96_table_state_regression as h96
import h97_narrow_coefficient_discriminator as h97


ROOT = pathlib.Path(__file__).resolve().parents[1]
H97_INPUTS = (
    ROOT
    / "capture-kit"
    / "inputs"
    / "constraint_narrow_coefficient_h97.txt"
)
H97_CAPTURE = (
    ROOT
    / "capture-kit-captures"
    / "skylake-h97-narrow-coefficient"
)


@dataclasses.dataclass(frozen=True)
class Interval:
    point: h58.PreparedPoint
    low: fractions.Fraction
    high: fractions.Fraction
    ulp: fractions.Fraction
    dataset: str


def tight_intervals(
    family_filter: str,
    max_width_bits: int = -68,
) -> list[Interval]:
    result = []
    for dataset, inputs, metadata, capture, prefix in h96.DATASETS:
        raw = h59.load_score_points(inputs, capture, prefix)
        meta = [line.split() for line in metadata.read_text().splitlines()]
        grouped: dict[tuple[str, int], list[h58.PreparedPoint]] = {}
        for item, fields in zip(raw, meta):
            key = fields[0], int(fields[1])
            grouped.setdefault(key, []).append(h58.prepare(item))
        for (family, _), points in grouped.items():
            if family != family_filter:
                continue
            inequalities, _, s0 = h78.group_inequalities(points)
            vertices = h78.feasible_vertices(inequalities)
            if not vertices:
                continue
            ss = [vertex[1] for vertex in vertices]
            low, high = min(ss), max(ss)
            if h78.log2_fraction(high - low) > max_width_bits:
                continue
            result.append(
                Interval(
                    point=points[0],
                    low=low,
                    high=high,
                    ulp=h78.local_ulp(s0),
                    dataset=dataset,
                )
            )
    return result


def tight_narrow_intervals(max_width_bits: int = -68) -> list[Interval]:
    return tight_intervals("narrow", max_width_bits)


def candidate_ds(
    point: h58.PreparedPoint,
    delta: int,
    bias: int,
    denominator_bits: int,
) -> h58.FP:
    baseline = h79.table_state(point, h79.BASE)[1]
    altered = h97.alter_p(point, delta)
    candidate = h79.table_state(altered, h79.BASE)[1]
    candidate = h79.bias_toward_zero(
        candidate,
        bias,
        denominator_bits,
    )
    return h58.add_exact(candidate, h58.neg(baseline))


def interval_rank(
    intervals: list[Interval],
    delta: int,
    bias: int,
    denominator_bits: int,
) -> tuple[int, float, float]:
    outside = 0
    total_distance = 0.0
    worst_distance = 0.0
    for record in intervals:
        value = h78.fp_fraction(
            candidate_ds(
                record.point,
                delta,
                bias,
                denominator_bits,
            )
        )
        if value < record.low:
            distance = float((record.low - value) / record.ulp)
        elif value > record.high:
            distance = float((value - record.high) / record.ulp)
        else:
            distance = 0.0
        outside += distance != 0.0
        total_distance += distance
        worst_distance = max(worst_distance, distance)
    return outside, total_distance, worst_distance


def h97_rank(
    raw: list[
        tuple[
            int,
            int,
            tuple[tuple[tuple[int, int], tuple[int, int]], ...],
        ]
    ],
    delta: int,
    bias: int,
    denominator_bits: int,
) -> tuple[int, int, int]:
    mode_misses = 0
    input_misses = 0
    rn_misses = 0
    for se, sig, hardware in raw:
        predicted = h97.predictions(
            se,
            sig,
            delta,
            bias,
            denominator_bits,
        )
        missed_input = False
        for rc_index, (expected_lanes, actual_lanes) in enumerate(
            zip(predicted, hardware)
        ):
            for expected, actual in zip(expected_lanes, actual_lanes):
                mismatch = expected != actual
                mode_misses += mismatch
                rn_misses += mismatch if rc_index == 0 else 0
                missed_input |= mismatch
        input_misses += missed_input
    return mode_misses, input_misses, rn_misses


def architectural_grid(
    raw: list[
        tuple[
            int,
            int,
            tuple[tuple[tuple[int, int], tuple[int, int]], ...],
        ]
    ],
    deltas: range,
    biases: range,
    denominator_bits: int,
) -> list[tuple[tuple[int, int, int], int, int]]:
    prepared = []
    for index, (se, sig, hardware) in enumerate(raw):
        point = h58.RawPoint(
            index=index,
            sign=se >> 15,
            exponent=(se & 0x7FFF) - 16383,
            sig=sig,
            hw=hardware,
        )
        prepared.append(h58.prepare(point))
    ranked = []
    for delta in deltas:
        scores = [[0, 0, 0] for _ in biases]
        for point in prepared:
            altered = h97.alter_p(point, delta)
            one_plus_tail, sine_a = h79.table_state(
                altered,
                h79.BASE,
            )
            for bias_index, bias in enumerate(biases):
                adjusted_s = h79.bias_toward_zero(
                    sine_a,
                    bias,
                    denominator_bits,
                )
                sine = h58.add_exact(
                    h58.mul_exact(point.sin_t, one_plus_tail),
                    h58.mul_exact(point.cos_t, adjusted_s),
                )
                cosine = h58.add_exact(
                    h58.mul_exact(point.cos_t, one_plus_tail),
                    h58.neg(h58.mul_exact(point.sin_t, adjusted_s)),
                )
                if point.raw.sign:
                    sine = h58.neg(sine)
                missed_input = False
                for rc_index, rc in enumerate(h58.RCS):
                    for side, value in enumerate((sine, cosine)):
                        mismatch = (
                            h58.x87_round(value, rc)
                            != point.raw.hw[rc_index][side]
                        )
                        scores[bias_index][0] += mismatch
                        scores[bias_index][2] += (
                            mismatch if rc_index == 0 else 0
                        )
                        missed_input |= mismatch
                scores[bias_index][1] += missed_input
        ranked.extend(
            (tuple(score), delta, bias)
            for score, bias in zip(scores, biases)
        )
    return sorted(ranked)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--delta-low", type=int, default=0)
    parser.add_argument("--delta-high", type=int, default=12288)
    parser.add_argument("--delta-step", type=int, default=256)
    parser.add_argument("--bias-low", type=int, default=0)
    parser.add_argument("--bias-high", type=int, default=64)
    parser.add_argument("--bias-denominator-bits", type=int, default=8)
    parser.add_argument("--keep", type=int, default=24)
    parser.add_argument(
        "--full-h97-grid",
        action="store_true",
        help="also rank every delta/bias pair on the held-out h97 outputs",
    )
    args = parser.parse_args()

    intervals = tight_narrow_intervals()
    print(
        f"h98: {len(intervals)} tight narrow intervals "
        + " ".join(
            f"{dataset}={sum(item.dataset == dataset for item in intervals)}"
            for dataset, *_ in h96.DATASETS
        )
    )
    ranked = []
    for delta in range(
        args.delta_low,
        args.delta_high + 1,
        args.delta_step,
    ):
        for bias in range(args.bias_low, args.bias_high + 1):
            rank = interval_rank(
                intervals,
                delta,
                bias,
                args.bias_denominator_bits,
            )
            ranked.append((rank, delta, bias))
    ranked.sort()

    h97_raw = h97.load_capture(H97_INPUTS, H97_CAPTURE)
    finalists = []
    print("paired-interval finalists:")
    for interval_score, delta, bias in ranked[:args.keep]:
        architectural = h97_rank(
            h97_raw,
            delta,
            bias,
            args.bias_denominator_bits,
        )
        finalists.append((architectural, interval_score, delta, bias))
        print(
            f"  delta={delta:+6d} bias={bias:2d}/"
            f"{1 << args.bias_denominator_bits}: "
            f"outside={interval_score[0]:3d}/{len(intervals)} "
            f"distance={interval_score[1]:8.3f} "
            f"worst={interval_score[2]:6.3f} ulp; "
            f"h97={architectural[0]:4d} mode "
            f"{architectural[1]:4d} input "
            f"{architectural[2]:4d} RN"
        )
    print("h97-ranked interval finalists:")
    for architectural, interval_score, delta, bias in sorted(finalists):
        print(
            f"  delta={delta:+6d} bias={bias:2d}/"
            f"{1 << args.bias_denominator_bits}: "
            f"h97={architectural[0]:4d}; "
            f"outside={interval_score[0]:3d} "
            f"distance={interval_score[1]:8.3f}"
        )
    if args.full_h97_grid:
        print("full h97 architectural grid:")
        all_h97 = architectural_grid(
            h97_raw,
            range(
                args.delta_low,
                args.delta_high + 1,
                args.delta_step,
            ),
            range(args.bias_low, args.bias_high + 1),
            args.bias_denominator_bits,
        )
        for architectural, delta, bias in all_h97[:args.keep]:
            interval_score = interval_rank(
                intervals,
                delta,
                bias,
                args.bias_denominator_bits,
            )
            print(
                f"  delta={delta:+6d} bias={bias:2d}/"
                f"{1 << args.bias_denominator_bits}: "
                f"h97={architectural[0]:4d} mode "
                f"{architectural[1]:4d} input "
                f"{architectural[2]:4d} RN; "
                f"outside={interval_score[0]:3d} "
                f"distance={interval_score[1]:8.3f}"
            )


if __name__ == "__main__":
    main()
