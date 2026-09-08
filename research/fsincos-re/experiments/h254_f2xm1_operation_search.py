#!/usr/bin/env python3
"""Constrain F2XM1 table-path arithmetic by shared operation class.

Every ordinary FMUL shares one materialization, every FADD shares another,
and the multiply-class residual scaling has one independent materialization.
No site-local parameters are searched.
"""

from __future__ import annotations

import dataclasses

import h58_constraint_search as h58
import h110_fsin_standalone as h110
import h251_f2xm1_exact_baseline as h251
import h252_f2xm1_literal_graph as h252


ACTIONS = ("exact",) + tuple(
    f"{mode}{bits}"
    for bits in range(64, 69)
    for mode in ("rn", "chop", "away", "odd")
)


@dataclasses.dataclass(frozen=True)
class Candidate:
    ordinary_mul: str = "exact"
    ordinary_add: str = "exact"
    scale_mul: str = "exact"

    def short(self) -> str:
        return (
            f"FMUL={self.ordinary_mul} FADD={self.ordinary_add} "
            f"MUL769={self.scale_mul}"
        )


@dataclasses.dataclass(frozen=True)
class Point:
    dataset: str
    index: int
    se: int
    sig: int
    hardware: tuple[tuple[int, int], ...]


def quantize(value: h58.FP, action: str) -> h58.FP:
    if action == "exact":
        return value
    return h110.quantize(value, h110.Quant(int(action[-2:]), action[:-2]))


def mul(left: h58.FP, right: h58.FP, action: str) -> h58.FP:
    return quantize(h58.mul_exact(left, right), action)


def add(left: h58.FP, right: h58.FP, action: str) -> h58.FP:
    return quantize(h58.add_exact(left, right), action)


def value(
    point: Point,
    candidate: Candidate,
    lookup_override: h58.FP | None = None,
) -> h58.FP:
    x = h252.input_fp(point.se, point.sig)
    anchor = h252.table_anchor(x)
    residual = add(
        x,
        h58.neg(h252.fraction_fp(anchor, 67)),
        candidate.ordinary_add,
    )
    z = mul(h252.LN2, residual, candidate.scale_mul)
    z2 = mul(z, z, candidate.ordinary_mul)
    c2, c3, c4, c5, c6, c7 = (
        h58.ROM[row] for row in h252.SHORT
    )

    even = add(
        c4,
        mul(z2, c6, candidate.ordinary_mul),
        candidate.ordinary_add,
    )
    even = add(
        c2,
        mul(z2, even, candidate.ordinary_mul),
        candidate.ordinary_add,
    )
    even = add(
        z,
        mul(z2, even, candidate.ordinary_mul),
        candidate.ordinary_add,
    )

    odd = add(
        c5,
        mul(z2, c7, candidate.ordinary_mul),
        candidate.ordinary_add,
    )
    odd = add(
        c3,
        mul(z2, odd, candidate.ordinary_mul),
        candidate.ordinary_add,
    )
    odd = mul(
        z,
        mul(z2, odd, candidate.ordinary_mul),
        candidate.ordinary_mul,
    )
    polynomial = add(even, odd, candidate.ordinary_add)

    lookup = lookup_override if lookup_override is not None else h252.table_value(anchor)
    one_plus_lookup = add(lookup, h58.ONE, candidate.ordinary_add)
    scaled = mul(one_plus_lookup, polynomial, candidate.ordinary_mul)
    return h58.add_exact(lookup, scaled)  # final add/writeback class


def metric(point: Point, candidate: Candidate) -> tuple[int, int]:
    result = value(point, candidate)
    misses = sum(
        h252.rounded(result, rc) != point.hardware[index]
        for index, rc in enumerate(h251.RCS)
    )
    return misses, bool(misses)


def metric_override(
    point: Point, candidate: Candidate, lookup: h58.FP
) -> int:
    result = value(point, candidate, lookup)
    return sum(
        h252.rounded(result, rc) != point.hardware[index]
        for index, rc in enumerate(h251.RCS)
    )


