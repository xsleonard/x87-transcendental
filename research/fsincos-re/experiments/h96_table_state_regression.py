#!/usr/bin/env python3
"""Regress tightly triangulated S corrections against datapath phases.

The h78 and h95 exact polygons provide per-residual dS centers.  This pass
keeps groups whose U and S widths are both at most 2^-68, then measures
Pearson correlation between dS-toward-zero and:

* leading discarded fractions at each product/sum;
* low retained significand phases;
* alternative 65..72-bit S materializations;
* residual magnitude/sign.

This is diagnostic only; it does not fit or emit an output correction.
"""

from __future__ import annotations

import dataclasses
import math
import pathlib
import statistics

import h58_constraint_search as h58
import h59_discriminator as h59
import h78_paired_table_tomography as h78
import h79_table_state_bias as h79


ROOT = pathlib.Path(__file__).resolve().parents[1]
DATASETS = (
    (
        "h78",
        ROOT / "capture-kit" / "inputs" / "constraint_paired_table_h78.txt",
        ROOT
        / "capture-kit"
        / "inputs"
        / "constraint_paired_table_h78.meta.txt",
        ROOT / "capture-kit-captures" / "skylake-h78-paired-table",
        "constraint_paired_table",
    ),
    (
        "h95",
        ROOT / "capture-kit" / "inputs" / "constraint_table_local_h95.txt",
        ROOT
        / "capture-kit"
        / "inputs"
        / "constraint_table_local_h95.meta.txt",
        ROOT / "capture-kit-captures" / "skylake-h95-table-local",
        "constraint_table_local",
    ),
)


def fp_signed_fraction(value: h58.FP) -> float:
    if not value[1]:
        return 0.0
    magnitude = math.ldexp(float(value[1]), value[2])
    return -magnitude if value[0] else magnitude


def discarded_fraction(value: h58.FP) -> float:
    shift = value[1].bit_length() - 64
    if shift <= 0:
        return 0.0
    remainder = value[1] & ((1 << shift) - 1)
    return remainder / float(1 << shift)


def retained_fraction(value: h58.FP, bits: int = 8) -> float:
    rounded = h58.round_fp(value, 64, "rn")
    return (
        rounded[1] & ((1 << bits) - 1)
    ) / float(1 << bits)


def shared_carriers(
    point: h58.PreparedPoint,
) -> dict[str, h58.FP]:
    m_product = h58.mul_exact(point.p, point.asq)
    m = h58.round_fp(m_product, 64, "rn")
    correction_product = h58.mul_exact(m, point.a)
    correction = h58.round_fp(correction_product, 64, "rn")
    sine_sum = h58.add_exact(point.a, correction)
    one_plus_m = h58.fadd(h58.ONE, m, 64, "rn")
    factored = h58.mul_exact(point.a, one_plus_m)
    tail_product = h58.mul_exact(point.q, point.asq)
    return {
        "a": point.a,
        "asq": point.asq,
        "p": point.p,
        "q": point.q,
        "p*asq": m_product,
        "m": m,
        "m*a": correction_product,
        "correction": correction,
        "a+correction": sine_sum,
        "a*(1+m)": factored,
        "q*asq": tail_product,
    }


def pearson(xs: list[float], ys: list[float]) -> float:
    if len(xs) != len(ys) or len(xs) < 2:
        return float("nan")
    xmean = statistics.fmean(xs)
    ymean = statistics.fmean(ys)
    dx = [value - xmean for value in xs]
    dy = [value - ymean for value in ys]
    denominator = math.sqrt(
        sum(value * value for value in dx)
        * sum(value * value for value in dy)
    )
    if not denominator:
        return 0.0
    return sum(x * y for x, y in zip(dx, dy)) / denominator


