#!/usr/bin/env python3
"""Fit selectors over the first literal reconstruction FADD state.

h213's pre-add term predicates leave three sweep survivors, all rejected by
dense/fresh validation.  A real microprogram can also make a control decision
after an FADD has produced its raw carrier.  This pass adds only causally
available first-node signals: operation class, exponent distance, alignment
discarded-tail state, and raw/retained J, G, R, S, overflow, sign, exponent,
and low carrier bits.  It otherwise repeats h213's shared lane-local rule and
old/fresh componentwise gates.
"""

from __future__ import annotations

import collections
import itertools

import h200_p5_fadd_bitvector as h200
import h206_p5_fadd_complete as h206
import h207_tang_literal_fadd as h207
import h211_fadd_complete_tree_grammar as h211
import h213_fadd_causal_selector as h213


PAIR_ATOMS = 32


def first_node(tree):
    if isinstance(tree, str):
        raise ValueError("leaf has no FADD node")
    for child in tree:
        if not isinstance(child, str):
            return first_node(child)
    return tree


def relevant_terms(
    point: h207.Point,
    candidate: h211.Candidate,
    cosine_output: bool,
):
    observed = point.prepared.joint.observed
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
    return {
        "lead": terms.lead,
        "linear": terms.linear,
        "q": terms.q_product,
        "p": terms.p_product,
    }


def discarded_alignment(left, right) -> int:
    if not left.word or not right.word:
        return 0
    exponent = max(left.exponent, right.exponent)
    discarded = False
    for operand in (left, right):
        _, tail = h200.shift_right(
            operand.word << 1, exponent - operand.exponent
        )
        discarded |= tail
    return int(discarded)


def lane_features(
    point: h207.Point,
    candidate: h211.Candidate,
    cosine_output: bool,
):
    result = h213.lane_features(point, candidate, cosine_output)
    values = relevant_terms(point, candidate, cosine_output)
    node = first_node(candidate.tree)
    left = values[node[0]]
    right = values[node[1]]
    normalize = candidate.first != "retain-raw"
    raw, trace = h206.fadd(
        left, right, candidate.mode, normalize=normalize
    )
    retained = h206.materialize(raw, candidate.first)
    result.update(
        {
            "node0.operation-add": int(trace.operation == "add"),
            "node0.operation-far-sub": int(
                trace.operation == "far-sub"
            ),
            "node0.operation-near-sub": int(
                trace.operation == "near-sub"
            ),
            "node0.exponent-difference": trace.exponent_difference,
            "node0.difference-parity": trace.exponent_difference & 1,
            "node0.alignment-discarded": discarded_alignment(left, right),
            "node0.input-sign-xor": left.sign ^ right.sign,
            "node0.normalization-enabled": int(normalize),
        }
    )
    h213.bit_features(result, "node0.raw", raw)
    h213.bit_features(result, "node0.retained", retained)
    return result


def lane_records(datasets, candidate: h211.Candidate):
    records = []
    for partition_index, (_, points) in enumerate(datasets):
        for point in points:
            baseline_values = h207.current_values(point.prepared)
            candidate_values = h211.hidden_values(
                point.prepared, candidate
            )
            baseline_metric = h213.metric_for_values(
                point, *baseline_values
            )
            candidate_metric = h213.metric_for_values(
                point, *candidate_values
            )
            records.append(
                (
                    partition_index,
                    h213.active_atoms(
                        lane_features(point, candidate, False)
                    ),
                    h213.lane_delta(
                        candidate_metric[0], baseline_metric[0], False
                    ),
                )
            )
            if point.cosine_hardware:
                records.append(
                    (
                        partition_index,
                        h213.active_atoms(
                            lane_features(point, candidate, True)
                        ),
                        h213.lane_delta(
                            candidate_metric[1], baseline_metric[1], True
                        ),
                    )
                )
    return records


def conditional_metric(point: h207.Point, rule: h213.Rule):
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
    return h213.metric_for_values(point, *outputs)


def validate(rule, datasets, baselines):
    values = []
    for _, points in datasets:
        value = h213.ZERO_JOINT
        for point in points:
            value = h213.add(value, conditional_metric(point, rule))
        values.append(value)
    passed = all(
        h207.no_worse(value, baseline)
        for value, baseline in zip(values, baselines)
    ) and any(value != baseline for value, baseline in zip(values, baselines))
    return values, passed


