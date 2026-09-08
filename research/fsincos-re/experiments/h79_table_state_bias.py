#!/usr/bin/env python3
"""Cross-validate the table-kernel shared-state bias exposed by h78.

Paired-cell tomography observes the same ``S(a)`` through several table
rotations.  Its first robust aggregate signal is a small correction toward
zero relative to the reconstructed 64-bit ``S`` state.  This experiment
scores exact rational fractions of one local S ulp across:

* the complete direct-table capture;
* the independently generated h59 narrow/wide discriminator;
* the independent h67 wide-producer discriminator; and
* the h78 double-close paired capture, when it is still available.

The correction is deliberately a diagnostic proxy, not a claimed micro-op:

    S' = S - sign(S) * k/32 * ulp64(S)

For narrow cells it is tested both on the historical baseline state and on
the constraint-validated Round-17 RN69/chop68 state.  A proxy is eligible for
the C model only after a concrete datapath operation explains it.
"""

from __future__ import annotations

import argparse
import dataclasses
import pathlib

import h58_constraint_search as h58
import h59_discriminator as h59


ROOT = pathlib.Path(__file__).resolve().parents[1]
DENSE_CAPTURE = ROOT / "capture-kit-captures" / "pentiumII"
H59_CAPTURE = ROOT / "capture-kit-captures" / "skylake-h59-constraints"
H67_CAPTURE = ROOT / "capture-kit-captures" / "skylake-h67-wide-producer"
H67_INPUTS = (
    ROOT / "capture-kit" / "inputs" / "constraint_wide_producer_h67.txt"
)
PAIRED_INPUTS = (
    ROOT / "capture-kit" / "inputs" / "constraint_paired_table_h78.txt"
)
PAIRED_CAPTURE = (
    ROOT / "capture-kit-captures" / "skylake-h78-paired-table"
)


@dataclasses.dataclass(frozen=True)
class StateSchedule:
    name: str
    narrow_tail: h58.TailConfig
    wide_tail: h58.TailConfig


BASE = StateSchedule("base", h58.BASE, h58.BASE)
ROUND17 = StateSchedule("round17", h58.NARROW_TAIL, h58.BASE)


def table_state(
    point: h58.PreparedPoint,
    schedule: StateSchedule,
) -> tuple[h58.FP, h58.FP]:
    cfg = schedule.wide_tail if point.wide else schedule.narrow_tail
    m = h58.fmul(point.p, point.asq, cfg.m_bits, cfg.m_mode)
    if cfg.topology == "direct":
        correction = h58.fmul(
            m, point.a, cfg.mid_bits, cfg.mid_mode
        )
        sine_a = h58.fadd(
            point.a, correction, cfg.s_bits, cfg.s_mode
        )
    elif cfg.topology == "factored":
        one_plus_m = h58.fadd(
            h58.ONE, m, cfg.mid_bits, cfg.mid_mode
        )
        sine_a = h58.fmul(
            point.a, one_plus_m, cfg.s_bits, cfg.s_mode
        )
    elif cfg.topology == "fma":
        sine_a = h58.ffma(
            m, point.a, point.a, cfg.s_bits, cfg.s_mode
        )
    elif cfg.topology == "full-fma":
        product = h58.mul_exact(
            h58.mul_exact(point.p, point.asq), point.a
        )
        sine_a = h58.round_fp(
            h58.add_exact(point.a, product),
            cfg.s_bits,
            cfg.s_mode,
        )
    else:
        raise ValueError(cfg.topology)
    tail = h58.fmul(
        point.q, point.asq, cfg.t_bits, cfg.t_mode
    )
    return h58.add_exact(h58.ONE, tail), sine_a


