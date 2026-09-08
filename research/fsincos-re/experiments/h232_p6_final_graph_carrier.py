#!/usr/bin/env python3
"""Replay the final table graph from the validated P/Q state.

h226 finds the table graph numerically competitive, while h231 shows that
rebuilding every producer with one global multiplication rule is too coarse.
This pass fixes the following numerical operations:

    q_product = multiply(table_lead, cos(a)-1)
    p_product = multiply(table_cross, sin(a))
    correction = subtract(q_product, p_product)
    result = final_add(table_lead, correction)

The cross-validated Round-35/36 state supplies ``sin(a)`` and the cosine tail.
The two products may use distinct materializations while sharing the same
operand routing. The subtraction retains the h206 FAMUBUS representation
until the architectural addition. A candidate must be componentwise
non-regressing on every old partition before it is considered for the C model."""

from __future__ import annotations

import dataclasses
import functools

import h58_constraint_search as h58
import h60_round16_parity as h60
import h110_fsin_standalone as h110
import h170_fsin_table_correction_search as h170
import h200_p5_fadd_bitvector as h200
import h206_p5_fadd_complete as h206
import h207_tang_literal_fadd as h207
import h218_fadd_residual_programs as h218
import h226_p6_full_sine_graph as h226


OUTPUTS = ("odd67", "rn64", "chop64", "away64", "odd64")
Y_MODES = ("rn64", "chop64", "away64", "odd64")
ACTIONS = ("retain", "rn64", "chop64", "away64", "odd64", "odd67")


@dataclasses.dataclass(frozen=True)
class Candidate:
    state_on_x: bool = True
    q_y_mode: str = "rn64"
    p_y_mode: str = "rn64"
    q_output: str = "odd67"
    p_output: str = "odd67"
    correction_mode: str = "jam-sub"
    correction_normalize: bool = True
    correction_action: str = "retain"

    def short(self) -> str:
        route = "state-X" if self.state_on_x else "constant-X"
        return (
            f"{route} q={self.q_y_mode}/{self.q_output} "
            f"p={self.p_y_mode}/{self.p_output} "
            f"FSUB={self.correction_mode}/"
            f"{'norm' if self.correction_normalize else 'raw'}/"
            f"{self.correction_action}"
        )


CURRENT = Candidate()
FIELDS = (
    ("state_on_x", (False, True)),
    ("q_y_mode", Y_MODES),
    ("p_y_mode", Y_MODES),
    ("q_output", OUTPUTS),
    ("p_output", OUTPUTS),
    ("correction_mode", h206.MODES),
    ("correction_normalize", (False, True)),
    ("correction_action", ACTIONS),
)


def value_bus(value: h58.FP) -> h206.Bus:
    return h200.normalized_bus(value)


def multiply(
    state: h58.FP,
    constant: h58.FP,
    state_on_x: bool,
    y_mode: str,
    output: str,
) -> h206.Bus:
    x, y = (
        (value_bus(state), value_bus(constant))
        if state_on_x
        else (value_bus(constant), value_bus(state))
    )
    return h206.fmul_x67_y64(x, y, y_mode=y_mode, output=output)


