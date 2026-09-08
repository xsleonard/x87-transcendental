#!/usr/bin/env python3
"""Fit a physical X67*Y64 FMUL at FSIN's internal-cosine tail.

h144 rejects normalized-versus-raw grid changes.  This pass changes only
the final ``q*a2`` product in h121's otherwise fixed producer.  The two
operands are explicitly formatted onto the documented P5 67-bit
multiplicand and 64-bit multiplier buses, in both orientations, and the
product is materialized by one of the multiplier's IEEE/internal modes.

Candidates are ranked on a constrained training sample, then must be no
worse than h121 on both complete deterministic halves.
"""

from __future__ import annotations

import dataclasses

import h58_constraint_search as h58
import h110_fsin_standalone as h110
import h119_fcos_standalone as h119
import h121_fsin_internal_cosine as h121
import h139_p5_fmul_route_search as h139


@dataclasses.dataclass(frozen=True)
class Route:
    q_bus: str
    x_mode: str
    y_mode: str
    output_bits: int
    output_mode: str

    def short(self) -> str:
        return (
            f"q->{self.q_bus} X67={self.x_mode} "
            f"Y64={self.y_mode} "
            f"O{self.output_bits}={self.output_mode}"
        )


MODES = ("rn", "chop", "away", "odd")


def routes() -> tuple[Route, ...]:
    return tuple(
        Route(bus, x_mode, y_mode, output_bits, output_mode)
        for bus in ("x", "y")
        for x_mode in MODES
        for y_mode in MODES
        for output_bits in range(64, 73)
        for output_mode in h139.OUTPUT_MODES
    )


def state(point: h121.Point) -> tuple[h58.FP, h58.FP]:
    observed = point.observed
    schedule = h121.FSIN_INTERNAL_COSINE
    magnitude: h58.FP = (
        0,
        observed.raw.sig,
        observed.raw.exponent - 63,
    )
    square = h110.quantize(
        h58.mul_exact(magnitude, magnitude), schedule.square
    )
    value = h119.coefficient(h58.C6[0], schedule, 0)
    for index, row in enumerate(h58.C6[1:]):
        product = h110.quantize(
            h58.mul_exact(value, square), schedule.products[index]
        )
        value = h110.quantize(
            h58.add_exact(
                product, h119.coefficient(row, schedule, index + 1)
            ),
            schedule.sums[index],
        )
    return value, square


def product(q: h58.FP, square: h58.FP, route: Route) -> h58.FP:
    if route.q_bus == "x":
        x_value, y_value = q, square
    else:
        x_value, y_value = square, q
    x_value = h139.quantize(x_value, 67, route.x_mode)
    y_value = h139.quantize(y_value, 64, route.y_mode)
    return h139.quantize(
        h58.mul_exact(x_value, y_value),
        route.output_bits,
        route.output_mode,
    )


def hidden_value(
    point: h121.Point,
    prepared: tuple[h58.FP, h58.FP],
    route: Route | None,
) -> h58.FP:
    q, square = prepared
    tail = (
        h110.quantize(
            h58.mul_exact(q, square),
            h121.FSIN_INTERNAL_COSINE.tail,
        )
        if route is None
        else product(q, square, route)
    )
    result = h110.quantize(
        h58.add_exact(h58.ONE, tail),
        h121.FSIN_INTERNAL_COSINE.final_sum,
    )
    return h58.neg(result) if point.negate else result


def score(
    points: list[h121.Point],
    states: dict[int, tuple[h58.FP, h58.FP]],
    route: Route | None,
) -> h110.Score:
    result = h110.Score()
    for point in points:
        hidden = hidden_value(
            point, states[point.observed.raw.index], route
        )
        result.total += 1
        any_miss = False
        for index, rc in enumerate(h58.RCS):
            expected = point.observed.outputs[index]
            predicted = h58.x87_round(hidden, rc)
            mismatch = predicted != expected
            result.mode_misses += mismatch
            any_miss |= mismatch
            if not mismatch:
                predicted_c1 = (
                    h110.compare_magnitude(expected, hidden) > 0
                )
                result.c1_misses += (
                    predicted_c1 != point.observed.c1[index]
                )
        result.output_misses += any_miss
    return result


def sample(
    points: list[h121.Point],
    states: dict[int, tuple[h58.FP, h58.FP]],
    controls: int,
) -> list[h121.Point]:
    constrained = [
        point for point in points
        if score([point], states, None).rank() != (0, 0, 0)
    ]
    exact = [
        point for point in points
        if score([point], states, None).rank() == (0, 0, 0)
    ]
    count = min(controls, len(exact))
    return constrained + [
        exact[(index * len(exact)) // count]
        for index in range(count)
    ]


def main() -> None:
    points = h121.load_points()
    train = [point for point in points if h121.is_train(point)]
    heldout = [point for point in points if not h121.is_train(point)]
    states = {
        point.observed.raw.index: state(point) for point in points
    }
    selected = sample(train, states, 1200)
    train_base = score(train, states, None)
    heldout_base = score(heldout, states, None)
    print(
        f"h145: {len(routes())} terminal FMUL routes; "
        f"sample={len(selected)}"
    )
    print(
        f"  baseline train {train_base.describe()}; "
        f"heldout {heldout_base.describe()}"
    )
    ranked = sorted(
        (
            score(selected, states, route).rank(),
            route.short(),
            route,
        )
        for route in routes()
    )
    survivors = []
    for _, _, route in ranked[:64]:
        train_score = score(train, states, route)
        heldout_score = score(heldout, states, route)
        if (
            h110.no_worse(train_score, train_base)
            and h110.no_worse(heldout_score, heldout_base)
        ):
            survivors.append((route, train_score, heldout_score))
    if not survivors:
        print("no X67*Y64 terminal route survives both complete halves")
        return
    for route, train_score, heldout_score in survivors:
        print(f"  {route.short()}")
        print(
            f"    train {train_score.describe()}; "
            f"heldout {heldout_score.describe()}; "
            f"complete {score(points, states, route).describe()}"
        )


if __name__ == "__main__":
    main()
