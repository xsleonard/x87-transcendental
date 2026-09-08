#!/usr/bin/env python3
"""Paired-cell tomography for the shared table-kernel S(a) and 1+t(a).

For one exactly represented residual ``a``, all cells in a polynomial family
reuse the same sine/cosine kernel values but project them through different
table entries:

    sin(b+a) = sinT[b] * (1+t) + cosT[b] * S
    cos(b+a) = cosT[b] * (1+t) - sinT[b] * S

Earlier tiebreaker captures selected one cell and output at a time.  This
instrument emits every cell in a family for the same ``a``.  RN/RD/RU then
give several differently oriented interval constraints on the same hidden
``(1+t, S)`` pair.

``generate`` is host-FP-free and does not consult hardware.  It retains a
group when any baseline output lies within 2^-window-bits ulp of an RN
boundary, then emits every cell in that group.  ``analyze`` intersects the
captured constraints exactly with rational arithmetic and reports how tightly
the paired observations localize corrections to the baseline shared state.
"""

from __future__ import annotations

import argparse
import collections
import fractions
import math
import pathlib
import random
import statistics
import sys

import h58_constraint_search as h58
import h59_discriminator as h59


PI_BY_4_SIG = 0xC90FDAA22168C234
DUMMY_HW = (((0, 0), (0, 0)),) * 3


def fp_fraction(value: h58.FP) -> fractions.Fraction:
    sign, significand, scale = value
    numerator = -significand if sign else significand
    if scale >= 0:
        return fractions.Fraction(numerator << scale, 1)
    return fractions.Fraction(numerator, 1 << -scale)


def output_fraction(output: tuple[int, int]) -> fractions.Fraction:
    se, sig = output
    if not sig:
        return fractions.Fraction(0)
    exponent = (se & 0x7FFF) - 16383
    numerator = -sig if se >> 15 else sig
    return fractions.Fraction(numerator, 1 << (63 - exponent))


def boundary_distance(value: h58.FP) -> tuple[int, int] | None:
    """Return absolute distance to an RN midpoint as (numerator, ulp-denom)."""
    significand = value[1]
    shift = significand.bit_length() - 64
    if shift <= 0:
        return None
    remainder = significand & ((1 << shift) - 1)
    return abs(remainder - (1 << (shift - 1))), 1 << shift


def raw_for(cell: int, family: str, residual: int, index: int) -> h58.RawPoint:
    if family == "narrow":
        exponent = -2
        center_sig = cell << 59
    elif family == "wide":
        exponent = -1
        center_sig = cell << 58
    else:
        raise ValueError(family)
    sig = center_sig + residual
    raw = h58.RawPoint(
        index=index,
        sign=0,
        exponent=exponent,
        sig=sig,
        hw=DUMMY_HW,
    )
    if h58.cell_for(sig, exponent) != cell:
        raise AssertionError((family, residual, cell, hex(sig)))
    return raw


def family_spec(family: str) -> tuple[tuple[int, ...], int, int]:
    if family == "narrow":
        # a is an integer multiple of 2^-65; every four-term cell admits
        # -2/64 <= a < 2/64.
        return (18, 22, 26, 30), -(1 << 60) + 1, (1 << 60) - 1
    if family == "wide":
        # a is an integer multiple of 2^-64.  Cell 52 is truncated by pi/4,
        # so the common three-cell interval is necessarily negative.
        last = PI_BY_4_SIG - (52 << 58) - 1
        return (36, 44, 52), -(1 << 60) + 1, last
    raise ValueError(family)


def group_points(family: str, residual: int) -> list[h58.RawPoint]:
    cells, _, _ = family_spec(family)
    return [
        raw_for(cell, family, residual, index)
        for index, cell in enumerate(cells)
    ]


def near_boundary_count(
    raw_points: list[h58.RawPoint], window_bits: int
) -> tuple[int, int]:
    close = 0
    closest_bits = 0
    for raw in raw_points:
        values = h58.table_tail(h58.prepare(raw), h58.BASE)
        for value in values:
            distance = boundary_distance(value)
            if distance is None:
                continue
            numerator, denominator = distance
            if numerator << window_bits <= denominator:
                close += 1
            if numerator:
                bits = math.floor(
                    math.log2(denominator) - math.log2(numerator)
                )
                closest_bits = max(closest_bits, bits)
            else:
                closest_bits = 999
    return close, closest_bits


