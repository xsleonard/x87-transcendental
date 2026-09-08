#!/usr/bin/env python3
"""Score global single-site counterfactuals after Round 35.

h193 finds no stable unsigned P/Q correction direction, which is not enough
to reject a physical rounding operation: operand signs can reverse the
architectural correction.  This pass changes the operation itself and
propagates it through Round 35.  It covers every wide P/Q Horner coordinate,
the shared square, the three P-to-S carrier edges, and the Q tail.  Standalone
FSIN and paired-FSINCOS cosine are scored jointly.

All currently failing wide structured-sweep inputs plus deterministic correct
controls form the ranking sample.  Only leading candidates are evaluated on
the complete sweep train/held halves.  A transferable operation must be
componentwise no worse for both lanes in both halves; raw leaders are also
reported so a near miss cannot be mistaken for an untested family.
"""

from __future__ import annotations

import dataclasses

import h58_constraint_search as h58
import h79_table_state_bias as h79
import h110_fsin_standalone as h110
import h131_fsin_table_c1_search as h131
import h134_fsin_table_per_edge_search as h134
import h136_tang_reconstruction_search as h136
import h170_fsin_table_correction_search as h170
import h173_fsin_table_fadd_topology as h173
import h182_table_joint_terminal_edges as h182
import h184_table_lookup_firc_routes as h184
import h188_table_stage_local_pairs as h188
import h190_table_stage_local_c_parity as h190


Metric = h173.Metric
JointMetric = tuple[Metric, Metric]
RN64 = h110.Quant(64, "rn")
AWAY64 = h110.Quant(64, "away")
CHOP65 = h110.Quant(65, "chop")
ROUND34 = h184.Candidate(p_product="rn64")


@dataclasses.dataclass(frozen=True)
class Candidate:
    site: str
    quant: h110.Quant
    extra: tuple[tuple[str, h110.Quant], ...] = ()

    def short(self) -> str:
        terms = ((self.site, self.quant), *self.extra)
        return " ".join(
            f"{site}={quant.short()}" for site, quant in terms
        )

    def quant_for(
        self, site: str, current: h110.Quant
    ) -> h110.Quant:
        for candidate_site, quant in (
            (self.site, self.quant),
            *self.extra,
        ):
            if candidate_site == site:
                return quant
        return current


CURRENT = Candidate("current", RN64)


def selected_quant(
    candidate: Candidate,
    site: str,
    current: h110.Quant,
) -> h110.Quant:
    return candidate.quant_for(site, current)


def materialize(
    exact: h58.FP,
    candidate: Candidate,
    site: str,
    current: h110.Quant,
) -> h58.FP:
    return h110.quantize(
        exact, selected_quant(candidate, site, current)
    )


def horner(
    rows: tuple[int, ...],
    square: h58.FP,
    coefficients: tuple[h110.Quant, ...],
    products: tuple[h110.Quant, ...],
    sums: tuple[h110.Quant, ...],
    prefix: str,
    candidate: Candidate,
) -> h58.FP:
    value = materialize(
        h58.ROM[rows[0]],
        candidate,
        f"{prefix}.coefficient-1",
        coefficients[0],
    )
    for index, row in enumerate(rows[1:], 1):
        product = materialize(
            h58.mul_exact(value, square),
            candidate,
            f"{prefix}.product-{index}",
            products[index - 1],
        )
        coefficient_site = f"{prefix}.coefficient-{index + 1}"
        coefficient = materialize(
            h58.ROM[row],
            candidate,
            coefficient_site,
            coefficients[index],
        )
        value = materialize(
            h58.add_exact(product, coefficient),
            candidate,
            f"{prefix}.sum-{index}",
            sums[index - 1],
        )
    return value


def q_prefix(shared: bool, index: int, kind: str) -> str:
    if kind == "coefficient" and index == 6:
        return "q-shared" if shared else "q-standalone"
    return "q"


def q_horner(
    point: h188.Point,
    square: h58.FP,
    shared: bool,
    candidate: Candidate,
) -> h58.FP:
    schedule = h134.CURRENT if shared else point.base
    coefficients = schedule.q_coefficients
    products = schedule.q_products
    sums = schedule.q_sums
    value = materialize(
        h58.ROM[h58.C6[0]],
        candidate,
        "q.coefficient-1",
        coefficients[0],
    )
    for index, row in enumerate(h58.C6[1:], 1):
        product = materialize(
            h58.mul_exact(value, square),
            candidate,
            f"q.product-{index}",
            products[index - 1],
        )
        coefficient = materialize(
            h58.ROM[row],
            candidate,
            f"{q_prefix(shared, index + 1, 'coefficient')}.coefficient-{index + 1}",
            coefficients[index],
        )
        value = materialize(
            h58.add_exact(product, coefficient),
            candidate,
            f"q.sum-{index}",
            sums[index - 1],
        )
    return value


