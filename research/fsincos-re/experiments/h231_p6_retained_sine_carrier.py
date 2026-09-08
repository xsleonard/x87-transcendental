#!/usr/bin/env python3
"""Replay the P6 FSINCOS retained-sine carrier through the P5 datapath.

h226 shows that the modeled full-``sin(a)`` reconstruction graph has much
lower aggregate error than the earlier four-term proxy, but no scalar
materialization passes every independent partition.  The operation ordering
identifies the missing physical edge: the FADD that forms ``sin(a)`` writes a
temporary consumed immediately by FMUL.  This pass retains h206's literal
FAMUBUS representation across that edge and then follows the modeled two-add
final graph.

All ordinary multiplication instances share one output rule.  The separate
residual-scaling operation that forms the cosine tail is allowed its own
rule because its name/semantics remain unresolved.  Both operands in the
64-bit multiplier position share one materialization rule.
"""

from __future__ import annotations

import dataclasses
import functools

import h58_constraint_search as h58
import h60_round16_parity as h60
import h110_fsin_standalone as h110
import h134_fsin_table_per_edge_search as h134
import h170_fsin_table_correction_search as h170
import h188_table_stage_local_pairs as h188
import h189_table_stage_local_discriminator as h189
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
    fmul_output: str = "odd67"
    cosine_tail_output: str = "odd67"
    y_mode: str = "rn64"
    sine_fadd_mode: str = "jam-sub"
    sine_normalize: bool = True
    sine_action: str = "retain"
    correction_fadd_mode: str = "jam-sub"
    correction_normalize: bool = True
    correction_action: str = "retain"

    def short(self) -> str:
        return (
            f"FMUL={self.fmul_output} FDIV769={self.cosine_tail_output} "
            f"Y={self.y_mode} "
            f"sinFADD={self.sine_fadd_mode}/"
            f"{'norm' if self.sine_normalize else 'raw'}/"
            f"{self.sine_action} "
            f"corrFADD={self.correction_fadd_mode}/"
            f"{'norm' if self.correction_normalize else 'raw'}/"
            f"{self.correction_action}"
        )


CURRENT = Candidate()
FIELDS = (
    ("fmul_output", OUTPUTS),
    ("cosine_tail_output", OUTPUTS),
    ("y_mode", Y_MODES),
    ("sine_fadd_mode", h206.MODES),
    ("sine_normalize", (False, True)),
    ("sine_action", ACTIONS),
    ("correction_fadd_mode", h206.MODES),
    ("correction_normalize", (False, True)),
    ("correction_action", ACTIONS),
)


def value_bus(value: h58.FP) -> h206.Bus:
    return h200.normalized_bus(value)


@functools.lru_cache(maxsize=None)
def producer(point, chain: str, shared: bool) -> h58.FP:
    if chain == "p":
        return h188.producer(point, h189.CANDIDATES[1])
    if shared:
        return h134.horner(
            h58.C6,
            point.square,
            h134.CURRENT.q_coefficients,
            h134.CURRENT.q_products,
            h134.CURRENT.q_sums,
        )
    return point.q_current


def multiply(
    x: h206.Bus,
    y: h206.Bus,
    candidate: Candidate,
    output: str | None = None,
) -> h206.Bus:
    return h206.fmul_x67_y64(
        x,
        y,
        y_mode=candidate.y_mode,
        output=output or candidate.fmul_output,
    )


@functools.lru_cache(maxsize=None)
def micro_state(point, shared: bool, candidate: Candidate):
    a = value_bus(point.joint.observed.point.a)
    square = value_bus(point.square)
    p = value_bus(producer(point, "p", shared))
    q = value_bus(producer(point, "q", shared))

    p_square = multiply(p, square, candidate)
    p_tail = multiply(a, p_square, candidate)
    sine, _ = h206.fadd(
        a,
        p_tail,
        candidate.sine_fadd_mode,
        normalize=candidate.sine_normalize,
    )
    sine = h206.materialize(sine, candidate.sine_action)

    cosine_tail = multiply(
        q,
        square,
        candidate,
        output=candidate.cosine_tail_output,
    )
    return sine, cosine_tail


@functools.lru_cache(maxsize=None)
def local_value(
    point,
    shared: bool,
    cosine_lane: bool,
    candidate: Candidate,
) -> h58.FP:
    prepared = point.joint.observed.point
    sine, cosine_tail = micro_state(point, shared, candidate)
    if cosine_lane:
        lead, cross = prepared.cos_t, prepared.sin_t
    else:
        lead, cross = prepared.sin_t, prepared.cos_t

    q_product = multiply(
        cosine_tail, value_bus(lead), candidate
    )
    p_product = multiply(sine, value_bus(cross), candidate)
    if cosine_lane:
        p_product = dataclasses.replace(
            p_product, sign=p_product.sign ^ 1
        )
    correction, _ = h206.fadd(
        q_product,
        p_product,
        candidate.correction_fadd_mode,
        normalize=candidate.correction_normalize,
    )
    correction = h206.materialize(
        correction, candidate.correction_action
    )
    return h58.add_exact(lead, correction.value())


def hidden_values(point, candidate: Candidate):
    sine = local_value(point, False, False, candidate)
    cosine = local_value(point, True, True, candidate)
    if point.joint.observed.point.raw.sign:
        sine = h58.neg(sine)
    return h60.rotate(
        (sine, cosine), point.joint.observed.signed_n
    )


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


def search(selected, baselines, width: int = 32, rounds: int = 5):
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
        h226.sample_dataset(name, points, controls=64)
        for name, points in complete
    ]
    baselines = score(selected, None)
    print(
        f"h231 P6 retained-sine carrier: selected="
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
    print(f"h231 complete survivors={len(finalists)}")
    for item in finalists[:20]:
        print(f"  {item[0]} {item[1]}")


if __name__ == "__main__":
    main()
