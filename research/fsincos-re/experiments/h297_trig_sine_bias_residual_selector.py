#!/usr/bin/env python3
"""Search a physical selector for the Round-44 bias-3 reversals.

The h292 capture confirms bias 3 strongly at both promoted coordinates, but
also supplies a minority of counterexamples.  Starting from Round 44, this
pass tests whether one retained/carry/sticky or route feature can select the
old bias-5 state on those counterexamples.  h292 is split before scoring so a
candidate must improve both halves as well as avoid aggregate regressions on
the earlier partitions.
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
import h287_trig_sine_bias_cegis as h287
import h293_ingest_trig_coordinate_capture as h293
import h294_trig_sine_bias_rule as h294


def h292_points():
    operands = [
        tuple(int(field, 16) for field in line.split())
        for line in (h293.CAPTURE / "inputs.txt").read_text().splitlines()
    ]
    hardware = h293.captures()
    result = []
    for index, (se, sig) in enumerate(operands):
        base = h285.point_from_input(index, se, sig)
        if base is None or not h294.selected(base):
            raise SystemExit(f"h292 input {index + 1} is not selected")
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


def round44_values(point):
    candidate = h283.BIAS3 if h294.selected(point) else h228.CANDIDATE
    return h230.hidden_values(point, candidate)


def main() -> None:
    captured = h292_points()
    datasets = [
        *h218.datasets(),
        ("h285", h287.fresh_points()),
        ("h292-train", captured[::2]),
        ("h292-held", captured[1::2]),
    ]
    baseline = []
    records = collections.defaultdict(list)
    classes = collections.Counter()
    for dataset_index, (dataset, points) in enumerate(datasets):
        total = h226.ZERO_JOINT
        for point in points:
            current = round44_values(point)
            current_metric = h226.metric_for(point, current)
            total = h226.add_metric(total, current_metric)
            if not h294.selected(point):
                continue
            alternative_metric = h226.metric_for(
                point,
                h230.hidden_values(point, h228.CANDIDATE),
            )
            if alternative_metric == current_metric:
                continue
            delta = h283.subtract_metric(alternative_metric, current_metric)
            features = h283.features(point)
            coord = (
                features["a.top-exponent"],
                features["align.difference"],
            )
            classification = (
                "improves"
                if h283.joint_no_worse(alternative_metric, current_metric)
                else "regresses"
                if h283.joint_no_worse(current_metric, alternative_metric)
                else "mixed"
            )
            classes[dataset, coord, classification] += 1
            records[coord].append(
                (dataset_index, dataset, delta, features, classification)
            )
        baseline.append(total)
    baseline_tuple = tuple(baseline)
    print(
        "h297 Round-44 residual selector: "
        f"datasets={len(datasets)} baseline={h226.objective(baseline_tuple)}"
    )
    print(f"classes={dict(sorted(classes.items()))}")

    for coord in sorted(records):
        domains = collections.defaultdict(set)
        for _, _, _, row, _ in records[coord]:
            for name, value in row.items():
                if name not in ("align.difference", "a.top-exponent"):
                    domains[name].add(value)
        ranked = []
        for feature, values in domains.items():
            for expected in values:
                for operation in ("eq", "ne"):
                    candidate = list(baseline_tuple)
                    active = collections.Counter()
                    for dataset_index, dataset, delta, row, classification in records[coord]:
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
                            h226.regressions(candidate_tuple, baseline_tuple),
                            h226.objective(candidate_tuple),
                            feature,
                            operation,
                            expected,
                            sum(active.values()),
                            dict(active),
                        )
                    )
        ranked.sort()
        print(f"coordinate={coord} records={len(records[coord])}")
        print("  regression leaders:")
        for item in ranked[:32]:
            print(
                f"    regressions={item[0]} objective={item[1]} "
                f"active={item[5]} {item[2]} {item[3]} {item[4]} "
                f"classes={item[6]}"
            )
        print("  objective leaders:")
        for item in sorted(
            ranked, key=lambda item: (item[1], item[0], item[2])
        )[:20]:
            print(
                f"    objective={item[1]} regressions={item[0]} "
                f"active={item[5]} {item[2]} {item[3]} {item[4]} "
                f"classes={item[6]}"
            )


if __name__ == "__main__":
    main()
