#!/usr/bin/env python3
"""Test the table-reconstruction graph directly.

This model uses a smaller graph than the four-term Tang expansion evaluated
by earlier searches. It forms the complete ``sin(a)`` state, multiplies it
by the cross-table constant, combines that product with
``lead*(cos(a)-1)``, and only then adds the leading table constant.
The producer/consumer edge is the complete sine-state addition feeding
multiplication, rather than independently rounded ``cross*a`` and
``cross*(sin(a)-a)`` products.

This pass keeps the validated P/Q producers and searches scalar
materializations on that fixed graph. It first checks which numerical
widths are compatible with existing hardware captures before testing
retained-addition carriers."""

from __future__ import annotations

import dataclasses
import functools

import h58_constraint_search as h58
import h60_round16_parity as h60
import h110_fsin_standalone as h110
import h170_fsin_table_correction_search as h170
import h207_tang_literal_fadd as h207
import h218_fadd_residual_programs as h218


Metric = h207.Metric
JointMetric = h207.JointMetric
ZERO_JOINT: JointMetric = ((0, 0, 0), (0, 0, 0))

QUANTS = {
    "exact": None,
    "rn64": h110.Quant(64, "rn"),
    "chop64": h110.Quant(64, "chop"),
    "away64": h110.Quant(64, "away"),
    "odd64": h110.Quant(64, "odd"),
    "rn67": h110.Quant(67, "rn"),
    "chop67": h110.Quant(67, "chop"),
    "away67": h110.Quant(67, "away"),
    "odd67": h110.Quant(67, "odd"),
}

STATE_ACTIONS = ("exact", "rn64", "chop67", "away67", "odd67")
CONSTANT_ACTIONS = ("exact", "rn64", "chop64", "away64", "odd64")
PRODUCT_ACTIONS = ("exact", "rn64", "chop67", "away67", "odd67")
CORRECTION_ACTIONS = ("rn67", "exact", "rn64", "chop67", "away67", "odd67")


@dataclasses.dataclass(frozen=True)
class Candidate:
    sine_state: str = "exact"
    cosine_state: str = "exact"
    lead_constant: str = "exact"
    cross_constant: str = "rn64"
    q_product: str = "exact"
    p_product: str = "exact"
    correction: str = "rn67"

    def short(self) -> str:
        return (
            f"state={self.sine_state}/{self.cosine_state} "
            f"const={self.lead_constant}/{self.cross_constant} "
            f"product={self.q_product}/{self.p_product} "
            f"correction={self.correction}"
        )


CURRENT = Candidate()
FIELDS = (
    ("sine_state", STATE_ACTIONS),
    ("cosine_state", STATE_ACTIONS),
    ("lead_constant", CONSTANT_ACTIONS),
    ("cross_constant", CONSTANT_ACTIONS),
    ("q_product", PRODUCT_ACTIONS),
    ("p_product", PRODUCT_ACTIONS),
    ("correction", CORRECTION_ACTIONS),
)


def quantize(value: h58.FP, action: str) -> h58.FP:
    quant = QUANTS[action]
    return value if quant is None else h110.quantize(value, quant)


@functools.lru_cache(maxsize=None)
def local_value(
    point,
    shared: bool,
    cosine_lane: bool,
    candidate: Candidate,
) -> h58.FP:
    prepared = point.joint.observed.point
    state = h207.state(point, shared)
    sine_a = h58.add_exact(state.residual, state.sine_correction)
    sine_a = quantize(sine_a, candidate.sine_state)
    cosine_tail = quantize(
        state.cosine_tail, candidate.cosine_state
    )

    if cosine_lane:
        lead, cross = prepared.cos_t, prepared.sin_t
    else:
        lead, cross = prepared.sin_t, prepared.cos_t

    q_product = quantize(
        h58.mul_exact(
            quantize(lead, candidate.lead_constant), cosine_tail
        ),
        candidate.q_product,
    )
    p_product = quantize(
        h58.mul_exact(
            quantize(cross, candidate.cross_constant), sine_a
        ),
        candidate.p_product,
    )
    if cosine_lane:
        p_product = h58.neg(p_product)
    correction = quantize(
        h58.add_exact(q_product, p_product), candidate.correction
    )
    return h58.add_exact(lead, correction)


def hidden_values(point, candidate: Candidate) -> tuple[h58.FP, h58.FP]:
    sine = local_value(point, False, False, candidate)
    cosine = local_value(point, True, True, candidate)
    if point.joint.observed.point.raw.sign:
        sine = h58.neg(sine)
    return h60.rotate(
        (sine, cosine), point.joint.observed.signed_n
    )


