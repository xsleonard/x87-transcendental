#!/usr/bin/env python3
"""Triangulate dense table carriers across FSIN, FCOS, and FSINCOS.

The dense set supplies the same reduced argument to all three x87
instructions.  RN/RD/RU results are inverted into hidden-value intervals.
This pass measures whether standalone FSIN's sine carrier overlaps the
paired FSINCOS sine carrier, and whether standalone FCOS's cosine carrier
overlaps paired FSINCOS cosine.  It also correlates sibling differences with
the current standalone-FSIN table residual.
"""

from __future__ import annotations

import collections
import dataclasses
import fractions
import pathlib

import h58_constraint_search as h58
import h131_fsin_table_c1_search as h131
import h169_fsin_table_round33_tomography as h169
import h170_fsin_table_correction_search as h170


ROOT = pathlib.Path(__file__).resolve().parents[1]
SINGLE = (
    ROOT / "capture-kit-captures" / "skylake-fsin-h110"
)
PAIRED = (
    ROOT / "capture-kit-captures" / "skylake-fsin-h177"
)
Fraction = fractions.Fraction


def parse_single(path: pathlib.Path) -> list[tuple[tuple[int, int], bool]]:
    result = []
    for line in path.read_text().splitlines():
        fields = line.split()
        if (
            len(fields) == 3
            and fields[0] == "C2"
            and fields[1] == "SW"
        ):
            result.append(((-1, 0), False))
            continue
        if (
            len(fields) != 5
            or fields[0] != "OK"
            or fields[3] != "SW"
        ):
            raise ValueError(line)
        result.append(
            (
                (int(fields[1], 16), int(fields[2], 16)),
                bool(int(fields[4], 16) & 0x0200),
            )
        )
    return result


def parse_pair(
    path: pathlib.Path,
) -> list[tuple[tuple[int, int], tuple[int, int], bool]]:
    result = []
    for line in path.read_text().splitlines():
        fields = line.split()
        if (
            len(fields) == 3
            and fields[0] == "C2"
            and fields[1] == "SW"
        ):
            result.append(((-1, 0), (-1, 0), False))
            continue
        if (
            len(fields) != 7
            or fields[0] != "OK"
            or fields[5] != "SW"
        ):
            raise ValueError(line)
        result.append(
            (
                (int(fields[1], 16), int(fields[2], 16)),
                (int(fields[3], 16), int(fields[4], 16)),
                bool(int(fields[6], 16) & 0x0200),
            )
        )
    return result


def overlap_relation(
    left: tuple[Fraction, Fraction],
    right: tuple[Fraction, Fraction],
) -> str:
    left_low, left_high = left
    right_low, right_high = right
    if left_high < right_low:
        return "paired-higher"
    if right_high < left_low:
        return "paired-lower"
    return "overlap"


def interval_point(
    point: h131.Observed,
    outputs: tuple[tuple[int, int], ...],
    c1: tuple[bool, ...],
) -> h131.Observed:
    return dataclasses.replace(point, outputs=outputs, c1=c1)


def main() -> None:
    points = h131.load_dataset(
        "dense", h131.INPUTS / "dense_qn.txt"
    )
    fcos = {
        rc: parse_single(
            SINGLE / f"dense_fcos_{rc}_status.txt"
        )
        for rc in h58.RCS
    }
    paired = {
        rc: parse_pair(
            PAIRED / f"dense_fsincos_{rc}_status.txt"
        )
        for rc in h58.RCS
    }
    if any(
        len(rows) != 240_000
        for rows in (*fcos.values(), *paired.values())
    ):
        raise SystemExit("h177 dense capture line count mismatch")

    sine_modes = 0
    sine_inputs = 0
    cosine_modes = 0
    cosine_inputs = 0
    cosine_c1 = 0
    sine_intervals: collections.Counter[str] = collections.Counter()
    cosine_intervals: collections.Counter[str] = collections.Counter()
    model_groups: dict[
        str, collections.Counter[str]
    ] = collections.defaultdict(collections.Counter)
    cells: dict[
        tuple[str, int], collections.Counter[str]
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

        sine_differences = sum(
            left != right
            for left, right in zip(point.outputs, pair_sine)
        )
        cosine_differences = sum(
            left != right
            for left, right in zip(
                standalone_cosine, pair_cosine
            )
        )
        sine_modes += sine_differences
        sine_inputs += bool(sine_differences)
        cosine_modes += cosine_differences
        cosine_inputs += bool(cosine_differences)
        cosine_c1 += sum(
            left != right
            for left, right in zip(
                standalone_cosine_c1, pair_c1
            )
        )

        sine_pair_point = interval_point(
            point, pair_sine, (False,) * len(h58.RCS)
        )
        standalone_cosine_point = interval_point(
            point, standalone_cosine, standalone_cosine_c1
        )
        pair_cosine_point = interval_point(
            point, pair_cosine, pair_c1
        )
        sine_relation = overlap_relation(
            h169.interval(point),
            h169.interval(sine_pair_point),
        )
        cosine_relation = overlap_relation(
            h169.interval(standalone_cosine_point),
            h169.interval(pair_cosine_point),
        )
        sine_intervals[sine_relation] += 1
        cosine_intervals[cosine_relation] += 1

        model_metric = h170.point_metric(
            point, h169.hidden(point)
        )
        model_kind = (
            "model-miss" if model_metric[1] else "model-hit"
        )
        model_groups[model_kind][sine_relation] += 1
        model_groups[model_kind][
            "sibling-value-diff"
        ] += bool(sine_differences)
        cell = point.point.cell
        key = point.family, cell
        cells[key]["points"] += 1
        cells[key]["fsin-pair-diff"] += bool(
            sine_differences
        )
        cells[key]["fcos-pair-diff"] += bool(
            cosine_differences
        )

    print(f"h177 dense table points: {len(points)}")
    print(
        "  FSIN versus FSINCOS sine: "
        f"mode={sine_modes}/{len(points) * 3} "
        f"input={sine_inputs}/{len(points)} "
        f"intervals={dict(sine_intervals)}"
    )
    print(
        "  FCOS versus FSINCOS cosine: "
        f"mode={cosine_modes}/{len(points) * 3} "
        f"input={cosine_inputs}/{len(points)} "
        f"C1={cosine_c1}/{len(points) * 3} "
        f"intervals={dict(cosine_intervals)}"
    )
    print("  standalone-FSIN model correlation:")
    for name, counts in model_groups.items():
        print(f"    {name}: {dict(counts)}")
    print("  cells with sibling value differences:")
    for key, counts in sorted(cells.items()):
        if (
            counts["fsin-pair-diff"]
            or counts["fcos-pair-diff"]
        ):
            print(f"    {key}: {dict(counts)}")


if __name__ == "__main__":
    main()
