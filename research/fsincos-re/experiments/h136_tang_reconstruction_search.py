#!/usr/bin/env python3
"""Test Tang's literal table-reconstruction operation graph.

Tang reconstructs sine as::

    Sj + r*Cj + (Sj*q(r) + Cj*p(r))

The current model instead evaluates the algebraically equivalent::

    Sj*(1+q(r)) + Cj*(r+p(r))

h104 tested 545 materialization variants of the latter graph, but never
split ``Cj*(r+p)`` into ``Cj*r + Cj*p``.  This pass keeps the validated
standalone-FSIN P/Q producers and searches physically justified 64-, 67-,
and 69-bit materializations in Tang's graph.  Candidate selection uses only
training partitions.  Held-out standalone data, fresh h135 separators,
Pentium-II dense FSINCOS, and the master sweep are independent gates.
"""

from __future__ import annotations

import dataclasses
import functools

import h58_constraint_search as h58
import h60_round16_parity as h60
import h79_table_state_bias as h79
import h99_narrow_candidate_crossvalidate as h99
import h104_table_final_partial_search as h104
import h110_fsin_standalone as h110
import h131_fsin_table_c1_search as h131
import h134_fsin_table_per_edge_search as h134
import h135_fsin_table_terminal_discriminator as h135


@dataclasses.dataclass(frozen=True)
class Variant:
    kind: str
    bits: int = 0
    mode: str = "exact"

    def short(self) -> str:
        if not self.bits:
            return self.kind
        return f"{self.kind}-{self.mode}{self.bits}"


EXACT = Variant("exact")
KINDS = (
    "products",
    "linear",
    "q-product",
    "p-product",
    "nonlinear",
    "correction",
    "lead-linear",
    "lead-nonlinear",
    "products-nonlinear",
    "nonlinear-correction",
)


def variants() -> tuple[Variant, ...]:
    return (
        EXACT,
        *(
            Variant(kind, bits, mode)
            for kind in KINDS
            for bits in (64, 67, 69)
            for mode in ("rn", "chop", "away", "odd")
        ),
    )


def materialize(value: h58.FP, variant: Variant) -> h58.FP:
    return h110.quantize(
        value, h110.Quant(variant.bits, variant.mode)
    )


def lane_value(
    lead: h58.FP,
    cross: h58.FP,
    residual: h58.FP,
    sine_correction: h58.FP,
    cosine_tail: h58.FP,
    subtract_cross: bool,
    variant: Variant,
) -> h58.FP:
    """Evaluate Tang's sine or cosine reconstruction graph."""

    linear = h58.mul_exact(cross, residual)
    p_product = h58.mul_exact(cross, sine_correction)
    if subtract_cross:
        linear = h58.neg(linear)
        p_product = h58.neg(p_product)
    q_product = h58.mul_exact(lead, cosine_tail)

    if variant.kind == "products":
        linear = materialize(linear, variant)
        q_product = materialize(q_product, variant)
        p_product = materialize(p_product, variant)
    elif variant.kind == "linear":
        linear = materialize(linear, variant)
    elif variant.kind == "q-product":
        q_product = materialize(q_product, variant)
    elif variant.kind == "p-product":
        p_product = materialize(p_product, variant)

    nonlinear = h58.add_exact(q_product, p_product)
    if variant.kind in (
        "nonlinear",
        "products-nonlinear",
        "nonlinear-correction",
    ):
        nonlinear = materialize(nonlinear, variant)

    if variant.kind == "lead-linear":
        partial = materialize(
            h58.add_exact(lead, linear), variant
        )
        return h58.add_exact(partial, nonlinear)
    if variant.kind == "lead-nonlinear":
        partial = materialize(
            h58.add_exact(lead, nonlinear), variant
        )
        return h58.add_exact(partial, linear)

    correction = h58.add_exact(linear, nonlinear)
    if variant.kind in ("correction", "nonlinear-correction"):
        correction = materialize(correction, variant)
    return h58.add_exact(lead, correction)


@dataclasses.dataclass(frozen=True)
class State:
    residual: h58.FP
    sine_correction: h58.FP
    cosine_tail: h58.FP


