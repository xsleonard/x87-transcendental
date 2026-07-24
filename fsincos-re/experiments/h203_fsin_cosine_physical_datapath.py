#!/usr/bin/env python3
"""Search a bounded physical FMUL/FADD polynomial datapath.

h202 proves that inserting the literal FADD borrow path underneath the
existing scalar schedule is close but inconsistent: it improves aggregate
old/fresh metrics while regressing h148 and the dedicated h163 product
capture.  The 65/66/71/72-bit scalar operations are explicitly equivalent
representatives, so this pass does not assume they are also the operands
present on the hardware buses.

The candidate controls are restricted to routes exposed by the P5 patents:

* square: current Round-30 representative, RN64 FMUL, or sticky X67;
* ROM coefficient: current representative, native ROM67, or RN64 FIRC;
* Horner FMUL writeback: current, RN64, chop64, or sticky X67;
* FADD: literal h200 far subtraction, followed by current or RN64 FRND;
* retained FADD stages: none, stage 4, stage 5, stages 4+5, or all;
* tail: current Round-31 representative, RN64, or sticky X67;
* final subtraction: current exact representative (h202 found its literal
  form observationally identical throughout the leading profiles).

The initial coherent-bus grid requires a native67/RN64 coefficient route,
an RN64/chop64/sticky-X67 product route, and RN64 FRND when FADD is not
retained.  Hybrid combinations with the already-rejected scalar proxies are
not multiplied into this first grid.  Selection uses every currently wrong
old point, deterministic correct controls, and every complete focused capture
h147--h168.  Survivors are then checked on the complete old train/held
partitions.  This is a small microcontrol search, not a free per-input Boolean
fit.
"""

from __future__ import annotations

import collections
import dataclasses
import hashlib

import h58_constraint_search as h58
import h110_fsin_standalone as h110
import h119_fcos_standalone as h119
import h121_fsin_internal_cosine as h121
import h146_fsin_cosine_boolean_search as h146
import h167_fsin_cosine_round33_operation_search as h167
import h202_fsin_cosine_fadd_bitvector as h202
import h200_p5_fadd_bitvector as h200


Metric = h146.Metric
SQUARE_ROUTES = ("current", "rn64", "odd67")
COEFFICIENT_ROUTES = ("current", "native67", "rn64")
PRODUCT_ROUTES = ("current", "rn64", "chop64", "odd67")
SUM_ROUTES = ("current", "rn64")
RETAIN_MASKS = (0, 1 << 3, 1 << 4, (1 << 3) | (1 << 4), 31)
TAIL_ROUTES = ("current", "rn64", "odd67")


@dataclasses.dataclass(frozen=True)
class Candidate:
    mode: str
    square: str
    coefficient: str
    product: str
    sum_route: str
    retain_mask: int
    tail: str
    final_literal: bool
    normalize_retained: bool = True

    def short(self) -> str:
        stages = "".join(
            str(index + 1)
            for index in range(5)
            if self.retain_mask & (1 << index)
        )
        final = "literal" if self.final_literal else "exact"
        normalization = "norm" if self.normalize_retained else "raw"
        return (
            f"{self.mode}/{normalization} sq={self.square} "
            f"c={self.coefficient} "
            f"p={self.product} sum={self.sum_route} "
            f"retain[{stages or '-'}] tail={self.tail} final={final}"
        )


def quantized(value: h58.FP, route: str, current: h110.Quant) -> h58.FP:
    quant = {
        "current": current,
        "rn64": h110.Quant(64, "rn"),
        "chop64": h110.Quant(64, "chop"),
        "odd67": h110.Quant(67, "odd"),
    }[route]
    return h110.quantize(value, quant)


def coefficient(
    row: int,
    index: int,
    value_schedule: h119.Schedule,
    route: str,
) -> h58.FP:
    if route == "current":
        return h119.coefficient(row, value_schedule, index)
    if route == "native67":
        return h58.ROM[row]
    if route == "rn64":
        return h110.quantize(h58.ROM[row], h110.Quant(64, "rn"))
    raise ValueError(route)


def hidden(point: h121.Point, candidate: Candidate) -> h58.FP:
    value_schedule = h167.current_schedule(point)
    observed = point.observed
    magnitude: h58.FP = (
        0,
        observed.raw.sig,
        observed.raw.exponent - 63,
    )
    square = quantized(
        h58.mul_exact(magnitude, magnitude),
        candidate.square,
        value_schedule.square,
    )
    value = h200.normalized_bus(
        coefficient(h58.C6[0], 0, value_schedule, candidate.coefficient)
    )
    for index, row in enumerate(h58.C6[1:]):
        product = quantized(
            h58.mul_exact(value.value(), square),
            candidate.product,
            value_schedule.products[index],
        )
        product_bus = h200.normalized_bus(product)
        constant = h200.normalized_bus(
            coefficient(
                row,
                index + 1,
                value_schedule,
                candidate.coefficient,
            )
        )
        retain = bool(candidate.retain_mask & (1 << index))
        value = h200.fadd_bus(
            product_bus,
            constant,
            candidate.mode,
            normalize=candidate.normalize_retained or not retain,
        )
        if not retain:
            sum_quant = (
                value_schedule.sums[index]
                if candidate.sum_route == "current"
                else h110.Quant(64, "rn")
            )
            value = h200.materialize_bus(value, sum_quant)
    tail = quantized(
        h58.mul_exact(value.value(), square),
        candidate.tail,
        value_schedule.tail,
    )
    if candidate.final_literal:
        result = h200.fadd_bus(
            h200.normalized_bus(h58.ONE),
            h202.jam_bus(tail),
            candidate.mode,
        ).value()
    else:
        result = h110.quantize(
            h58.add_exact(h58.ONE, tail), value_schedule.final_sum
        )
    return h58.neg(result) if point.negate else result


