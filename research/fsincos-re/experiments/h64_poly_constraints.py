#!/usr/bin/env python3
"""Cross-validated constraint search for the six-term polynomial region.

The dense capture has 80,000 direct inputs in [2^-3, 1/4).  FSINCOS was
captured under RN/RD/RU, while standalone FSIN and FCOS were captured under
RN.  Intel uses a different microcode path for the standalone instructions
only in this region, making the path difference an additional constraint on
the unresolved last-operation details.

This pass searches plausible 64..69-bit RN/chop placements in:

* r^2, coefficient materialization, and Horner operations;
* the sine correction product and fused/factored final;
* the cosine tail and fused/fixed final.

Each output and instruction path is fitted on one deterministic half of the
capture and verified on the untouched half.  A result is carryable only when
it improves both halves; schedules that merely fit boundary points are
reported but rejected.
"""

from __future__ import annotations

import argparse
import dataclasses
import itertools
import pathlib
from collections import Counter

import h58_constraint_search as h58


ROOT = pathlib.Path(__file__).resolve().parents[1]
CAPTURE = ROOT / "capture-kit-captures" / "pentiumII"
INPUTS = ROOT / "capture-kit" / "inputs" / "dense_qn.txt"


@dataclasses.dataclass(frozen=True)
class PolyRaw:
    index: int
    sign: int
    exponent: int
    sig: int
    sincos: tuple[
        tuple[tuple[int, int], tuple[int, int]],
        tuple[tuple[int, int], tuple[int, int]],
        tuple[tuple[int, int], tuple[int, int]],
    ]
    standalone: tuple[tuple[int, int], tuple[int, int]]


@dataclasses.dataclass(frozen=True)
class PolyPoint:
    raw: PolyRaw
    r: h58.FP
    asq: h58.FP
    p: h58.FP
    q: h58.FP


@dataclasses.dataclass(frozen=True)
class PolyTail:
    topology: str
    product_bits: int = 64
    product_mode: str = "rn"
    mid_bits: int = 64
    mid_mode: str = "rn"

    def short(self) -> str:
        return (
            f"{self.topology}:p{self.product_bits}{self.product_mode[0]}"
            f"/i{self.mid_bits}{self.mid_mode[0]}"
        )


SIN_BASE = PolyTail("sin-w-fused")
COS_BASE = PolyTail("cos-fused")


@dataclasses.dataclass
class PathScore:
    mode_misses: float = 0
    output_misses: float = 0
    rn_misses: float = 0
    total: float = 0
    by_bin: Counter[int] = dataclasses.field(default_factory=Counter)

    def rank(self) -> tuple[float, float, float]:
        return self.mode_misses, self.output_misses, self.rn_misses

    def describe(self, path: str) -> str:
        modes = 3 if path == "sincos" else 1
        return (
            f"{self.mode_misses:.0f}/{modes * self.total:.0f} mode, "
            f"{self.output_misses:.0f}/{self.total:.0f} output, "
            f"{self.rn_misses:.0f}/{self.total:.0f} RN"
        )


def parse_single(line: str) -> tuple[int, int]:
    fields = line.split()
    if fields[0] != "OK" or len(fields) != 3:
        raise ValueError(line)
    return int(fields[1], 16), int(fields[2], 16)


def load_raw() -> list[PolyRaw]:
    input_lines = INPUTS.read_text().splitlines()
    sincos_lines = [
        (CAPTURE / f"dense_{rc}.txt").read_text().splitlines()
        for rc in h58.RCS
    ]
    fsin_lines = (CAPTURE / "dense_fsin.txt").read_text().splitlines()
    fcos_lines = (CAPTURE / "dense_fcos.txt").read_text().splitlines()
    all_outputs = (*sincos_lines, fsin_lines, fcos_lines)
    if any(len(lines) != len(input_lines) for lines in all_outputs):
        raise SystemExit("input/capture line counts differ")
    points = []
    for index, line in enumerate(input_lines):
        se_text, sig_text = line.split()
        se, sig = int(se_text, 16), int(sig_text, 16)
        exponent = (se & 0x7FFF) - 16383
        if exponent != -3:
            continue
        points.append(
            PolyRaw(
                index=index,
                sign=se >> 15,
                exponent=exponent,
                sig=sig,
                sincos=tuple(
                    h58.parse_sincos(lines[index]) for lines in sincos_lines
                ),
                standalone=(
                    parse_single(fsin_lines[index]),
                    parse_single(fcos_lines[index]),
                ),
            )
        )
    return points


