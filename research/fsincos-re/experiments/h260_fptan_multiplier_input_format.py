#!/usr/bin/env python3
"""Test a shared multiplier with source-class input materialization.

h258 established that F2XM1 ordinary FMUL is exactly described by a
magnitude-chopped 67-bit product on all available captures.  Applying that
same result rule to FPTAN leaves more misses than the earlier abstract
``away67`` proxy.  The important operand difference is that FPTAN's complete
sine state is a 69-bit retained carrier, while its table constants are 67
bits and its cosine tail is 64 bits.

This pass keeps the shared FMUL result rule fixed at ``chop67`` and varies
only a uniform read/materialization action for each operand source class.
There are deliberately no per-edge choices: both uses of the sine state,
both uses of the cosine tail, and all table values share their respective
action.
"""

from __future__ import annotations

import dataclasses

import h58_constraint_search as h58
import h110_fsin_standalone as h110
import h228_p6_four_term_c_parity as h228
import h230_p6_microop_materialization_search as h230
import h245_fptan_shared_state as h245
import h246_fptan_operation_search as h246


ACTIONS = ("exact",) + tuple(
    f"{mode}{bits}"
    for bits in range(64, 73)
    for mode in ("rn", "chop", "away", "odd")
)
SHARED_RESULT = h246.Candidate("chop67", "chop67")
EMPIRICAL_RESULT = h246.Candidate("away67", "chop67")
LEGACY_STATE = dataclasses.replace(
    h228.CANDIDATE,
    p_horner_product="rn64",
    q_horner_product="rn64",
    p_square="away67",
    p_times_a="chop65",
)


@dataclasses.dataclass(frozen=True)
class Candidate:
    sine_input: str = "exact"
    tail_input: str = "exact"
    table_input: str = "exact"

    def short(self) -> str:
        return (
            f"sine={self.sine_input} tail={self.tail_input} "
            f"table={self.table_input}"
        )


def quantize(value: h58.FP, action: str) -> h58.FP:
    if action == "exact":
        return value
    mode = action[:-2]
    bits = int(action[-2:])
    return h110.quantize(value, h110.Quant(bits, mode))


def values(
    point,
    candidate: Candidate,
    state_candidate: h230.Candidate = LEGACY_STATE,
):
    prepared = point.prepared.joint.observed.point
    sine_a, cosine_tail = h230.state(point, state_candidate)
    sine_a = quantize(sine_a, candidate.sine_input)
    cosine_tail = quantize(cosine_tail, candidate.tail_input)
    sin_t = quantize(prepared.sin_t, candidate.table_input)
    cos_t = quantize(prepared.cos_t, candidate.table_input)
    negative_sine = h58.neg(sine_a)
    negative_table_sine = h58.neg(sin_t)

    denominator_partial = h246.sub(
        h246.mul(negative_table_sine, negative_sine, SHARED_RESULT),
        h246.mul(cos_t, cosine_tail, SHARED_RESULT),
        SHARED_RESULT,
    )
    denominator = h246.sub(
        cos_t, denominator_partial, SHARED_RESULT
    )

    numerator_partial = h246.sub(
        h246.mul(cos_t, negative_sine, SHARED_RESULT),
        h246.mul(sin_t, cosine_tail, SHARED_RESULT),
        SHARED_RESULT,
    )
    numerator = h246.sub(
        sin_t, numerator_partial, SHARED_RESULT
    )

    if prepared.raw.sign:
        numerator = h58.neg(numerator)
    return h230.h60.rotate(
        (numerator, denominator), point.prepared.joint.observed.signed_n
    )


def metric(
    point,
    hardware,
    candidate: Candidate,
    state_candidate: h230.Candidate = LEGACY_STATE,
) -> tuple[int, int, int]:
    numerator, denominator = values(point, candidate, state_candidate)
    mode_misses = 0
    c1_misses = 0
    for rc in h58.RCS:
        predicted, increment = h245.round_div(numerator, denominator, rc)
        expected, sw = hardware[rc][point.prepared.joint.observed.index]
        if expected is None:
            raise AssertionError("table FPTAN returned C2")
        mode_misses += predicted != expected
        if predicted == expected:
            c1_misses += increment != bool(sw & 0x0200)
    return mode_misses, bool(mode_misses), c1_misses