def point_metric(point: h121.Point, candidate: Candidate | None) -> Metric:
    value = (
        h146.hidden_value(point, h167.current_schedule(point))
        if candidate is None
        else hidden(point, candidate)
    )
    return h146.metric(point, value)


def score_signature(datasets, candidate: Candidate | None):
    digest = hashlib.sha256()
    values = []
    for name, points in datasets:
        digest.update(name.encode("ascii"))
        result: Metric = (0, 0, 0)
        for point in points:
            metric = point_metric(point, candidate)
            digest.update(bytes(metric))
            result = h146.add(result, metric)
        values.append(result)
    return values, digest.digest()


def no_worse(value: Metric, baseline: Metric) -> bool:
    return all(new <= old for new, old in zip(value, baseline))


def objective(values) -> tuple[int, int, int]:
    return tuple(
        sum(value[index] for value in values) for index in (0, 2, 1)
    )


def candidates():
    for mode in h200.FADD_MODES:
        for square in SQUARE_ROUTES:
            # The clean physical pass replaces, rather than combines, the
            # inferred coefficient/product/sum scalar representatives.  The
            # all-current combination is h202; mixed proxy/physical routes
            # are deferred unless this coherent bus family leaves a useful
            # separator.
            for coefficient_route in ("native67", "rn64"):
                for product in ("rn64", "chop64", "odd67"):
                    for retain_mask in RETAIN_MASKS:
                        for tail in TAIL_ROUTES:
                            yield Candidate(
                                mode,
                                square,
                                coefficient_route,
                                product,
                                "rn64",
                                retain_mask,
                                tail,
                                False,
                            )


def selection_datasets(controls_per_half: int = 160):
    complete = h202.datasets()
    selected = []
    for name, points in complete:
        if not name.startswith("old-"):
            selected.append((name, points))
            continue
        constrained = []
        controls = []
        for point in points:
            target = (
                constrained
                if point_metric(point, None) != (0, 0, 0)
                else controls
            )
            target.append(point)
        controls.sort(
            key=lambda point: (
                point.observed.raw.sig
                ^ (point.observed.raw.sig >> 19)
                ^ (point.observed.raw.sig >> 43)
                ^ point.observed.raw.index
            )
        )
        selected.append((name, constrained + controls[:controls_per_half]))
    return complete, selected


def main() -> None:
    complete, selected = selection_datasets()
    baselines, baseline_signature = score_signature(selected, None)
    values_to_test = tuple(candidates())
    print(
        f"h203 physical datapath: candidates={len(values_to_test)} "
        f"sample-points={sum(len(points) for _, points in selected)} "
        f"complete-points={sum(len(points) for _, points in complete)}"
    )
    profiles: dict[bytes, list[tuple]] = collections.defaultdict(list)
    raw_ranked = []
    for candidate in values_to_test:
        scores, signature = score_signature(selected, candidate)
        item = (*objective(scores), candidate.short(), candidate, scores)
        raw_ranked.append(item)
        if (
            signature != baseline_signature
            and all(
                no_worse(value, baseline)
                for value, baseline in zip(scores, baselines)
            )
            and any(
                value != baseline
                for value, baseline in zip(scores, baselines)
            )
        ):
            profiles[signature].append(item)
    raw_ranked.sort()
    representatives = sorted(min(items) for items in profiles.values())
    print("  leading raw sample candidates:")
    for item in raw_ranked[:16]:
        print(
            f"    modes/c1/inputs={item[0]}/{item[1]}/{item[2]} "
            f"{item[4].short()}"
        )
    print(
        f"h203 sample gate: "
        f"{sum(len(items) for items in profiles.values())} survivors "
        f"in {len(representatives)} exact profiles"
    )
    if not representatives:
        print("h203 complete gate: 0 survivors")
        return

    complete_baselines = score_signature(complete, None)[0]
    final = []
    for item in representatives:
        candidate = item[4]
        scores, _ = score_signature(complete, candidate)
        if all(
            no_worse(value, baseline)
            for value, baseline in zip(scores, complete_baselines)
        ) and any(
            value != baseline
            for value, baseline in zip(scores, complete_baselines)
        ):
            final.append((*objective(scores), candidate.short(), candidate, scores))
    final.sort()
    print(f"h203 complete gate: {len(final)} survivors")
    for item in final:
        candidate = item[4]
        scores = item[5]
        print(f"  {candidate.short()}")
        for (name, _), baseline, value in zip(
            complete, complete_baselines, scores
        ):
            if value != baseline:
                print(f"    {name:38s} {baseline}->{value}")


if __name__ == "__main__":
    main()
