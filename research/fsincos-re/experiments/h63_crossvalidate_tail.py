#!/usr/bin/env python3
"""Cross-validate remaining narrow table-tail schedules.

h59 deliberately conditions on points where the Round-17 schedule differs
from the old baseline, so optimizing on h59 alone overfits badly.  This pass
searches each FSINCOS output independently on one deterministic half of the
complete direct-table capture, keeps one representative per observational
equivalence class, and verifies the finalists on:

* the untouched half of the complete capture;
* the complete capture;
* the independently generated h59 discriminator; and
* the h62 m-width discriminator.

The output-specific search tests the still-plausible possibility that
sequential FSINCOS microcode materializes S or t differently for sine and
cosine.  A schedule is a useful survivor only if it improves the complete
capture and h59 without regressing the held-out half.
"""

from __future__ import annotations

import argparse
import dataclasses
import itertools
import pathlib
from collections import Counter

import h58_constraint_search as h58
import h59_discriminator as h59


ROOT = pathlib.Path(__file__).resolve().parents[1]
H59_CAPTURE = ROOT / "capture-kit-captures" / "skylake-h59-constraints"
H59_INPUTS = H59_CAPTURE / "narrow_inputs.txt"
H62_CAPTURE = ROOT / "capture-kit-captures" / "skylake-h62-mwidth"
H62_INPUTS = ROOT / "capture-kit" / "inputs" / "constraint_mwidth_h62.txt"


@dataclasses.dataclass
class SideScore:
    mode_misses: float = 0
    output_misses: float = 0
    rn_misses: float = 0
    total: float = 0
    by_cell: Counter[int] = dataclasses.field(default_factory=Counter)

    def rank(self) -> tuple[float, float, float]:
        return self.mode_misses, self.output_misses, self.rn_misses

    def describe(self) -> str:
        return (
            f"{self.mode_misses:.0f}/{3 * self.total:.0f} mode, "
            f"{self.output_misses:.0f}/{self.total:.0f} output, "
            f"{self.rn_misses:.0f}/{self.total:.0f} RN"
        )


def side_score(
    points: list[h58.PreparedPoint],
    cfg: h58.TailConfig,
    side: int,
    weights: dict[int, float] | None = None,
    fingerprint: bool = False,
) -> tuple[SideScore, int]:
    score = SideScore()
    prediction_hash = 0xCBF29CE484222325
    for point in points:
        weight = weights.get(point.raw.index, 1.0) if weights else 1.0
        value = h58.table_tail(point, cfg)[side]
        misses = 0
        score.total += weight
        for rc_index, rc in enumerate(h58.RCS):
            predicted = h58.x87_round(value, rc)
            if fingerprint:
                for word in predicted:
                    prediction_hash ^= word
                    prediction_hash = (
                        prediction_hash * 0x100000001B3
                    ) & 0xFFFFFFFFFFFFFFFF
            mismatch = predicted != point.raw.hw[rc_index][side]
            misses += mismatch
            score.mode_misses += mismatch * weight
            if rc == "rn":
                score.rn_misses += mismatch * weight
        if misses:
            score.output_misses += weight
            score.by_cell[point.cell] += weight
    return score, prediction_hash


def is_train(point: h58.PreparedPoint) -> bool:
    """Host-FP-free stable split, balanced within random dense inputs."""
    sig = point.raw.sig
    folded = sig ^ (sig >> 17) ^ (sig >> 41) ^ point.raw.sign
    return not (folded & 1)


