#!/usr/bin/env python3
"""Resolve direct/reduced P5 FMUL output modes for Tang's C*p edge.

h140 shows that direct narrow-table witnesses select RU64 while an
M66-reduced witness selects RN64.  This pass searches all standard/internal
mode pairs independently by entry path.  Input routing is fixed to the
h139 survivor: ROM constant on X67, p-state on Y64.
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
import h139_p5_fmul_route_search as h139


@dataclasses.dataclass(frozen=True)
class Schedule:
    direct_mode: str
    reduced_mode: str

    def short(self) -> str:
        return (
            f"direct={self.direct_mode}64 "
            f"reduced={self.reduced_mode}64"
        )

    def route(self, reduced: bool) -> h139.Route:
        mode = self.reduced_mode if reduced else self.direct_mode
        return h139.Route("x", "rn", "rn", mode)


MODES = h139.OUTPUT_MODES
BASELINE = Schedule("away", "away")


def hidden_value(
    point: h131.Observed, schedule: Schedule
) -> h58.FP:
    return h139.hidden_value(
        point, schedule.route(point.source == "reduced")
    )


def point_score(
    point: h131.Observed, schedule: Schedule
) -> tuple[int, int]:
    hidden = hidden_value(point, schedule)
    output_misses = 0
    c1_misses = 0
    for index, rc in enumerate(h58.RCS):
        predicted = h58.x87_round(hidden, rc)
        expected = point.outputs[index]
        if predicted != expected:
            output_misses += 1
        else:
            predicted_c1 = (
                h110.compare_magnitude(expected, hidden) > 0
            )
            c1_misses += predicted_c1 != point.c1[index]
    return output_misses, c1_misses


def score(
    points: list[h131.Observed], schedule: Schedule
) -> tuple[int, int, int]:
    mode_misses = 0
    input_misses = 0
    c1_misses = 0
    for point in points:
        mode, c1 = point_score(point, schedule)
        mode_misses += mode
        input_misses += bool(mode)
        c1_misses += c1
    return mode_misses, input_misses, c1_misses


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
    fresh = [
        point
        for key, points in fresh_by_path.items()
        if key[0] == "narrow"
        for point in points
    ]
    baseline = [score(points, BASELINE) for _, points in complete]
    fresh_baseline = score(fresh, BASELINE)
    ranked = []
    for direct_mode in MODES:
        for reduced_mode in MODES:
            schedule = Schedule(direct_mode, reduced_mode)
            results = [score(points, schedule) for _, points in complete]
            fresh_result = score(fresh, schedule)
            if (
                all(
                    result <= base
                    for result, base in zip(results, baseline)
                )
                and fresh_result <= fresh_baseline
            ):
                ranked.append(
                    (
                        sum(result[0] for result in results)
                        + fresh_result[0],
                        sum(result[2] for result in results)
                        + fresh_result[2],
                        sum(result[1] for result in results)
                        + fresh_result[1],
                        schedule.short(),
                        schedule,
                        results,
                        fresh_result,
                    )
                )
    ranked.sort()
    print(f"h141: {len(MODES) ** 2} direct/reduced mode pairs")
    for (name, points), result in zip(complete, baseline):
        print(
            f"  baseline {name:11s} "
            f"{h131.describe(result, len(points))}"
        )
    print(
        f"  baseline {'fresh':11s} "
        f"{h131.describe(fresh_baseline, len(fresh))}"
    )
    if not ranked:
        print("no mode pair survives standalone gates")
        return

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
        f"  shared baselines dense={dense_baseline} "
        f"master={master_baseline}"
    )
    for _, _, _, _, schedule, results, fresh_result in ranked[:12]:
        dense_result = shared_dense_score(shared_dense, schedule)
        master_result = master_score(master, schedule)
        passed = (
            dense_result <= dense_baseline
            and master_result <= master_baseline
        )
        print(f"  {schedule.short():32s} {'PASS' if passed else 'FAIL'}")
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