def prepare(
    raw: PolyRaw,
    producer: h58.ProducerConfig = h58.BASE_PRODUCER,
    q_final_product_bits: int | None = None,
) -> PolyPoint:
    r: h58.FP = (0, raw.sig, raw.exponent - 63)
    asq = h58.fmul(
        r, r, producer.asq_bits, producer.asq_mode
    )
    p = h58.horner(h58.S6, asq, producer)
    if q_final_product_bits is None:
        q = h58.horner(h58.C6, asq, producer)
    else:
        q = h58.coefficient(h58.C6[0], producer)
        for step, row in enumerate(h58.C6[1:], 1):
            product = h58.mul_exact(q, asq)
            if step == len(h58.C6) - 1:
                product = h58.round_fp(
                    product, q_final_product_bits, "chop"
                )
            constant = h58.coefficient(row, producer)
            if producer.horner_form == "fused":
                q = h58.round_fp(
                    h58.add_exact(product, constant),
                    producer.horner_bits,
                    producer.horner_mode,
                )
            else:
                q = h58.fadd(
                    h58.round_fp(
                        product,
                        producer.horner_bits,
                        producer.horner_mode,
                    ),
                    constant,
                    producer.horner_bits,
                    producer.horner_mode,
                )
    return PolyPoint(raw=raw, r=r, asq=asq, p=p, q=q)


def poly_value(point: PolyPoint, side: int, tail: PolyTail) -> h58.FP:
    if side == 0:
        m = h58.fmul(
            point.p,
            point.asq,
            tail.product_bits,
            tail.product_mode,
        )
        if tail.topology == "sin-w-fused":
            value = h58.add_exact(
                point.r, h58.mul_exact(m, point.r)
            )
        elif tail.topology == "sin-full-fused":
            correction = h58.mul_exact(
                h58.mul_exact(point.p, point.asq), point.r
            )
            value = h58.add_exact(point.r, correction)
        elif tail.topology == "sin-correction-rounded":
            correction = h58.fmul(
                m, point.r, tail.mid_bits, tail.mid_mode
            )
            value = h58.add_exact(point.r, correction)
        elif tail.topology == "sin-factored":
            factor = h58.fadd(
                h58.ONE, m, tail.mid_bits, tail.mid_mode
            )
            value = h58.mul_exact(point.r, factor)
        elif tail.topology == "sin-fixed-final":
            value = h58.round_fp(
                h58.add_exact(point.r, h58.mul_exact(m, point.r)),
                tail.mid_bits,
                tail.mid_mode,
            )
        else:
            raise ValueError(tail.topology)
        return h58.neg(value) if point.raw.sign else value

    if tail.topology == "cos-fused":
        return h58.add_exact(
            h58.ONE, h58.mul_exact(point.q, point.asq)
        )
    product = h58.fmul(
        point.q,
        point.asq,
        tail.product_bits,
        tail.product_mode,
    )
    if tail.topology == "cos-tail":
        return h58.add_exact(h58.ONE, product)
    if tail.topology == "cos-fixed-final":
        return h58.round_fp(
            h58.add_exact(
                h58.ONE, h58.mul_exact(point.q, point.asq)
            ),
            tail.mid_bits,
            tail.mid_mode,
        )
    raise ValueError(tail.topology)