def generate(
    inputs: pathlib.Path,
    metadata: pathlib.Path,
    count: int,
    seed: int,
    scan_limit: int,
    window_bits: int,
    min_close: int,
) -> None:
    rng = random.Random(seed)
    input_rows: list[str] = []
    metadata_rows: list[str] = []
    selected = collections.Counter()
    scanned = collections.Counter()
    close_histogram = collections.Counter()
    families = ("narrow", "wide")
    while sum(selected.values()) < 2 * count:
        scan_index = sum(scanned.values())
        if scan_index >= scan_limit:
            raise SystemExit(
                f"selected {dict(selected)} after {scan_index} scans; "
                f"wanted {count} per family"
            )
        family = families[scan_index & 1]
        scanned[family] += 1
        if selected[family] >= count:
            continue
        cells, low, high = family_spec(family)
        residual = rng.randrange(low, high)
        points = group_points(family, residual)
        close, closest_bits = near_boundary_count(points, window_bits)
        if close < min_close:
            continue
        group = selected[family]
        selected[family] += 1
        close_histogram[(family, close)] += 1
        exponent = -2 if family == "narrow" else -1
        for point, cell in zip(points, cells):
            se = exponent + 16383
            input_rows.append(f"{se:04x} {point.sig:016x}")
            metadata_rows.append(
                f"{family} {group} {residual} {cell} "
                f"{close} {closest_bits}"
            )

    inputs.write_text("\n".join(input_rows) + "\n")
    metadata.write_text("\n".join(metadata_rows) + "\n")
    print(
        f"selected {dict(selected)} paired groups from {dict(scanned)} scans; "
        f"emitted {len(input_rows)} inputs; seed={seed:#x}; "
        f"window=2^-{window_bits} ulp; min-close={min_close}; "
        f"close={dict(close_histogram)}",
        file=sys.stderr,
    )


def shared_state(point: h58.PreparedPoint) -> tuple[h58.FP, h58.FP]:
    m = h58.fmul(point.p, point.asq, 64, "rn")
    correction = h58.fmul(m, point.a, 64, "rn")
    sine_a = h58.fadd(point.a, correction, 64, "rn")
    tail = h58.fmul(point.q, point.asq, 64, "rn")
    return h58.add_exact(h58.ONE, tail), sine_a


def hardware_interval(
    point: h58.RawPoint, side: int
) -> tuple[fractions.Fraction, fractions.Fraction]:
    rn = output_fraction(point.hw[0][side])
    rd = output_fraction(point.hw[1][side])
    ru = output_fraction(point.hw[2][side])
    low, high = min(rd, ru), max(rd, ru)
    if low == high:
        return low, high
    midpoint = (low + high) / 2
    if rn == low:
        high = midpoint
    elif rn == high:
        low = midpoint
    else:
        raise AssertionError(
            f"RN is not an endpoint: rn={rn}, rd={rd}, ru={ru}"
        )
    return low, high


Inequality = tuple[
    fractions.Fraction,
    fractions.Fraction,
    fractions.Fraction,
]


def group_inequalities(
    points: list[h58.PreparedPoint],
) -> tuple[list[Inequality], h58.FP, h58.FP]:
    u0, s0 = shared_state(points[0])
    inequalities: list[Inequality] = []
    for point in points:
        actual_u, actual_s = shared_state(point)
        if actual_u != u0 or actual_s != s0:
            raise AssertionError("paired cells do not share baseline state")
        baseline = h58.table_tail(point, h58.BASE)
        sin_t = fp_fraction(point.sin_t)
        cos_t = fp_fraction(point.cos_t)
        for side in range(2):
            low, high = hardware_interval(point.raw, side)
            base = fp_fraction(baseline[side])
            if side == 0:
                a, b = sin_t, cos_t
            else:
                a, b = cos_t, -sin_t
            # low-base <= a*dU+b*dS <= high-base.
            inequalities.append((a, b, high - base))
            inequalities.append((-a, -b, base - low))
    return inequalities, u0, s0


