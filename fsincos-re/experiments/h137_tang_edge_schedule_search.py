#!/usr/bin/env python3
"""Coordinate-search independent edges of Tang's reconstruction graph.

h136 rejects every uniform materialization of Tang's split table formula.
This pass tests its remaining non-uniform form.  Products ``C*r``, ``S*q``,
and ``C*p`` plus the nonlinear and total-correction sums receive independent
64-, 67-, or 69-bit quantizers.  A change is accepted only when it is no
worse on every complete train/held-out partition and the fresh h135 capture,
and improves at least one of them.
"""

from __future__ import annotations

import argparse
import dataclasses
from collections.abc import Iterable

import h58_constraint_search as h58
import h60_round16_parity as h60
import h99_narrow_candidate_crossvalidate as h99
import h104_table_final_partial_search as h104
import h110_fsin_standalone as h110
import h131_fsin_table_c1_search as h131
import h135_fsin_table_terminal_discriminator as h135
import h136_tang_reconstruction_search as h136


Quant = h110.Quant
EXACT = h110.EXACT
RN67 = Quant(67, "rn")


@dataclasses.dataclass(frozen=True)
class Schedule:
    linear: Quant = EXACT
    q_product: Quant = EXACT
    p_product: Quant = EXACT
    nonlinear: Quant = EXACT
    correction: Quant = RN67

    def short(self) -> str:
        return (
            f"L={self.linear.short()} Q={self.q_product.short()} "
            f"P={self.p_product.short()} N={self.nonlinear.short()} "
            f"C={self.correction.short()}"
        )


CURRENT = Schedule()


def quantize(value: h58.FP, quant: Quant) -> h58.FP:
    return h110.quantize(value, quant)


def lane_value(
    lead: h58.FP,
    cross: h58.FP,
    residual: h58.FP,
    sine_correction: h58.FP,
    cosine_tail: h58.FP,
    subtract_cross: bool,
    schedule: Schedule,
) -> h58.FP:
    linear = h58.mul_exact(cross, residual)
    p_product = h58.mul_exact(cross, sine_correction)
    if subtract_cross:
        linear = h58.neg(linear)
        p_product = h58.neg(p_product)
    linear = quantize(linear, schedule.linear)
    q_product = quantize(
        h58.mul_exact(lead, cosine_tail), schedule.q_product
    )
    p_product = quantize(p_product, schedule.p_product)
    nonlinear = quantize(
        h58.add_exact(q_product, p_product), schedule.nonlinear
    )
    correction = quantize(
        h58.add_exact(linear, nonlinear), schedule.correction
    )
    return h58.add_exact(lead, correction)


def hidden_value(
    observed: h131.Observed, schedule: Schedule
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
            state.residual,
            state.sine_correction,
            state.cosine_tail,
            True,
            schedule,
        )
    else:
        value = lane_value(
            point.sin_t,
            point.cos_t,
            state.residual,
            state.sine_correction,
            state.cosine_tail,
            False,
            schedule,
        )
        if point.raw.sign:
            value = h58.neg(value)
    return h58.neg(value) if quadrant & 2 else value


