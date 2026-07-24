#!/usr/bin/env python3
"""Search standalone-FSIN table state parameters using value plus C1.

h131 rejects every 64..80-bit final-partial materialization in h104's
family.  This pass instead searches the inputs to that supported RN67
delta-correction combine:

* the narrow row-169 effective correction;
* a fine 1/256-ulp shared-S correction, including away-from-zero values;
* a fine 1/256-ulp correction to the shared (1+t) state.

The corrections are equivalent state probes, not proposed ROM edits.
Candidates are selected on constrained samples, then required to be no worse
on complete dense-direct and reduced-sweep train/heldout partitions.
"""

from __future__ import annotations

import dataclasses

import h58_constraint_search as h58
import h60_round16_parity as h60
import h79_table_state_bias as h79
import h97_narrow_coefficient_discriminator as h97
import h104_table_final_partial_search as h104
import h110_fsin_standalone as h110
import h131_fsin_table_c1_search as h131


@dataclasses.dataclass(frozen=True)
class Parameters:
    narrow_delta: int = 7168
    sine_bias_256: int = 0
    u_bias_256: int = 0

    def short(self) -> str:
        return (
            f"delta={self.narrow_delta:+d} "
            f"S={self.sine_bias_256:+d}/256 "
            f"U={self.u_bias_256:+d}/256"
        )


CURRENT = {
    "narrow": Parameters(sine_bias_256=32),
    "wide": Parameters(sine_bias_256=40),
}
VARIANT = h104.Variant("delta-correction", 67, "rn")


def hidden_value(
    observed: h131.Observed, parameters: Parameters
) -> h58.FP:
    point = observed.point
    altered = (
        point
        if point.wide
        else h97.alter_p(point, parameters.narrow_delta)
    )
    one_plus_tail, sine_a = h79.table_state(altered, h79.BASE)
    sine_a = h79.bias_toward_zero(
        sine_a, parameters.sine_bias_256, denominator_bits=8
    )
    one_plus_tail = h79.bias_toward_zero(
        one_plus_tail, parameters.u_bias_256, denominator_bits=8
    )

    quadrant = observed.signed_n & 3
    if quadrant & 1:
        value = h104.lane_value(
            altered.cos_t,
            altered.sin_t,
            one_plus_tail,
            sine_a,
            True,
            VARIANT,
        )
    else:
        value = h104.lane_value(
            altered.sin_t,
            altered.cos_t,
            one_plus_tail,
            sine_a,
            False,
            VARIANT,
        )
        if point.raw.sign:
            value = h58.neg(value)
    return h58.neg(value) if quadrant & 2 else value


def score(
    points: list[h131.Observed], parameters: Parameters
) -> tuple[int, int, int]:
    mode_misses = 0
    input_misses = 0
    c1_misses = 0
    for point in points:
        hidden = hidden_value(point, parameters)
        missed_input = False
        for index, rc in enumerate(h58.RCS):
            predicted = h58.x87_round(hidden, rc)
            expected = point.outputs[index]
            mismatch = predicted != expected
            mode_misses += mismatch
            missed_input |= mismatch
            if not mismatch:
                predicted_c1 = (
                    h110.compare_magnitude(expected, hidden) > 0
                )
                c1_misses += predicted_c1 != point.c1[index]
        input_misses += missed_input
    return mode_misses, input_misses, c1_misses


def parameter_axes(
    family: str, current: Parameters
) -> tuple[tuple[str, tuple[Parameters, ...]], ...]:
    result = []
    if family == "narrow":
        deltas = set(range(-32768, 32769, 256))
        deltas.add(current.narrow_delta)
        result.append(
            (
                "row-169 delta",
                tuple(
                    dataclasses.replace(current, narrow_delta=value)
                    for value in sorted(deltas)
                ),
            )
        )
    result.extend(
        (
            (
                "shared S /256",
                tuple(
                    dataclasses.replace(current, sine_bias_256=value)
                    for value in range(-64, 129)
                ),
            ),
            (
                "shared U /256",
                tuple(
                    dataclasses.replace(current, u_bias_256=value)
                    for value in range(-64, 65)
                ),
            ),
        )
    )
    return tuple(result)


def search_family(
    family: str,
    dense: list[h131.Observed],
    sweep: list[h131.Observed],
) -> None:
    partitions = []
    for name, dataset in (("dense", dense), ("sweep", sweep)):
        selected = [point for point in dataset if point.family == family]
        partitions.extend(
            (
                (f"{name}-train", [p for p in selected if h131.is_train(p)]),
                (
                    f"{name}-held",
                    [p for p in selected if not h131.is_train(p)],
                ),
            )
        )
    samples = [
        (name, h131.sample(points, 1500))
        for name, points in partitions
    ]
    current = CURRENT[family]
    baseline = [score(points, current) for _, points in partitions]
    print(f"\n{family}: current {current.short()}")
    for (name, points), result in zip(partitions, baseline):
        print(
            f"  {name:11s} "
            f"{h131.describe(result, len(points))}"
        )

    for axis, candidates in parameter_axes(family, current):
        ranked = []
        for candidate in candidates:
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
        validated = []
        for _, _, _, _, candidate in ranked[:20]:
            results = [
                score(points, candidate) for _, points in partitions
            ]
            if all(
                result <= base
                for result, base in zip(results, baseline)
            ):
                validated.append((candidate, results))
        print(f"  {axis}:")
        if not validated:
            print("    no top-20 candidate transfers to all partitions")
            continue
        for candidate, results in validated[:8]:
            marker = " *" if any(
                result < base
                for result, base in zip(results, baseline)
            ) else ""
            print(f"    {candidate.short()}{marker}")
            for (name, points), result in zip(partitions, results):
                print(
                    f"      {name:11s} "
                    f"{h131.describe(result, len(points))}"
                )


def main() -> None:
    dense = h131.load_dataset("dense", h131.INPUTS / "dense_qn.txt")
    sweep = h131.load_dataset("sweep", h131.INPUTS / "sweep_inputs.txt")
    print(
        f"loaded {len(dense)} direct and {len(sweep)} sweep table inputs"
    )
    for family in ("narrow", "wide"):
        search_family(family, dense, sweep)


if __name__ == "__main__":
    main()