@functools.lru_cache(maxsize=None)
def local_value(point, shared: bool, cosine_lane: bool, candidate: Candidate):
    prepared = point.joint.observed.point
    state = h207.state(point, shared)
    sine_a = h58.add_exact(state.residual, state.sine_correction)
    # h207 stores the empirically validated state as two exact terms.  Their
    # recombination can carry redundant low zeroes in the tuple encoding even
    # though the value itself is a 64-bit state; canonicalize it before the
    # physical bus-width check.
    sine_a = h110.quantize(sine_a, h110.Quant(67, "rn"))
    if cosine_lane:
        lead, cross = prepared.cos_t, prepared.sin_t
    else:
        lead, cross = prepared.sin_t, prepared.cos_t

    q_product = multiply(
        state.cosine_tail,
        lead,
        candidate.state_on_x,
        candidate.q_y_mode,
        candidate.q_output,
    )
    p_product = multiply(
        sine_a,
        cross,
        candidate.state_on_x,
        candidate.p_y_mode,
        candidate.p_output,
    )
    if cosine_lane:
        p_product = dataclasses.replace(
            p_product, sign=p_product.sign ^ 1
        )
    correction, _ = h206.fadd(
        q_product,
        p_product,
        candidate.correction_mode,
        normalize=candidate.correction_normalize,
    )
    correction = h206.materialize(
        correction, candidate.correction_action
    )
    # FINAL_ADD performs the final lead-plus-correction operation and the
    # architectural rounding selected by the x87 control word.  Keeping the
    # exact hidden sum lets the existing RN/RD/RU interval scorer apply it.
    return h58.add_exact(lead, correction.value())


def hidden_values(point, candidate: Candidate):
    sine = local_value(point, False, False, candidate)
    cosine = local_value(point, True, True, candidate)
    if point.joint.observed.point.raw.sign:
        sine = h58.neg(sine)
    return h60.rotate((sine, cosine), point.joint.observed.signed_n)


def score(datasets, candidate: Candidate | None):
    totals = []
    cache = {}
    for _, points in datasets:
        total = h226.ZERO_JOINT
        for point in points:
            key = (point, candidate)
            value = cache.get(key)
            if value is None:
                values = (
                    h218.current_values(point)
                    if candidate is None
                    else hidden_values(point.prepared, candidate)
                )
                value = h226.metric_for(point, values)
                cache[key] = value
            total = h226.add_metric(total, value)
        totals.append(total)
    return tuple(totals)


def expand(beam):
    result = set(beam)
    for candidate in beam:
        for field, actions in FIELDS:
            for action in actions:
                result.add(dataclasses.replace(
                    candidate, **{field: action}
                ))
    return result


def search(selected, baselines, width: int = 40, rounds: int = 5):
    beam = [CURRENT]
    seen = set()
    for round_index in range(1, rounds + 1):
        ranked = []
        failures = 0
        for candidate in expand(beam):
            if candidate in seen:
                continue
            seen.add(candidate)
            try:
                values = score(selected, candidate)
            except ValueError:
                failures += 1
                continue
            ranked.append((
                h226.regressions(values, baselines),
                h226.objective(values),
                candidate.short(),
                candidate,
                values,
            ))
        ranked.sort()
        beam = [item[3] for item in ranked[:width]]
        print(
            f"round {round_index}: tested={len(ranked)} "
            f"invalid={failures} seen={len(seen)} best={ranked[0][0:3]}",
            flush=True,
        )
    return beam


def main() -> None:
    complete = h218.datasets()
    selected = [
        h226.sample_dataset(name, points, controls=80)
        for name, points in complete
    ]
    baselines = score(selected, None)
    print(
        f"h232 P6 final graph carrier: selected="
        f"{sum(len(points) for _, points in selected)} "
        f"complete={sum(len(points) for _, points in complete)}"
    )
    print(f"  Round36 selected objective={h226.objective(baselines)}")
    seed = score(selected, CURRENT)
    print(
        f"  seed objective={h226.objective(seed)} "
        f"regressions={h226.regressions(seed, baselines)}"
    )
    beam = search(selected, baselines)
    complete_baselines = score(complete, None)
    finalists = []
    for candidate in beam:
        selected_values = score(selected, candidate)
        if not h226.no_worse(selected_values, baselines):
            continue
        complete_values = score(complete, candidate)
        if h226.no_worse(complete_values, complete_baselines):
            finalists.append((
                h226.objective(complete_values),
                candidate.short(),
                candidate,
                complete_values,
            ))
    finalists.sort()
    print(f"h232 complete survivors={len(finalists)}")
    for item in finalists[:20]:
        print(f"  {item[0]} {item[1]}")


if __name__ == "__main__":
    main()
