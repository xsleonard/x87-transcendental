#!/usr/bin/env python3
"""Intersect h93's targeted table-state constraints.

Original reduced inputs are first unrotated back to their kernel sine/cosine
outputs, including the RD/RU swap required when undoing a sign change.  Each
representable residual is then combined with all of its direct paired-cell
projections.  The resulting exact polygons constrain corrections to the
baseline shared state ``(U=1+t, S)``.
"""

from __future__ import annotations

import dataclasses
import pathlib
import statistics

import h58_constraint_search as h58
import h59_discriminator as h59
import h78_paired_table_tomography as h78
import h80_round21_parity as h80


ROOT = pathlib.Path(__file__).resolve().parents[1]
INPUTS = (
    ROOT / "capture-kit" / "inputs" / "constraint_table_residual_h93.txt"
)
METADATA = (
    ROOT
    / "capture-kit"
    / "inputs"
    / "constraint_table_residual_h93.meta.txt"
)
CAPTURE = ROOT / "capture-kit-captures" / "skylake-h93-table-residual"
PREFIX = "constraint_table_residual"


def negate(output: tuple[int, int]) -> tuple[int, int]:
    return output[0] ^ 0x8000, output[1]


def unrotate_hardware(
    hardware: tuple[
        tuple[tuple[int, int], tuple[int, int]],
        tuple[tuple[int, int], tuple[int, int]],
        tuple[tuple[int, int], tuple[int, int]],
    ],
    quadrant: int,
) -> tuple[
    tuple[tuple[int, int], tuple[int, int]],
    tuple[tuple[int, int], tuple[int, int]],
    tuple[tuple[int, int], tuple[int, int]],
]:
    """Undo h60.rotate on rounded values, respecting directed modes."""
    flip = (0, 2, 1)
    result = []
    for mode in range(3):
        sine, cosine = hardware[mode]
        flipped_sine, flipped_cosine = hardware[flip[mode]]
        quadrant &= 3
        if quadrant == 0:
            kernel = sine, cosine
        elif quadrant == 1:
            kernel = negate(flipped_cosine), sine
        elif quadrant == 2:
            kernel = negate(flipped_sine), negate(flipped_cosine)
        else:
            kernel = cosine, negate(flipped_sine)
        result.append(kernel)
    return tuple(result)  # type: ignore[return-value]


def make_positive_kernel(
    hardware: tuple[
        tuple[tuple[int, int], tuple[int, int]],
        tuple[tuple[int, int], tuple[int, int]],
        tuple[tuple[int, int], tuple[int, int]],
    ],
) -> tuple[
    tuple[tuple[int, int], tuple[int, int]],
    tuple[tuple[int, int], tuple[int, int]],
    tuple[tuple[int, int], tuple[int, int]],
]:
    flip = (0, 2, 1)
    return tuple(
        (negate(hardware[flip[mode]][0]), hardware[mode][1])
        for mode in range(3)
    )  # type: ignore[return-value]


def main() -> None:
    raw = h59.load_score_points(INPUTS, CAPTURE, PREFIX)
    input_rows = [
        tuple(int(field, 16) for field in line.split())
        for line in INPUTS.read_text().splitlines()
    ]
    metadata = [
        line.split() for line in METADATA.read_text().splitlines()
    ]
    if len(raw) != len(metadata):
        raise SystemExit("h93 input/metadata/capture line counts differ")

    groups: dict[int, list[h58.PreparedPoint]] = {}
    family_by_group: dict[int, str] = {}
    paired_by_group: dict[int, int] = {}
    for item, fields in zip(raw, metadata):
        group = int(fields[0])
        kind = fields[1]
        family = fields[3]
        family_by_group[group] = family
        if kind == "paired":
            point = h58.prepare(item)
            paired_by_group[group] = paired_by_group.get(group, 0) + 1
        else:
            signed_n = int(fields[6])
            active = h80.active_table_input(
                *input_rows[item.index],
            )
            if active is None:
                raise AssertionError("h93 original is not table-active")
            actual_n, point, _ = active
            if actual_n != signed_n:
                raise AssertionError((actual_n, signed_n))
            kernel_hw = unrotate_hardware(item.hw, signed_n)
            if point.raw.sign:
                kernel_hw = make_positive_kernel(kernel_hw)
            point = dataclasses.replace(
                point,
                raw=dataclasses.replace(
                    point.raw, sign=0, hw=kernel_hw
                ),
            )
        groups.setdefault(group, []).append(point)

    summaries: dict[str, list[dict[str, float]]] = {
        "narrow": [],
        "wide": [],
    }
    empty = 0
    for group, points in sorted(groups.items()):
        inequalities, u0, s0 = h78.group_inequalities(points)
        vertices = h78.feasible_vertices(inequalities)
        if not vertices:
            empty += 1
            continue
        us = [vertex[0] for vertex in vertices]
        ss = [vertex[1] for vertex in vertices]
        u_low, u_high = min(us), max(us)
        s_low, s_high = min(ss), max(ss)
        u_center = (u_low + u_high) / 2
        s_center = (s_low + s_high) / 2
        s_orientation = 1 if s0[0] else -1
        record = {
            "group": float(group),
            "paired": float(paired_by_group.get(group, 0)),
            "u_width_log2": h78.log2_fraction(u_high - u_low),
            "s_width_log2": h78.log2_fraction(s_high - s_low),
            "u_center_ulp": float(u_center / h78.local_ulp(u0)),
            "s_toward_zero_ulp": float(
                s_orientation * s_center / h78.local_ulp(s0)
            ),
            "a_sign": float(points[0].a[0]),
            "a_exponent": float(
                points[0].a[2] + points[0].a[1].bit_length() - 1
            ),
        }
        summaries[family_by_group[group]].append(record)

    print(
        f"h93 groups={len(groups)} feasible={len(groups) - empty} "
        f"empty={empty}; paired-groups={len(paired_by_group)}"
    )
    for family, records in summaries.items():
        paired = [record for record in records if record["paired"]]
        tight = [
            record
            for record in paired
            if record["u_width_log2"] <= -68
            and record["s_width_log2"] <= -68
        ]
        print(
            f"{family}: feasible={len(records)} paired={len(paired)} "
            f"tight={len(tight)}"
        )
        for selected_name, selected in (
            ("paired", paired),
            ("tight", tight),
        ):
            if not selected:
                continue
            for key in ("u_center_ulp", "s_toward_zero_ulp"):
                values = [record[key] for record in selected]
                print(
                    f"  {selected_name} {key}: "
                    f"median={statistics.median(values):+.4f} "
                    f"mean={statistics.fmean(values):+.4f} "
                    f"min={min(values):+.4f} max={max(values):+.4f}"
                )
            print(
                f"  {selected_name} widths log2: "
                f"U={statistics.median(record['u_width_log2'] for record in selected):.2f} "
                f"S={statistics.median(record['s_width_log2'] for record in selected):.2f}"
            )


if __name__ == "__main__":
    main()