def hidden_values(
    point: h188.Point, candidate: Candidate
) -> tuple[h58.FP, h58.FP]:
    prepared = point.joint.observed.point
    square = materialize(
        h58.mul_exact(prepared.a, prepared.a),
        candidate,
        "square",
        RN64,
    )
    schedule = point.base
    p_coefficients = (*schedule.p_coefficients[:-1], AWAY64)
    p_sums = (*schedule.p_sums[:-1], CHOP65)
    p = horner(
        h58.S6,
        square,
        p_coefficients,
        schedule.p_products,
        p_sums,
        "p",
        candidate,
    )
    q_standalone = q_horner(point, square, False, candidate)
    q_shared = q_horner(point, square, True, candidate)

    p_square = materialize(
        h58.mul_exact(p, square),
        candidate,
        "p-square",
        RN64,
    )
    correction = materialize(
        h58.mul_exact(p_square, prepared.a),
        candidate,
        "p-a",
        RN64,
    )
    sine_a = materialize(
        h58.add_exact(prepared.a, correction),
        candidate,
        "sine-sum",
        RN64,
    )
    sine_a = h79.bias_toward_zero(sine_a, 5)
    sine_correction = h58.add_exact(
        sine_a, h58.neg(prepared.a)
    )

    def state(q: h58.FP) -> h136.State:
        tail = materialize(
            h58.mul_exact(q, square),
            candidate,
            "q-tail",
            RN64,
        )
        return h136.State(prepared.a, sine_correction, tail)

    sine = h184.values(
        h184.Point(point.joint, state(q_standalone), None),
        ROUND34,
    )[0]
    cosine = h184.values(
        h184.Point(point.joint, state(q_shared), None),
        ROUND34,
    )[1]
    return sine, cosine


def point_metric(
    point: h188.Point, candidate: Candidate
) -> JointMetric:
    sine, cosine = hidden_values(point, candidate)
    return (
        h170.point_metric(point.joint.observed, sine),
        h182.point_metric(
            point.joint.cosine_outputs,
            point.joint.cosine_c1,
            cosine,
        ),
    )


def add(left: JointMetric, right: JointMetric) -> JointMetric:
    return tuple(
        h170.add(old, new) for old, new in zip(left, right)
    )  # type: ignore[return-value]


def score(
    points: list[h188.Point], candidate: Candidate
) -> JointMetric:
    result: JointMetric = ((0, 0, 0), (0, 0, 0))
    for point in points:
        result = add(result, point_metric(point, candidate))
    return result


def objective(values: list[JointMetric]) -> tuple[int, int, int]:
    return tuple(
        sum(lane[index] for value in values for lane in value)
        for index in (0, 2, 1)
    )


def no_worse(value: JointMetric, baseline: JointMetric) -> bool:
    return all(
        h173.no_worse(new, old)
        for new, old in zip(value, baseline)
    )


def quant_options(exact: bool) -> tuple[h110.Quant, ...]:
    values = tuple(
        h110.Quant(bits, mode)
        for bits in range(64, 73)
        for mode in ("rn", "chop", "away", "odd")
    )
    return ((h110.EXACT,) + values) if exact else values


def candidates() -> tuple[Candidate, ...]:
    sites: list[tuple[str, bool]] = [("square", False)]
    for prefix, terms in (("p", 6), ("q", 6)):
        sites.extend(
            (f"{prefix}.coefficient-{index}", False)
            for index in range(1, terms + 1)
            if not (prefix == "q" and index == terms)
        )
        sites.extend(
            (f"{prefix}.product-{index}", True)
            for index in range(1, terms)
        )
        sites.extend(
            (f"{prefix}.sum-{index}", False)
            for index in range(1, terms)
        )
    sites.extend(
        (
            ("q-standalone.coefficient-6", False),
            ("q-shared.coefficient-6", False),
            ("p-square", False),
            ("p-a", False),
            ("sine-sum", False),
            ("q-tail", False),
        )
    )
    return tuple(
        Candidate(site, quant)
        for site, exact in sites
        for quant in quant_options(exact)
    )