def validate_group(rules, datasets, baselines):
    """Score rules sharing one program with point/program replay cached."""
    candidate = rules[0].candidate
    values = {rule: list(baselines) for rule in rules}
    for dataset_index, (_, points) in enumerate(datasets):
        for point in points:
            baseline_values = h207.current_values(point.prepared)
            candidate_values = h211.hidden_values(
                point.prepared, candidate
            )
            baseline_metric = h213.metric_for_values(
                point, *baseline_values
            )
            candidate_metric = h213.metric_for_values(
                point, *candidate_values
            )
            sine_delta = h213.lane_delta(
                candidate_metric[0], baseline_metric[0], False
            )
            sine_features = lane_features(point, candidate, False)
            cosine_delta = None
            cosine_features = None
            if point.cosine_hardware:
                cosine_delta = h213.lane_delta(
                    candidate_metric[1], baseline_metric[1], True
                )
                cosine_features = lane_features(point, candidate, True)
            for rule in rules:
                if all(
                    sine_features.get(name) == value
                    for name, value in rule.terms
                ):
                    values[rule][dataset_index] = h213.add(
                        values[rule][dataset_index], sine_delta
                    )
                if cosine_features is not None and all(
                    cosine_features.get(name) == value
                    for name, value in rule.terms
                ):
                    values[rule][dataset_index] = h213.add(
                        values[rule][dataset_index], cosine_delta
                    )
    result = {}
    for rule, rule_values in values.items():
        passed = all(
            h207.no_worse(value, baseline)
            for value, baseline in zip(rule_values, baselines)
        ) and any(
            value != baseline
            for value, baseline in zip(rule_values, baselines)
        )
        result[rule] = (rule_values, passed)
    return result


def changed_report(datasets, values, baselines):
    return [
        (name, baseline, value)
        for (name, _), baseline, value in zip(datasets, baselines, values)
        if value != baseline
    ]


def main() -> None:
    selection = h207.joint_partitions("sweep")
    baselines = h213.partition_baselines(selection)
    print(
        "h214 first-FADD selector: "
        f"programs={len(h213.PROGRAMS)} points="
        f"{sum(len(points) for _, points in selection)}"
    )
    singles = []
    conjunctions = []
    for candidate_index, candidate in enumerate(h213.PROGRAMS, 1):
        records = lane_records(selection, candidate)
        single_deltas = h213.sum_deltas(records, 1)
        ranked_atoms = []
        for terms, delta in single_deltas.items():
            values, passed = h213.score_delta(delta, baselines)
            ranked_atoms.append(
                (
                    h213.violation(values, baselines),
                    h207.objective(values),
                    terms[0],
                )
            )
            if passed:
                singles.append(
                    (h207.objective(values), h213.Rule(candidate, terms), values)
                )
        ranked_atoms.sort()
        allowed = {entry[2] for entry in ranked_atoms[:PAIR_ATOMS]}
        pair_deltas = h213.sum_deltas(records, 2, allowed)
        for terms, delta in pair_deltas.items():
            values, passed = h213.score_delta(delta, baselines)
            if passed:
                conjunctions.append(
                    (h207.objective(values), h213.Rule(candidate, terms), values)
                )
        node_atoms = {
            terms[0]
            for terms in single_deltas
            if terms[0][0].startswith("node0.")
        }
        node_pair_deltas = h213.sum_deltas(records, 2, node_atoms)
        for terms, delta in node_pair_deltas.items():
            values, passed = h213.score_delta(delta, baselines)
            if passed:
                conjunctions.append(
                    (h207.objective(values), h213.Rule(candidate, terms), values)
                )
        print(
            f"  program {candidate_index:2d}: atoms={len(single_deltas)} "
            f"best-violation={ranked_atoms[0][0]} "
            f"ranked-pairs={len(pair_deltas)} "
            f"node-pairs={len(node_pair_deltas)}",
            flush=True,
        )

    singles.sort(key=lambda item: (item[0], item[1].short()))
    conjunctions = list({
        (item[1], tuple(item[2])): item
        for item in conjunctions
    }.values())
    conjunctions.sort(key=lambda item: (item[0], item[1].short()))
    print(
        f"h214 sweep survivors: singles={len(singles)} "
        f"pairs={len(conjunctions)}"
    )
    for _, rule, values in [*singles[:15], *conjunctions[:30]]:
        print(f"  {rule.short()}")
        print(f"    sweep={values}")

    rules = [item[1] for item in [*singles, *conjunctions]]
    if not rules:
        return
    validation = [*h207.joint_partitions("dense"), *h207.focused_datasets()]
    validation_baselines = h213.partition_baselines(validation)
    final = []
    rejected = []
    groups = collections.defaultdict(list)
    for rule in rules:
        groups[rule.candidate].append(rule)
    for candidate_index, candidate_rules in enumerate(groups.values(), 1):
        results = validate_group(
            candidate_rules, validation, validation_baselines
        )
        for rule, (values, passed) in results.items():
            item = (h207.objective(values), rule, values)
            (final if passed else rejected).append(item)
        print(
            f"  validated program-group {candidate_index}/{len(groups)} "
            f"rules={len(candidate_rules)}",
            flush=True,
        )
    final.sort(key=lambda item: (item[0], item[1].short()))
    rejected.sort(
        key=lambda item: (
            h213.violation(item[2], validation_baselines),
            item[0],
            item[1].short(),
        )
    )
    print(f"h214 dense/focused survivors: {len(final)}")
    for _, rule, values in final[:30]:
        print(f"  {rule.short()}")
        print(f"    validation={values}")
    print("  leading rejected validation profiles:")
    for _, rule, values in rejected[:10]:
        print(
            f"    violation={h213.violation(values, validation_baselines)} "
            f"{rule.short()}"
        )
        for name, baseline, value in changed_report(
            validation, values, validation_baselines
        ):
            print(f"      {name}: {baseline}->{value}")


if __name__ == "__main__":
    main()
