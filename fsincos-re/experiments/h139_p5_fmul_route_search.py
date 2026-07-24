#!/usr/bin/env python3
"""Test a physical 67x64 P5 FMUL explanation for h137's C*p edge.

Intel's P5-era FMUL patents expose asymmetric 67-bit multiplicand and 64-bit
multiplier inputs.  h137's validated narrow Tang graph instead represents
``C*p`` as an exact product materialized away from zero at 64 bits.  This
pass asks whether that survivor is a proxy for a real operand route:

* constant on X67, p-state on Y64; or the reverse;
* explicit RN/chop/away/odd input formatting at each bus width;
* explicit 64-bit product materialization.

Candidate selection uses standalone training partitions.  Complete
train/held-out, fresh h135, Pentium-II dense FSINCOS, and master results are
independent gates.
"""

from __future__ import annotations

import dataclasses

import h58_constraint_search as h58
import h60_round16_parity as h60
import h99_narrow_candidate_crossvalidate as h99
import h104_table_final_partial_search as h104
import h110_fsin_standalone as h110
import h131_fsin_table_c1_search as h131
import h135_fsin_table_terminal_discriminator as h135
import h136_tang_reconstruction_search as h136
import h137_tang_edge_schedule_search as h137


@dataclasses.dataclass(frozen=True)
class Route:
    constant_bus: str
    x_mode: str
    y_mode: str
    output_mode: str

    def short(self) -> str:
        return (
            f"C->{self.constant_bus} "
            f"X67={self.x_mode} Y64={self.y_mode} "
            f"O64={self.output_mode}"
        )


MODES = ("rn", "chop", "away", "odd")
OUTPUT_MODES = (*MODES, "ru", "rd")
NARROW = dataclasses.replace(
    h137.CURRENT, p_product=h137.Quant(64, "away")
)


def routes() -> tuple[Route, ...]:
    return tuple(
        Route(bus, x_mode, y_mode, output_mode)
        for bus in ("x", "y")
        for x_mode in MODES
        for y_mode in MODES
        for output_mode in OUTPUT_MODES
    )


def quantize(value: h58.FP, bits: int, mode: str) -> h58.FP:
    return h110.quantize(value, h110.Quant(bits, mode))


def p5_fmul(
    constant: h58.FP, state: h58.FP, route: Route
) -> h58.FP:
    if route.constant_bus == "x":
        x_value, y_value = constant, state
    else:
        x_value, y_value = state, constant
    x_value = quantize(x_value, 67, route.x_mode)
    y_value = quantize(y_value, 64, route.y_mode)
    return quantize(
        h58.mul_exact(x_value, y_value),
        64,
        route.output_mode,
    )


def lane_value(
    lead: h58.FP,
    cross: h58.FP,
    state: h136.State,
    subtract_cross: bool,
    route: Route,
) -> h58.FP:
    linear = h58.mul_exact(cross, state.residual)
    p_product = p5_fmul(cross, state.sine_correction, route)
    if subtract_cross:
        linear = h58.neg(linear)
        p_product = h58.neg(p_product)
    q_product = h58.mul_exact(lead, state.cosine_tail)
    nonlinear = h58.add_exact(q_product, p_product)
    correction = quantize(
        h58.add_exact(linear, nonlinear), 67, "rn"
    )
    return h58.add_exact(lead, correction)


def hidden_value(
    observed: h131.Observed, route: Route
) -> h58.FP:
    point = observed.point
    state = h136.standalone_state(
        point, h135.path_candidate(observed)
    )
    quadrant = observed.signed_n & 3
    if quadrant & 1:
        value = lane_value(
            point.cos_t,
            point.sin_t,
            state,
            True,
            route,
        )
    else:
        value = lane_value(
            point.sin_t,
            point.cos_t,
            state,
            False,
            route,
        )
        if point.raw.sign:
            value = h58.neg(value)
    return h58.neg(value) if quadrant & 2 else value


def point_score(
    observed: h131.Observed, route: Route | None
) -> tuple[int, int]:
    hidden = (
        h137.hidden_value(observed, NARROW)
        if route is None
        else hidden_value(observed, route)
    )
    output_misses = 0
    c1_misses = 0
    for index, rc in enumerate(h58.RCS):
        predicted = h58.x87_round(hidden, rc)
        expected = observed.outputs[index]
        if predicted != expected:
            output_misses += 1
        else:
            predicted_c1 = (
                h110.compare_magnitude(expected, hidden) > 0
            )
            c1_misses += predicted_c1 != observed.c1[index]
    return output_misses, c1_misses


def score(
    points: list[h131.Observed], route: Route | None
) -> tuple[int, int, int]:
    mode_misses = 0
    input_misses = 0
    c1_misses = 0
    for point in points:
        mode, c1 = point_score(point, route)
        mode_misses += mode
        input_misses += bool(mode)
        c1_misses += c1
    return mode_misses, input_misses, c1_misses


