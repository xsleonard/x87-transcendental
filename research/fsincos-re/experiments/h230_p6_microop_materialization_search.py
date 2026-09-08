#!/usr/bin/env python3
"""Search materializations on the fixed table arithmetic graph.

h227 established that the P6 four-term table kernel and adjusted C9
coefficient are a large improvement over the empirical six-term proxy.  It
still inherited every polynomial/state materialization from that proxy.  The
model uses the following bounded search space:

    square = FMUL(a, a)
    P, Q = three alternating FMUL/FADD Horner edges
    sine = FADD(a, FMUL(FMUL(square, P), a))
    cosine_tail = residual_scale(square, Q)

This pass varies only the materialization after those named operations.  The
same action is used for all three edges in one Horner chain; per-edge search
is deferred until a uniform operation family survives complete and fresh
captures.  ``exact`` is included as a useful retained-carrier bound, not as a
claim that the physical register is unbounded.
"""

from __future__ import annotations

import argparse
import dataclasses
import functools

import h58_constraint_search as h58
import h60_round16_parity as h60
import h79_table_state_bias as h79
import h110_fsin_standalone as h110
import h218_fadd_residual_programs as h218
import h226_p6_full_sine_graph as h226
import h227_p6_four_term_kernel as h227


QUANTS = {
    "exact": h110.EXACT,
    **{
        f"{mode}{bits}": h110.Quant(bits, mode)
        for bits in range(64, 73)
        for mode in ("rn", "chop", "away", "odd")
    },
}
ACTIONS = tuple(QUANTS)
BIAS_ACTIONS = tuple(range(0, 9))


@dataclasses.dataclass(frozen=True)
class Candidate:
    square: str = "rn64"
    p_horner_product: str = "rn64"
    p_horner_sum: str = "rn64"
    q_horner_product: str = "rn64"
    q_horner_sum: str = "rn64"
    p_square: str = "rn64"
    p_times_a: str = "rn64"
    sine_add: str = "rn64"
    q_tail: str = "rn64"
    sine_bias: int = 5

    def short(self) -> str:
        return (
            f"sq={self.square} "
            f"P={self.p_horner_product}/{self.p_horner_sum} "
            f"Q={self.q_horner_product}/{self.q_horner_sum} "
            f"sin={self.p_square}/{self.p_times_a}/{self.sine_add} "
            f"qtail={self.q_tail} bias={self.sine_bias}"
        )


CURRENT = Candidate()
START = dataclasses.replace(
    CURRENT,
    square="chop67",
    p_square="away67",
    p_times_a="chop65",
)
FINAL = h226.Candidate(
    sine_state="exact",
    cosine_state="away67",
    lead_constant="exact",
    cross_constant="exact",
    q_product="odd67",
    p_product="chop67",
    correction="away67",
)
FIELDS = (
    "square",
    "p_horner_product",
    "p_horner_sum",
    "q_horner_product",
    "q_horner_sum",
    "p_square",
    "p_times_a",
    "sine_add",
    "q_tail",
)


def quantize(value: h58.FP, action: str) -> h58.FP:
    return h110.quantize(value, QUANTS[action])


def horner(
    rows: tuple[int, ...],
    square: h58.FP,
    coefficient_quants: tuple[h110.Quant, ...],
    product_action: str,
    sum_action: str,
) -> h58.FP:
    value = h227.coefficient(rows[0], coefficient_quants[0], True)
    for index, row in enumerate(rows[1:]):
        value = quantize(
            h58.mul_exact(value, square), product_action
        )
        value = quantize(
            h58.add_exact(
                value,
                h227.coefficient(
                    row, coefficient_quants[index + 1], True
                ),
            ),
            sum_action,
        )
    return value


