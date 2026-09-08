#!/usr/bin/env python3
"""Measure the hidden FMUL effect implied by the Round-48 sine proxy.

h326 proves that materializing the output-equivalent shared-sine proxy in a
normalized 67-bit carrier loses part of the Round-48 improvement.  A stored
TMP value is therefore the wrong place to interpret all of the proxy's low
bits.  The next physically bounded possibility is the immediately dependent
FMUL: it can consume the 67-bit numeric carrier together with non-numeric
carry/sticky state from its producer.

This pass projects the proxy to a legal 67-bit numeric carrier, multiplies it
by each table cross operand, and compares that chop67 product with the product
obtained from the unprojected proxy.  It reports the signed retained-unit
correction that a producer-to-FMUL bypass would have to supply.  No hardware
result is fitted here; Round 48 remains the frozen output target.
"""

from __future__ import annotations

import argparse
import collections

import h58_constraint_search as h58
import h79_table_state_bias as h79
import h110_fsin_standalone as h110
import h218_fadd_residual_programs as h218
import h226_p6_full_sine_graph as h226
import h228_p6_four_term_c_parity as h228
import h287_trig_sine_bias_cegis as h287
import h291_trig_sine_bias_coordinate_scan as h291
import h283_trig_sine_bias_selector as h283
import h326_p6_tmp_sine_projection as h326


PROJECTIONS = {
    "rn64": h110.Quant(64, "rn"),
    "rn67": h110.Quant(67, "rn"),
    "chop67": h110.Quant(67, "chop"),
    "away67": h110.Quant(67, "away"),
    "odd67": h110.Quant(67, "odd"),
}
SPECIAL_COORDINATES = {
    ("wide", (-5, 13)),
    ("wide", (-6, 15)),
    ("narrow", (-6, 15)),
    ("narrow", (-8, 19)),
    ("narrow", (-7, 17)),
}


def datasets(scope: str):
    """Load one bounded corpus at a time to keep the analysis memory-stable."""
    if scope == "wide":
        return [*h218.datasets(), ("h285", h287.fresh_points())]
    return [
        (
            f"{scope}-narrow",
            [
                point
                for point in h228.points(scope)
                if point.prepared.joint.observed.family == "narrow"
            ],
        )
    ]


def signed_at(value: h58.FP, scale: int) -> int:
    sign, significand, value_scale = value
    if value_scale < scale:
        raise ValueError((value, scale))
    magnitude = significand << (value_scale - scale)
    return -magnitude if sign else magnitude


def retained_unit_delta(target: h58.FP, base: h58.FP) -> int:
    """Return target-base in units of a normalized 67-bit result LSB."""
    target_top = target[2] + target[1].bit_length() - 1
    base_top = base[2] + base[1].bit_length() - 1
    if target_top != base_top:
        raise ValueError((target, base))
    unit_scale = target_top - 66
    return signed_at(target, unit_scale) - signed_at(base, unit_scale)


def products(point, sine):
    prepared = point.prepared.joint.observed.point
    return (
        h226.quantize(h58.mul_exact(prepared.cos_t, sine), "chop67"),
        h226.quantize(h58.mul_exact(prepared.sin_t, sine), "chop67"),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scope", choices=("wide", "dense", "sweep"), default="wide"
    )
    parser.add_argument("--details", action="store_true")
    args = parser.parse_args()
    selected = datasets(args.scope)
    total_points = sum(len(points) for _, points in selected)
    print(
        "h327 sine bypass units: "
        f"scope={args.scope} datasets={len(selected)} points={total_points}"
    )
    for projection_name, quant in PROJECTIONS.items():
        deltas = collections.Counter()
        by_coordinate = collections.defaultdict(collections.Counter)
        changed_points = 0
        changed_products = 0
        maximum = 0
        universal_mismatches = 0
        for _, points in selected:
            for point in points:
                proxy = h326.proxy_sine(point)
                carrier = h110.quantize(proxy, quant)
                if projection_name == "rn67":
                    rn64 = h283.state_inputs(point)[-1]
                    universal = h110.quantize(
                        h79.bias_toward_zero(rn64, 32, 8), quant
                    )
                    universal_mismatches += carrier != universal
                target_products = products(point, proxy)
                base_products = products(point, carrier)
                point_changed = False
                observed = point.prepared.joint.observed
                key = (observed.family, h291.coordinate(point)[0])
                for lane, (target, base) in enumerate(
                    zip(target_products, base_products)
                ):
                    delta = retained_unit_delta(target, base)
                    deltas[lane, delta] += 1
                    by_coordinate[key][lane, delta] += 1
                    if delta:
                        point_changed = True
                        changed_products += 1
                        maximum = max(maximum, abs(delta))
                changed_points += point_changed
        print(
            f"  {projection_name}: changed-points={changed_points}/"
            f"{total_points} changed-products={changed_products}/"
            f"{2 * total_points} max-unit={maximum}"
        )
        if projection_name == "rn67":
            print(
                "    universal 1/8-ulp carrier mismatches="
                f"{universal_mismatches}/{total_points}"
            )
        print(
            "    aggregate="
            f"{dict(sorted(deltas.items()))}"
        )
        for coordinate, counts in sorted(by_coordinate.items()):
            if (
                (args.details or coordinate in SPECIAL_COORDINATES)
                and any(delta for (_, delta), count in counts.items() if count)
            ):
                print(
                    f"    {coordinate}: "
                    f"{dict(sorted(counts.items()))}"
                )


if __name__ == "__main__":
    main()