def bias_toward_zero(
    value: h58.FP,
    numerator: int,
    denominator_bits: int = 5,
) -> h58.FP:
    """Subtract ``numerator / 2^denominator_bits`` of a local 64-bit ulp."""
    if not value[1] or not numerator:
        return value
    sign, significand, scale = value
    width = significand.bit_length()
    ulp_scale = scale + width - 64
    correction_sign = sign ^ int(numerator > 0)
    correction = (
        correction_sign,
        abs(numerator),
        ulp_scale - denominator_bits,
    )
    result = h58.add_exact(value, correction)
    if result[0] != sign:
        raise AssertionError("bias exceeds state magnitude")
    return result


def values(
    point: h58.PreparedPoint,
    schedule: StateSchedule,
    numerator: int,
    denominator_bits: int = 5,
    u_numerator: int = 0,
    u_denominator_bits: int = 5,
) -> tuple[h58.FP, h58.FP]:
    one_plus_tail, sine_a = table_state(point, schedule)
    sine_a = bias_toward_zero(
        sine_a, numerator, denominator_bits
    )
    one_plus_tail = bias_toward_zero(
        one_plus_tail, u_numerator, u_denominator_bits
    )
    sine = h58.add_exact(
        h58.mul_exact(point.sin_t, one_plus_tail),
        h58.mul_exact(point.cos_t, sine_a),
    )
    cosine = h58.add_exact(
        h58.mul_exact(point.cos_t, one_plus_tail),
        h58.neg(h58.mul_exact(point.sin_t, sine_a)),
    )
    if point.raw.sign:
        sine = h58.neg(sine)
    return sine, cosine


def score(
    raw: list[h58.RawPoint],
    schedule: StateSchedule,
    numerator: int,
    denominator_bits: int = 5,
    u_numerator: int = 0,
    u_denominator_bits: int = 5,
) -> h58.Score:
    result = h58.Score(total_outputs=2 * len(raw))
    for item in raw:
        point = h58.prepare(item)
        predicted = values(
            point,
            schedule,
            numerator,
            denominator_bits,
            u_numerator,
            u_denominator_bits,
        )
        for side, value in enumerate(predicted):
            output_missed = False
            for rc_index, rc in enumerate(h58.RCS):
                mismatch = (
                    h58.x87_round(value, rc)
                    != item.hw[rc_index][side]
                )
                result.mode_misses += mismatch
                result.rn_misses += mismatch if rc == "rn" else 0
                output_missed |= mismatch
            result.constrained_output_misses += output_missed
    return result


def rank(result: h58.Score) -> tuple[int, int, int]:
    return (
        int(result.mode_misses),
        int(result.constrained_output_misses),
        int(result.rn_misses),
    )


