#!/usr/bin/env python3
"""Refine the h284 rule with the fresh h285 Skylake counterexamples.

The two-term alignment-distance/local-exponent rule improves the fresh set
strongly but is not exact.  This CEGIS pass tests one further physical
equality or inequality predicate and scores it simultaneously on every old
partition and the new hardware capture.  The original two-term rule remains
the componentwise winner, so no fitted third term is promoted.
"""

from __future__ import annotations

import collections
import dataclasses

import h58_constraint_search as h58
import h182_table_joint_terminal_edges as h182
import h188_table_stage_local_pairs as h188
import h207_tang_literal_fadd as h207
import h218_fadd_residual_programs as h218
import h226_p6_full_sine_graph as h226
import h228_p6_four_term_c_parity as h228
import h230_p6_microop_materialization_search as h230
import h283_trig_sine_bias_selector as h283
import h285_trig_sine_bias_discriminator as h285
import h286_ingest_trig_sine_bias_capture as h286


def fresh_points():
    operands = [
        tuple(int(field, 16) for field in line.split())
        for line in (h286.CAPTURE / "inputs.txt").read_text().splitlines()
    ]
    hardware = h286.captures()
    result = []
    for index, (se, sig) in enumerate(operands):
        base = h285.point_from_input(index, se, sig)
        if base is None or not h285.selected(base):
            raise SystemExit(f"h285 input {index + 1} is not selected")
        observed = base.prepared.joint.observed
        sine_outputs = tuple(
            hardware["fsin"][rc][index][0] for rc in h58.RCS
        )
        sine_c1 = tuple(
            hardware["fsin"][rc][index][1] for rc in h58.RCS
        )
        cosine_outputs = tuple(
            hardware["fsincos"][rc][index][1] for rc in h58.RCS
        )
        cosine_c1 = tuple(
            hardware["fsincos"][rc][index][2] for rc in h58.RCS
        )
        joint = h182.Point(
            dataclasses.replace(
                observed, outputs=sine_outputs, c1=sine_c1
            ),
            cosine_outputs,
            cosine_c1,
        )
        result.append(h207.Point(h188.prepare(joint), True))
    return result


def main() -> None:
    datasets = [*h218.datasets(), ("h285", fresh_points())]
    baseline = h230.score(datasets, h228.CANDIDATE)
    records = []
    classes = collections.Counter()
    origins = collections.Counter()
    for dataset_index, (dataset, points) in enumerate(datasets):
        for point in points:
            values = h283.features(point)
            if not (
                values["align.difference"] == 13
                and values["a.top-exponent"] == -5
            ):
                continue
            old = h226.metric_for(
                point, h230.hidden_values(point, h228.CANDIDATE)
            )
            new = h226.metric_for(
                point, h230.hidden_values(point, h283.BIAS3)
            )
            if old == new:
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
            origins[dataset, classification] += 1
            records.append(
                (dataset_index, delta, values, classification, dataset)
            )

    domains = collections.defaultdict(set)
    for _, _, values, _, _ in records:
        for name, value in values.items():
            if name not in ("align.difference", "a.top-exponent"):
                domains[name].add(value)

    ranked = []
    for feature, values in domains.items():
        for expected in values:
            for operation in ("eq", "ne"):
                candidate = list(baseline)
                active = collections.Counter()
                for dataset_index, delta, row, classification, dataset in records:
                    selected = (
                        row[feature] == expected
                        if operation == "eq"
                        else row[feature] != expected
                    )
                    if not selected:
                        continue
                    active[dataset, classification] += 1
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
                        sum(active.values()),
                        dict(active),
                        candidate_tuple,
                    )
                )
    ranked.sort()
    print(
        "h287 combined CEGIS: "
        f"datasets={len(datasets)} records={len(records)} "
        f"classes={dict(classes)} predicates={len(ranked)}"
    )
    print(f"origins={dict(sorted(origins.items()))}")
    print(f"baseline={h226.objective(baseline)}")
    print("regression leaders:")
    for item in ranked[:40]:
        print(
            f"  regressions={item[0]} objective={item[1]} "
            f"active={item[5]} {item[2]} {item[3]} {item[4]} "
            f"classes={item[6]}"
        )
    print("objective leaders:")
    for item in sorted(ranked, key=lambda item: (item[1], item[0], item[2]))[:24]:
        print(
            f"  objective={item[1]} regressions={item[0]} "
            f"active={item[5]} {item[2]} {item[3]} {item[4]} "
            f"classes={item[6]}"
        )


if __name__ == "__main__":
    main()