def group_records() -> list[dict[str, object]]:
    records = []
    for dataset, inputs, metadata, capture, prefix in DATASETS:
        raw = h59.load_score_points(inputs, capture, prefix)
        meta = [line.split() for line in metadata.read_text().splitlines()]
        grouped: dict[tuple[str, int], list[h58.PreparedPoint]] = {}
        for item, fields in zip(raw, meta):
            family = fields[0]
            group = int(fields[1])
            grouped.setdefault((family, group), []).append(
                h58.prepare(item)
            )
        for (family, group), points in grouped.items():
            inequalities, u0, s0 = h78.group_inequalities(points)
            vertices = h78.feasible_vertices(inequalities)
            if not vertices:
                continue
            us = [vertex[0] for vertex in vertices]
            ss = [vertex[1] for vertex in vertices]
            u_low, u_high = min(us), max(us)
            s_low, s_high = min(ss), max(ss)
            if (
                h78.log2_fraction(u_high - u_low) > -68
                or h78.log2_fraction(s_high - s_low) > -68
            ):
                continue
            u_center = (u_low + u_high) / 2
            s_center = (s_low + s_high) / 2
            s_orientation = 1 if s0[0] else -1
            point = points[0]
            carriers = shared_carriers(point)
            features: dict[str, float] = {
                "a.sign": float(point.a[0]),
                "a.value": abs(fp_signed_fraction(point.a)),
                "a.exponent": float(
                    point.a[2] + point.a[1].bit_length() - 1
                ),
                "U.center-ulp": float(
                    u_center / h78.local_ulp(u0)
                ),
            }
            for name, value in carriers.items():
                features[f"{name}.discarded"] = discarded_fraction(value)
                features[f"{name}.retained8"] = retained_fraction(value)
            baseline_s = h79.table_state(point, h79.BASE)[1]
            for bits in range(65, 73):
                for mode in ("rn", "chop", "away"):
                    tail = dataclasses.replace(
                        h58.BASE, s_bits=bits, s_mode=mode
                    )
                    schedule = h79.StateSchedule(
                        "candidate", tail, tail
                    )
                    candidate_s = h79.table_state(
                        point, schedule
                    )[1]
                    delta = h58.add_exact(
                        candidate_s, h58.neg(baseline_s)
                    )
                    signed_delta = fp_signed_fraction(delta)
                    orientation = 1 if baseline_s[0] else -1
                    features[
                        f"S{bits}.{mode}"
                    ] = (
                        orientation
                        * signed_delta
                        / float(h78.local_ulp(baseline_s))
                    )
            records.append(
                {
                    "dataset": dataset,
                    "family": family,
                    "group": group,
                    "target": float(
                        s_orientation
                        * s_center
                        / h78.local_ulp(s0)
                    ),
                    "features": features,
                }
            )
    return records


def main() -> None:
    records = group_records()
    print(
        f"tight records={len(records)} "
        + " ".join(
            f"{dataset}-{family}="
            f"{sum(record['dataset'] == dataset and record['family'] == family for record in records)}"
            for dataset, *_ in DATASETS
            for family in ("narrow", "wide")
        )
    )
    for family in ("narrow", "wide"):
        selected = [
            record for record in records if record["family"] == family
        ]
        targets = [float(record["target"]) for record in selected]
        names = sorted(
            set.intersection(
                *[
                    set(record["features"])  # type: ignore[arg-type]
                    for record in selected
                ]
            )
        )
        ranked = []
        for name in names:
            values = [
                float(record["features"][name])  # type: ignore[index]
                for record in selected
            ]
            correlation = pearson(values, targets)
            ranked.append(
                (
                    -abs(correlation),
                    name,
                    correlation,
                    statistics.fmean(values),
                )
            )
        ranked.sort()
        print(
            f"{family}: n={len(selected)} "
            f"target mean={statistics.fmean(targets):+.4f} "
            f"median={statistics.median(targets):+.4f}"
        )
        for _, name, correlation, mean in ranked[:20]:
            print(
                f"  {name:28s} r={correlation:+.4f} "
                f"feature-mean={mean:+.4f}"
            )


if __name__ == "__main__":
    main()
