#!/usr/bin/env python3
"""Cross-validate path-specific X67/Y64 routes for Tang's C*p product.

h139 found the global X67-constant route and h141 found a small direct-path
gain from an RU64 product.  The independent h140 capture adds two facts that
the aggregate search could not see: reduced RN/away are wrong on one boundary,
and one direct boundary distinguishes the X67 and Y64 constant routes.

This pass therefore selects the multiplier orientation and output rule
independently for direct and M66-reduced entries.  Every route must be no
worse than h137's X67/away64 baseline on every complete old partition, h135,
and the independent h140 capture for its path.  Surviving direct/reduced
pairs are then gated on Pentium-II dense FSINCOS and the untouched master.
"""

from __future__ import annotations

import dataclasses

import h58_constraint_search as h58
import h60_round16_parity as h60
import h99_narrow_candidate_crossvalidate as h99
import h104_table_final_partial_search as h104
import h131_fsin_table_c1_search as h131
import h135_fsin_table_terminal_discriminator as h135
import h136_tang_reconstruction_search as h136
import h139_p5_fmul_route_search as h139
import h140_p5_fmul_discriminator as h140


@dataclasses.dataclass(frozen=True)
class Schedule:
    direct: h139.Route
    reduced: h139.Route

    def route(self, reduced: bool) -> h139.Route:
        return self.reduced if reduced else self.direct

    def short(self) -> str:
        return (
            f"direct[{self.direct.short()}] "
            f"reduced[{self.reduced.short()}]"
        )


BASE_ROUTE = h139.Route("x", "rn", "rn", "away")
BASELINE = Schedule(BASE_ROUTE, BASE_ROUTE)


def routes() -> tuple[h139.Route, ...]:
    return tuple(
        h139.Route(bus, "rn", "rn", mode)
        for bus in ("x", "y")
        for mode in h139.OUTPUT_MODES
    )


def score(
    points: list[h131.Observed], route: h139.Route
) -> tuple[int, int, int]:
    return h139.score(points, route)


def shared_values(
    point: h58.PreparedPoint, schedule: Schedule, reduced: bool
) -> tuple[h58.FP, h58.FP]:
    route = schedule.route(reduced)
    altered, one_plus_tail, sine_a = h104.state(point)
    state = h136.State(
        altered.a,
        h58.add_exact(sine_a, h58.neg(altered.a)),
        h58.add_exact(one_plus_tail, h58.neg(h58.ONE)),
    )
    sine = h139.lane_value(
        altered.sin_t, altered.cos_t, state, False, route
    )
    cosine = h139.lane_value(
        altered.cos_t, altered.sin_t, state, True, route
    )
    if point.raw.sign:
        sine = h58.neg(sine)
    return sine, cosine


def shared_dense_score(
    points: list[h58.PreparedPoint], schedule: Schedule
) -> tuple[int, int, int]:
    mode_misses = 0
    output_misses = 0
    rn_misses = 0
    for point in points:
        predicted = shared_values(point, schedule, False)
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


def master_score(master, schedule: Schedule) -> tuple[int, int, int]:
    misses = 0
    narrow = 0
    wide = 0
    for active, expected in master:
        if active is None:
            continue
        if expected is None:
            raise AssertionError("table-active master input returned C2")
        signed_n, point, reduced = active
        if point.wide:
            predicted = h104.values(point, h104.EXACT)
        else:
            predicted = shared_values(point, schedule, reduced)
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
    fresh_by_path = h135.load_capture(
        h135.DEFAULT_OUTPUT,
        h135.DEFAULT_METADATA,
        h135.ROOT / "capture-kit-captures" / "skylake-fsin-h135",
    )
    captured = h140.load_capture(
        h140.DEFAULT_OUTPUT,
        h140.ROOT / "capture-kit-captures" / "skylake-fsin-h140",
    )
    datasets: dict[str, list[tuple[str, list[h131.Observed]]]] = {}
    for source in ("direct", "reduced"):
        datasets[source] = [
            (
                name,
                [point for point in points if point.source == source],
            )
            for name, points in complete
        ]
        datasets[source].extend(
            (
                (
                    "fresh",
                    [
                        point
                        for (family, path), points in fresh_by_path.items()
                        if family == "narrow" and path == source
                        for point in points
                    ],
                ),
                (
                    "h140",
                    [point for point in captured if point.source == source],
                ),
            )
        )

    survivors: dict[str, list[h139.Route]] = {}
    for source in ("direct", "reduced"):
        parts = datasets[source]
        baselines = [score(points, BASE_ROUTE) for _, points in parts]
        print(f"h142 {source}: {len(routes())} routes")
        for (name, points), result in zip(parts, baselines):
            print(
                f"  baseline {name:11s} "
                f"{h131.describe(result, len(points))}"
            )
        ranked = []
        for route in routes():
            results = [score(points, route) for _, points in parts]
            if all(
                result <= baseline
                for result, baseline in zip(results, baselines)
            ):
                ranked.append(
                    (
                        sum(result[0] for result in results),
                        sum(result[2] for result in results),
                        sum(result[1] for result in results),
                        route.short(),
                        route,
                        results,
                    )
                )
        ranked.sort()
        survivors[source] = [entry[4] for entry in ranked]
        for _, _, _, label, _, results in ranked:
            print(f"  {label}")
            for (name, points), result in zip(parts, results):
                print(
                    f"    {name:11s} "
                    f"{h131.describe(result, len(points))}"
                )

    shared_dense = [
        h58.prepare(point)
        for point in h58.load_points(
            h99.ROOT / "capture-kit-captures" / "pentiumII"
        )
        if point.exponent == -2
    ]
    master = h99.master_points()
    dense_baseline = shared_dense_score(shared_dense, BASELINE)
    master_baseline = master_score(master, BASELINE)
    print(
        f"h142 pair gate: baseline dense={dense_baseline} "
        f"master={master_baseline}"
    )
    for direct in survivors["direct"]:
        for reduced in survivors["reduced"]:
            schedule = Schedule(direct, reduced)
            dense_result = shared_dense_score(shared_dense, schedule)
            master_result = master_score(master, schedule)
            if (
                dense_result <= dense_baseline
                and master_result <= master_baseline
            ):
                print(
                    f"  PASS {schedule.short()} "
                    f"dense={dense_result} master={master_result}"
                )


if __name__ == "__main__":
    main()