@functools.lru_cache(maxsize=None)
def state(point, candidate: Candidate):
    observed = point.prepared.joint.observed
    base = point.prepared.base
    a = observed.point.a
    square = quantize(h58.mul_exact(a, a), candidate.square)
    p = horner(
        h58.S4,
        square,
        base.p_coefficients,
        candidate.p_horner_product,
        candidate.p_horner_sum,
    )
    q = horner(
        h58.C4,
        square,
        base.q_coefficients,
        candidate.q_horner_product,
        candidate.q_horner_sum,
    )
    p_square = quantize(
        h58.mul_exact(p, square), candidate.p_square
    )
    p_times_a = quantize(
        h58.mul_exact(p_square, a), candidate.p_times_a
    )
    sine = quantize(
        h58.add_exact(a, p_times_a), candidate.sine_add
    )
    sine = h79.bias_toward_zero(
        sine,
        candidate.sine_bias if observed.family == "wide" else 4,
    )
    q_tail = quantize(h58.mul_exact(square, q), candidate.q_tail)
    return sine, q_tail


def local_value(point, candidate: Candidate, cosine_lane: bool):
    prepared = point.prepared.joint.observed.point
    sine, q_tail = state(point, candidate)
    if cosine_lane:
        lead, cross = prepared.cos_t, prepared.sin_t
    else:
        lead, cross = prepared.sin_t, prepared.cos_t
    q_product = h226.quantize(
        h58.mul_exact(
            h226.quantize(lead, FINAL.lead_constant), q_tail
        ),
        FINAL.q_product,
    )
    p_product = h226.quantize(
        h58.mul_exact(
            h226.quantize(cross, FINAL.cross_constant), sine
        ),
        FINAL.p_product,
    )
    if cosine_lane:
        p_product = h58.neg(p_product)
    correction = h226.quantize(
        h58.add_exact(q_product, p_product), FINAL.correction
    )
    return h58.add_exact(lead, correction)


def hidden_values(point, candidate: Candidate):
    sine = local_value(point, candidate, False)
    cosine = local_value(point, candidate, True)
    if point.prepared.joint.observed.point.raw.sign:
        sine = h58.neg(sine)
    return h60.rotate(
        (sine, cosine), point.prepared.joint.observed.signed_n
    )


def score(datasets, candidate: Candidate):
    totals = []
    for _, points in datasets:
        total = h226.ZERO_JOINT
        for point in points:
            total = h226.add_metric(
                total,
                h226.metric_for(point, hidden_values(point, candidate)),
            )
        totals.append(total)
    return tuple(totals)


def expand(beam):
    result = set(beam)
    for candidate in beam:
        for field in FIELDS:
            for action in ACTIONS:
                result.add(dataclasses.replace(
                    candidate, **{field: action}
                ))
        for bias in BIAS_ACTIONS:
            result.add(dataclasses.replace(candidate, sine_bias=bias))
    return result


def search(datasets, width: int, rounds: int):
    selected = [
        h226.sample_dataset(name, points) for name, points in datasets
    ]
    baselines = h226.score(selected, None)
    beam = [START]
    seen = set()
    for round_index in range(1, rounds + 1):
        ranked = []
        for candidate in expand(beam):
            if candidate in seen:
                continue
            seen.add(candidate)
            values = score(selected, candidate)
            ranked.append((
                h226.regressions(values, baselines),
                h226.objective(values),
                candidate.short(),
                candidate,
            ))
        ranked.sort()
        beam = [item[3] for item in ranked[:width]]
        print(
            f"round {round_index}: new={len(ranked)} seen={len(seen)} "
            f"best={ranked[0][:3]}",
            flush=True,
        )
    return beam


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--width", type=int, default=20)
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--full", type=int, default=12)
    args = parser.parse_args()
    datasets = h218.datasets()
    baselines = h226.score(datasets, None)
    seed = score(datasets, START)
    print(
        f"h230 P6 micro-op search: points="
        f"{sum(len(points) for _, points in datasets)}"
    )
    print(
        f"seed objective={h226.objective(seed)} "
        f"regressions={h226.regressions(seed, baselines)} "
        f"{START.short()}"
    )
    beam = search(datasets, args.width, args.rounds)
    full = []
    for candidate in beam[:args.full]:
        values = score(datasets, candidate)
        full.append((
            h226.regressions(values, baselines),
            h226.objective(values),
            candidate.short(),
            candidate,
        ))
    full.sort()
    print("complete-corpus finalists:")
    for item in full:
        print(f"  {item[:3]}")


if __name__ == "__main__":
    main()
