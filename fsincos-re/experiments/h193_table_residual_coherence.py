#!/usr/bin/env python3
"""Measure global coherence in the remaining wide-table residuals.

The local stage grids through h192 answer whether a particular nearby pair
of materializations improves output counts.  This pass instead asks whether
the remaining table failures share a compact cause.  It evaluates the exact
Round-35 standalone-FSIN sine and paired-FSINCOS cosine carriers, inverts
both hardware lanes into intervals, projects their midpoint corrections
onto approximate P/Q axes, and ranks physical P5 trace predicates on
deterministic train/held halves.

No candidate operation is fitted here.  A useful result is a correction
signature or physical predicate that independently enriches residuals with
meaningful coverage and few correct controls.  Direction is reported but is
not required to remain fixed: the same rounding operation can move P/Q in
opposite directions when operand signs or quadrant orientation change.
Structural cell/path labels are reported separately and cannot qualify as
mechanisms.
"""

from __future__ import annotations

import collections
import dataclasses
import itertools
import math
from fractions import Fraction

import h58_constraint_search as h58
import h110_fsin_standalone as h110
import h131_fsin_table_c1_search as h131
import h134_fsin_table_per_edge_search as h134
import h146_fsin_cosine_boolean_search as h146
import h155_fsin_cosine_state_tomography as h155
import h169_fsin_table_round33_tomography as h169
import h170_fsin_table_correction_search as h170
import h184_table_lookup_firc_routes as h184
import h188_table_stage_local_pairs as h188
import h190_table_stage_local_c_parity as h190


RN64 = h110.Quant(64, "rn")
RN67 = h110.Quant(67, "rn")
AWAY64 = h110.Quant(64, "away")
CHOP65 = h110.Quant(65, "chop")
LABELS = ("p+", "p-", "q+", "q-", "tied")


@dataclasses.dataclass(frozen=True)
class Row:
    point: h188.Point
    split: str
    sine_kind: str
    cosine_kind: str
    dp: Fraction
    dq: Fraction
    label: str
    features: dict[str, int]


def coefficient(row: int, quant: h110.Quant) -> h58.FP:
    return h134.coefficient(row, quant)


def add_quant_features(
    result: dict[str, int],
    prefix: str,
    exact: h58.FP,
    quant: h110.Quant,
    left: h58.FP | None = None,
    right: h58.FP | None = None,
) -> None:
    result.update(
        h146.rounded_features(prefix, exact, quant, left, right)
    )


def horner_trace(
    result: dict[str, int],
    prefix: str,
    rows: tuple[int, ...],
    square: h58.FP,
    coefficient_quants: tuple[h110.Quant, ...],
    product_quants: tuple[h110.Quant, ...],
    sum_quants: tuple[h110.Quant, ...],
) -> h58.FP:
    value = coefficient(rows[0], coefficient_quants[0])
    for index, row in enumerate(rows[1:], 1):
        product_exact = h58.mul_exact(value, square)
        add_quant_features(
            result,
            f"{prefix}.product-{index}",
            product_exact,
            product_quants[index - 1],
            value,
            square,
        )
        product = h110.quantize(
            product_exact, product_quants[index - 1]
        )
        raw_constant = h58.ROM[row]
        add_quant_features(
            result,
            f"{prefix}.coefficient-{index}",
            raw_constant,
            coefficient_quants[index],
        )
        constant = coefficient(row, coefficient_quants[index])
        sum_exact = h58.add_exact(product, constant)
        add_quant_features(
            result,
            f"{prefix}.sum-{index}",
            sum_exact,
            sum_quants[index - 1],
        )
        value = h110.quantize(sum_exact, sum_quants[index - 1])
    return value