def metric_for(point, values) -> JointMetric:
    sine, cosine = values
    sine_metric = h170.point_metric(
        point.prepared.joint.observed, sine
    )
    cosine_metric = (
        h207.h182.point_metric(
            point.prepared.joint.cosine_outputs,
            point.prepared.joint.cosine_c1,
            cosine,
        )
        if point.cosine_hardware
        else (0, 0, 0)
    )
    return sine_metric, cosine_metric


def add_metric(left: JointMetric, right: JointMetric) -> JointMetric:
    return tuple(
        h170.add(old, new) for old, new in zip(left, right)
    )  # type: ignore[return-value]


def score(datasets, candidate: Candidate | None):
    totals = []
    cache = {}
    for _, points in datasets:
        total = ZERO_JOINT
        for point in points:
            key = (point, candidate)
            value = cache.get(key)
            if value is None:
                values = (
                    h218.current_values(point)
                    if candidate is None
                    else hidden_values(point.prepared, candidate)
                )
                value = metric_for(point, values)
                cache[key] = value
            total = add_metric(total, value)
        totals.append(total)
    return tuple(totals)


def objective(values) -> tuple[int, int, int]:
    return tuple(
        sum(metric[index] for value in values for metric in value)
        for index in (0, 2, 1)
    )


def regressions(values, baselines) -> tuple[int, int, int]:
    positive = []
    for value, baseline in zip(values, baselines):
        for lane, old_lane in zip(value, baseline):
            positive.extend(
                max(0, new - old)
                for new, old in zip(lane, old_lane)
            )
    return sum(bool(delta) for delta in positive), max(positive), sum(positive)


def no_worse(values, baselines) -> bool:
    return all(
        all(
            h207.h173.no_worse(lane, old_lane)
            for lane, old_lane in zip(value, baseline)
        )
        for value, baseline in zip(values, baselines)
    )


def sample_dataset(name, points, controls: int = 96):
    constrained = []
    correct = []
    for point in points:
        target = (
            constrained
            if metric_for(point, h218.current_values(point)) != ZERO_JOINT
            else correct
        )
        target.append(point)
    correct.sort(
        key=lambda point: (
            point.prepared.joint.observed.point.raw.sig
            ^ (point.prepared.joint.observed.index << 9)
            ^ point.prepared.joint.observed.signed_n
        )
    )
    return name, constrained + correct[:controls]


def expand(beam):
    result = set(beam)
    for candidate in beam:
        for field, actions in FIELDS:
            for action in actions:
                result.add(dataclasses.replace(
                    candidate, **{field: action}
                ))
    return result


def search(selected, baselines, width: int = 24, rounds: int = 4):
    beam = [CURRENT]
    seen = set()
    for round_index in range(1, rounds + 1):
        ranked = []
        for candidate in expand(beam):
            if candidate in seen:
                continue
            seen.add(candidate)
            values = score(selected, candidate)
            ranked.append((
                regressions(values, baselines),
                objective(values),
                candidate.short(),
                candidate,
                values,
            ))
        ranked.sort()
        beam = [item[3] for item in ranked[:width]]
        print(
            f"round {round_index}: tested={len(ranked)} "
            f"seen={len(seen)} best={ranked[0][0:3]}",
            flush=True,
        )
    return beam


def main() -> None:
    complete = h218.datasets()
    selected = [sample_dataset(name, points) for name, points in complete]
    baselines = score(selected, None)
    print(
        f"h226 P6 full-sine graph: selected="
        f"{sum(len(points) for _, points in selected)} "
        f"complete={sum(len(points) for _, points in complete)}"
    )
    print(f"  Round36 selected objective={objective(baselines)}")
    current = score(selected, CURRENT)
    print(
        f"  exact-graph seed objective={objective(current)} "
        f"regressions={regressions(current, baselines)}"
    )
    beam = search(selected, baselines)
    finalists = []
    complete_baselines = score(complete, None)
    for candidate in beam:
        selected_values = score(selected, candidate)
        if not no_worse(selected_values, baselines):
            continue
        complete_values = score(complete, candidate)
        if no_worse(complete_values, complete_baselines):
            finalists.append((
                objective(complete_values),
                candidate.short(),
                candidate,
                complete_values,
            ))
    finalists.sort()
    print(f"h226 complete survivors={len(finalists)}")
    for item in finalists[:20]:
        print(f"  {item[0]} {item[1]}")


if __name__ == "__main__":
    main()
