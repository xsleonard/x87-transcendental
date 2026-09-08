#!/usr/bin/env python3
"""Close h218's eleven-program exceptions with the complete FADD grammar.

h218 finds only a few residual lane instances that none of h212's greedy
cover representatives reproduces exactly.  This pass deduplicates those
instances, tests every fixed jam-sub tree/control/product program, and only
then broadens to the other literal sticky modes if an exception remains.

The result distinguishes a deficient representative cover from a genuine
limit of the conditional literal-FADD grammar.
"""

from __future__ import annotations

import collections

import h211_fadd_complete_tree_grammar as h211
import h212_fadd_conditional_oracle as h212
import h213_fadd_causal_selector as h213
import h218_fadd_residual_programs as h218


ZERO = (0, 0, 0)


def residual_key(item: h218.Residual):
    joint = item.point.prepared.joint
    observed = joint.observed
    raw = observed.point.raw
    hardware = (
        joint.cosine_outputs if item.cosine else observed.outputs,
        joint.cosine_c1 if item.cosine else observed.c1,
    )
    return (
        raw.sign,
        raw.exponent,
        raw.sig,
        observed.source,
        observed.signed_n,
        item.cosine,
        hardware,
    )


def exceptions():
    unique = {}
    occurrences = collections.Counter()
    for name, points in h218.datasets():
        residuals = h218.inventory(name, points)[0]
        for item in residuals:
            if item.exact_mask:
                continue
            key = residual_key(item)
            unique.setdefault(key, item)
            occurrences[key] += 1
    return list(unique.values()), occurrences


def exact_mask_for_candidate(residuals, candidate):
    mask = 0
    cache = {}
    for index, item in enumerate(residuals):
        values = cache.get(item.point)
        if values is None:
            values = h211.hidden_values(item.point.prepared, candidate)
            cache[item.point] = values
        metric = h213.metric_for_values(item.point, *values)[item.cosine]
        if metric == ZERO:
            mask |= 1 << index
    return mask


def search(residuals, mode):
    profiles = collections.defaultdict(list)
    union = 0
    candidates = tuple(h212.candidates(mode))
    for index, candidate in enumerate(candidates, 1):
        mask = exact_mask_for_candidate(residuals, candidate)
        if mask:
            profiles[mask].append(candidate)
            union |= mask
        if index % 2048 == 0:
            print(
                f"  {mode or 'all'} progress={index}/{len(candidates)} "
                f"union={union.bit_count()}/{len(residuals)}",
                flush=True,
            )
    representatives = [
        min(values, key=lambda value: value.short())
        for values in profiles.values()
    ]
    representatives.sort(
        key=lambda value: (
            -exact_mask_for_candidate(residuals, value).bit_count(),
            value.short(),
        )
    )
    return profiles, representatives, union


def greedy(residuals, representatives, target):
    uncovered = target
    selected = []
    masks = {
        candidate: exact_mask_for_candidate(residuals, candidate)
        for candidate in representatives
    }
    while uncovered:
        candidate = max(
            representatives,
            key=lambda value: (masks[value] & uncovered).bit_count(),
        )
        covered = masks[candidate] & uncovered
        if not covered:
            break
        selected.append((candidate, covered.bit_count()))
        uncovered &= ~covered
    return selected, uncovered


def describe(item: h218.Residual, occurrences: int) -> str:
    observed = item.point.prepared.joint.observed
    raw = observed.point.raw
    return (
        f"lane={'cosine' if item.cosine else 'sine'} "
        f"source={observed.source} cell={observed.point.cell} "
        f"q={observed.signed_n & 3} sign={raw.sign} "
        f"exp={raw.exponent} sig=0x{raw.sig:016x} occurrences={occurrences}"
    )


def main() -> None:
    residuals, occurrences = exceptions()
    print(f"h219 unique eleven-program exceptions={len(residuals)}")
    for index, item in enumerate(residuals):
        print(f"  e{index + 1:02d} {describe(item, occurrences[residual_key(item)])}")

    profiles, representatives, union = search(residuals, "jam-sub")
    print(
        f"h219 jam-sub exact={union.bit_count()}/{len(residuals)} "
        f"profiles={len(profiles)} representatives={len(representatives)}"
    )
    target = (1 << len(residuals)) - 1
    if union != target:
        missing = target & ~union
        remaining = [
            item for index, item in enumerate(residuals) if missing & (1 << index)
        ]
        print(f"h219 broadening remaining={len(remaining)} to all modes")
        all_profiles, all_representatives, all_union = search(remaining, None)
        print(
            f"h219 all-mode exact={all_union.bit_count()}/{len(remaining)} "
            f"profiles={len(all_profiles)}"
        )
        representatives.extend(all_representatives)
        union |= sum(
            1 << index
            for index in range(len(residuals))
            if not missing & (1 << index)
        )

    selected, uncovered = greedy(residuals, representatives, target)
    print(
        f"h219 greedy exception cover={len(selected)} "
        f"uncovered={uncovered.bit_count()}"
    )
    for candidate, count in selected:
        print(f"  covers={count:2d} {candidate.short()}")


if __name__ == "__main__":
    main()
