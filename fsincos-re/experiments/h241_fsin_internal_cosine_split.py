#!/usr/bin/env python3
"""Test the P6 two-chain cosine graph inside standalone FSIN.

Round 38 established a two-chain dependency graph for standalone FCOS, but
standalone FSIN still evaluates its odd-quadrant internal cosine as serial
Horner.  Replay the split graph on FSIN's structured sweep, independently
fit only its named operation boundaries, and veto a survivor against the
earlier purpose-built internal-cosine captures.
"""

from __future__ import annotations

import pathlib

import h58_constraint_search as h58
import h110_fsin_standalone as h110
import h121_fsin_internal_cosine as h121
import h146_fsin_cosine_boolean_search as h146
import h147_fsin_cosine_boolean_discriminator as h147
import h148_fsin_cosine_boolean_crossvalidate as h148
import h151_fsin_cosine_tail_discriminator as h151
import h158_fsin_cosine_two_predicate_discriminator as h158
import h161_fsin_cosine_round32_composition as h161
import h163_fsin_cosine_product_discriminator as h163
import h166_fsin_cosine_round33_tomography as h166
import h168_fsin_cosine_round33_operation_discriminator as h168
import h235_fcos_p6_split_graph as h235


ROOT = pathlib.Path(__file__).resolve().parents[1]

# Complete-corpus survivor selected independently on both structured halves
# while every earlier focused capture supplied an aggregate no-worse gate.
FSIN_SPLIT_SURVIVOR = h235.Schedule(
    square=h110.Quant(67, "chop"),
    fourth=h110.Quant(64, "rn"),
    products=(
        h110.Quant(67, "chop"),
        h110.Quant(67, "chop"),
        h110.Quant(67, "chop"),
        h110.Quant(67, "chop"),
        h110.Quant(67, "rn"),
        h110.Quant(67, "chop"),
    ),
    sums=(
        h110.Quant(67, "chop"),
        h110.Quant(67, "chop"),
        h110.Quant(64, "rn"),
        h110.Quant(65, "away"),
    ),
    combine=h110.Quant(66, "chop"),
    final=h110.EXACT,
)


def serial_hidden(point: h121.Point) -> h58.FP:
    """Return the current Round-33 standalone-FSIN cosine state."""
    return h146.hidden_value(point, h166.schedule(point))


def split_hidden(
    point: h121.Point, schedule: h235.Schedule
) -> h58.FP:
    value = h235.hidden_value(point.observed, schedule)
    return h58.neg(value) if point.negate else value


def score(
    points: list[h121.Point],
    schedule: h235.Schedule,
    weights: dict[int, float] | None = None,
) -> h110.Score:
    result = h110.Score()
    for point in points:
        weight = (
            weights.get(point.observed.raw.index, 1.0)
            if weights
            else 1.0
        )
        hidden = split_hidden(point, schedule)
        result.total += weight
        any_miss = False
        for index, rc in enumerate(h58.RCS):
            expected = point.observed.outputs[index]
            output = h58.x87_round(hidden, rc)
            mismatch = output != expected
            result.mode_misses += mismatch * weight
            any_miss |= mismatch
            if not mismatch:
                predicted_c1 = (
                    h110.compare_magnitude(expected, hidden) > 0
                )
                result.c1_misses += (
                    predicted_c1 != point.observed.c1[index]
                ) * weight
        result.output_misses += any_miss * weight
    return result


def score_serial(points: list[h121.Point]) -> h110.Score:
    result = h110.Score()
    for point in points:
        hidden = serial_hidden(point)
        result.total += 1
        any_miss = False
        for index, rc in enumerate(h58.RCS):
            expected = point.observed.outputs[index]
            output = h58.x87_round(hidden, rc)
            mismatch = output != expected
            result.mode_misses += mismatch
            any_miss |= mismatch
            if not mismatch:
                predicted_c1 = (
                    h110.compare_magnitude(expected, hidden) > 0
                )
                result.c1_misses += (
                    predicted_c1 != point.observed.c1[index]
                )
        result.output_misses += any_miss
    return result


def point_active(
    point: h121.Point, schedule: h235.Schedule
) -> bool:
    return bool(
        score([point], schedule).mode_misses
        or score([point], schedule).c1_misses
        or score_serial([point]).mode_misses
        or score_serial([point]).c1_misses
    )


