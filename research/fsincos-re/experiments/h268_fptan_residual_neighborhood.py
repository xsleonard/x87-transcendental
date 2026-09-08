#!/usr/bin/env python3
"""Map h260 FPTAN residuals in dense neighborhoods around both seeds.

The h260 graph misses two inputs in the earlier 108k table corpus.  h267
captures adjacent x87 significands and logarithmically spaced controls around
those operands.  This pass reconstructs every point, identifies complete
RN/RD/RU failures, and records the low-bit state at all numerator and
denominator products/subtractions.  It also tests the already-observed
one-retained-unit numerator correction without adopting it as a model rule.
"""

from __future__ import annotations

import collections
import dataclasses
import pathlib

import h58_constraint_search as h58
import h80_round21_parity as h80
import h110_fsin_standalone as h110
import h131_fsin_table_c1_search as h131
import h182_table_joint_terminal_edges as h182
import h188_table_stage_local_pairs as h188
import h207_tang_literal_fadd as h207
import h230_p6_microop_materialization_search as h230
import h245_fptan_shared_state as h245
import h260_fptan_multiplier_input_format as h260
import h267_fptan_residual_inputs as h267


ROOT = pathlib.Path(__file__).resolve().parents[1]
CAPTURE = ROOT / "capture-kit-captures" / "skylake-fptan-h267"
INPUTS = CAPTURE / "fptan_residual_h267.txt"
CANDIDATE = h260.Candidate("rn64", "exact", "exact")
ZERO_OUTPUTS = ((0, 0),) * 3
ZERO_C1 = (False,) * 3


@dataclasses.dataclass(frozen=True)
class Trace:
    sine_before_read: h58.FP
    sine: h58.FP
    denominator_sine_product_exact: h58.FP
    denominator_sine_product: h58.FP
    denominator_tail_product_exact: h58.FP
    denominator_tail_product: h58.FP
    denominator_partial_exact: h58.FP
    denominator_partial: h58.FP
    denominator_final_exact: h58.FP
    denominator: h58.FP
    numerator_sine_product_exact: h58.FP
    numerator_sine_product: h58.FP
    numerator_tail_product_exact: h58.FP
    numerator_tail_product: h58.FP
    numerator_partial_exact: h58.FP
    numerator_partial: h58.FP
    numerator_final_exact: h58.FP
    numerator: h58.FP


def points(
    input_path: pathlib.Path = INPUTS,
) -> tuple[list[h207.Point], list[tuple[int, int]]]:
    operands = [
        tuple(int(field, 16) for field in line.split())
        for line in input_path.read_text().splitlines()
    ]
    result = []
    for index, (se, sig) in enumerate(operands):
        active = h80.active_table_input(se, sig)
        if active is None:
            raise AssertionError(f"inactive h267 input {index}: {se:04x} {sig:016x}")
        signed_n, prepared, reduced = active
        observed = h131.Observed(
            index,
            "reduced" if reduced else "direct",
            signed_n,
            prepared,
            ZERO_OUTPUTS,
            ZERO_C1,
        )
        joint = h182.Point(observed, ZERO_OUTPUTS, ZERO_C1)
        result.append(h207.Point(h188.prepare(joint), True))
    return result, operands


def captures() -> dict[str, list[tuple[tuple[int, int] | None, int]]]:
    return {
        rc: [
            h245.parse(line)
            for line in (CAPTURE / f"fptan_{rc}_status.txt")
            .read_text()
            .splitlines()
        ]
        for rc in h58.RCS
    }


def product(left: h58.FP, right: h58.FP) -> tuple[h58.FP, h58.FP]:
    exact = h58.mul_exact(left, right)
    return exact, h110.quantize(exact, h110.Quant(67, "chop"))


def subtract(left: h58.FP, right: h58.FP) -> tuple[h58.FP, h58.FP]:
    exact = h58.add_exact(left, h58.neg(right))
    return exact, h110.quantize(exact, h110.Quant(67, "chop"))


def trace(point: h207.Point) -> Trace:
    prepared = point.prepared.joint.observed.point
    sine_before_read, cosine_tail = h230.state(
        point, h260.LEGACY_STATE
    )
    sine = h260.quantize(sine_before_read, "rn64")
    negative_sine = h58.neg(sine)
    negative_table_sine = h58.neg(prepared.sin_t)

    dsp_exact, dsp = product(negative_table_sine, negative_sine)
    dtp_exact, dtp = product(prepared.cos_t, cosine_tail)
    dp_exact, dp = subtract(dsp, dtp)
    df_exact, denominator = subtract(prepared.cos_t, dp)

    nsp_exact, nsp = product(prepared.cos_t, negative_sine)
    ntp_exact, ntp = product(prepared.sin_t, cosine_tail)
    np_exact, np = subtract(nsp, ntp)
    nf_exact, numerator = subtract(prepared.sin_t, np)
    return Trace(
        sine_before_read,
        sine,
        dsp_exact,
        dsp,
        dtp_exact,
        dtp,
        dp_exact,
        dp,
        df_exact,
        denominator,
        nsp_exact,
        nsp,
        ntp_exact,
        ntp,
        np_exact,
        np,
        nf_exact,
        numerator,
    )


