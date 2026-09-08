#!/usr/bin/env python3
"""Search P5-plausible FADD order and carrier materializations.

h171 rejects changing only the final RN67 Tang correction.  This pass keeps
the solved P/Q producers and asymmetric narrow C*p route, but varies how the
four reconstruction terms are paired and accumulated.  Each topology has
two independently materialized FADD carriers selected from exact or the
physical 64/67/69-bit grids.

Selection begins on independent sweep halves and fresh h171.  Survivors are
then gated on dense halves, h135, and h140.  This is a topology test, not a
conditional Boolean search.
"""

from __future__ import annotations

import dataclasses

import h58_constraint_search as h58
import h110_fsin_standalone as h110
import h131_fsin_table_c1_search as h131
import h135_fsin_table_terminal_discriminator as h135
import h139_p5_fmul_route_search as h139
import h140_p5_fmul_discriminator as h140
import h143_p5_fmul_c_parity as h143
import h169_fsin_table_round33_tomography as h169
import h170_fsin_table_correction_search as h170
import h171_fsin_table_correction_discriminator as h171


Metric = tuple[int, int, int]


@dataclasses.dataclass(frozen=True)
class Terms:
    point: h131.Observed
    lead: h58.FP
    linear: h58.FP
    q_product: h58.FP
    p_product: h58.FP


@dataclasses.dataclass(frozen=True)
class Candidate:
    topology: str
    first: h110.Quant | None
    second: h110.Quant | None

    def short(self) -> str:
        first = "exact" if self.first is None else self.first.short()
        second = (
            "exact" if self.second is None else self.second.short()
        )
        return f"{self.topology} first={first} second={second}"


@dataclasses.dataclass
class Dataset:
    name: str
    terms: list[Terms]
    baseline: Metric


TOPOLOGIES = (
    "correction",
    "lead-linear",
    "lead-nonlinear",
    "lead-q",
    "lead-p",
    "serial-q-p",
    "serial-p-q",
)
QUANTS: tuple[h110.Quant | None, ...] = (
    None,
    *(
        h110.Quant(bits, mode)
        for bits in (64, 67, 69)
        for mode in ("rn", "chop", "away", "odd")
    ),
)
CURRENT = Candidate(
    "correction", None, h110.Quant(67, "rn")
)


def make_terms(point: h131.Observed) -> Terms:
    state, lead, cross, subtract, route = h169.lane_state(
        point
    )
    linear = h58.mul_exact(cross, state.residual)
    p_product = (
        h139.p5_fmul(
            cross, state.sine_correction, route
        )
        if route is not None
        else h58.mul_exact(cross, state.sine_correction)
    )
    if subtract:
        linear = h58.neg(linear)
        p_product = h58.neg(p_product)
    q_product = h58.mul_exact(lead, state.cosine_tail)
    return Terms(point, lead, linear, q_product, p_product)


def quantize(
    value: h58.FP, quant: h110.Quant | None
) -> h58.FP:
    return value if quant is None else h110.quantize(value, quant)


def finish(point: h131.Observed, value: h58.FP) -> h58.FP:
    quadrant = point.signed_n & 3
    if not (quadrant & 1) and point.point.raw.sign:
        value = h58.neg(value)
    return h58.neg(value) if quadrant & 2 else value


def hidden(terms: Terms, candidate: Candidate) -> h58.FP:
    lead = terms.lead
    linear = terms.linear
    q_product = terms.q_product
    p_product = terms.p_product
    first = candidate.first
    second = candidate.second
    if candidate.topology == "correction":
        partial = quantize(
            h58.add_exact(q_product, p_product), first
        )
        correction = quantize(
            h58.add_exact(linear, partial), second
        )
        value = h58.add_exact(lead, correction)
    elif candidate.topology == "lead-linear":
        partial = quantize(h58.add_exact(lead, linear), first)
        nonlinear = quantize(
            h58.add_exact(q_product, p_product), second
        )
        value = h58.add_exact(partial, nonlinear)
    elif candidate.topology == "lead-nonlinear":
        nonlinear = quantize(
            h58.add_exact(q_product, p_product), first
        )
        partial = quantize(
            h58.add_exact(lead, nonlinear), second
        )
        value = h58.add_exact(partial, linear)
    elif candidate.topology == "lead-q":
        partial = quantize(
            h58.add_exact(lead, q_product), first
        )
        cross = quantize(
            h58.add_exact(linear, p_product), second
        )
        value = h58.add_exact(partial, cross)
    elif candidate.topology == "lead-p":
        partial = quantize(
            h58.add_exact(lead, p_product), first
        )
        other = quantize(
            h58.add_exact(linear, q_product), second
        )
        value = h58.add_exact(partial, other)
    elif candidate.topology == "serial-q-p":
        partial = quantize(h58.add_exact(lead, linear), first)
        partial = quantize(
            h58.add_exact(partial, q_product), second
        )
        value = h58.add_exact(partial, p_product)
    elif candidate.topology == "serial-p-q":
        partial = quantize(h58.add_exact(lead, linear), first)
        partial = quantize(
            h58.add_exact(partial, p_product), second
        )
        value = h58.add_exact(partial, q_product)
    else:
        raise ValueError(candidate.topology)
    return finish(terms.point, value)