def sample(
    partitions: list[tuple[str, list[h188.Point]]],
    controls_per_half: int,
) -> list[tuple[str, list[h188.Point]]]:
    result = []
    for name, points in partitions:
        constrained = []
        controls = []
        for point in points:
            target = (
                constrained
                if point_metric(point, CURRENT)
                != ((0, 0, 0), (0, 0, 0))
                else controls
            )
            target.append(point)
        controls.sort(
            key=lambda point: (
                point.joint.observed.point.raw.sig
                ^ (point.joint.observed.point.raw.sig >> 23)
                ^ point.joint.observed.index
                ^ point.joint.observed.signed_n
            )
        )
        result.append(
            (name, constrained + controls[:controls_per_half])
        )
    return result


def main() -> None:
    points = [
        h188.prepare(point)
        for point in h184.dataset("sweep")
        if point.observed.family == "wide"
    ]
    for point in points:
        actual = point_metric(point, CURRENT)
        expected = h190.metric(point, True)
        if actual != expected:
            raise SystemExit(
                "h194 baseline differs from Round 35: "
                f"line {point.joint.observed.index + 1} "
                f"{actual}!={expected}"
            )
    partitions = [
        (
            split,
            [
                point
                for point in points
                if h131.is_train(point.joint.observed)
                == (split == "train")
            ],
        )
        for split in ("train", "held")
    ]
    samples = sample(partitions, 600)
    sample_baselines = [
        score(selected, CURRENT) for _, selected in samples
    ]
    complete_baselines = [
        score(selected, CURRENT) for _, selected in partitions
    ]
    print(
        f"h194 Round-35 counterfactuals: wide-sweep={len(points)} "
        f"sample={sum(len(selected) for _, selected in samples)} "
        f"candidates={len(candidates())}"
    )
    for (name, selected), baseline in zip(
        partitions, complete_baselines
    ):
        print(
            f"  baseline {name:5s} n={len(selected):5d} "
            f"sine={baseline[0]} cosine={baseline[1]}"
        )

    ranked = []
    for candidate in candidates():
        values = [
            score(selected, candidate) for _, selected in samples
        ]
        ranked.append(
            (*objective(values), candidate.short(), candidate, values)
        )
    ranked.sort()
    print("  leading sample counterfactuals:")
    for modes, c1, inputs, _, candidate, values in ranked[:20]:
        print(
            f"    modes/c1/inputs={modes}/{c1}/{inputs} "
            f"{candidate.short()} values={values}"
        )

    sample_survivors = [
        item
        for item in ranked
        if all(
            no_worse(value, baseline)
            for value, baseline in zip(item[-1], sample_baselines)
        )
        and any(
            value != baseline
            for value, baseline in zip(item[-1], sample_baselines)
        )
    ]
    print(
        f"  sample componentwise survivors: {len(sample_survivors)}"
    )
    complete_candidates = [item[-2] for item in sample_survivors]
    for item in ranked:
        candidate = item[-2]
        if candidate in complete_candidates:
            continue
        complete_candidates.append(candidate)
        if len(complete_candidates) >= len(sample_survivors) + 32:
            break

    complete = []
    for candidate in complete_candidates:
        values = [
            score(selected, candidate)
            for _, selected in partitions
        ]
        complete.append((objective(values), candidate, values))
    complete.sort(key=lambda item: (*item[0], item[1].short()))
    print("  leading complete counterfactuals:")
    for objective_value, candidate, values in complete[:20]:
        transferable = all(
            no_worse(value, baseline)
            for value, baseline in zip(values, complete_baselines)
        )
        changed = any(
            value != baseline
            for value, baseline in zip(values, complete_baselines)
        )
        status = "SURVIVOR" if transferable and changed else "reject"
        print(
            f"    {status:8s} modes/c1/inputs="
            f"{objective_value[0]}/{objective_value[1]}/{objective_value[2]} "
            f"{candidate.short()} values={values}"
        )
    survivors = [
        (candidate, values)
        for _, candidate, values in complete
        if all(
            no_worse(value, baseline)
            for value, baseline in zip(values, complete_baselines)
        )
        and any(
            value != baseline
            for value, baseline in zip(values, complete_baselines)
        )
    ]
    print(
        f"h194 complete componentwise survivors: {len(survivors)} "
        f"from {len(sample_survivors)} sample survivors; "
        f"raw-complete-leaders={len(complete_candidates) - len(sample_survivors)}"
    )


if __name__ == "__main__":
    main()
