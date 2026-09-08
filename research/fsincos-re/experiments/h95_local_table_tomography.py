#!/usr/bin/env python3
"""Generate locally densified tomography around the h93 master failures.

For each of the 195 remaining table states, scan nearby directly
representable residuals.  Keep a residual only when at least two Round-21
cell/output projections lie within a narrow RN-boundary window, then emit all
valid cells in that family.  Hardware is not consulted during generation.
"""

from __future__ import annotations

import argparse
import math
import pathlib

import h58_constraint_search as h58
import h60_round16_parity as h60
import h78_paired_table_tomography as h78
import h79_table_state_bias as h79
import h80_round21_parity as h80
import h93_master_table_tomography as h93


ROOT = pathlib.Path(__file__).resolve().parents[1]
MASTER_INPUTS = ROOT / "capture-kit" / "inputs" / "sweep_inputs.txt"
MASTER_CAPTURE = (
    ROOT / "capture-kit-captures" / "pentiumII" / "sweep_rn.txt"
)
MODEL = ROOT / "src" / "fsincos_skylake"
DEFAULT_OUTPUT = (
    ROOT / "capture-kit" / "inputs" / "constraint_table_local_h95.txt"
)
DEFAULT_METADATA = (
    ROOT
    / "capture-kit"
    / "inputs"
    / "constraint_table_local_h95.meta.txt"
)


def close_count(
    family: str,
    residual: int,
    window_bits: int,
) -> tuple[int, int, list[tuple[int, int, int]]]:
    close = 0
    closest_bits = 0
    emitted = []
    for cell in h78.family_spec(family)[0]:
        direct = h93.direct_for(family, cell, residual)
        if direct is None:
            continue
        se, sig = direct
        raw = h58.RawPoint(
            index=0,
            sign=0,
            exponent=(se & 0x7FFF) - 16383,
            sig=sig,
            hw=h78.DUMMY_HW,
        )
        point = h58.prepare(raw)
        numerator = 5 if point.wide else 4
        values = h79.values(point, h79.BASE, numerator)
        for value in values:
            distance = h78.boundary_distance(value)
            if distance is None:
                continue
            numerator_distance, denominator = distance
            if numerator_distance << window_bits <= denominator:
                close += 1
            if not numerator_distance:
                closest_bits = 999
            else:
                closest_bits = max(
                    closest_bits,
                    math.floor(
                        math.log2(denominator)
                        - math.log2(numerator_distance)
                    ),
                )
        emitted.append((cell, se, sig))
    return close, closest_bits, emitted


def offset_order(limit: int):
    yield 0
    for magnitude in range(1, limit + 1):
        yield magnitude
        yield -magnitude


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=pathlib.Path, default=MODEL)
    parser.add_argument("--output", type=pathlib.Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--metadata", type=pathlib.Path, default=DEFAULT_METADATA
    )
    parser.add_argument("--groups-per-source", type=int, default=4)
    parser.add_argument("--scan-radius", type=int, default=8192)
    parser.add_argument("--window-bits", type=int, default=8)
    parser.add_argument("--min-close", type=int, default=2)
    args = parser.parse_args()

    input_lines = MASTER_INPUTS.read_text().splitlines()
    inputs = [
        tuple(int(field, 16) for field in line.split())
        for line in input_lines
    ]
    hardware = [
        h60.parse_output(line)
        for line in MASTER_CAPTURE.read_text().splitlines()
    ]
    candidate = h93.run_candidate(
        args.binary.resolve(),
        "\n".join(input_lines) + "\n",
    )
    failures = [
        index
        for index, (actual, expected) in enumerate(zip(candidate, hardware))
        if actual != expected
    ]
    if len(failures) != 195:
        raise SystemExit(
            f"expected 195 current failures, found {len(failures)}"
        )

    output_rows: list[str] = []
    metadata_rows: list[str] = []
    selected_sources = 0
    selected_groups = 0
    selected_by_family = {"narrow": 0, "wide": 0}
    seen_groups: set[tuple[str, int]] = set()
    for source_group, index in enumerate(failures):
        active = h80.active_table_input(*inputs[index])
        if active is None:
            raise AssertionError("remaining failure is not table-active")
        _, point, _ = active
        family = "wide" if point.wide else "narrow"
        target_scale = -64 if point.wide else -65
        exact_units = h93.signed_units(point.a, target_scale)
        if exact_units is None:
            sign, significand, scale = point.a
            shift = target_scale - scale
            if shift <= 0:
                raise AssertionError("unexpected half-grid scale")
            magnitude_floor = significand >> shift
            center = -magnitude_floor if sign else magnitude_floor
        else:
            center = exact_units

        found = 0
        for offset in offset_order(args.scan_radius):
            residual = center + offset
            key = family, residual
            if key in seen_groups:
                continue
            close, closest_bits, emitted = close_count(
                family, residual, args.window_bits
            )
            if close < args.min_close or len(emitted) < 2:
                continue
            seen_groups.add(key)
            local_group = selected_groups
            selected_groups += 1
            selected_by_family[family] += 1
            found += 1
            for cell, se, sig in emitted:
                output_rows.append(f"{se:04x} {sig:016x}")
                metadata_rows.append(
                    f"{family} {local_group} {residual} {cell} "
                    f"{close} {closest_bits} {source_group} {index + 1}"
                )
            if found >= args.groups_per_source:
                break
        selected_sources += bool(found)

    args.output.write_text("\n".join(output_rows) + "\n")
    args.metadata.write_text("\n".join(metadata_rows) + "\n")
    print(
        f"h95: sources={len(failures)} with-groups={selected_sources}; "
        f"groups={selected_groups} {selected_by_family}; "
        f"inputs={len(output_rows)}; "
        f"window=2^-{args.window_bits}; min-close={args.min_close}; "
        f"scan-radius={args.scan_radius}"
    )


if __name__ == "__main__":
    main()
