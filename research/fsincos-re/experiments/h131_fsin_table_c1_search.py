#!/usr/bin/env python3
"""Use standalone FSIN status to search the table-combine hidden value.

Earlier table reconstruction fitted paired FSINCOS values.  Standalone FSIN
adds two independent constraints: directed RN/RD/RU outputs and C1, sampled
after FSIN itself.  This pass projects h104's complete final-partial family
through range-reduction quadrants and scores only the architectural sine
result.

Candidate selection uses constrained points plus deterministic controls.
Any reported survivor must then be no worse on all four complete partitions:
dense-direct train/heldout and full-sweep train/heldout.  Narrow and wide
table families are searched separately.
"""

from __future__ import annotations

import dataclasses
import functools
import pathlib

import h58_constraint_search as h58
import h60_round16_parity as h60
import h80_round21_parity as h80
import h104_table_final_partial_search as h104
import h110_fsin_standalone as h110


ROOT = pathlib.Path(__file__).resolve().parents[1]
INPUTS = ROOT / "capture-kit" / "inputs"
CAPTURE = ROOT / "capture-kit-captures" / "skylake-fsin-h110"
CURRENT = h104.Variant("delta-correction", 67, "rn")


@dataclasses.dataclass(frozen=True)
class Observed:
    index: int
    source: str
    signed_n: int
    point: h58.PreparedPoint
    outputs: tuple[tuple[int, int], ...]
    c1: tuple[bool, ...]

    @property
    def family(self) -> str:
        return "wide" if self.point.wide else "narrow"


def load_dataset(name: str, input_path: pathlib.Path) -> list[Observed]:
    operands = [
        tuple(int(field, 16) for field in line.split())
        for line in input_path.read_text().splitlines()
    ]
    modes = [
        (CAPTURE / f"{name}_fsin_{rc}_status.txt")
        .read_text()
        .splitlines()
        for rc in h58.RCS
    ]
    if any(len(lines) != len(operands) for lines in modes):
        raise SystemExit(f"{name} input/capture line counts differ")
    result = []
    for index, (se, sig) in enumerate(operands):
        active = h80.active_table_input(se, sig)
        if active is None:
            continue
        signed_n, point, reduced = active
        outputs = []
        c1 = []
        for lines in modes:
            fields = lines[index].split()
            if (
                len(fields) != 5
                or fields[0] != "OK"
                or fields[3] != "SW"
            ):
                raise ValueError(lines[index])
            outputs.append((int(fields[1], 16), int(fields[2], 16)))
            c1.append(bool(int(fields[4], 16) & 0x0200))
        result.append(
            Observed(
                index,
                "reduced" if reduced else "direct",
                signed_n,
                point,
                tuple(outputs),
                tuple(c1),
            )
        )
    return result


@functools.lru_cache(maxsize=None)
def table_state(
    point: h58.PreparedPoint,
) -> tuple[h58.PreparedPoint, h58.FP, h58.FP]:
    return h104.state(point)


def hidden_value(point: Observed, variant: h104.Variant) -> h58.FP:
    altered, one_plus_tail, sine_a = table_state(point.point)
    quadrant = point.signed_n & 3
    if quadrant & 1:
        value = h104.lane_value(
            altered.cos_t,
            altered.sin_t,
            one_plus_tail,
            sine_a,
            True,
            variant,
        )
    else:
        value = h104.lane_value(
            altered.sin_t,
            altered.cos_t,
            one_plus_tail,
            sine_a,
            False,
            variant,
        )
        if point.point.raw.sign:
            value = h58.neg(value)
    return h58.neg(value) if quadrant & 2 else value


def point_score(
    point: Observed, variant: h104.Variant
) -> tuple[int, int]:
    hidden = hidden_value(point, variant)
    output_misses = 0
    c1_misses = 0
    for index, rc in enumerate(h58.RCS):
        predicted = h58.x87_round(hidden, rc)
        expected = point.outputs[index]
        if predicted != expected:
            output_misses += 1
        else:
            predicted_c1 = h110.compare_magnitude(expected, hidden) > 0
            c1_misses += predicted_c1 != point.c1[index]
    return output_misses, c1_misses


def score(
    points: list[Observed], variant: h104.Variant
) -> tuple[int, int, int]:
    mode_misses = 0
    c1_misses = 0
    input_misses = 0
    for point in points:
        mode, c1 = point_score(point, variant)
        mode_misses += mode
        c1_misses += c1
        input_misses += bool(mode)
    return mode_misses, input_misses, c1_misses


def is_train(point: Observed) -> bool:
    raw = point.point.raw
    return not (
        (
            raw.sig
            ^ (raw.sig >> 17)
            ^ (raw.sig >> 41)
            ^ point.index
            ^ point.signed_n
        )
        & 1
    )


def sample(points: list[Observed], controls: int) -> list[Observed]:
    constrained = [
        point
        for point in points
        if point_score(point, CURRENT) != (0, 0)
    ]
    exact = [
        point
        for point in points
        if point_score(point, CURRENT) == (0, 0)
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


def describe(result: tuple[int, int, int], total: int) -> str:
    return (
        f"mode={result[0]}/{3 * total} "
        f"input={result[1]}/{total} C1={result[2]}/{3 * total}"
    )


def search_family(
    family: str,
    dense: list[Observed],
    sweep: list[Observed],
) -> None:
    partitions = []
    for name, dataset in (("dense", dense), ("sweep", sweep)):
        selected = [point for point in dataset if point.family == family]
        partitions.extend(
            (
                (f"{name}-train", [p for p in selected if is_train(p)]),
                (f"{name}-held", [p for p in selected if not is_train(p)]),
            )
        )
    samples = [
        (name, sample(points, 1500))
        for name, points in partitions
    ]
    print(f"\n{family}:")
    for (name, points), (_, chosen) in zip(partitions, samples):
        print(
            f"  {name:11s} {len(points):6d} complete, "
            f"{len(chosen):5d} search; "
            f"{describe(score(points, CURRENT), len(points))}"
        )

    ranked = []
    for variant in h104.variants():
        results = [score(points, variant) for _, points in samples]
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

    baseline = [score(points, CURRENT) for _, points in partitions]
    validated = []
    for _, _, _, _, variant in ranked[:24]:
        results = [score(points, variant) for _, points in partitions]
        if all(result <= base for result, base in zip(results, baseline)):
            validated.append((variant, results))
    if not validated:
        print("  no top-24 search candidate is no-worse on every partition")
        return
    for variant, results in validated[:12]:
        marker = " *" if any(
            result < base for result, base in zip(results, baseline)
        ) else ""
        print(f"  {variant.short():28s}{marker}")
        for (name, points), result in zip(partitions, results):
            print(
                f"    {name:11s} "
                f"{describe(result, len(points))}"
            )


def main() -> None:
    dense = load_dataset("dense", INPUTS / "dense_qn.txt")
    sweep = load_dataset("sweep", INPUTS / "sweep_inputs.txt")
    print(
        f"loaded {len(dense)} direct and {len(sweep)} sweep table inputs; "
        f"{len(h104.variants())} final-partial variants"
    )
    for family in ("narrow", "wide"):
        search_family(family, dense, sweep)


if __name__ == "__main__":
    main()