def predictions(
    point: PolyPoint,
    side: int,
    tail: PolyTail,
    path: str,
) -> tuple[tuple[int, int], ...]:
    value = poly_value(point, side, tail)
    rcs = h58.RCS if path == "sincos" else ("rn",)
    return tuple(h58.x87_round(value, rc) for rc in rcs)


def path_score(
    points: list[PolyPoint],
    side: int,
    tail: PolyTail,
    path: str,
    weights: dict[int, float] | None = None,
    fingerprint: bool = False,
) -> tuple[PathScore, int]:
    score = PathScore()
    prediction_hash = 0xCBF29CE484222325
    for point in points:
        weight = weights.get(point.raw.index, 1.0) if weights else 1.0
        predicted = predictions(point, side, tail, path)
        if path == "sincos":
            expected = tuple(row[side] for row in point.raw.sincos)
        else:
            expected = (point.raw.standalone[side],)
        misses = 0
        score.total += weight
        for rc_index, (actual, wanted) in enumerate(zip(predicted, expected)):
            if fingerprint:
                for word in actual:
                    prediction_hash ^= word
                    prediction_hash = (
                        prediction_hash * 0x100000001B3
                    ) & 0xFFFFFFFFFFFFFFFF
            mismatch = actual != wanted
            misses += mismatch
            score.mode_misses += mismatch * weight
            if rc_index == 0:
                score.rn_misses += mismatch * weight
        if misses:
            score.output_misses += weight
            score.by_bin[(point.raw.sig >> 60) & 7] += weight
    return score, prediction_hash


def is_train(point: PolyPoint) -> bool:
    sig = point.raw.sig
    return not ((sig ^ (sig >> 19) ^ (sig >> 43) ^ point.raw.sign) & 1)


def sample_for_search(
    points: list[PolyPoint],
    side: int,
    tail: PolyTail,
    path: str,
    controls: int,
) -> tuple[list[PolyPoint], dict[int, float]]:
    active = []
    exact_groups: dict[tuple[int, int], list[PolyPoint]] = {}
    for point in points:
        score, _ = path_score([point], side, tail, path)
        if score.output_misses:
            active.append(point)
        else:
            key = point.raw.sign, (point.raw.sig >> 60) & 7
            exact_groups.setdefault(key, []).append(point)
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
        f"    sample: {len(active)} constrained + "
        f"{len(selected) - len(active)} controls "
        f"(weighted to {sum(weights.values()):.0f})"
    )
    return selected, weights


def tail_candidates(side: int) -> list[PolyTail]:
    pm = h58.precision_modes()
    if side == 0:
        candidates = [
            PolyTail("sin-w-fused", bits, mode)
            for bits, mode in pm
        ]
        candidates.append(PolyTail("sin-full-fused"))
        for topology in (
            "sin-correction-rounded",
            "sin-factored",
            "sin-fixed-final",
        ):
            for product, mid in itertools.product(pm, repeat=2):
                candidates.append(
                    PolyTail(
                        topology,
                        product_bits=product[0],
                        product_mode=product[1],
                        mid_bits=mid[0],
                        mid_mode=mid[1],
                    )
                )
        return candidates
    candidates = [PolyTail("cos-fused")]
    candidates.extend(
        PolyTail("cos-tail", bits, mode) for bits, mode in pm
    )
    candidates.extend(
        PolyTail("cos-fixed-final", mid_bits=bits, mid_mode=mode)
        for bits, mode in pm
    )
    return candidates


def tail_distance(side: int, tail: PolyTail) -> int:
    baseline = SIN_BASE if side == 0 else COS_BASE
    return sum(
        getattr(tail, field.name) != getattr(baseline, field.name)
        for field in dataclasses.fields(PolyTail)
    )