def load_datasets() -> tuple[
    tuple[str, str, list[h58.RawPoint]], ...
]:
    dense = h58.load_points(DENSE_CAPTURE)
    datasets: list[tuple[str, str, list[h58.RawPoint]]] = [
        (
            "dense-narrow",
            "narrow",
            [point for point in dense if point.exponent == -2],
        ),
        (
            "dense-wide",
            "wide",
            [point for point in dense if point.exponent == -1],
        ),
        (
            "h59-narrow",
            "narrow",
            h59.load_score_points(
                H59_CAPTURE / "narrow_inputs.txt",
                H59_CAPTURE,
                "narrow",
            ),
        ),
        (
            "h59-wide",
            "wide",
            h59.load_score_points(
                H59_CAPTURE / "wide_inputs.txt",
                H59_CAPTURE,
                "wide",
            ),
        ),
        (
            "h67-wide",
            "wide",
            h59.load_score_points(
                H67_INPUTS,
                H67_CAPTURE,
                "constraint_wide_producer",
            ),
        ),
    ]
    if (
        PAIRED_INPUTS.exists()
        and all(
            (
                PAIRED_CAPTURE / f"constraint_paired_table_{rc}.txt"
            ).exists()
            for rc in h58.RCS
        )
    ):
        paired = h59.load_score_points(
            PAIRED_INPUTS,
            PAIRED_CAPTURE,
            "constraint_paired_table",
        )
        datasets.extend(
            (
                (
                    "h78-narrow",
                    "narrow",
                    [
                        point
                        for point in paired
                        if point.exponent == -2
                    ],
                ),
                (
                    "h78-wide",
                    "wide",
                    [
                        point
                        for point in paired
                        if point.exponent == -1
                    ],
                ),
            )
        )
    return tuple(datasets)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--u-only",
        action="store_true",
        help="skip the already established S-only scan",
    )
    args = parser.parse_args()
    datasets = load_datasets()
    print(
        "datasets: "
        + ", ".join(
            f"{name}={len(points)}" for name, _, points in datasets
        )
    )
    if not args.u_only:
        scores: dict[
            tuple[str, str, int], h58.Score
        ] = {}
        for schedule in (BASE, ROUND17):
            for name, family, points in datasets:
                if family == "wide" and schedule is ROUND17:
                    continue
                for numerator in range(17):
                    scores[(schedule.name, name, numerator)] = score(
                        points, schedule, numerator
                    )

        for family in ("narrow", "wide"):
            family_datasets = [
                row for row in datasets if row[1] == family
            ]
            schedules = (
                (BASE, ROUND17) if family == "narrow" else (BASE,)
            )
            for schedule in schedules:
                combined = []
                for numerator in range(17):
                    ranks = [
                        rank(scores[(schedule.name, name, numerator)])
                        for name, _, _ in family_datasets
                    ]
                    total = tuple(
                        sum(row[index] for row in ranks)
                        for index in range(3)
                    )
                    combined.append((total, numerator, ranks))
                combined.sort(key=lambda row: (row[0], row[1]))
                print(f"{family} schedule={schedule.name}")
                for total, numerator, ranks in combined[:8]:
                    print(
                        f"  bias={numerator}/32 combined="
                        f"{total[0]}/{total[1]}/{total[2]}"
                    )
                    for (name, _, _), result_rank in zip(
                        family_datasets, ranks
                    ):
                        print(
                            f"    {name:12s} "
                            f"{result_rank[0]}/{result_rank[1]}/"
                            f"{result_rank[2]}"
                        )

    print("binary dU corrections around the family S candidates")
    u_candidates = [(0, 5)] + [
        (direction, bits)
        for bits in range(5, 11)
        for direction in (1, -1)
    ]
    for family, schedule, s_numerator in (
        ("narrow", BASE, 4),
        ("narrow", ROUND17, 4),
        ("wide", BASE, 5),
    ):
        family_datasets = [
            row for row in datasets if row[1] == family
        ]
        ranked = []
        for u_numerator, u_bits in u_candidates:
            results = [
                score(
                    points,
                    schedule,
                    s_numerator,
                    u_numerator=u_numerator,
                    u_denominator_bits=u_bits,
                )
                for _, _, points in family_datasets
            ]
            total = tuple(
                sum(rank(result)[index] for result in results)
                for index in range(3)
            )
            ranked.append(
                (total, u_numerator, u_bits, results)
            )
        ranked.sort(key=lambda row: (row[0], row[1], row[2]))
        print(
            f"{family} schedule={schedule.name} "
            f"S-bias={s_numerator}/32"
        )
        for total, u_numerator, u_bits, results in ranked[:6]:
            direction = (
                "zero"
                if not u_numerator
                else "toward-zero"
                if u_numerator > 0
                else "away-zero"
            )
            print(
                f"  dU={direction} "
                f"{abs(u_numerator)}/2^{u_bits} ulp "
                f"combined={total[0]}/{total[1]}/{total[2]}"
            )
            for (name, _, _), result in zip(
                family_datasets, results
            ):
                actual = rank(result)
                print(
                    f"    {name:12s} "
                    f"{actual[0]}/{actual[1]}/{actual[2]}"
                )


if __name__ == "__main__":
    main()
