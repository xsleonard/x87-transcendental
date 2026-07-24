#!/usr/bin/env python3
"""Separate the widths in h163's best Round-33 product class.

h163 validates a sticky-preserving fifth-product state but its 33 inputs
leave 64/65-bit away, 66..71-bit odd, 72-bit RN, and exact carriers tied.
This pass predeclares one representative at each width and constructs only
architectural inputs on which at least two representatives predict
different output/C1 observations.
"""

from __future__ import annotations

import argparse
import collections
import dataclasses
import pathlib
import random
import sys

import h58_constraint_search as h58
import h110_fsin_standalone as h110
import h121_fsin_internal_cosine as h121
import h147_fsin_cosine_boolean_discriminator as h147
import h163_fsin_cosine_product_discriminator as h163


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = (
    ROOT
    / "capture-kit"
    / "inputs"
    / "constraint_fsin_cosine_product_width_h165.txt"
)
DEFAULT_METADATA = (
    ROOT
    / "capture-kit"
    / "inputs"
    / "constraint_fsin_cosine_product_width_h165.meta.txt"
)
SEED = 0xF165C5
NAMES = (
    "product5-64a",
    "product5-65a",
    "product5-66o",
    "product5-67o",
    "product5-68o",
    "product5-69o",
    "product5-70o",
    "product5-71o",
    "product5-72r",
    "product5-exact",
)
CANDIDATES = tuple(
    candidate
    for name in NAMES
    for candidate in h163.CANDIDATES
    if candidate.name == name
)
if tuple(candidate.name for candidate in CANDIDATES) != NAMES:
    raise RuntimeError("h165 candidate declaration mismatch")


def generate(
    output: pathlib.Path,
    metadata: pathlib.Path,
    count: int,
    scan_limit: int,
) -> None:
    rng = random.Random(SEED)
    rows = []
    meta = []
    residuals = set()
    pair_counts: collections.Counter[str] = collections.Counter()
    for scan_index in range(scan_limit):
        prepared = h163.construct_input(rng, scan_index)
        if prepared is None:
            continue
        se, sig, point, signed_n, r_se, r_sig = prepared
        state = h163.prepare_state(point)
        if not h163.selected(state):
            continue
        key = signed_n & 3, r_se, r_sig
        if key in residuals:
            continue
        profiles = tuple(
            h163.profile(state, candidate)
            for candidate in CANDIDATES
        )
        classes: dict[
            tuple[tuple[tuple[int, int], bool], ...],
            list[str],
        ] = {}
        for candidate, profile in zip(CANDIDATES, profiles):
            classes.setdefault(profile, []).append(candidate.name)
        if len(classes) < 2:
            continue
        residuals.add(key)
        rows.append(f"{se:04x} {sig:016x}")
        labels = []
        for class_index, names in enumerate(classes.values()):
            labels.append(
                f"{class_index}:" + ",".join(names)
            )
        meta.append(
            f"{scan_index} {signed_n} {r_se:04x} "
            f"{r_sig:016x} {';'.join(labels)}"
        )
        for left_index, left in enumerate(CANDIDATES):
            for right, right_profile in zip(
                CANDIDATES[left_index + 1 :],
                profiles[left_index + 1 :],
            ):
                if profiles[left_index] != right_profile:
                    pair_counts[
                        f"{left.name}/{right.name}"
                    ] += 1
        if len(rows) >= count:
            break
    if len(rows) < count:
        raise SystemExit(
            f"h165 selected {len(rows)} inputs after "
            f"{scan_limit} constructed scans; wanted {count}"
        )
    output.write_text("\n".join(rows) + "\n")
    metadata.write_text("\n".join(meta) + "\n")
    print(
        f"h165: selected {len(rows)} pairwise separators "
        f"from {scan_index + 1} constructed scans; "
        f"covered_pairs={len(pair_counts)}/45; "
        f"min_pair={min(pair_counts.values())}; "
        f"seed={SEED:#x}",
        file=sys.stderr,
    )


def load_capture(
    inputs: pathlib.Path, capture: pathlib.Path
) -> list[h121.Point]:
    input_rows = [
        tuple(int(field, 16) for field in line.split())
        for line in inputs.read_text().splitlines()
    ]
    modes = [
        (
            capture
            / f"constraint_fsin_cosine_product_width_h165_{rc}_status.txt"
        ).read_text().splitlines()
        for rc in h58.RCS
    ]
    if any(len(lines) != len(input_rows) for lines in modes):
        raise SystemExit("h165 input/capture line counts differ")
    result = []
    for index, (se, sig) in enumerate(input_rows):
        prepared = h147.point_from_input(index, se, sig)
        if prepared is None:
            raise SystemExit(
                f"h165 input {index + 1} is not active"
            )
        point = prepared[0]
        outputs = []
        c1 = []
        for lines in modes:
            fields = lines[index].split()
            if (
                len(fields) != 5
                or fields[0] != "OK"
                or fields[3] != "SW"
            ):
                raise ValueError(lines[index])
            outputs.append(
                (int(fields[1], 16), int(fields[2], 16))
            )
            c1.append(bool(int(fields[4], 16) & 0x0200))
        result.append(
            dataclasses.replace(
                point,
                observed=dataclasses.replace(
                    point.observed,
                    outputs=tuple(outputs),
                    c1=tuple(c1),
                ),
            )
        )
    return result


def score(
    points: list[h121.Point],
    candidate: h163.Candidate,
) -> h110.Score:
    result = h110.Score()
    for point in points:
        state = h163.prepare_state(point)
        value = h163.hidden(state, candidate)
        result.total += 1
        any_miss = False
        for index, rc in enumerate(h58.RCS):
            output = h58.x87_round(value, rc)
            mismatch = output != point.observed.outputs[index]
            result.mode_misses += mismatch
            any_miss |= mismatch
            if not mismatch:
                c1 = h110.compare_magnitude(output, value) > 0
                result.c1_misses += (
                    c1 != point.observed.c1[index]
                )
        result.output_misses += any_miss
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--generate", action="store_true")
    parser.add_argument("--score", type=pathlib.Path)
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument(
        "--scan-limit", type=int, default=30_000_000
    )
    parser.add_argument(
        "--output", type=pathlib.Path, default=DEFAULT_OUTPUT
    )
    parser.add_argument(
        "--metadata",
        type=pathlib.Path,
        default=DEFAULT_METADATA,
    )
    args = parser.parse_args()
    if args.generate:
        generate(
            args.output,
            args.metadata,
            args.count,
            args.scan_limit,
        )
    if args.score is not None:
        points = load_capture(args.output, args.score)
        ranked = sorted(
            (
                score(points, candidate).rank(),
                candidate.name,
                score(points, candidate),
            )
            for candidate in CANDIDATES
        )
        print(
            f"loaded {len(points)} fresh h165 separators"
        )
        for _, name, value in ranked:
            print(f"  {name:20s} {value.describe()}")
    if not args.generate and args.score is None:
        parser.error(
            "select --generate and/or --score CAPTURE_DIRECTORY"
        )


if __name__ == "__main__":
    main()