def trace(point: h188.Point) -> dict[str, int]:
    observed = point.joint.observed
    prepared = observed.point
    result = {
        "global.reduced": int(observed.source == "reduced"),
        "global.quadrant": observed.signed_n & 3,
        "global.cell": prepared.cell,
        "global.input-sign": prepared.raw.sign,
        "global.a-low3": prepared.a[1] & 7,
        "global.a-low6": prepared.a[1] & 63,
    }
    square_exact = h58.mul_exact(prepared.a, prepared.a)
    add_quant_features(
        result,
        "square",
        square_exact,
        RN64,
        prepared.a,
        prepared.a,
    )
    square = h110.quantize(square_exact, RN64)
    current = h134.CURRENT
    p_coefficients = (*current.p_coefficients[:-1], AWAY64)
    p_sums = (*current.p_sums[:-1], CHOP65)
    p = horner_trace(
        result,
        "p",
        h58.S6,
        square,
        p_coefficients,
        current.p_products,
        p_sums,
    )
    q_standalone_coefficients = (
        *current.q_coefficients[:-1],
        AWAY64,
    )
    q_standalone = horner_trace(
        result,
        "q-standalone",
        h58.C6,
        square,
        q_standalone_coefficients,
        current.q_products,
        current.q_sums,
    )
    q_shared = horner_trace(
        result,
        "q-shared",
        h58.C6,
        square,
        current.q_coefficients,
        current.q_products,
        current.q_sums,
    )

    p_square_exact = h58.mul_exact(p, square)
    add_quant_features(
        result,
        "state.p-square",
        p_square_exact,
        RN64,
        p,
        square,
    )
    p_square = h110.quantize(p_square_exact, RN64)
    correction_exact = h58.mul_exact(p_square, prepared.a)
    add_quant_features(
        result,
        "state.p-correction",
        correction_exact,
        RN64,
        p_square,
        prepared.a,
    )
    correction = h110.quantize(correction_exact, RN64)
    sine_sum_exact = h58.add_exact(prepared.a, correction)
    add_quant_features(
        result, "state.sine-sum", sine_sum_exact, RN64
    )
    for name, q in (
        ("standalone", q_standalone),
        ("shared", q_shared),
    ):
        q_tail_exact = h58.mul_exact(q, square)
        add_quant_features(
            result,
            f"state.q-tail-{name}",
            q_tail_exact,
            RN64,
            q,
            square,
        )
    return result


def cosine_observed(point: h188.Point) -> h131.Observed:
    return dataclasses.replace(
        point.joint.observed,
        outputs=point.joint.cosine_outputs,
        c1=point.joint.cosine_c1,
    )


def projected_label(dp: Fraction, dq: Fraction) -> str:
    if abs(dp) > abs(dq):
        return "p+" if dp > 0 else "p-"
    if abs(dq) > abs(dp):
        return "q+" if dq > 0 else "q-"
    return "tied"


def make_row(point: h188.Point) -> Row:
    sine_hidden, cosine_hidden = h190.hidden_values(point, True)
    sine_kind, ds = h169.magnitude_relation(
        point.joint.observed, sine_hidden
    )
    cosine_kind, dc = h169.magnitude_relation(
        cosine_observed(point), cosine_hidden
    )
    sj = h155.fp_fraction(point.joint.observed.point.sin_t)
    cj = h155.fp_fraction(point.joint.observed.point.cos_t)
    dp = cj * ds - sj * dc
    dq = sj * ds + cj * dc
    label = (
        "inside"
        if sine_kind == "inside" and cosine_kind == "inside"
        else projected_label(dp, dq)
    )
    return Row(
        point,
        "train" if h131.is_train(point.joint.observed) else "held",
        sine_kind,
        cosine_kind,
        dp,
        dq,
        label,
        trace(point),
    )


def scaled(value: Fraction, bits: int) -> int:
    return h155.rounded_scaled(value, bits)