def discarded(exact: h58.FP, rounded: h58.FP) -> tuple[int, int, int]:
    """Return quantizer shift, discarded integer, and retained low byte."""
    shift = max(0, exact[1].bit_length() - 67)
    remainder = exact[1] & ((1 << shift) - 1) if shift else 0
    return shift, remainder, rounded[1] & 0xFF


def increment_magnitude(value: h58.FP) -> h58.FP:
    return value[0], value[1] + 1, value[2]


def rotated_values(point: h207.Point, item: Trace, corrected: bool = False):
    observed = point.prepared.joint.observed
    numerator = item.numerator
    if observed.point.raw.sign:
        numerator = h58.neg(numerator)
    numerator, denominator = h230.h60.rotate(
        (numerator, item.denominator), observed.signed_n
    )
    if corrected:
        numerator = increment_magnitude(numerator)
    return numerator, denominator


def metric(point: h207.Point, item: Trace, hardware, corrected: bool = False):
    numerator, denominator = rotated_values(point, item, corrected)
    result_misses = 0
    c1_misses = 0
    for rc in h58.RCS:
        predicted, increment = h245.round_div(numerator, denominator, rc)
        expected, sw = hardware[rc][point.prepared.joint.observed.index]
        if expected is None:
            raise AssertionError("h267 table input returned C2")
        result_misses += predicted != expected
        if predicted == expected:
            c1_misses += increment != bool(sw & 0x0200)
    return result_misses, c1_misses


def seed_delta(operand: tuple[int, int]) -> tuple[int, int]:
    se, sig = operand
    choices = [
        (index, sig - seed_sig)
        for index, (seed_se, seed_sig) in enumerate(h267.SEEDS)
        if se == seed_se
    ]
    if not choices:
        raise AssertionError(operand)
    return min(choices, key=lambda item: abs(item[1]))


def remainder_summary(item: Trace) -> str:
    fields = (
        ("nsp", item.numerator_sine_product_exact, item.numerator_sine_product),
        ("ntp", item.numerator_tail_product_exact, item.numerator_tail_product),
        ("np", item.numerator_partial_exact, item.numerator_partial),
        ("nf", item.numerator_final_exact, item.numerator),
        ("dsp", item.denominator_sine_product_exact, item.denominator_sine_product),
        ("dtp", item.denominator_tail_product_exact, item.denominator_tail_product),
        ("dp", item.denominator_partial_exact, item.denominator_partial),
        ("df", item.denominator_final_exact, item.denominator),
    )
    values = []
    for name, exact, rounded in fields:
        shift, remainder, low = discarded(exact, rounded)
        values.append(f"{name}=s{shift}:r{remainder:x}:l{low:02x}")
    return " ".join(values)


def runs(values: list[int]) -> list[tuple[int, int]]:
    if not values:
        return []
    result = []
    start = previous = values[0]
    for value in values[1:]:
        if value != previous + 1:
            result.append((start, previous))
            start = value
        previous = value
    result.append((start, previous))
    return result


def main() -> None:
    selected, operands = points()
    hardware = captures()
    if any(len(values) != len(selected) for values in hardware.values()):
        raise SystemExit("h267 input/capture line counts differ")

    misses = []
    corrected_misses = []
    distributions = collections.Counter()
    dense_deltas = {0: [], 1: []}
    for point, operand in zip(selected, operands):
        item = trace(point)
        result_misses, c1_misses = metric(point, item, hardware)
        corrected_result, corrected_c1 = metric(point, item, hardware, True)
        distributions[(result_misses, c1_misses)] += 1
        seed, delta = seed_delta(operand)
        if abs(delta) <= 4096 and result_misses:
            dense_deltas[seed].append(delta)
        if result_misses or c1_misses:
            misses.append(
                (point, operand, seed, delta, item, result_misses, c1_misses)
            )
        if corrected_result or corrected_c1:
            corrected_misses.append((operand, corrected_result, corrected_c1))

    print(f"points={len(selected)} baseline-distribution={dict(sorted(distributions.items()))}")
    print(f"baseline wrong inputs={len(misses)}")
    for seed in range(len(h267.SEEDS)):
        values = sorted(set(dense_deltas[seed]))
        print(f"seed {seed} dense miss deltas={values}")
        print(f"seed {seed} dense miss runs={runs(values)}")
    for point, operand, seed, delta, item, result_misses, c1_misses in misses:
        observed = point.prepared.joint.observed
        print(
            f"miss index={observed.index} input={operand[0]:04x}:{operand[1]:016x} "
            f"seed={seed} delta={delta:+d} source={observed.source} "
            f"cell={observed.point.cell} n={observed.signed_n} "
            f"result={result_misses} C1={c1_misses} "
            f"sine-low={item.sine[1] & 0xff:02x} "
            f"num={item.numerator[0]}:{item.numerator[1]:x}:2^{item.numerator[2]} "
            f"den={item.denominator[0]}:{item.denominator[1]:x}:2^{item.denominator[2]}"
        )
        print(f"  {remainder_summary(item)}")
    print(
        f"uniform +1 post-rotation numerator correction wrong inputs={len(corrected_misses)} "
        f"(expected to reject a global correction)"
    )
    if corrected_misses:
        print(f"  first corrected failures={corrected_misses[:8]}")


if __name__ == "__main__":
    main()