def search_sample(
    points: list[h58.PreparedPoint],
    side: int,
    controls: int,
) -> tuple[list[h58.PreparedPoint], dict[int, float]]:
    active: list[h58.PreparedPoint] = []
    exact_groups: dict[tuple[int, int], list[h58.PreparedPoint]] = {}
    for point in points:
        score, _ = side_score([point], h58.NARROW_TAIL, side)
        if score.output_misses:
            active.append(point)
        else:
            exact_groups.setdefault((point.cell, point.raw.sign), []).append(
                point
            )
    quota = max(1, controls // len(exact_groups))
    selected = list(active)
    weights = {point.raw.index: 1.0 for point in active}
    for key in sorted(exact_groups):
        group = exact_groups[key]
        count = min(quota, len(group))
        chosen = [group[(index * len(group)) // count] for index in range(count)]
        selected.extend(chosen)
        weight = len(group) / count
        for point in chosen:
            weights[point.raw.index] = weight
    print(
        f"  search sample: {len(active)} constrained + "
        f"{len(selected) - len(active)} controls "
        f"(weighted to {sum(weights.values()):.0f})"
    )
    return selected, weights


def s_candidates() -> list[h58.TailConfig]:
    pm = h58.precision_modes()
    candidates: list[h58.TailConfig] = []
    for topology in ("direct", "factored"):
        for m, mid, s in itertools.product(pm, repeat=3):
            candidates.append(
                dataclasses.replace(
                    h58.NARROW_TAIL,
                    topology=topology,
                    m_bits=m[0],
                    m_mode=m[1],
                    mid_bits=mid[0],
                    mid_mode=mid[1],
                    s_bits=s[0],
                    s_mode=s[1],
                )
            )
    for m, s in itertools.product(pm, repeat=2):
        candidates.append(
            dataclasses.replace(
                h58.NARROW_TAIL,
                topology="fma",
                m_bits=m[0],
                m_mode=m[1],
                s_bits=s[0],
                s_mode=s[1],
            )
        )
    for s in pm:
        candidates.append(
            dataclasses.replace(
                h58.NARROW_TAIL,
                topology="full-fma",
                s_bits=s[0],
                s_mode=s[1],
            )
        )
    return candidates


def t_candidates() -> list[h58.TailConfig]:
    return [
        dataclasses.replace(
            h58.NARROW_TAIL, t_bits=bits, t_mode=mode
        )
        for bits, mode in h58.precision_modes()
    ]


def canonical_distance(cfg: h58.TailConfig) -> int:
    """Prefer h62-proven fields when a training sample cannot distinguish."""
    canonical = h58.NARROW_TAIL
    return sum(
        getattr(cfg, field.name) != getattr(canonical, field.name)
        for field in dataclasses.fields(h58.TailConfig)
    )


def rank_unique(
    points: list[h58.PreparedPoint],
    weights: dict[int, float],
    side: int,
    candidates: list[h58.TailConfig],
    keep: int,
    label: str,
) -> list[h58.TailConfig]:
    by_prediction: dict[
        int, tuple[tuple[float, float, float], h58.TailConfig, SideScore]
    ] = {}
    for index, cfg in enumerate(candidates, 1):
        score, prediction_hash = side_score(
            points, cfg, side, weights, fingerprint=True
        )
        row = (score.rank(), cfg, score)
        previous = by_prediction.get(prediction_hash)
        if previous is None or (
            row[0], canonical_distance(row[1]), row[1].short()
        ) < (
            previous[0],
            canonical_distance(previous[1]),
            previous[1].short(),
        ):
            by_prediction[prediction_hash] = row
        if index % 500 == 0:
            print(f"    searched {index}/{len(candidates)} {label}")
    ranked = sorted(
        by_prediction.values(),
        key=lambda row: (
            row[0], canonical_distance(row[1]), row[1].short()
        ),
    )
    print(
        f"  {label}: {len(candidates)} schedules -> "
        f"{len(ranked)} prediction classes"
    )
    for _, cfg, score in ranked[: min(8, keep)]:
        print(f"    {cfg.short():46s} {score.describe()}")
    return [cfg for _, cfg, _ in ranked[:keep]]


def search_side(
    train: list[h58.PreparedPoint],
    side: int,
    controls: int,
    keep: int,
) -> list[h58.TailConfig]:
    sample, weights = search_sample(train, side, controls)
    top_s = rank_unique(
        sample, weights, side, s_candidates(), keep, "S schedules"
    )
    rank_unique(
        sample, weights, side, t_candidates(), keep, "t schedules"
    )
    top_s = list(dict.fromkeys((*top_s, h58.NARROW_TAIL)))
    crossed = {
        dataclasses.replace(
            s_cfg, t_bits=t_cfg.t_bits, t_mode=t_cfg.t_mode
        )
        for s_cfg, t_cfg in itertools.product(top_s, t_candidates())
    }
    crossed.add(h58.NARROW_TAIL)
    return rank_unique(
        sample,
        weights,
        side,
        sorted(crossed, key=lambda cfg: cfg.short()),
        keep,
        "crossed S/t schedules",
    )


def load_auxiliary() -> dict[str, list[h58.PreparedPoint]]:
    h59_raw = h59.load_score_points(H59_INPUTS, H59_CAPTURE, "narrow")
    h62_raw = h59.load_score_points(
        H62_INPUTS, H62_CAPTURE, "constraint_mwidth"
    )
    return {
        "h59": [h58.prepare(point) for point in h59_raw],
        "h62": [h58.prepare(point) for point in h62_raw],
    }


def dominates(
    candidate: SideScore,
    baseline: SideScore,
    strict: bool,
) -> bool:
    no_worse = all(
        actual <= expected
        for actual, expected in zip(candidate.rank(), baseline.rank())
    )
    return no_worse and (not strict or candidate.rank() < baseline.rank())


def validate(
    datasets: dict[str, list[h58.PreparedPoint]],
    side: int,
    candidates: list[h58.TailConfig],
) -> None:
    baseline = {
        name: side_score(points, h58.NARROW_TAIL, side)[0]
        for name, points in datasets.items()
    }
    print("  canonical:")
    for name in datasets:
        print(f"    {name:8s} {baseline[name].describe()}")

    rows = []
    for cfg in dict.fromkeys((h58.NARROW_TAIL, *candidates)):
        scores = {
            name: side_score(points, cfg, side)[0]
            for name, points in datasets.items()
        }
        survivor = (
            dominates(scores["heldout"], baseline["heldout"], strict=False)
            and dominates(scores["complete"], baseline["complete"], strict=True)
            and dominates(scores["h59"], baseline["h59"], strict=False)
        )
        rank = (
            not survivor,
            scores["heldout"].rank(),
            scores["complete"].rank(),
            scores["h59"].rank(),
            cfg.short(),
        )
        rows.append((rank, survivor, cfg, scores))
    rows.sort(key=lambda row: row[0])

    print("  validation finalists (* satisfies carrying rule):")
    for _, survivor, cfg, scores in rows[:12]:
        print(f"   {'*' if survivor else ' '} {cfg.short()}")
        for name in datasets:
            delta = tuple(
                actual - expected
                for actual, expected in zip(
                    scores[name].rank(), baseline[name].rank()
                )
            )
            print(
                f"      {name:8s} {scores[name].describe()} "
                f"delta={delta}"
            )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--controls", type=int, default=3000)
    parser.add_argument("--keep", type=int, default=32)
    args = parser.parse_args()

    raw = h58.load_points(h58.DEFAULT_CAPTURE)
    complete = [
        h58.prepare(point)
        for point in raw
        if point.exponent == -2
    ]
    train = [point for point in complete if is_train(point)]
    heldout = [point for point in complete if not is_train(point)]
    auxiliary = load_auxiliary()
    datasets = {
        "train": train,
        "heldout": heldout,
        "complete": complete,
        **auxiliary,
    }
    print(
        f"loaded {len(complete)} complete narrow inputs: "
        f"{len(train)} train, {len(heldout)} held out; "
        f"h59={len(auxiliary['h59'])}, h62={len(auxiliary['h62'])}"
    )

    for side, name in enumerate(("sine", "cosine")):
        print(f"\n{name} output-specific search")
        finalists = search_side(train, side, args.controls, args.keep)
        validate(datasets, side, finalists)


if __name__ == "__main__":
    main()
