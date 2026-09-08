#!/usr/bin/env python3
"""Apply h200's literal FADD carrier to FSIN's polynomial cosine path.

The remaining polynomial residue is dominated by the odd-quadrant internal
cosine producer, where the validated scalar representatives contain the
irregular 65-bit Horner, 67-bit sticky, and 71/72-bit tail effects.  This is
the higher-value use of the patent datapath: replace each exact scalar add
with the FAMUBUS alignment/sticky/borrow operation before applying any
microcode-selected materialization.

Five-bit masks retain the unrounded normalized FADD carrier at selected
Horner stages.  The final ``1+tail`` subtraction is tested both in its
current exact representative and through the same literal carrier.  Three
starting schedules determine whether the physical FADD path layers on top
of Round 33 or subsumes its conditional product/sum representatives:

* ``round33``: current Rounds 30--33;
* ``round32``: current through Round 32, before the product-5 refinement;
* ``round31``: current through Round 31, before both late-Horner rules.

Acceptance is componentwise across the old train/held halves and every
pooled focused capture h147/h148/h151/h158/h161/h163/h165/h168.  Exact
metric profiles are collapsed before complete reporting.
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
import h157_fsin_cosine_two_predicate as h157
import h162_fsin_cosine_round32_residual_search as h162
import h167_fsin_cosine_round33_operation_search as h167
import h168_fsin_cosine_round33_operation_discriminator as h168
import h200_p5_fadd_bitvector as h200


Metric = h146.Metric
FOUNDATIONS = ("round33", "round32", "round31")


@dataclasses.dataclass(frozen=True)
class Candidate:
    mode: str = "scalar"
    foundation: str = "round33"
    mask: int = 0
    final_literal: bool = False
    normalize_retained: bool = True

    def short(self) -> str:
        if self.mode == "scalar":
            return "current Round33 scalar"
        stages = "".join(
            str(index + 1)
            for index in range(5)
            if self.mask & (1 << index)
        )
        final = "literal" if self.final_literal else "exact"
        normalization = "norm" if self.normalize_retained else "raw"
        return (
            f"{self.mode}/{normalization} {self.foundation} "
            f"retain[{stages or '-'}] final={final}"
        )


CURRENT = Candidate()


def schedule(point: h121.Point, foundation: str) -> h119.Schedule:
    if foundation == "round33":
        return h167.current_schedule(point)
    if foundation == "round32":
        return h162.baseline_schedule(point)
    if foundation == "round31":
        return h157.round31_schedule(point)[1]
    raise ValueError(foundation)


def jam_bus(value: h58.FP) -> h200.Bus:
    return h200.normalized_bus(
        h110.quantize(value, h110.Quant(67, "odd"))
    )


def literal_hidden(point: h121.Point, candidate: Candidate) -> h58.FP:
    value_schedule = schedule(point, candidate.foundation)
    observed = point.observed
    magnitude: h58.FP = (
        0,
        observed.raw.sig,
        observed.raw.exponent - 63,
    )
    square = h110.quantize(
        h58.mul_exact(magnitude, magnitude), value_schedule.square
    )
    value = h200.normalized_bus(
        h119.coefficient(h58.C6[0], value_schedule, 0)
    )
    for index, row in enumerate(h58.C6[1:]):
        product = h110.quantize(
            h58.mul_exact(value.value(), square),
            value_schedule.products[index],
        )
        product_bus = h200.normalized_bus(product)
        coefficient = h200.normalized_bus(
            h119.coefficient(row, value_schedule, index + 1)
        )
        retain = bool(candidate.mask & (1 << index))
        value = h200.fadd_bus(
            product_bus,
            coefficient,
            candidate.mode,
            normalize=candidate.normalize_retained or not retain,
        )
        if not retain:
            value = h200.materialize_bus(
                value, value_schedule.sums[index]
            )
    tail = h110.quantize(
        h58.mul_exact(value.value(), square), value_schedule.tail
    )
    if candidate.final_literal:
        hidden = h200.fadd_bus(
            h200.normalized_bus(h58.ONE),
            jam_bus(tail),
            candidate.mode,
        ).value()
    else:
        hidden = h110.quantize(
            h58.add_exact(h58.ONE, tail), value_schedule.final_sum
        )
    return h58.neg(hidden) if point.negate else hidden


def hidden(point: h121.Point, candidate: Candidate) -> h58.FP:
    if candidate == CURRENT:
        return h146.hidden_value(point, h167.current_schedule(point))
    return literal_hidden(point, candidate)


def point_metric(point: h121.Point, candidate: Candidate) -> Metric:
    return h146.metric(point, hidden(point, candidate))


def score_signature(datasets, candidate: Candidate):
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


def candidates() -> tuple[Candidate, ...]:
    return tuple(
        Candidate(mode, foundation, mask, final_literal)
        for mode in h200.FADD_MODES
        for foundation in FOUNDATIONS
        for mask in range(32)
        for final_literal in (False, True)
    )


def datasets():
    values = [
        (dataset.name, dataset.points) for dataset in h167.datasets()
    ]
    fresh168 = h168.load_capture(
        h168.DEFAULT_OUTPUT,
        h121.ROOT / "capture-kit-captures" / "skylake-fsin-h168",
    )
    values.append(("h168", fresh168))
    metadata = h168.DEFAULT_METADATA.read_text().splitlines()
    for mechanism in h168.CANDIDATES:
        values.append(
            (
                f"h168-{mechanism.name}",
                [
                    point
                    for point, line in zip(fresh168, metadata)
                    if mechanism.name
                    in tuple(
                        item.split(":", 1)[0]
                        for item in line.split()[-1].split(",")
                    )
                ],
            )
        )
    return values


def main() -> None:
    values = datasets()
    baselines, baseline_signature = score_signature(values, CURRENT)
    print(
        f"h202 literal polynomial FADD: candidates={len(candidates())} "
        f"datasets={len(values)} points="
        f"{sum(len(points) for _, points in values)}"
    )
    for (name, points), baseline in zip(values, baselines):
        print(f"  baseline {name:38s} n={len(points):5d} {baseline}")

    profiles: dict[bytes, list[tuple]] = collections.defaultdict(list)
    raw_ranked = []
    for candidate in candidates():
        scores, signature = score_signature(values, candidate)
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
    print("  leading raw candidates:")
    for item in raw_ranked[:16]:
        print(
            f"    modes/c1/inputs={item[0]}/{item[1]}/{item[2]} "
            f"{item[4].short()}"
        )
    print(
        f"h202 componentwise gate: "
        f"{sum(len(items) for items in profiles.values())} survivors "
        f"in {len(representatives)} exact profiles"
    )
    for item in representatives:
        candidate = item[4]
        scores = item[5]
        print(f"  {candidate.short()}")
        for (name, _), baseline, value in zip(values, baselines, scores):
            if value != baseline:
                print(f"    {name:38s} {baseline}->{value}")


if __name__ == "__main__":
    main()