def sample_for_search(
    points: list[h121.Point],
    schedule: h235.Schedule,
    controls: int,
) -> tuple[list[h121.Point], dict[int, float]]:
    active = []
    exact_groups: dict[tuple[int, int, int], list[h121.Point]] = {}
    for point in points:
        if point_active(point, schedule):
            active.append(point)
            continue
        raw = point.observed.raw
        key = int(point.negate), raw.exponent, (raw.sig >> 60) & 7
        exact_groups.setdefault(key, []).append(point)

    quota = max(1, controls // len(exact_groups))
    selected = list(active)
    weights = {
        point.observed.raw.index: 1.0 for point in active
    }
    for key in sorted(exact_groups):
        group = exact_groups[key]
        count = min(quota, len(group))
        chosen = [
            group[(index * len(group)) // count]
            for index in range(count)
        ]
        selected.extend(chosen)
        group_weight = len(group) / count
        for point in chosen:
            weights[point.observed.raw.index] = group_weight
    return selected, weights


def optimize(
    train: list[h121.Point],
    heldout: list[h121.Point],
    focused: list[tuple[str, list[h121.Point]]],
    start: h235.Schedule,
    passes: int = 4,
) -> h235.Schedule:
    train_sample, train_weights = sample_for_search(train, start, 1536)
    heldout_sample, heldout_weights = sample_for_search(
        heldout, start, 1536
    )
    print(
        f"search samples: train={len(train_sample)} "
        f"heldout={len(heldout_sample)}",
        flush=True,
    )
    current = start
    for pass_index in range(passes):
        changed = False
        print(f"coordinate pass {pass_index + 1}", flush=True)
        for coordinate in h235.coordinates():
            train_base = score(train_sample, current, train_weights)
            heldout_base = score(
                heldout_sample, current, heldout_weights
            )
            focused_base = {
                name: score(dataset, current)
                for name, dataset in focused
            }
            ranked = sorted(
                (
                    score(
                        train_sample, candidate, train_weights
                    ).rank(),
                    candidate.short(),
                    candidate,
                )
                for candidate in dict.fromkeys(
                    coordinate.candidates(current)
                )
            )
            accepted = None
            for _, _, candidate in ranked[:12]:
                train_score = score(
                    train_sample, candidate, train_weights
                )
                heldout_score = score(
                    heldout_sample, candidate, heldout_weights
                )
                if (
                    train_score.rank() <= train_base.rank()
                    and heldout_score.rank() <= heldout_base.rank()
                    and (
                        train_score.rank() < train_base.rank()
                        or heldout_score.rank() < heldout_base.rank()
                    )
                ):
                    focused_score = {
                        name: score(dataset, candidate)
                        for name, dataset in focused
                    }
                    if not all(
                        focused_score[name].rank()
                        <= focused_base[name].rank()
                        for name, _ in focused
                    ):
                        continue
                    accepted = (
                        candidate,
                        train_score,
                        heldout_score,
                    )
                    break
            if accepted is None:
                continue
            current, train_score, heldout_score = accepted
            changed = True
            print(
                f"  {coordinate.name:10s}: "
                f"train={train_score.rank()} "
                f"heldout={heldout_score.rank()}\n"
                f"    {current.short()}",
                flush=True,
            )
        if not changed:
            break
    return current


def focused_datasets() -> list[tuple[str, list[h121.Point]]]:
    captures = ROOT / "capture-kit-captures"
    return [
        (
            "h147",
            h147.load_capture(
                h147.DEFAULT_OUTPUT, captures / "skylake-fsin-h147"
            ),
        ),
        (
            "h148",
            h148.load_capture(
                h148.DEFAULT_OUTPUT, captures / "skylake-fsin-h148"
            ),
        ),
        (
            "h151",
            h151.load_capture(
                h151.DEFAULT_OUTPUT, captures / "skylake-fsin-h151"
            ),
        ),
        (
            "h158",
            h158.load_capture(
                h158.DEFAULT_OUTPUT, captures / "skylake-fsin-h158"
            ),
        ),
        (
            "h161",
            h161.load_capture(
                h161.DEFAULT_OUTPUT, captures / "skylake-fsin-h161"
            ),
        ),
        (
            "h163",
            h163.load_capture(
                h163.DEFAULT_OUTPUT, captures / "skylake-fsin-h163"
            ),
        ),
        (
            "h168",
            h168.load_capture(
                h168.DEFAULT_OUTPUT, captures / "skylake-fsin-h168"
            ),
        ),
    ]


def main() -> None:
    points = h121.load_points()
    train = [point for point in points if h121.is_train(point)]
    heldout = [point for point in points if not h121.is_train(point)]
    print(
        f"loaded {len(points)} FSIN internal-cosine points: "
        f"{len(train)} train, {len(heldout)} held out"
    )
    print(f"serial Round 33: {score_serial(points).describe()}")
    print(f"split start:     {score(points, h235.P6_START).describe()}")
    print(
        "FCOS split:      "
        f"{score(points, h235.P6_SURVIVOR).describe()}"
    )

    focused = focused_datasets()
    winner = optimize(
        train, heldout, focused, h235.P6_SURVIVOR
    )
    if winner != FSIN_SPLIT_SURVIVOR:
        raise SystemExit("h241 search no longer selects the frozen survivor")
    print("\nFSIN split survivor")
    print(f"  {winner.short()}")
    print(f"  train:    {score(train, winner).describe()}")
    print(f"  heldout:  {score(heldout, winner).describe()}")
    print(f"  complete: {score(points, winner).describe()}")

    print("\nindependent focused-capture vetoes")
    for name, dataset in focused:
        old = score_serial(dataset)
        shared = score(dataset, h235.P6_SURVIVOR)
        fitted = score(dataset, winner)
        print(
            f"  {name}: n={len(dataset)} serial={old.rank()} "
            f"FCOS-split={shared.rank()} fitted={fitted.rank()}"
        )


if __name__ == "__main__":
    main()