def rank_tails(
    points: list[PolyPoint],
    weights: dict[int, float],
    side: int,
    path: str,
    candidates: list[PolyTail],
    keep: int,
) -> list[PolyTail]:
    by_prediction: dict[
        int, tuple[tuple[float, float, float], PolyTail, PathScore]
    ] = {}
    for tail in candidates:
        score, prediction_hash = path_score(
            points, side, tail, path, weights, fingerprint=True
        )
        row = score.rank(), tail, score
        previous = by_prediction.get(prediction_hash)
        if previous is None or (
            row[0], tail_distance(side, row[1]), row[1].short()
        ) < (
            previous[0],
            tail_distance(side, previous[1]),
            previous[1].short(),
        ):
            by_prediction[prediction_hash] = row
    ranked = sorted(
        by_prediction.values(),
        key=lambda row: (
            row[0], tail_distance(side, row[1]), row[1].short()
        ),
    )
    print(
        f"    tails: {len(candidates)} schedules -> "
        f"{len(ranked)} prediction classes"
    )
    for _, tail, score in ranked[: min(8, keep)]:
        print(f"      {tail.short():38s} {score.describe(path)}")
    return [tail for _, tail, _ in ranked[:keep]]


def producer_distance(cfg: h58.ProducerConfig) -> int:
    baseline = h58.BASE_PRODUCER
    return sum(
        getattr(cfg, field.name) != getattr(baseline, field.name)
        for field in dataclasses.fields(h58.ProducerConfig)
    )


def producer_beam(
    raw_points: list[PolyRaw],
    weights: dict[int, float],
    side: int,
    path: str,
    tail: PolyTail,
    keep: int,
    rounds: int,
) -> list[h58.ProducerConfig]:
    beam = [h58.BASE_PRODUCER]
    cache: dict[h58.ProducerConfig, PathScore] = {}
    for round_index in range(rounds):
        candidates = {
            candidate
            for cfg in beam
            for candidate in (cfg, *h58.producer_neighbors(cfg))
        }
        ranked = []
        for producer in candidates:
            score = cache.get(producer)
            if score is None:
                prepared = [prepare(raw, producer) for raw in raw_points]
                score = path_score(
                    prepared, side, tail, path, weights
                )[0]
                cache[producer] = score
            ranked.append((score.rank(), producer, score))
        ranked.sort(
            key=lambda row: (
                row[0], producer_distance(row[1]), row[1].short()
            )
        )
        beam = [producer for _, producer, _ in ranked[:keep]]
        print(f"    producer beam round {round_index + 1}:")
        for _, producer, score in ranked[: min(6, keep)]:
            print(
                f"      {producer.short():30s} {score.describe(path)}"
            )
    return beam


def score_pair(
    raw: list[PolyRaw],
    producer: h58.ProducerConfig,
    tail: PolyTail,
    side: int,
    path: str,
) -> PathScore:
    return path_score(
        [prepare(point, producer) for point in raw],
        side,
        tail,
        path,
    )[0]


def dominates(candidate: PathScore, baseline: PathScore, strict: bool) -> bool:
    no_worse = all(
        actual <= expected
        for actual, expected in zip(candidate.rank(), baseline.rank())
    )
    return no_worse and (not strict or candidate.rank() < baseline.rank())


def fit(
    train: list[PolyPoint],
    side: int,
    path: str,
    controls: int,
    keep: int,
    rounds: int,
) -> list[tuple[h58.ProducerConfig, PolyTail]]:
    baseline_tail = SIN_BASE if side == 0 else COS_BASE
    sample, weights = sample_for_search(
        train, side, baseline_tail, path, controls
    )
    tails = rank_tails(
        sample, weights, side, path, tail_candidates(side), keep
    )
    producers = {h58.BASE_PRODUCER}
    raw_sample = [point.raw for point in sample]
    for tail in tails[:3]:
        producers.update(
            producer_beam(
                raw_sample,
                weights,
                side,
                path,
                tail,
                keep,
                rounds,
            )
        )
    ranked = []
    for producer, tail in itertools.product(producers, tails):
        score = path_score(
            [prepare(raw, producer) for raw in raw_sample],
            side,
            tail,
            path,
            weights,
        )[0]
        ranked.append((score.rank(), producer, tail, score))
    ranked.sort(
        key=lambda row: (
            row[0],
            producer_distance(row[1]),
            tail_distance(side, row[2]),
            row[1].short(),
            row[2].short(),
        )
    )
    print("    joint producer/tail:")
    for _, producer, tail, score in ranked[: min(8, keep)]:
        print(
            f"      {producer.short():30s} {tail.short():38s} "
            f"{score.describe(path)}"
        )
    return [
        (producer, tail)
        for _, producer, tail, _ in ranked[:keep]
    ]


