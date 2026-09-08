#!/usr/bin/env python3
"""Fit causal lane-local selectors for h212's literal FADD programs.

h212 proves that fixed ``jam-sub`` datapath semantics can exactly reach every
remaining sine and cosine lane, but its oracle may choose a program by point
identity.  This pass restricts selection to signals available before the
first reconstruction FADD: range-reduction state plus sign, exponent, J/GRS,
and low retained bits of the four term buses.  The same predicate is applied
independently to both architectural lanes, allowing their distinct operand
states to drive different controls without using a lane label.

The eleven programs are h212's deterministic greedy exact cover.  Single
predicates are tested first.  If none survives both sweep halves, bounded
two-predicate conjunctions are formed only from the best physical atoms for
each program.  Any survivor must then pass dense halves and every h207 fresh
capture subset before it can justify a hardware discriminator.
"""

from __future__ import annotations

import collections
import dataclasses
import itertools

import h170_fsin_table_correction_search as h170
import h182_table_joint_terminal_edges as h182
import h207_tang_literal_fadd as h207
import h211_fadd_complete_tree_grammar as h211


Metric = tuple[int, int, int]
JointMetric = tuple[Metric, Metric]
Atom = tuple[str, int]
ZERO_METRIC: Metric = (0, 0, 0)
ZERO_JOINT: JointMetric = (ZERO_METRIC, ZERO_METRIC)
PAIR_ATOMS = 24


@dataclasses.dataclass(frozen=True)
class Rule:
    candidate: h211.Candidate
    terms: tuple[Atom, ...]

    def short(self) -> str:
        predicate = " & ".join(
            f"{name}={value}" for name, value in self.terms
        )
        return f"if {predicate}: {self.candidate.short()}"


def tree(text: str):
    return next(
        value for value in h211.ALL_TREES if h211.tree_key(value) == text
    )


def program(
    tree_text: str,
    first: str,
    second: str,
    linear: str = "odd67",
) -> h211.Candidate:
    return h211.Candidate(
        tree(tree_text),
        "jam-sub",
        first,
        second,
        False,
        h207.ProductRoute(linear, "odd67", "odd67"),
    )


PROGRAMS = (
    program("(((linear+p)+q)+lead)", "odd64", "away64"),
    program("(((linear+p)+lead)+q)", "chop64", "retain"),
    program(
        "(((linear+p)+q)+lead)", "odd64", "chop64", "rn64"
    ),
    program("(((linear+q)+p)+lead)", "away64", "away64"),
    program("(((linear+p)+q)+lead)", "chop64", "rn64"),
    program("((lead+p)+(linear+q))", "retain", "away64", "rn64"),
    program("(((linear+p)+q)+lead)", "odd64", "retain"),
    program("(((linear+q)+p)+lead)", "odd64", "retain"),
    program("(((lead+q)+linear)+p)", "retain", "retain"),
    program("(((linear+p)+q)+lead)", "chop64", "away64"),
    program("(((lead+p)+q)+linear)", "rn64", "retain"),
)


def add(left: JointMetric, right: JointMetric) -> JointMetric:
    return h207.add_metric(left, right)


def subtract(new: Metric, old: Metric) -> Metric:
    return tuple(a - b for a, b in zip(new, old))  # type: ignore[return-value]


def lane_delta(new: Metric, old: Metric, cosine: bool) -> JointMetric:
    delta = subtract(new, old)
    return (ZERO_METRIC, delta) if cosine else (delta, ZERO_METRIC)


def metric_for_values(point: h207.Point, sine, cosine) -> JointMetric:
    sine_metric = h170.point_metric(point.prepared.joint.observed, sine)
    cosine_metric = (
        h182.point_metric(
            point.prepared.joint.cosine_outputs,
            point.prepared.joint.cosine_c1,
            cosine,
        )
        if point.cosine_hardware
        else ZERO_METRIC
    )
    return sine_metric, cosine_metric