def signature_report(rows: list[Row]) -> None:
    outside = [row for row in rows if row.label != "inside"]
    print(f"  joint labels: {dict(collections.Counter(row.label for row in rows))}")
    print(
        "  lane relations: "
        f"sine={dict(collections.Counter(row.sine_kind for row in rows))} "
        f"cosine={dict(collections.Counter(row.cosine_kind for row in rows))}"
    )
    groups: dict[tuple[str, int], collections.Counter[str]] = (
        collections.defaultdict(collections.Counter)
    )
    for row in outside:
        observed = row.point.joint.observed
        groups[observed.source, observed.point.cell][row.label] += 1
    print("  outside labels by source/cell:")
    for key, counts in sorted(groups.items()):
        print(f"    {key}: {dict(counts)}")

    print("  source/cell correction coherence @2^-67:")
    for key in sorted(groups):
        selected = [
            row
            for row in outside
            if (
                row.point.joint.observed.source,
                row.point.joint.observed.point.cell,
            )
            == key
        ]
        signatures = collections.Counter(
            (scaled(row.dp, 67), scaled(row.dq, 67))
            for row in selected
        )
        vectors = [
            (float(row.dp * (1 << 72)), float(row.dq * (1 << 72)))
            for row in selected
        ]
        concentration = axis_concentration(vectors)
        top = signatures.most_common(4)
        covered = sum(count for _, count in top)
        print(
            f"    {key}: unique={len(signatures)} "
            f"top4={covered}/{len(selected)} axis={concentration:.4f} "
            f"{top}"
        )

    for bits in (67, 68, 69, 70, 71, 72):
        signatures = collections.Counter(
            (scaled(row.dp, bits), scaled(row.dq, bits))
            for row in outside
        )
        top = signatures.most_common(4)
        covered = sum(count for _, count in top)
        print(
            f"  P/Q signatures @2^-{bits}: unique={len(signatures)} "
            f"top4={covered}/{len(outside)} {top}"
        )

    vectors = [
        (float(row.dp * (1 << 72)), float(row.dq * (1 << 72)))
        for row in outside
    ]
    concentration = axis_concentration(vectors)
    print(
        "  global correction-axis concentration: "
        f"{concentration:.4f}"
    )


def axis_concentration(vectors: list[tuple[float, float]]) -> float:
    xx = sum(x * x for x, _ in vectors)
    yy = sum(y * y for _, y in vectors)
    xy = sum(x * y for x, y in vectors)
    trace_value = xx + yy
    if not trace_value:
        return 0.0
    discriminant = math.sqrt(max(0.0, (xx - yy) ** 2 + 4 * xy * xy))
    leading = (trace_value + discriminant) / 2
    return leading / trace_value


def predicate_counts(
    rows: list[Row], terms: tuple[tuple[str, int], ...]
) -> collections.Counter[str]:
    return collections.Counter(
        row.label
        for row in rows
        if all(row.features[name] == value for name, value in terms)
    )


def predicate_score(
    rows_by_split: dict[str, list[Row]],
    totals_by_split: dict[str, collections.Counter[str]],
    terms: tuple[tuple[str, int], ...],
):
    reports = {}
    dominant_label = None
    scores = []
    for split in ("train", "held"):
        counts = predicate_counts(rows_by_split[split], terms)
        selected = sum(counts.values())
        outside_counts = {label: counts[label] for label in LABELS}
        label, dominant = max(
            outside_counts.items(), key=lambda item: item[1]
        )
        outside = sum(outside_counts.values())
        if selected < 4 or outside < 2 or dominant < 2:
            return None
        if dominant_label is None:
            dominant_label = label
        elif dominant_label != label:
            return None
        precision = dominant / selected
        coverage = dominant / totals_by_split[split][label]
        scores.append(precision * coverage)
        reports[split] = (counts, precision, coverage)
    return min(scores), dominant_label, reports


def predicates(rows: list[Row], structural: bool):
    values: dict[str, set[int]] = collections.defaultdict(set)
    for row in rows:
        for name, value in row.features.items():
            if name.startswith("global.") != structural:
                continue
            values[name].add(value)
    return tuple(
        (name, value)
        for name, choices in sorted(values.items())
        if 1 < len(choices) <= 64
        for value in sorted(choices)
    )


def rank_predicates(rows: list[Row], structural: bool) -> None:
    rows_by_split = {
        split: [row for row in rows if row.split == split]
        for split in ("train", "held")
    }
    totals_by_split = {
        split: collections.Counter(row.label for row in split_rows)
        for split, split_rows in rows_by_split.items()
    }
    candidates = predicates(rows, structural)
    singles = []
    for term in candidates:
        result = predicate_score(
            rows_by_split, totals_by_split, (term,)
        )
        if result is not None:
            singles.append((*result, (term,)))
    singles.sort(key=lambda item: (-item[0], item[3]))
    title = "structural" if structural else "physical"
    print(f"  strongest {title} single predicates:")
    for score, label, reports, terms in singles[:20]:
        term = terms[0]
        print(
            f"    {term[0]}={term[1]} -> {label} score={score:.4f} "
            f"train={dict(reports['train'][0])} "
            f"held={dict(reports['held'][0])}"
        )

    if structural:
        return
    top_terms = []
    for item in singles[:80]:
        term = item[3][0]
        if term not in top_terms:
            top_terms.append(term)
    pairs = []
    for left, right in itertools.combinations(top_terms, 2):
        if left[0] == right[0]:
            continue
        terms = (left, right)
        result = predicate_score(
            rows_by_split, totals_by_split, terms
        )
        if result is not None:
            pairs.append((*result, terms))
    pairs.sort(key=lambda item: (-item[0], item[3]))
    print("  strongest physical two-predicate conjunctions:")
    for score, label, reports, terms in pairs[:30]:
        name = " & ".join(f"{key}={value}" for key, value in terms)
        print(
            f"    {name} -> {label} score={score:.4f} "
            f"train={dict(reports['train'][0])} "
            f"held={dict(reports['held'][0])}"
        )