@functools.lru_cache(maxsize=None)
def standalone_state(
    point: h58.PreparedPoint,
    schedule: h134.Schedule,
) -> State:
    """Produce current P/Q state but retain Tang's separate p(r)."""

    square = h58.fmul(point.a, point.a, 64, "rn")
    p_rows = h58.S6 if point.wide else h58.S4
    q_rows = h58.C6 if point.wide else h58.C4
    p = h134.horner(
        p_rows,
        square,
        schedule.p_coefficients,
        schedule.p_products,
        schedule.p_sums,
        0 if point.wide else 7168,
    )
    q = h134.horner(
        q_rows,
        square,
        schedule.q_coefficients,
        schedule.q_products,
        schedule.q_sums,
    )
    m = h58.fmul(p, square, 64, "rn")
    raw_correction = h58.fmul(m, point.a, 64, "rn")
    sine_a = h58.fadd(point.a, raw_correction, 64, "rn")
    sine_a = h79.bias_toward_zero(
        sine_a, 5 if point.wide else 4
    )
    # Deriving p from the validated shared-S carrier makes the exact Tang
    # graph algebraically identical to the current producer.  It isolates
    # reconstruction grouping from a separate producer hypothesis.
    sine_correction = h58.add_exact(sine_a, h58.neg(point.a))
    cosine_tail = h58.fmul(q, square, 64, "rn")
    return State(point.a, sine_correction, cosine_tail)


def hidden_value(
    observed: h131.Observed, variant: Variant
) -> h58.FP:
    point = observed.point
    state = standalone_state(point, h135.path_candidate(observed))
    quadrant = observed.signed_n & 3
    if quadrant & 1:
        value = lane_value(
            point.cos_t,
            point.sin_t,
            state.residual,
            state.sine_correction,
            state.cosine_tail,
            True,
            variant,
        )
    else:
        value = lane_value(
            point.sin_t,
            point.cos_t,
            state.residual,
            state.sine_correction,
            state.cosine_tail,
            False,
            variant,
        )
        if point.raw.sign:
            value = h58.neg(value)
    return h58.neg(value) if quadrant & 2 else value


def baseline_hidden(observed: h131.Observed) -> h58.FP:
    return h134.hidden_value(observed, h135.path_candidate(observed))


def point_score(
    observed: h131.Observed, variant: Variant | None
) -> tuple[int, int]:
    hidden = (
        baseline_hidden(observed)
        if variant is None
        else hidden_value(observed, variant)
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
    points: list[h131.Observed], variant: Variant | None
) -> tuple[int, int, int]:
    mode_misses = 0
    input_misses = 0
    c1_misses = 0
    for point in points:
        mode, c1 = point_score(point, variant)
        mode_misses += mode
        input_misses += bool(mode)
        c1_misses += c1
    return mode_misses, input_misses, c1_misses