def bit_features(result: dict[str, int], prefix: str, bus) -> None:
    result[f"{prefix}.sign"] = bus.sign
    result[f"{prefix}.sticky"] = bus.word & 1
    result[f"{prefix}.round"] = (bus.word >> 1) & 1
    result[f"{prefix}.guard"] = (bus.word >> 2) & 1
    result[f"{prefix}.j"] = (bus.word >> 66) & 1
    result[f"{prefix}.overflow"] = (bus.word >> 67) & 1
    result[f"{prefix}.exponent-parity"] = bus.exponent & 1
    result[f"{prefix}.exponent-mod4"] = bus.exponent & 3
    for index in range(3, 9):
        result[f"{prefix}.bit{index}"] = (bus.word >> index) & 1


def lane_features(
    point: h207.Point,
    candidate: h211.Candidate,
    cosine_output: bool,
) -> dict[str, int]:
    observed = point.prepared.joint.observed
    prepared = observed.point
    odd_quadrant = bool(observed.signed_n & 1)
    if cosine_output:
        shared = True
        cosine_lane = not odd_quadrant
    else:
        shared = False
        cosine_lane = odd_quadrant
    terms = h207.lane_terms(
        point.prepared, shared, cosine_lane, candidate.products
    )
    values = {
        "lead": terms.lead,
        "linear": terms.linear,
        "q": terms.q_product,
        "p": terms.p_product,
    }
    result = {
        "global.reduced": int(observed.source == "reduced"),
        "global.quadrant-bit0": observed.signed_n & 1,
        "global.quadrant-bit1": (observed.signed_n >> 1) & 1,
        "global.input-sign": prepared.raw.sign,
        "global.residual-sign": prepared.a[0],
        "global.cell": prepared.cell,
    }
    for index in range(6):
        result[f"global.input-bit{index}"] = (
            prepared.raw.sig >> index
        ) & 1
        result[f"global.residual-bit{index}"] = (
            prepared.a[1] >> index
        ) & 1
    for name, bus in values.items():
        bit_features(result, f"term.{name}", bus)
    for left_name, right_name in itertools.combinations(values, 2):
        left = values[left_name]
        right = values[right_name]
        prefix = f"pair.{left_name}-{right_name}"
        difference = abs(left.exponent - right.exponent)
        result[f"{prefix}.difference"] = difference
        result[f"{prefix}.difference-parity"] = difference & 1
        result[f"{prefix}.sign-xor"] = left.sign ^ right.sign
    return result


def active_atoms(features: dict[str, int]) -> tuple[Atom, ...]:
    return tuple(sorted(features.items()))


def partition_baselines(datasets):
    result = []
    for _, points in datasets:
        value = ZERO_JOINT
        for point in points:
            value = add(value, h211.point_metric(point, None))
        result.append(value)
    return result


def lane_records(datasets, candidate: h211.Candidate):
    records = []
    for partition_index, (_, points) in enumerate(datasets):
        for point in points:
            baseline_values = h207.current_values(point.prepared)
            candidate_values = h211.hidden_values(
                point.prepared, candidate
            )
            baseline_metric = metric_for_values(
                point, *baseline_values
            )
            candidate_metric = metric_for_values(
                point, *candidate_values
            )
            records.append(
                (
                    partition_index,
                    active_atoms(lane_features(point, candidate, False)),
                    lane_delta(
                        candidate_metric[0], baseline_metric[0], False
                    ),
                )
            )
            if point.cosine_hardware:
                records.append(
                    (
                        partition_index,
                        active_atoms(
                            lane_features(point, candidate, True)
                        ),
                        lane_delta(
                            candidate_metric[1], baseline_metric[1], True
                        ),
                    )
                )
    return records


def sum_deltas(records, term_count: int, allowed=None):
    result = collections.defaultdict(
        lambda: [ZERO_JOINT for _ in range(2)]
    )
    for partition_index, atoms, delta in records:
        selected = atoms if allowed is None else tuple(
            atom for atom in atoms if atom in allowed
        )
        keys = (
            ((atom,) for atom in selected)
            if term_count == 1
            else itertools.combinations(selected, 2)
        )
        for key in keys:
            result[key][partition_index] = add(
                result[key][partition_index], delta
            )
    return result