def residual_score(
    rows_by_split: dict[str, list[Row]],
    terms: tuple[tuple[str, int], ...],
):
    reports = {}
    scores = []
    for split in ("train", "held"):
        split_rows = rows_by_split[split]
        selected = [
            row
            for row in split_rows
            if all(row.features[name] == value for name, value in terms)
        ]
        counts = collections.Counter(row.label for row in selected)
        outside = len(selected) - counts["inside"]
        total_outside = sum(row.label != "inside" for row in split_rows)
        if len(selected) < 4 or outside < 2 or total_outside == 0:
            return None
        precision = outside / len(selected)
        coverage = outside / total_outside
        baseline = total_outside / len(split_rows)
        lift = precision / baseline
        if lift <= 1.0:
            return None
        f1 = 2 * precision * coverage / (precision + coverage)
        scores.append(f1)
        reports[split] = (counts, len(selected), outside, precision, coverage, lift)
    return min(scores), reports


def rank_residual_enrichment(rows: list[Row], structural: bool) -> None:
    rows_by_split = {
        split: [row for row in rows if row.split == split]
        for split in ("train", "held")
    }
    candidates = predicates(rows, structural)
    singles = []
    for term in candidates:
        result = residual_score(rows_by_split, (term,))
        if result is not None:
            singles.append((*result, (term,)))
    singles.sort(key=lambda item: (-item[0], item[2]))
    title = "structural" if structural else "physical"
    print(f"  strongest {title} residual-enrichment predicates:")
    for score, reports, terms in singles[:20]:
        term = terms[0]
        train = reports["train"]
        held = reports["held"]
        print(
            f"    {term[0]}={term[1]} score={score:.4f} "
            f"train={train[2]}/{train[1]} lift={train[5]:.2f} "
            f"held={held[2]}/{held[1]} lift={held[5]:.2f} "
            f"directions={dict(train[0] + held[0])}"
        )

    if structural:
        return
    top_terms = [item[2][0] for item in singles[:100]]
    pairs = []
    for left, right in itertools.combinations(top_terms, 2):
        if left[0] == right[0]:
            continue
        terms = (left, right)
        result = residual_score(rows_by_split, terms)
        if result is not None:
            pairs.append((*result, terms))
    pairs.sort(key=lambda item: (-item[0], item[2]))
    print("  strongest physical two-predicate residual enrichments:")
    for score, reports, terms in pairs[:30]:
        name = " & ".join(f"{key}={value}" for key, value in terms)
        train = reports["train"]
        held = reports["held"]
        print(
            f"    {name} score={score:.4f} "
            f"train={train[2]}/{train[1]} lift={train[5]:.2f} "
            f"held={held[2]}/{held[1]} lift={held[5]:.2f} "
            f"directions={dict(train[0] + held[0])}"
        )


def main() -> None:
    points = [
        h188.prepare(point)
        for point in h184.dataset("sweep")
        if point.observed.family == "wide"
    ]
    rows = [make_row(point) for point in points]
    baseline = ((0, 0, 0), (0, 0, 0))
    for point in points:
        baseline = tuple(
            h170.add(old, new)
            for old, new in zip(baseline, h190.metric(point, True))
        )
    print(
        f"h193 Round-35 wide table sweep: n={len(rows)} "
        f"metrics={baseline}"
    )
    signature_report(rows)
    rank_predicates(rows, structural=True)
    rank_predicates(rows, structural=False)
    rank_residual_enrichment(rows, structural=True)
    rank_residual_enrichment(rows, structural=False)


if __name__ == "__main__":
    main()