def score(terms: list[Terms], candidate: Candidate) -> Metric:
    result: Metric = (0, 0, 0)
    for item in terms:
        result = h170.add(
            result,
            h170.point_metric(
                item.point, hidden(item, candidate)
            ),
        )
    return result


def make_dataset(
    name: str, points: list[h131.Observed]
) -> Dataset:
    terms = [make_terms(point) for point in points]
    return Dataset(name, terms, score(terms, CURRENT))


def no_worse(value: Metric, baseline: Metric) -> bool:
    return all(
        candidate <= old
        for candidate, old in zip(value, baseline)
    )


def main() -> None:
    sweep = h131.load_dataset(
        "sweep", h131.INPUTS / "sweep_inputs.txt"
    )
    fresh171 = h171.load_capture(
        h171.DEFAULT_OUTPUT,
        h171.ROOT
        / "capture-kit-captures"
        / "skylake-fsin-h171",
    )
    selection = (
        make_dataset(
            "sweep-train",
            [point for point in sweep if h131.is_train(point)],
        ),
        make_dataset(
            "sweep-held",
            [point for point in sweep if not h131.is_train(point)],
        ),
        make_dataset("h171", fresh171),
    )
    for dataset in selection:
        print(
            f"h173 baseline {dataset.name:11s} "
            f"n={len(dataset.terms):5d} {dataset.baseline}"
        )

    survivors: list[tuple[Candidate, tuple[Metric, ...]]] = []
    tested = 0
    for topology in TOPOLOGIES:
        for first in QUANTS:
            for second in QUANTS:
                candidate = Candidate(topology, first, second)
                tested += 1
                scores = tuple(
                    score(dataset.terms, candidate)
                    for dataset in selection
                )
                if not all(
                    no_worse(value, dataset.baseline)
                    for value, dataset in zip(scores, selection)
                ):
                    continue
                if not any(
                    value != dataset.baseline
                    for value, dataset in zip(scores, selection[:2])
                ):
                    continue
                survivors.append((candidate, scores))

    print(
        f"h173 selection: {len(survivors)} survivors "
        f"from {tested} topology/carrier schedules"
    )
    if not survivors:
        return

    dense = h131.load_dataset(
        "dense", h131.INPUTS / "dense_qn.txt"
    )
    fresh135 = h135.load_capture(
        h135.DEFAULT_OUTPUT,
        h135.DEFAULT_METADATA,
        h135.ROOT
        / "capture-kit-captures"
        / "skylake-fsin-h135",
    )
    validation = (
        make_dataset(
            "dense-train",
            [point for point in dense if h131.is_train(point)],
        ),
        make_dataset(
            "dense-held",
            [point for point in dense if not h131.is_train(point)],
        ),
        make_dataset(
            "h135",
            [
                point
                for points in fresh135.values()
                for point in points
            ],
        ),
        make_dataset(
            "h140",
            h140.load_capture(
                h140.DEFAULT_OUTPUT,
                h140.ROOT
                / "capture-kit-captures"
                / "skylake-fsin-h140",
            ),
        ),
    )
    final = []
    for candidate, selected_scores in survivors:
        values = tuple(
            score(dataset.terms, candidate)
            for dataset in validation
        )
        if all(
            no_worse(value, dataset.baseline)
            for value, dataset in zip(values, validation)
        ):
            final.append(
                (candidate, selected_scores, values)
            )
    final.sort(
        key=lambda item: tuple(
            value
            for scores in (item[1], item[2])
            for score in scores
            for value in score
        )
    )
    print(
        f"h173 complete gates: {len(final)} survivors"
    )
    for candidate, selected_scores, values in final[:40]:
        print(f"  {candidate.short()}")
        for dataset, value in zip(
            (*selection, *validation),
            (*selected_scores, *values),
        ):
            if value != dataset.baseline:
                print(
                    f"    {dataset.name:11s} "
                    f"{dataset.baseline}->{value}"
                )


if __name__ == "__main__":
    main()