def feasible_vertices(
    inequalities: list[Inequality],
) -> list[tuple[fractions.Fraction, fractions.Fraction]]:
    vertices: set[
        tuple[fractions.Fraction, fractions.Fraction]
    ] = set()
    for first_index, (a1, b1, c1) in enumerate(inequalities):
        for a2, b2, c2 in inequalities[first_index + 1:]:
            determinant = a1 * b2 - a2 * b1
            if not determinant:
                continue
            x = (c1 * b2 - c2 * b1) / determinant
            y = (a1 * c2 - a2 * c1) / determinant
            if all(a * x + b * y <= c for a, b, c in inequalities):
                vertices.add((x, y))
    return list(vertices)


def log2_fraction(value: fractions.Fraction) -> float:
    if value <= 0:
        return float("-inf")
    return math.log2(value.numerator) - math.log2(value.denominator)


def local_ulp(value: h58.FP) -> fractions.Fraction:
    """Return one ulp at 64 significant bits for an exact FP carrier."""
    if not value[1]:
        raise ValueError("zero has no local normalized ulp")
    width = value[1].bit_length()
    scale = value[2] + width - 64
    if scale >= 0:
        return fractions.Fraction(1 << scale, 1)
    return fractions.Fraction(1, 1 << -scale)


def analyze(
    inputs: pathlib.Path,
    metadata: pathlib.Path,
    capture: pathlib.Path,
    prefix: str,
    limit: int | None,
    min_close: int,
) -> None:
    raw = h59.load_score_points(inputs, capture, prefix)
    meta = [line.split() for line in metadata.read_text().splitlines()]
    if len(raw) != len(meta):
        raise SystemExit("input/metadata/capture line counts differ")
    grouped: dict[tuple[str, int], list[h58.PreparedPoint]] = {}
    eligible: set[tuple[str, int]] = set()
    for point, fields in zip(raw, meta):
        family, group_text, residual_text, cell_text = fields[:4]
        key = family, int(group_text)
        if int(fields[4]) >= min_close:
            eligible.add(key)
        expected_cell = int(cell_text)
        prepared = h58.prepare(point)
        if prepared.cell != expected_cell:
            raise AssertionError((prepared.cell, expected_cell))
        expected_a = (
            0,
            abs(int(residual_text)),
            -65 if family == "narrow" else -64,
        )
        if int(residual_text) < 0:
            expected_a = (1, expected_a[1], expected_a[2])
        if prepared.a != expected_a:
            raise AssertionError((prepared.a, expected_a))
        grouped.setdefault(key, []).append(prepared)
    grouped = {
        key: points for key, points in grouped.items() if key in eligible
    }

    baseline = h58.score_config(
        [point for points in grouped.values() for point in points],
        h58.BASE,
    )
    print(
        f"loaded {len(grouped)} paired groups / {len(raw)} inputs; "
        f"baseline {baseline.describe()}"
    )

    summaries: dict[str, dict[str, list[float] | int]] = {
        family: {
            "groups": 0,
            "empty": 0,
            "baseline_outside": 0,
            "u_width": [],
            "s_width": [],
            "u_center": [],
            "s_center": [],
            "u_center_ulp": [],
            "s_toward_zero_ulp": [],
            "tight_u_center_ulp": [],
            "tight_s_toward_zero_ulp": [],
        }
        for family in ("narrow", "wide")
    }
    for (family, _), points in sorted(grouped.items()):
        summary = summaries[family]
        if limit is not None and int(summary["groups"]) >= limit:
            continue
        summary["groups"] = int(summary["groups"]) + 1
        inequalities, u0, s0 = group_inequalities(points)
        vertices = feasible_vertices(inequalities)
        if not vertices:
            summary["empty"] = int(summary["empty"]) + 1
            continue
        if not all(c >= 0 for _, _, c in inequalities):
            summary["baseline_outside"] = (
                int(summary["baseline_outside"]) + 1
            )
        us = [vertex[0] for vertex in vertices]
        ss = [vertex[1] for vertex in vertices]
        u_low, u_high = min(us), max(us)
        s_low, s_high = min(ss), max(ss)
        u_width = log2_fraction(u_high - u_low)
        s_width = log2_fraction(s_high - s_low)
        summary["u_width"].append(u_width)
        summary["s_width"].append(s_width)
        u_center = (u_low + u_high) / 2
        s_center = (s_low + s_high) / 2
        summary["u_center"].append(float(u_center))
        summary["s_center"].append(float(s_center))
        u_center_ulp = float(u_center / local_ulp(u0))
        # Positive S moves toward zero for negative dS; negative S moves
        # toward zero for positive dS.
        s_orientation = 1 if s0[0] else -1
        s_toward_zero_ulp = float(
            s_orientation * s_center / local_ulp(s0)
        )
        summary["u_center_ulp"].append(u_center_ulp)
        summary["s_toward_zero_ulp"].append(s_toward_zero_ulp)
        if u_width <= -68 and s_width <= -68:
            summary["tight_u_center_ulp"].append(u_center_ulp)
            summary["tight_s_toward_zero_ulp"].append(
                s_toward_zero_ulp
            )

    for family, summary in summaries.items():
        count = int(summary["groups"])
        empty = int(summary["empty"])
        print(
            f"{family}: groups={count}, feasible={count - empty}, "
            f"empty={empty}, baseline-outside="
            f"{summary['baseline_outside']}"
        )
        for state in ("u", "s"):
            widths = summary[f"{state}_width"]
            centers = summary[f"{state}_center"]
            if not widths:
                continue
            print(
                f"  d{state.upper()} width log2: "
                f"median={statistics.median(widths):.2f}, "
                f"p10={statistics.quantiles(widths, n=10)[0]:.2f}, "
                f"p90={statistics.quantiles(widths, n=10)[-1]:.2f}; "
                f"center mean={statistics.fmean(centers):+.3e}"
            )
        for name, label in (
            ("u_center_ulp", "dU / ulp64(U)"),
            ("s_toward_zero_ulp", "dS toward zero / ulp64(S)"),
        ):
            values = summary[name]
            if not values:
                continue
            print(
                f"  {label}: median={statistics.median(values):+.4f}, "
                f"mean={statistics.fmean(values):+.4f}, "
                f"p10={statistics.quantiles(values, n=10)[0]:+.4f}, "
                f"p90={statistics.quantiles(values, n=10)[-1]:+.4f}"
            )
        tight_u = summary["tight_u_center_ulp"]
        tight_s = summary["tight_s_toward_zero_ulp"]
        if tight_u:
            print(
                f"  tight-both<=2^-68 ({len(tight_u)}): "
                f"dU mean={statistics.fmean(tight_u):+.4f} ulp; "
                f"dS-toward-zero mean="
                f"{statistics.fmean(tight_s):+.4f} ulp"
            )


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    generating = sub.add_parser("generate")
    generating.add_argument("inputs", type=pathlib.Path)
    generating.add_argument("metadata", type=pathlib.Path)
    generating.add_argument("--count", type=int, default=2048)
    generating.add_argument(
        "--seed", type=lambda value: int(value, 0), default=0xF780
    )
    generating.add_argument("--scan-limit", type=int, default=500_000)
    generating.add_argument("--window-bits", type=int, default=8)
    generating.add_argument("--min-close", type=int, default=1)
    analyzing = sub.add_parser("analyze")
    analyzing.add_argument("inputs", type=pathlib.Path)
    analyzing.add_argument("metadata", type=pathlib.Path)
    analyzing.add_argument("capture", type=pathlib.Path)
    analyzing.add_argument("--prefix", default="paired_table")
    analyzing.add_argument("--limit", type=int)
    analyzing.add_argument("--min-close", type=int, default=1)
    args = parser.parse_args()
    if args.command == "generate":
        generate(
            args.inputs,
            args.metadata,
            args.count,
            args.seed,
            args.scan_limit,
            args.window_bits,
            args.min_close,
        )
    else:
        analyze(
            args.inputs,
            args.metadata,
            args.capture,
            args.prefix,
            args.limit,
            args.min_close,
        )


if __name__ == "__main__":
    main()
