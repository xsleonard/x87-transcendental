#!/usr/bin/env python3
"""Search structural path gates for h173's FADD schedules.

A single alternate addition tree fails in h173.  Pentium microcode already
has distinct direct/M66-reduced and narrow/wide paths, and odd quadrants
reconstruct the cosine lane.  This pass conditionally applies each h173
schedule under only those architectural path predicates.  It does not use
low result bits, table cells, or fitted coefficients.
"""

from __future__ import annotations

import dataclasses

import h110_fsin_standalone as h110
import h131_fsin_table_c1_search as h131
import h135_fsin_table_terminal_discriminator as h135
import h140_p5_fmul_discriminator as h140
import h170_fsin_table_correction_search as h170
import h171_fsin_table_correction_discriminator as h171
import h173_fsin_table_fadd_topology as h173


Metric = h173.Metric


@dataclasses.dataclass(frozen=True)
class Gate:
    name: str
    source: str | None = None
    family: str | None = None
    parity: int | None = None

    def selected(self, point: h131.Observed) -> bool:
        return (
            (self.source is None or point.source == self.source)
            and (self.family is None or point.family == self.family)
            and (
                self.parity is None
                or (point.signed_n & 1) == self.parity
            )
        )


@dataclasses.dataclass
class Dataset:
    name: str
    terms: list[h173.Terms]
    old: list[Metric]
    selected: list[tuple[int, ...]]
    baseline: Metric


GATES = (
    *(Gate(source, source=source) for source in ("direct", "reduced")),
    *(Gate(family, family=family) for family in ("narrow", "wide")),
    Gate("sine-lane", parity=0),
    Gate("cosine-lane", parity=1),
    *(
        Gate(f"{source}-{family}", source=source, family=family)
        for source in ("direct", "reduced")
        for family in ("narrow", "wide")
    ),
    *(
        Gate(
            f"{source}-{'sine' if parity == 0 else 'cosine'}",
            source=source,
            parity=parity,
        )
        for source in ("direct", "reduced")
        for parity in (0, 1)
    ),
    *(
        Gate(
            f"{family}-{'sine' if parity == 0 else 'cosine'}",
            family=family,
            parity=parity,
        )
        for family in ("narrow", "wide")
        for parity in (0, 1)
    ),
)


def make_dataset(
    name: str, points: list[h131.Observed]
) -> Dataset:
    terms = [h173.make_terms(point) for point in points]
    old = [
        h170.point_metric(
            item.point, h173.hidden(item, h173.CURRENT)
        )
        for item in terms
    ]
    selected = [
        tuple(
            index
            for index, gate in enumerate(GATES)
            if gate.selected(item.point)
        )
        for item in terms
    ]
    baseline: Metric = (0, 0, 0)
    for value in old:
        baseline = h170.add(baseline, value)
    return Dataset(name, terms, old, selected, baseline)


def scores(
    dataset: Dataset, candidate: h173.Candidate
) -> tuple[Metric, ...]:
    deltas: list[Metric] = [
        (0, 0, 0) for _ in GATES
    ]
    for item, old, selected in zip(
        dataset.terms, dataset.old, dataset.selected
    ):
        new = h170.point_metric(
            item.point, h173.hidden(item, candidate)
        )
        delta: Metric = tuple(
            right - left
            for left, right in zip(old, new)
        )  # type: ignore[assignment]
        if delta == (0, 0, 0):
            continue
        for gate_index in selected:
            deltas[gate_index] = h170.add(
                deltas[gate_index], delta
            )
    return tuple(
        h170.add(dataset.baseline, delta)
        for delta in deltas
    )


def candidates():
    for topology in h173.TOPOLOGIES:
        for first in h173.QUANTS:
            for second in h173.QUANTS:
                candidate = h173.Candidate(
                    topology, first, second
                )
                if candidate != h173.CURRENT:
                    yield candidate


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
            f"h174 baseline {dataset.name:11s} "
            f"n={len(dataset.terms):5d} {dataset.baseline}"
        )

    survivors = []
    tested = 0
    for candidate in candidates():
        tested += len(GATES)
        candidate_scores = tuple(
            scores(dataset, candidate)
            for dataset in selection
        )
        for gate_index, gate in enumerate(GATES):
            values = tuple(
                row[gate_index] for row in candidate_scores
            )
            if not all(
                h173.no_worse(value, dataset.baseline)
                for value, dataset in zip(values, selection)
            ):
                continue
            if not any(
                value != dataset.baseline
                for value, dataset in zip(values, selection[:2])
            ):
                continue
            survivors.append(
                (candidate, gate, values)
            )
    print(
        f"h174 selection: {len(survivors)} survivors "
        f"from {tested} path-gated schedules"
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
    for candidate, gate, selected_values in survivors:
        gate_index = GATES.index(gate)
        values = tuple(
            scores(dataset, candidate)[gate_index]
            for dataset in validation
        )
        if all(
            h173.no_worse(value, dataset.baseline)
            for value, dataset in zip(values, validation)
        ):
            final.append(
                (candidate, gate, selected_values, values)
            )
    final.sort(
        key=lambda item: tuple(
            value
            for scores_ in (item[2], item[3])
            for score in scores_
            for value in score
        )
    )
    print(f"h174 complete gates: {len(final)} survivors")
    for candidate, gate, selected_values, values in final[:40]:
        print(f"  {gate.name}: {candidate.short()}")
        for dataset, value in zip(
            (*selection, *validation),
            (*selected_values, *values),
        ):
            if value != dataset.baseline:
                print(
                    f"    {dataset.name:11s} "
                    f"{dataset.baseline}->{value}"
                )


if __name__ == "__main__":
    main()