def score(
    points,
    hardware,
    candidate: Candidate,
    state_candidate: h230.Candidate = LEGACY_STATE,
):
    result = (0, 0, 0)
    for point in points:
        result = h246.add(
            result,
            metric(point, hardware, candidate, state_candidate),
        )
    return result


def objective(results):
    return tuple(sum(value[i] for value in results) for i in (0, 2, 1))


def widths(points):
    result = {name: set() for name in ("sine", "tail", "table")}
    for point in points:
        prepared = point.prepared.joint.observed.point
        sine, tail = h230.state(point, h228.CANDIDATE)
        result["sine"].add(sine[1].bit_length())
        result["tail"].add(tail[1].bit_length())
        result["table"].update(
            (prepared.sin_t[1].bit_length(), prepared.cos_t[1].bit_length())
        )
    return {name: sorted(value) for name, value in result.items()}


def main() -> None:
    datasets = []
    for name in ("dense", "sweep"):
        hardware = h245.captures(name)
        points = h228.points(name)
        selected = h246.sample(points, hardware, 2400)
        datasets.append((name, points, selected, hardware))
    print(
        "operand significant widths:",
        widths([point for _, points, _, _ in datasets for point in points]),
    )

    baseline = Candidate()
    baseline_results = tuple(
        score(points, hardware, baseline)
        for _, points, _, hardware in datasets
    )
    empirical_results = tuple(
        h246.score(points, hardware, EMPIRICAL_RESULT)
        for _, points, _, hardware in datasets
    )
    print("complete shared-result baseline:", objective(baseline_results), baseline_results)
    print("complete abstract away67 proxy:", objective(empirical_results), empirical_results)

    # Coordinate ranking first identifies which source class is observable.
    candidates = {baseline}
    for field in ("sine_input", "tail_input", "table_input"):
        for action in ACTIONS:
            candidates.add(dataclasses.replace(baseline, **{field: action}))
    ranked = []
    for candidate in candidates:
        results = tuple(
            score(selected, hardware, candidate)
            for _, _, selected, hardware in datasets
        )
        ranked.append((objective(results), candidate.short(), candidate, results))
    ranked.sort()
    print("selected coordinate leaders:")
    for item in ranked[:16]:
        print(f"  {item[0]} {item[1]} {item[3]}")

    # Cross the observable sine-input leaders with every source action.  The
    # tail/table dimensions should be inert at or above their native widths,
    # but retaining them here checks lower-width port hypotheses as well.
    sine_actions = []
    for _, _, candidate, _ in ranked:
        if candidate.tail_input == candidate.table_input == "exact":
            if candidate.sine_input not in sine_actions:
                sine_actions.append(candidate.sine_input)
        if len(sine_actions) == 8:
            break
    crossed = []
    # A quantizer at or above the operand's existing width is an identity.
    # The tail is already 64 bits, while only 64..66 can alter a 67-bit
    # table value.  Collapse those provably duplicate actions before crossing.
    tail_actions = ("exact",)
    table_actions = ("exact",) + tuple(
        action for action in ACTIONS
        if action != "exact" and int(action[-2:]) < 67
    )
    for sine_action in sine_actions:
        for tail_action in tail_actions:
            for table_action in table_actions:
                candidate = Candidate(sine_action, tail_action, table_action)
                results = tuple(
                    score(selected, hardware, candidate)
                    for _, _, selected, hardware in datasets
                )
                crossed.append(
                    (objective(results), candidate.short(), candidate, results)
                )
    crossed.sort()
    print("selected crossed leaders:")
    for item in crossed[:16]:
        print(f"  {item[0]} {item[1]} {item[3]}")

    complete = []
    for _, _, candidate, _ in crossed[:12]:
        results = tuple(
            score(points, hardware, candidate)
            for _, points, _, hardware in datasets
        )
        complete.append((objective(results), candidate.short(), results))
    print("complete crossed leaders:")
    for item in sorted(complete):
        print(f"  {item}")


if __name__ == "__main__":
    main()
