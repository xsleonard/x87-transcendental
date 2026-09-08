#!/usr/bin/env python3
"""Separate the h283 exponent-difference-13 sine-bias near-miss.

Selecting wide bias 3 instead of 5 only when the shared-sine FADD operands
have exponent difference 13 removes about one hundred mode misses but has
three regressing metric components.  This pass adds one equality or
inequality predicate over the physical features already extracted by h283.
Every candidate is scored on all frozen train, held-out, dense, sweep, and
focused partitions; no per-input feature is available.
"""

from __future__ import annotations

import collections

import h218_fadd_residual_programs as h218
import h226_p6_full_sine_graph as h226
import h228_p6_four_term_c_parity as h228
import h230_p6_microop_materialization_search as h230
import h283_trig_sine_bias_selector as h283


def main() -> None:
    datasets = h218.datasets()
    baseline = h230.score(datasets, h228.CANDIDATE)
    records = []
    classes = collections.Counter()
    for dataset_index, (_, points) in enumerate(datasets):
        for point in points:
            old = h226.metric_for(
                point, h230.hidden_values(point, h228.CANDIDATE)
            )
            new = h226.metric_for(
                point, h230.hidden_values(point, h283.BIAS3)
            )
            if old == new:
                continue
            values = h283.features(point)
            if values["align.difference"] != 13:
                continue
            delta = h283.subtract_metric(new, old)
            classification = (
                "improves"
                if h283.joint_no_worse(new, old)
                else "regresses"
                if h283.joint_no_worse(old, new)
                else "mixed"
            )
            classes[classification] += 1
            records.append((dataset_index, delta, values, classification))

    domains = collections.defaultdict(set)
    for _, _, values, _ in records:
        for name, value in values.items():
            if name != "align.difference":
                domains[name].add(value)

    selectors = [("all", "", None)]
    for name, values in domains.items():
        for value in values:
            selectors.append((name, "eq", value))
            selectors.append((name, "ne", value))

    ranked = []
    for feature, operation, expected in selectors:
        candidate = list(baseline)
        active = 0
        active_classes = collections.Counter()
        for dataset_index, delta, values, classification in records:
            selected = (
                feature == "all"
                or (
                    (values[feature] == expected)
                    if operation == "eq"
                    else (values[feature] != expected)
                )
            )
            if not selected:
                continue
            active += 1
            active_classes[classification] += 1
            candidate[dataset_index] = h283.add_delta(
                candidate[dataset_index], delta
            )
        candidate_tuple = tuple(candidate)
        ranked.append(
            (
                h226.regressions(candidate_tuple, baseline),
                h226.objective(candidate_tuple),
                feature,
                operation,
                expected,
                active,
                dict(active_classes),
                candidate_tuple,
            )
        )
    ranked.sort()
    print(
        "h284 align-difference-13 selector: "
        f"differing-points={len(records)} classes={dict(classes)} "
        f"predicates={len(ranked)}"
    )
    print(f"baseline={h226.objective(baseline)}")
    print("regression leaders:")
    for item in ranked[:40]:
        print(
            f"  regressions={item[0]} objective={item[1]} "
            f"active={item[5]} classes={item[6]} "
            f"{item[2]} {item[3]} {item[4]}"
        )
    print("objective leaders:")
    for item in sorted(ranked, key=lambda item: (item[1], item[0], item[2]))[:24]:
        print(
            f"  objective={item[1]} regressions={item[0]} "
            f"active={item[5]} classes={item[6]} "
            f"{item[2]} {item[3]} {item[4]}"
        )


if __name__ == "__main__":
    main()
