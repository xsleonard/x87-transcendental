#!/usr/bin/env python3
"""Extend h177 sibling triangulation through reduced table quadrants."""

from __future__ import annotations

import collections

import h58_constraint_search as h58
import h131_fsin_table_c1_search as h131
import h169_fsin_table_round33_tomography as h169
import h170_fsin_table_correction_search as h170
import h177_table_sibling_triangulation as h177


def main() -> None:
    points = h131.load_dataset(
        "sweep", h131.INPUTS / "sweep_inputs.txt"
    )
    fcos = {
        rc: h177.parse_single(
            h177.SINGLE / f"sweep_fcos_{rc}_status.txt"
        )
        for rc in h58.RCS
    }
    paired = {
        rc: h177.parse_pair(
            h177.PAIRED / f"sweep_fsincos_{rc}_status.txt"
        )
        for rc in h58.RCS
    }
    mode_counts = collections.Counter()
    input_counts = collections.Counter()
    interval_counts = collections.Counter()
    groups: dict[
        tuple[str, str, int, int], collections.Counter[str]
    ] = collections.defaultdict(collections.Counter)
    model_groups: dict[
        str, collections.Counter[str]
    ] = collections.defaultdict(collections.Counter)

    for point in points:
        index = point.index
        pair_sine = tuple(
            paired[rc][index][0] for rc in h58.RCS
        )
        pair_cosine = tuple(
            paired[rc][index][1] for rc in h58.RCS
        )
        pair_c1 = tuple(
            paired[rc][index][2] for rc in h58.RCS
        )
        standalone_cosine = tuple(
            fcos[rc][index][0] for rc in h58.RCS
        )
        standalone_cosine_c1 = tuple(
            fcos[rc][index][1] for rc in h58.RCS
        )
        sine_mode = sum(
            left != right
            for left, right in zip(point.outputs, pair_sine)
        )
        cosine_mode = sum(
            left != right
            for left, right in zip(
                standalone_cosine, pair_cosine
            )
        )
        mode_counts["sine"] += sine_mode
        mode_counts["cosine"] += cosine_mode
        input_counts["sine"] += bool(sine_mode)
        input_counts["cosine"] += bool(cosine_mode)

        pair_sine_point = h177.interval_point(
            point, pair_sine, (False,) * len(h58.RCS)
        )
        standalone_cosine_point = h177.interval_point(
            point, standalone_cosine, standalone_cosine_c1
        )
        pair_cosine_point = h177.interval_point(
            point, pair_cosine, pair_c1
        )
        sine_relation = h177.overlap_relation(
            h169.interval(point),
            h169.interval(pair_sine_point),
        )
        cosine_relation = h177.overlap_relation(
            h169.interval(standalone_cosine_point),
            h169.interval(pair_cosine_point),
        )
        interval_counts[f"sine-{sine_relation}"] += 1
        interval_counts[f"cosine-{cosine_relation}"] += 1

        model_metric = h170.point_metric(
            point, h169.hidden(point)
        )
        model_kind = (
            "model-miss" if model_metric[1] else "model-hit"
        )
        model_groups[model_kind][sine_relation] += 1
        model_groups[model_kind][
            "sibling-value-diff"
        ] += bool(sine_mode)

        key = (
            point.family,
            point.source,
            point.signed_n & 3,
            point.point.cell,
        )
        groups[key]["points"] += 1
        groups[key]["sine-diff"] += bool(sine_mode)
        groups[key]["cosine-diff"] += bool(cosine_mode)

    print(f"h178 table-active sweep points: {len(points)}")
    print(
        "  standalone/paired value differences: "
        f"sine modes={mode_counts['sine']}/{len(points) * 3} "
        f"inputs={input_counts['sine']}/{len(points)}; "
        f"cosine modes={mode_counts['cosine']}/{len(points) * 3} "
        f"inputs={input_counts['cosine']}/{len(points)}"
    )
    print(f"  interval relations: {dict(interval_counts)}")
    print("  standalone-FSIN model correlation:")
    for name, counts in model_groups.items():
        print(f"    {name}: {dict(counts)}")
    print("  groups with sibling value differences:")
    for key, counts in sorted(groups.items()):
        if counts["sine-diff"] or counts["cosine-diff"]:
            print(f"    {key}: {dict(counts)}")


if __name__ == "__main__":
    main()