def violation(values, baselines) -> int:
    return sum(
        max(0, candidate - old)
        for value, baseline in zip(values, baselines)
        for lane, old_lane in zip(value, baseline)
        for candidate, old in zip(lane, old_lane)
    )


def score_delta(delta, baselines):
    values = [add(baseline, item) for baseline, item in zip(baselines, delta)]
    passed = all(
        h207.no_worse(value, baseline)
        for value, baseline in zip(values, baselines)
    )
    changed = any(value != baseline for value, baseline in zip(values, baselines))
    return values, passed and changed


def conditional_metric(point: h207.Point, rule: Rule) -> JointMetric:
    baseline = h207.current_values(point.prepared)
    candidate = h211.hidden_values(point.prepared, rule.candidate)
    outputs = []
    for cosine in (False, True):
        use_candidate = point.cosine_hardware or not cosine
        if use_candidate:
            features = lane_features(point, rule.candidate, cosine)
            use_candidate = all(
                features.get(name) == value for name, value in rule.terms
            )
        outputs.append(candidate[cosine] if use_candidate else baseline[cosine])
    return metric_for_values(point, *outputs)


def validate(rule: Rule, datasets, baselines):
    values = []
    for _, points in datasets:
        value = ZERO_JOINT
        for point in points:
            value = add(value, conditional_metric(point, rule))
        values.append(value)
    passed = all(
        h207.no_worse(value, baseline)
        for value, baseline in zip(values, baselines)
    ) and any(value != baseline for value, baseline in zip(values, baselines))
    return values, passed


def main() -> None:
    h211.assert_grammar()
    selection = h207.joint_partitions("sweep")
    baselines = partition_baselines(selection)
    print(
        "h213 causal selector: "
        f"programs={len(PROGRAMS)} points="
        f"{sum(len(points) for _, points in selection)}"
    )
    for (name, points), baseline in zip(selection, baselines):
        print(f"  baseline {name} n={len(points)} {baseline}")

    survivors = []
    pair_survivors = []
    for candidate_index, candidate in enumerate(PROGRAMS, 1):
        records = lane_records(selection, candidate)
        singles = sum_deltas(records, 1)
        ranked_atoms = []
        for terms, delta in singles.items():
            values, passed = score_delta(delta, baselines)
            ranked_atoms.append(
                (
                    violation(values, baselines),
                    h207.objective(values),
                    terms[0],
                )
            )
            if passed:
                survivors.append(
                    (h207.objective(values), Rule(candidate, terms), values)
                )
        ranked_atoms.sort()
        allowed = {entry[2] for entry in ranked_atoms[:PAIR_ATOMS]}
        pairs = sum_deltas(records, 2, allowed)
        for terms, delta in pairs.items():
            values, passed = score_delta(delta, baselines)
            if passed:
                pair_survivors.append(
                    (h207.objective(values), Rule(candidate, terms), values)
                )
        best = ranked_atoms[0]
        print(
            f"  program {candidate_index:2d}: singles={len(singles)} "
            f"best-violation={best[0]} best={best[2]} "
            f"pairs={len(pairs)}",
            flush=True,
        )

    survivors.sort(key=lambda item: (item[0], item[1].short()))
    pair_survivors.sort(key=lambda item: (item[0], item[1].short()))
    print(
        f"h213 sweep survivors: singles={len(survivors)} "
        f"pairs={len(pair_survivors)}"
    )
    for _, rule, values in [*survivors[:10], *pair_survivors[:20]]:
        print(f"  {rule.short()}")
        print(f"    sweep={values}")

    rules = [item[1] for item in [*survivors, *pair_survivors]]
    if not rules:
        return
    validation = [*h207.joint_partitions("dense"), *h207.focused_datasets()]
    validation_baselines = partition_baselines(validation)
    final = []
    for rule in rules:
        values, passed = validate(rule, validation, validation_baselines)
        if passed:
            final.append((h207.objective(values), rule, values))
    final.sort(key=lambda item: (item[0], item[1].short()))
    print(f"h213 dense/focused survivors: {len(final)}")
    for _, rule, values in final[:30]:
        print(f"  {rule.short()}")
        print(f"    validation={values}")


if __name__ == "__main__":
    main()