def search_sample(
    points: list[h131.Observed], controls: int
) -> list[h131.Observed]:
    constrained = [
        point for point in points if point_score(point, None) != (0, 0)
    ]
    exact = [
        point for point in points if point_score(point, None) == (0, 0)
    ]
    count = min(controls, len(exact))
    selected = (
        [
            exact[(index * len(exact)) // count]
            for index in range(count)
        ]
        if count
        else []
    )
    return constrained + selected


def shared_values(
    point: h58.PreparedPoint, variant: Variant
) -> tuple[h58.FP, h58.FP]:
    altered, one_plus_tail, sine_a = h104.state(point)
    state = State(
        altered.a,
        h58.add_exact(sine_a, h58.neg(altered.a)),
        h58.add_exact(one_plus_tail, h58.neg(h58.ONE)),
    )
    sine = lane_value(
        altered.sin_t,
        altered.cos_t,
        state.residual,
        state.sine_correction,
        state.cosine_tail,
        False,
        variant,
    )
    cosine = lane_value(
        altered.cos_t,
        altered.sin_t,
        state.residual,
        state.sine_correction,
        state.cosine_tail,
        True,
        variant,
    )
    if point.raw.sign:
        sine = h58.neg(sine)
    return sine, cosine


def shared_dense_score(
    points: list[h58.PreparedPoint], variant: Variant
) -> tuple[int, int, int]:
    mode_misses = 0
    output_misses = 0
    rn_misses = 0
    for point in points:
        predicted = shared_values(point, variant)
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


def master_score(
    points: list[
        tuple[
            tuple[int, h58.PreparedPoint, bool] | None,
            tuple[tuple[int, int], tuple[int, int]] | None,
        ]
    ],
    family: str,
    variant: Variant,
) -> tuple[int, int]:
    misses = 0
    selected_misses = 0
    for active, expected in points:
        if active is None:
            continue
        if expected is None:
            raise AssertionError("table-active master input returned C2")
        signed_n, point, _ = active
        selected = ("wide" if point.wide else "narrow") == family
        predicted = (
            shared_values(point, variant)
            if selected
            else h104.values(point, h104.VARIANT)
        )
        actual = tuple(
            h58.x87_round(value, "rn")
            for value in h60.rotate(predicted, signed_n)
        )
        mismatch = actual != expected
        misses += mismatch
        selected_misses += mismatch if selected else 0
    return misses, selected_misses


def partitions(
    family: str,
    dense: list[h131.Observed],
    sweep: list[h131.Observed],
) -> list[tuple[str, list[h131.Observed]]]:
    result = []
    for name, dataset in (("dense", dense), ("sweep", sweep)):
        selected = [point for point in dataset if point.family == family]
        result.extend(
            (
                (
                    f"{name}-train",
                    [point for point in selected if h131.is_train(point)],
                ),
                (
                    f"{name}-held",
                    [
                        point
                        for point in selected
                        if not h131.is_train(point)
                    ],
                ),
            )
        )
    return result


def search_family(
    family: str,
    dense: list[h131.Observed],
    sweep: list[h131.Observed],
    fresh: list[h131.Observed],
    shared_dense: list[h58.PreparedPoint],
    master,
) -> None:
    complete = partitions(family, dense, sweep)
    training = [
        (name, search_sample(points, 1500))
        for name, points in complete
        if name.endswith("-train")
    ]
    baseline = [score(points, None) for _, points in complete]
    fresh_baseline = score(fresh, None)
    print(f"\n{family}: {len(variants())} Tang variants")
    for (name, points), result in zip(complete, baseline):
        print(
            f"  {name:11s} {len(points):6d} "
            f"{h131.describe(result, len(points))}"
        )
    print(
        f"  fresh       {len(fresh):6d} "
        f"{h131.describe(fresh_baseline, len(fresh))}"
    )

    ranked = []
    for variant in variants():
        results = [score(points, variant) for _, points in training]
        ranked.append(
            (
                sum(result[0] for result in results),
                sum(result[2] for result in results),
                sum(result[1] for result in results),
                variant.short(),
                variant,
            )
        )
    ranked.sort()

    validated = []
    for _, _, _, _, variant in ranked[:32]:
        results = [score(points, variant) for _, points in complete]
        fresh_result = score(fresh, variant)
        if (
            all(
                result <= base
                for result, base in zip(results, baseline)
            )
            and fresh_result <= fresh_baseline
            and (
                any(
                    result < base
                    for result, base in zip(results, baseline)
                )
                or fresh_result < fresh_baseline
            )
        ):
            validated.append((variant, results, fresh_result))

    if not validated:
        print("  no Tang variant transfers across standalone gates")
        print("  leading training candidates:")
        for item in ranked[:8]:
            variant = item[4]
            results = [score(points, variant) for _, points in complete]
            fresh_result = score(fresh, variant)
            print(
                f"    {variant.short():32s} train={item[:3]} "
                f"complete={[result[0] for result in results]} "
                f"fresh={fresh_result[0]}"
            )
        return

    dense_baseline = h104.score(shared_dense, h104.VARIANT)
    master_baseline = h104.master_score(
        master, family, h104.VARIANT
    )
    print(
        f"  shared baselines: dense={dense_baseline} "
        f"master={master_baseline}"
    )
    for variant, results, fresh_result in validated[:12]:
        dense_result = shared_dense_score(shared_dense, variant)
        master_result = master_score(master, family, variant)
        shared_ok = (
            dense_result <= dense_baseline
            and master_result[0] <= master_baseline[0]
        )
        print(
            f"  {variant.short():32s} "
            f"shared={'PASS' if shared_ok else 'FAIL'} "
            f"dense={dense_result} master={master_result}"
        )
        for (name, points), result in zip(complete, results):
            print(
                f"    {name:11s} "
                f"{h131.describe(result, len(points))}"
            )
        print(
            f"    {'fresh':11s} "
            f"{h131.describe(fresh_result, len(fresh))}"
        )


def main() -> None:
    dense = h131.load_dataset("dense", h131.INPUTS / "dense_qn.txt")
    sweep = h131.load_dataset("sweep", h131.INPUTS / "sweep_inputs.txt")
    fresh_by_path = h135.load_capture(
        h135.DEFAULT_OUTPUT,
        h135.DEFAULT_METADATA,
        h135.ROOT / "capture-kit-captures" / "skylake-fsin-h135",
    )
    shared_all = [
        h58.prepare(point)
        for point in h58.load_points(
            h99.ROOT / "capture-kit-captures" / "pentiumII"
        )
    ]
    master = h99.master_points()
    print(
        f"loaded standalone dense={len(dense)} sweep={len(sweep)}, "
        f"fresh={sum(len(points) for points in fresh_by_path.values())}, "
        f"shared dense={len(shared_all)}"
    )
    for family in ("narrow", "wide"):
        fresh = [
            point
            for key, points in fresh_by_path.items()
            if key[0] == family
            for point in points
        ]
        shared_dense = [
            point
            for point in shared_all
            if ("wide" if point.wide else "narrow") == family
        ]
        search_family(
            family,
            dense,
            sweep,
            fresh,
            shared_dense,
            master,
        )


if __name__ == "__main__":
    main()