def shared_values(
    point: h58.PreparedPoint, schedule: Schedule
) -> tuple[h58.FP, h58.FP]:
    altered, one_plus_tail, sine_a = h104.state(point)
    residual = altered.a
    sine_correction = h58.add_exact(sine_a, h58.neg(residual))
    cosine_tail = h58.add_exact(one_plus_tail, h58.neg(h58.ONE))
    sine = lane_value(
        altered.sin_t,
        altered.cos_t,
        residual,
        sine_correction,
        cosine_tail,
        False,
        schedule,
    )
    cosine = lane_value(
        altered.cos_t,
        altered.sin_t,
        residual,
        sine_correction,
        cosine_tail,
        True,
        schedule,
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
        predicted = shared_values(point, schedule)
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


def shared_master_score(
    points: list[
        tuple[
            tuple[int, h58.PreparedPoint, bool] | None,
            tuple[tuple[int, int], tuple[int, int]] | None,
        ]
    ],
    family: str,
    schedule: Schedule,
) -> tuple[int, int, int]:
    misses = 0
    narrow = 0
    wide = 0
    for active, expected in points:
        if active is None:
            continue
        if expected is None:
            raise AssertionError("table-active master input returned C2")
        signed_n, point, _ = active
        selected = ("wide" if point.wide else "narrow") == family
        predicted = (
            shared_values(point, schedule)
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


def point_score(
    observed: h131.Observed, schedule: Schedule
) -> tuple[int, int]:
    hidden = hidden_value(observed, schedule)
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


def options() -> tuple[Quant, ...]:
    return (
        EXACT,
        *(
            Quant(bits, mode)
            for bits in (64, 67, 69)
            for mode in ("rn", "chop", "away", "odd")
        ),
    )


def coordinates(
    schedule: Schedule,
) -> Iterable[tuple[str, Iterable[Schedule]]]:
    for field in (
        "linear",
        "q_product",
        "p_product",
        "nonlinear",
        "correction",
    ):
        yield (
            field,
            (
                dataclasses.replace(schedule, **{field: value})
                for value in options()
            ),
        )


def search_family(
    family: str,
    dense: list[h131.Observed],
    sweep: list[h131.Observed],
    fresh: list[h131.Observed],
) -> Schedule:
    complete = h136.partitions(family, dense, sweep)
    samples = [
        (name, h136.search_sample(points, 1000))
        for name, points in complete
    ]
    current = CURRENT
    complete_baseline = [
        score(points, current) for _, points in complete
    ]
    fresh_baseline = score(fresh, current)
    print(f"\n{family}: baseline {current.short()}")
    for (name, points), result in zip(complete, complete_baseline):
        print(
            f"  {name:11s} "
            f"{h131.describe(result, len(points))}"
        )
    print(
        f"  {'fresh':11s} "
        f"{h131.describe(fresh_baseline, len(fresh))}"
    )

    for pass_index in range(4):
        changed = False
        print(f"  coordinate pass {pass_index + 1}")
        for name, candidates in coordinates(current):
            ranked = []
            sample_baseline = [
                score(points, current) for _, points in samples
            ]
            for candidate in dict.fromkeys(candidates):
                results = [
                    score(points, candidate) for _, points in samples
                ]
                ranked.append(
                    (
                        sum(result[0] for result in results),
                        sum(result[2] for result in results),
                        sum(result[1] for result in results),
                        candidate.short(),
                        candidate,
                    )
                )
            ranked.sort()
            accepted = None
            for _, _, _, _, candidate in ranked:
                sample_results = [
                    score(points, candidate) for _, points in samples
                ]
                if not all(
                    result <= base
                    for result, base in zip(
                        sample_results, sample_baseline
                    )
                ):
                    continue
                results = [
                    score(points, candidate) for _, points in complete
                ]
                fresh_result = score(fresh, candidate)
                if (
                    all(
                        result <= base
                        for result, base in zip(
                            results, complete_baseline
                        )
                    )
                    and fresh_result <= fresh_baseline
                    and (
                        any(
                            result < base
                            for result, base in zip(
                                results, complete_baseline
                            )
                        )
                        or fresh_result < fresh_baseline
                    )
                ):
                    accepted = candidate, results, fresh_result
                    break
            if accepted is None:
                print(f"    {name:10s}: no transferable change")
                continue
            current, complete_baseline, fresh_baseline = accepted
            changed = True
            print(f"    {name:10s}: {current.short()}")
            for (partition, points), result in zip(
                complete, complete_baseline
            ):
                print(
                    f"      {partition:11s} "
                    f"{h131.describe(result, len(points))}"
                )
            print(
                f"      {'fresh':11s} "
                f"{h131.describe(fresh_baseline, len(fresh))}"
            )
        if not changed:
            break
    print(f"  survivor {current.short()}")
    return current


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--crossvalidate-only", action="store_true")
    args = parser.parse_args()
    if args.crossvalidate_only:
        survivors = {
            "narrow": dataclasses.replace(
                CURRENT, p_product=Quant(64, "away")
            ),
            "wide": dataclasses.replace(
                CURRENT, q_product=Quant(67, "odd")
            ),
        }
    else:
        dense = h131.load_dataset("dense", h131.INPUTS / "dense_qn.txt")
        sweep = h131.load_dataset(
            "sweep", h131.INPUTS / "sweep_inputs.txt"
        )
        fresh_by_path = h135.load_capture(
            h135.DEFAULT_OUTPUT,
            h135.DEFAULT_METADATA,
            h135.ROOT / "capture-kit-captures" / "skylake-fsin-h135",
        )
        print(
            f"loaded standalone dense={len(dense)} sweep={len(sweep)}, "
            f"fresh={sum(len(points) for points in fresh_by_path.values())}"
        )
        survivors = {}
        for family in ("narrow", "wide"):
            fresh = [
                point
                for key, points in fresh_by_path.items()
                if key[0] == family
                for point in points
            ]
            survivors[family] = search_family(
                family, dense, sweep, fresh
            )
    if all(schedule == CURRENT for schedule in survivors.values()):
        print("\nno non-uniform Tang edge transfers")
        return

    # Only load the larger shared gates if a standalone survivor exists.
    shared_all = [
        h58.prepare(point)
        for point in h58.load_points(
            h99.ROOT / "capture-kit-captures" / "pentiumII"
        )
    ]
    master = h99.master_points()
    print("\nshared FSINCOS cross-validation:")
    for family, schedule in survivors.items():
        if schedule != CURRENT:
            selected = [
                point
                for point in shared_all
                if ("wide" if point.wide else "narrow") == family
            ]
            dense_baseline = shared_dense_score(selected, CURRENT)
            reference = h104.score(selected, h131.CURRENT)
            if dense_baseline != reference:
                raise SystemExit(
                    f"{family} Tang baseline differs from h104: "
                    f"{dense_baseline} != {reference}"
                )
            dense_candidate = shared_dense_score(selected, schedule)
            master_baseline = shared_master_score(
                master, family, CURRENT
            )
            master_reference = h104.master_score(
                master, family, h131.CURRENT
            )
            if master_baseline != master_reference:
                raise SystemExit(
                    f"{family} Tang master baseline differs from h104: "
                    f"{master_baseline} != {master_reference}"
                )
            master_candidate = shared_master_score(
                master, family, schedule
            )
            passed = (
                dense_candidate <= dense_baseline
                and master_candidate <= master_baseline
            )
            print(f"  {family}: {schedule.short()}")
            print(
                f"    dense  {dense_baseline} -> {dense_candidate}"
            )
            print(
                f"    master {master_baseline} -> {master_candidate}"
            )
            print(f"    {'PASS' if passed else 'FAIL'}")


if __name__ == "__main__":
    main()