def add_metric(left, right):
    return tuple(a + b for a, b in zip(left, right))


def score(points: list[Point], candidate: Candidate) -> tuple[int, int]:
    result = (0, 0)
    for point in points:
        result = add_metric(result, metric(point, candidate))
    return result


def points() -> list[Point]:
    result = []
    for dataset in ("dense", "sweep", "target"):
        inputs = [
            tuple(int(field, 16) for field in line.split())
            for line in h251.INPUTS[dataset].read_text().splitlines()
        ]
        captures = {
            rc: [
                h251.parse_output(line)[0]
                for line in (
                    h251.CAPTURE / f"{dataset}_f2xm1_{rc}_status.txt"
                ).read_text().splitlines()
            ]
            for rc in h251.RCS
        }
        for index, (se, sig) in enumerate(inputs):
            x = h251.decode_input(se, sig)
            if not (1 / 4 <= abs(x) <= 1):
                continue
            result.append(
                Point(
                    dataset,
                    index,
                    se,
                    sig,
                    tuple(captures[rc][index] for rc in h251.RCS),
                )
            )
    return result


def sample(all_points: list[Point], count: int = 3200) -> list[Point]:
    baseline = Candidate()
    constrained = []
    controls = []
    for point in all_points:
        target = constrained if metric(point, baseline)[0] else controls
        target.append(point)

    def key(point: Point):
        return (
            point.sig
            ^ (point.index << 17)
            ^ (sum(map(ord, point.dataset)) << 7)
        )

    constrained.sort(key=key)
    controls.sort(key=key)
    half = count // 2
    return constrained[:half] + controls[: count - half]


def objective(result: tuple[int, int]) -> tuple[int, int]:
    return result


def main() -> None:
    complete = points()
    selected = sample(complete)
    baseline = Candidate()
    print(
        f"complete={len(complete)} selected={len(selected)} "
        f"exact selected={score(selected, baseline)} "
        f"complete={score(complete, baseline)}"
    )

    first = []
    for ordinary_mul in ACTIONS:
        for ordinary_add in ACTIONS:
            candidate = Candidate(ordinary_mul, ordinary_add, "exact")
            result = score(selected, candidate)
            first.append((objective(result), candidate.short(), candidate))
    first.sort()
    print("ordinary-class leaders with exact multiply-class scaling:")
    for item in first[:12]:
        print(f"  {item[0]} {item[1]}")

    second = []
    seeds = [item[2] for item in first[:16]]
    for seed in seeds:
        for scale_mul in ACTIONS:
            candidate = dataclasses.replace(seed, scale_mul=scale_mul)
            result = score(selected, candidate)
            second.append((objective(result), candidate.short(), candidate))
    second.sort()

    # Re-open the ordinary grid around the four leading multiply-class modes
    # so a useful interaction is not excluded by the exact-scale first pass.
    scale_modes = []
    for _, _, candidate in second:
        if candidate.scale_mul not in scale_modes:
            scale_modes.append(candidate.scale_mul)
        if len(scale_modes) == 4:
            break
    refined = []
    for scale_mul in scale_modes:
        for ordinary_mul in ACTIONS:
            for ordinary_add in ACTIONS:
                candidate = Candidate(ordinary_mul, ordinary_add, scale_mul)
                result = score(selected, candidate)
                refined.append((objective(result), candidate.short(), candidate))
    refined.sort()
    print("selected leaders after multiply-class refinement:")
    for item in refined[:16]:
        print(f"  {item[0]} {item[1]}")

    print("complete leaders:")
    seen = set()
    finalists = []
    for _, _, candidate in refined:
        if candidate in seen:
            continue
        seen.add(candidate)
        finalists.append(candidate)
        if len(finalists) == 2:
            break
    complete_scores = []
    for candidate in finalists:
        result = score(complete, candidate)
        complete_scores.append((objective(result), candidate.short()))
    for item in sorted(complete_scores):
        print(f"  {item[0]} {item[1]}")


if __name__ == "__main__":
    main()