def shared_values(
    point: h58.PreparedPoint, route: Route
) -> tuple[h58.FP, h58.FP]:
    altered, one_plus_tail, sine_a = h104.state(point)
    state = h136.State(
        altered.a,
        h58.add_exact(sine_a, h58.neg(altered.a)),
        h58.add_exact(one_plus_tail, h58.neg(h58.ONE)),
    )
    sine = lane_value(
        altered.sin_t, altered.cos_t, state, False, route
    )
    cosine = lane_value(
        altered.cos_t, altered.sin_t, state, True, route
    )
    if point.raw.sign:
        sine = h58.neg(sine)
    return sine, cosine


def shared_dense_score(
    points: list[h58.PreparedPoint], route: Route
) -> tuple[int, int, int]:
    mode_misses = 0
    output_misses = 0
    rn_misses = 0
    for point in points:
        predicted = shared_values(point, route)
        for side, value in enumerate(predicted):
            missed_output = False
            for rc_index, rc in enumerate(h58.RCS):
                mismatch = (
                    h58.x87_round(value, rc)
                    != point.raw.hw[rc_index][side]
                )
                mode_misses += mismatch
                rn_misses += mismatch if rc_index == 0 else 0
                missed_output |= mismatch
            output_misses += missed_output
    return mode_misses, output_misses, rn_misses


def master_score(master, route: Route) -> tuple[int, int, int]:
    misses = 0
    narrow = 0
    wide = 0
    for active, expected in master:
        if active is None:
            continue
        if expected is None:
            raise AssertionError("table-active master input returned C2")
        signed_n, point, _ = active
        selected = not point.wide
        predicted = (
            shared_values(point, route)
            if selected
            else h104.values(point, h104.EXACT)
        )
        actual = tuple(
            h58.x87_round(value, "rn")
            for value in h60.rotate(predicted, signed_n)
        )
        mismatch = actual != expected
        misses += mismatch
        narrow += mismatch if not point.wide else 0
        wide += mismatch if point.wide else 0
    return misses, narrow, wide


def main() -> None:
    dense = h131.load_dataset("dense", h131.INPUTS / "dense_qn.txt")
    sweep = h131.load_dataset("sweep", h131.INPUTS / "sweep_inputs.txt")
    complete = h136.partitions("narrow", dense, sweep)
    training = [
        (name, h136.search_sample(points, 1500))
        for name, points in complete
        if name.endswith("-train")
    ]
    fresh_by_path = h135.load_capture(
        h135.DEFAULT_OUTPUT,
        h135.DEFAULT_METADATA,
        h135.ROOT / "capture-kit-captures" / "skylake-fsin-h135",
    )
    fresh = [
        point
        for key, points in fresh_by_path.items()
        if key[0] == "narrow"
        for point in points
    ]
    baseline = [score(points, None) for _, points in complete]
    fresh_baseline = score(fresh, None)
    print(f"h139: {len(routes())} physical C*p routes")
    for (name, points), result in zip(complete, baseline):
        print(
            f"  {name:11s} "
            f"{h131.describe(result, len(points))}"
        )
    print(
        f"  {'fresh':11s} "
        f"{h131.describe(fresh_baseline, len(fresh))}"
    )

    ranked = []
    for route in routes():
        results = [score(points, route) for _, points in training]
        ranked.append(
            (
                sum(result[0] for result in results),
                sum(result[2] for result in results),
                sum(result[1] for result in results),
                route.short(),
                route,
            )
        )
    ranked.sort()

    validated = []
    for _, _, _, _, route in ranked[:48]:
        results = [score(points, route) for _, points in complete]
        fresh_result = score(fresh, route)
        if (
            all(
                result <= base
                for result, base in zip(results, baseline)
            )
            and fresh_result <= fresh_baseline
        ):
            validated.append((route, results, fresh_result))

    if not validated:
        print("no asymmetric FMUL route matches the h137 gates")
        for item in ranked[:12]:
            print(f"  {item[4].short():52s} train={item[:3]}")
        return

    shared_all = [
        h58.prepare(point)
        for point in h58.load_points(
            h99.ROOT / "capture-kit-captures" / "pentiumII"
        )
        if point.exponent == -2
    ]
    master = h99.master_points()
    dense_baseline = h137.shared_dense_score(
        shared_all, NARROW
    )
    master_baseline = h137.shared_master_score(
        master, "narrow", NARROW
    )
    print(
        f"shared baselines: dense={dense_baseline} "
        f"master={master_baseline}"
    )
    for route, results, fresh_result in validated[:16]:
        dense_result = shared_dense_score(shared_all, route)
        master_result = master_score(master, route)
        passed = (
            dense_result <= dense_baseline
            and master_result <= master_baseline
        )
        print(f"  {route.short():52s} {'PASS' if passed else 'FAIL'}")
        for (name, points), result in zip(complete, results):
            print(
                f"    {name:11s} "
                f"{h131.describe(result, len(points))}"
            )
        print(
            f"    {'fresh':11s} "
            f"{h131.describe(fresh_result, len(fresh))}"
        )
        print(
            f"    shared dense={dense_result} master={master_result}"
        )


if __name__ == "__main__":
    main()
