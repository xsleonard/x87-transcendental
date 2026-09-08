#!/usr/bin/env python3
"""Refine h220 branches with one h221 counterexample predicate.

All four h220 representative branches fail the purpose-built h221 capture.
This bounded CEGIS pass adds exactly one physical atom to each two-atom base
rule and gates the result on complete sweep/dense, old focused captures,
h216, and h221.  Input-identity bits remain excluded.  A zero-survivor result
closes three-atom conjunctions for these two causal branch families.
"""

from __future__ import annotations

import collections

import h211_fadd_complete_tree_grammar as h211
import h213_fadd_causal_selector as h213
import h214_fadd_node0_selector as h214
import h216_fadd_microcontrol_discriminator as h216
import h220_fadd_causal_tree as h220
import h221_fadd_tree_discriminator as h221


BASE_RULES = tuple(h221.RULES.values())


def extended_lanes():
    named, lanes, baselines = h220.build_lanes()
    fresh = h221.load_capture(
        h221.DEFAULT_OUTPUT,
        h221.ROOT / "capture-kit-captures" / "skylake-fsin-h221",
    )
    partition = len(named)
    fresh_baseline = h220.ZERO_VECTOR
    for point in fresh:
        metrics = h220.point_metrics(point, h220.baseline_values(point))
        for cosine in (False, True):
            metric = metrics[cosine]
            active = h220.base_selected(point, cosine)
            lanes.append(
                h220.Lane(partition, point, cosine, metric, active)
            )
            fresh_baseline = h220.add(
                fresh_baseline, h220.vector(metric, cosine)
            )
    return (
        [*named, ("h221", fresh)],
        lanes,
        (*baselines, fresh_baseline),
    )


def matches(features, terms):
    return all(features.get(name) == value for name, value in terms)


def score_rule(lanes, baselines, base):
    node_allowed = h220.same_first_node(base.candidate)
    deltas = collections.defaultdict(
        lambda: [h220.ZERO_VECTOR for _ in baselines]
    )
    candidate_cache = {}
    base_delta = [h220.ZERO_VECTOR for _ in baselines]
    selected_lanes = 0
    for lane in lanes:
        if lane.current_active:
            continue
        features = h214.lane_features(
            lane.point, h220.CURRENT_RULE.candidate, lane.cosine
        )
        if not matches(features, base.terms):
            continue
        selected_lanes += 1
        metrics = candidate_cache.get(lane.point)
        if metrics is None:
            values = h211.hidden_values(lane.point.prepared, base.candidate)
            metrics = h220.point_metrics(lane.point, values)
            candidate_cache[lane.point] = metrics
        old = h220.vector(lane.baseline, lane.cosine)
        new = h220.vector(metrics[lane.cosine], lane.cosine)
        delta = h220.subtract(new, old)
        base_delta[lane.partition] = h220.add(
            base_delta[lane.partition], delta
        )
        for atom in sorted(features.items()):
            if atom in base.terms or not h220.allowed_feature(
                atom[0], node_allowed
            ):
                continue
            deltas[atom][lane.partition] = h220.add(
                deltas[atom][lane.partition], delta
            )

    base_values = tuple(
        h220.add(baseline, delta)
        for baseline, delta in zip(baselines, base_delta)
    )
    results = []
    for atom, atom_deltas in deltas.items():
        values = tuple(
            h220.add(baseline, delta)
            for baseline, delta in zip(baselines, atom_deltas)
        )
        violation = sum(
            max(0, new - old)
            for value, baseline in zip(values, baselines)
            for new, old in zip(value, baseline)
        )
        changed = any(value != baseline for value, baseline in zip(values, baselines))
        objective = sum(sum(value) for value in values)
        results.append(
            h220.Result(
                violation,
                objective,
                h213.Rule(base.candidate, (*base.terms, atom)),
                values,
            )
        )
    results.sort(
        key=lambda item: (
            item.violation,
            item.objective,
            item.rule.short(),
        )
    )
    survivors = [
        item
        for item in results
        if item.violation == 0 and item.values != baselines
    ]
    return selected_lanes, len(deltas), base_values, survivors, results[:10]


def main() -> None:
    named, lanes, baselines = extended_lanes()
    print(
        f"h222 h221 CEGIS bases={len(BASE_RULES)} lanes={len(lanes)}"
    )
    total = []
    for index, base in enumerate(BASE_RULES, 1):
        selected, atom_count, base_values, survivors, closest = score_rule(
            lanes, baselines, base
        )
        total.extend(survivors)
        base_violation = sum(
            max(0, new - old)
            for value, baseline in zip(base_values, baselines)
            for new, old in zip(value, baseline)
        )
        print(
            f"  base {index} selected-lanes={selected} "
            f"base-violation={base_violation} "
            f"atoms={atom_count} "
            f"survivors={len(survivors)} {base.short()}"
        )
        for item in closest[:5]:
            print(
                f"    violation={item.violation} atom={item.rule.terms[-1]}"
            )
    total.sort(key=lambda item: (item.objective, item.rule.short()))
    print(f"h222 complete three-atom survivors={len(total)}")
    for item in total[:40]:
        print(f"  {item.rule.short()}")
        for (name, _), baseline, value in zip(named, baselines, item.values):
            if value != baseline:
                print(f"    {name}: {baseline}->{value}")


if __name__ == "__main__":
    main()
