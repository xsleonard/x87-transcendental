#!/usr/bin/env python3
"""Measure whether conditional literal FADD programs can reach the residuals.

h207 and h211 require one fixed program to be componentwise non-regressing
over every partition.  Undocumented microcode may instead select controls
from internal state.  Before fitting any selector, this pass computes a
strictly more permissive oracle bound: for each currently failing wide-table
point, may an arbitrary choice among every literal three-FADD program produce
the exact joint standalone-sine/paired-cosine hardware interval?

The oracle intentionally ignores the cost of recognizing a point and never
changes a currently correct control.  Therefore an uncovered residual proves
that conditional selection within this grammar is insufficient; complete
coverage merely licenses the later physical-predicate synthesis.
"""

from __future__ import annotations

import argparse
import collections
import dataclasses

import h207_tang_literal_fadd as h207
import h211_fadd_complete_tree_grammar as h211


ZERO = ((0, 0, 0), (0, 0, 0))


@dataclasses.dataclass(frozen=True)
class Profile:
    candidate: h211.Candidate
    exact: int
    improved: int
    gain: int


def popcount(value: int) -> int:
    return bin(value).count("1")


def candidates(selected_mode: str | None = None):
    routes = tuple(
        h207.ProductRoute(linear, q_product, p_product)
        for linear in h207.PRODUCT_OUTPUTS
        for q_product in h207.PRODUCT_OUTPUTS
        for p_product in h207.PRODUCT_OUTPUTS
    )
    for products in routes:
        for tree in h211.ALL_TREES:
            for mode in h207.MODES:
                if selected_mode is not None and mode != selected_mode:
                    continue
                for first in h207.ACTIONS:
                    for second in h207.ACTIONS:
                        for final_normalize in (False, True):
                            yield h211.Candidate(
                                tree,
                                mode,
                                first,
                                second,
                                final_normalize,
                                products,
                            )


def failure_points():
    partitions = h207.joint_partitions("sweep")
    points = [point for _, values in partitions for point in values]
    return [point for point in points if h211.point_metric(point, None) != ZERO]


def improvement(baseline, value) -> int:
    old = h207.objective([baseline])
    new = h207.objective([value])
    return sum(left - right for left, right in zip(old, new))


def greedy_cover(profiles: list[Profile], target: int):
    uncovered = target
    selected = []
    while uncovered:
        best = max(
            profiles,
            key=lambda profile: popcount(profile.exact & uncovered),
        )
        covered = best.exact & uncovered
        if not covered:
            break
        selected.append((best, popcount(covered)))
        uncovered &= ~covered
    return selected, uncovered


def point_name(point: h207.Point) -> str:
    observed = point.prepared.joint.observed
    prepared = observed.point
    return (
        f"index={observed.index} source={observed.source} "
        f"cell={prepared.cell} quadrant={observed.signed_n & 3} "
        f"sign={prepared.raw.sign} sig=0x{prepared.raw.sig:x}"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=h207.MODES)
    args = parser.parse_args()
    h211.assert_grammar()
    points = failure_points()
    baselines = [h211.point_metric(point, None) for point in points]
    values_to_test = tuple(candidates(args.mode))
    print(
        "h212 conditional literal-program oracle: "
        f"mode={args.mode or 'all'} programs={len(values_to_test)} "
        f"residuals={len(points)}"
    )
    print(
        "  residual classes "
        + str(collections.Counter(
            (
                baseline[0] != (0, 0, 0),
                baseline[1] != (0, 0, 0),
            )
            for baseline in baselines
        ))
    )

    exact_counts = [0] * len(points)
    improved_counts = [0] * len(points)
    exact_union = 0
    sine_exact_union = 0
    cosine_exact_union = 0
    improved_union = 0
    profiles = []
    exact_signatures = collections.Counter()
    for candidate_index, candidate in enumerate(values_to_test, 1):
        exact = 0
        improved = 0
        gain = 0
        for point_index, (point, baseline) in enumerate(zip(points, baselines)):
            value = h211.point_metric(point, candidate)
            if value[0] == (0, 0, 0):
                sine_exact_union |= 1 << point_index
            if value[1] == (0, 0, 0):
                cosine_exact_union |= 1 << point_index
            if value == ZERO:
                exact |= 1 << point_index
                exact_counts[point_index] += 1
            if h207.no_worse(value, baseline) and value != baseline:
                improved |= 1 << point_index
                improved_counts[point_index] += 1
                gain += improvement(baseline, value)
        exact_union |= exact
        improved_union |= improved
        if exact or improved:
            profiles.append(Profile(candidate, exact, improved, gain))
        exact_signatures[exact] += 1
        if candidate_index % 2048 == 0:
            print(
                f"  progress {candidate_index}/{len(values_to_test)} "
                f"exact-union={popcount(exact_union)}/{len(points)} "
                f"lane-union={popcount(sine_exact_union)}/"
                f"{popcount(cosine_exact_union)} "
                f"improved-union={popcount(improved_union)}/{len(points)}",
                flush=True,
            )

    print(
        f"h212 oracle exact={popcount(exact_union)}/{len(points)} "
        f"improved={popcount(improved_union)}/{len(points)} "
        f"exact-profiles={len(exact_signatures)}"
    )
    sine_target = sum(
        1 for baseline in baselines if baseline[0] != (0, 0, 0)
    )
    cosine_target = sum(
        1 for baseline in baselines if baseline[1] != (0, 0, 0)
    )
    sine_missing = sum(
        1
        for index, baseline in enumerate(baselines)
        if baseline[0] != (0, 0, 0)
        and not sine_exact_union & (1 << index)
    )
    cosine_missing = sum(
        1
        for index, baseline in enumerate(baselines)
        if baseline[1] != (0, 0, 0)
        and not cosine_exact_union & (1 << index)
    )
    print(
        f"  lane-local exact: sine={sine_target - sine_missing}/"
        f"{sine_target} cosine={cosine_target - cosine_missing}/"
        f"{cosine_target}"
    )
    ranked = sorted(
        profiles,
        key=lambda profile: (
            -popcount(profile.exact),
            -popcount(profile.improved),
            -profile.gain,
            profile.candidate.short(),
        ),
    )
    print("  leading conditional branches:")
    for profile in ranked[:20]:
        print(
            f"    exact={popcount(profile.exact):3d} "
            f"improved={popcount(profile.improved):3d} "
            f"gain={profile.gain:4d} {profile.candidate.short()}"
        )

    selected, greedy_uncovered = greedy_cover(profiles, exact_union)
    print(
        f"  greedy exact cover: programs={len(selected)} "
        f"uncovered-within-union={popcount(greedy_uncovered)}"
    )
    for profile, count in selected[:20]:
        print(f"    covers={count:3d} {profile.candidate.short()}")
    if len(selected) > 20:
        print(f"    ... {len(selected) - 20} additional programs")

    missing = ((1 << len(points)) - 1) & ~exact_union
    print(f"  exact-unreachable residuals={popcount(missing)}")
    for index, (point, baseline) in enumerate(zip(points, baselines)):
        if missing & (1 << index):
            print(
                f"    {point_name(point)} baseline={baseline} "
                f"improving-programs={improved_counts[index]}"
            )


if __name__ == "__main__":
    main()