def validate(
    raw_datasets: dict[str, list[PolyRaw]],
    side: int,
    fitted_path: str,
    candidates: list[tuple[h58.ProducerConfig, PolyTail]],
) -> None:
    baseline_tail = SIN_BASE if side == 0 else COS_BASE
    baseline_pair = h58.BASE_PRODUCER, baseline_tail
    pairs = list(dict.fromkeys((baseline_pair, *candidates)))
    baselines = {
        path: {
            name: score_pair(
                raw, *baseline_pair, side, path
            )
            for name, raw in raw_datasets.items()
        }
        for path in ("sincos", "standalone")
    }
    rows = []
    for producer, tail in pairs:
        scores = {
            path: {
                name: score_pair(raw, producer, tail, side, path)
                for name, raw in raw_datasets.items()
            }
            for path in ("sincos", "standalone")
        }
        target = scores[fitted_path]
        base = baselines[fitted_path]
        survivor = (
            dominates(target["heldout"], base["heldout"], strict=False)
            and dominates(target["complete"], base["complete"], strict=True)
        )
        rows.append(
            (
                (
                    not survivor,
                    target["heldout"].rank(),
                    target["complete"].rank(),
                    producer_distance(producer),
                    tail_distance(side, tail),
                ),
                survivor,
                producer,
                tail,
                scores,
            )
        )
    rows.sort(key=lambda row: row[0])

    print("    complete baselines:")
    for path in ("sincos", "standalone"):
        print(
            f"      {path:10s} "
            f"{baselines[path]['complete'].describe(path)}"
        )
    print("    validation finalists (* improves fitted path on both halves):")
    for _, survivor, producer, tail, scores in rows[:10]:
        print(
            f"     {'*' if survivor else ' '} {producer.short()} "
            f"{tail.short()}"
        )
        for path in ("sincos", "standalone"):
            for name in ("train", "heldout", "complete"):
                actual = scores[path][name]
                expected = baselines[path][name]
                delta = tuple(
                    value - base
                    for value, base in zip(actual.rank(), expected.rank())
                )
                print(
                    f"        {path:10s} {name:8s} "
                    f"{actual.describe(path)} delta={delta}"
                )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--controls", type=int, default=2000)
    parser.add_argument("--keep", type=int, default=12)
    parser.add_argument("--producer-rounds", type=int, default=2)
    parser.add_argument(
        "--path",
        choices=("sincos", "standalone", "both"),
        default="both",
    )
    args = parser.parse_args()

    raw = load_raw()
    baseline_points = [prepare(point) for point in raw]
    train = [point for point in baseline_points if is_train(point)]
    heldout = [point for point in baseline_points if not is_train(point)]
    raw_datasets = {
        "train": [point.raw for point in train],
        "heldout": [point.raw for point in heldout],
        "complete": raw,
    }
    paths = (
        ("sincos", "standalone")
        if args.path == "both"
        else (args.path,)
    )
    print(
        f"loaded {len(raw)} polynomial inputs: "
        f"{len(train)} train, {len(heldout)} held out"
    )
    for side, name in enumerate(("sine", "cosine")):
        for path in paths:
            print(f"\n{name}, fitted to {path}")
            candidates = fit(
                train,
                side,
                path,
                args.controls,
                args.keep,
                args.producer_rounds,
            )
            validate(raw_datasets, side, path, candidates)


if __name__ == "__main__":
    main()
