#!/usr/bin/env python3
"""Map h347 Round-49 residuals into seed-relative transition geometry."""

from __future__ import annotations

import argparse
import collections
import dataclasses
import pathlib

import h171_fsin_table_correction_discriminator as h171


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_CAPTURE = ROOT / "capture-kit-captures" / "skylake-trig-h347"
DEFAULT_METADATA = (
    ROOT / "capture-kit" / "inputs" /
    "constraint_round49_residual_neighbors_h347.meta.txt"
)


@dataclasses.dataclass(frozen=True)
class Residual:
    index: int
    se: int
    sig: int
    rc: str
    lane: str
    step: int


def seeds(path: pathlib.Path):
    result = []
    for line in path.read_text().splitlines():
        if not line or line.startswith("#"):
            continue
        fields = line.split()
        result.append((int(fields[0], 16), int(fields[1], 16)))
    return tuple(result)


def records(path: pathlib.Path):
    result = []
    for line in path.read_text().splitlines():
        if not line or line.startswith("#"):
            continue
        fields = line.split()
        result.append(Residual(
            int(fields[0]),
            int(fields[1], 16),
            int(fields[2], 16),
            fields[3],
            fields[4],
            int(fields[10]),
        ))
    return result


def seed_delta(record: Residual, values):
    choices = []
    for seed_index, (seed_se, seed_sig) in enumerate(values):
        if record.se not in (seed_se, seed_se ^ 0x8000):
            continue
        choices.append((
            abs(record.sig - seed_sig),
            seed_index,
            int(record.se != seed_se),
            record.sig - seed_sig,
        ))
    if not choices:
        raise AssertionError(record)
    return min(choices)


def runs(values):
    values = sorted(set(values))
    if not values:
        return []
    result = []
    start = previous = values[0]
    for value in values[1:]:
        if value != previous + 1:
            result.append((start, previous))
            start = value
        previous = value
    result.append((start, previous))
    return result


def format_runs(values):
    return ",".join(
        str(start) if start == end else f"{start}..{end}"
        for start, end in runs(values)
    ) or "none"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture", type=pathlib.Path, default=DEFAULT_CAPTURE)
    parser.add_argument("--metadata", type=pathlib.Path, default=DEFAULT_METADATA)
    args = parser.parse_args()

    seed_values = seeds(args.metadata)
    residuals = records(args.capture / "residuals.tsv")
    counts = collections.Counter()
    groups = collections.defaultdict(list)
    symmetry = collections.defaultdict(set)
    affected_inputs = set()
    for record in residuals:
        _, seed_index, mirrored, delta = seed_delta(record, seed_values)
        observed = h171.observed_from_input(record.index, record.se, record.sig)
        if observed is None:
            raise AssertionError(record)
        counts["lane", record.lane] += 1
        counts["rc", record.rc] += 1
        counts["step", record.step] += 1
        counts["path", observed.source, observed.family] += 1
        counts["cell", observed.point.cell] += 1
        counts["seed", seed_index] += 1
        groups[seed_index, mirrored, record.lane, record.rc, record.step].append(delta)
        symmetry_rc = record.rc
        symmetry_step = record.step
        if mirrored and record.lane == "sin":
            symmetry_rc = {"rn": "rn", "rd": "ru", "ru": "rd"}[record.rc]
            symmetry_step = -record.step
        symmetry[
            seed_index,
            record.lane,
            symmetry_rc,
            symmetry_step,
            mirrored,
        ].add(delta)
        affected_inputs.add((record.se, record.sig))

    print(
        f"h351 neighborhood geometry: residuals={len(residuals)} "
        f"affected-inputs={len(affected_inputs)} seeds={len(seed_values)}"
    )
    for prefix in ("lane", "rc", "step", "path", "cell", "seed"):
        selected = {
            key[1:] if len(key) > 2 else key[1]: value
            for key, value in counts.items()
            if key[0] == prefix
        }
        print(f"  {prefix}: {dict(sorted(selected.items(), key=lambda item: str(item[0])))}")

    matched = original_only = mirror_only = 0
    bases = {
        key[:-1]
        for key in symmetry
    }
    for base in bases:
        original = symmetry.get((*base, 0), set())
        mirror = symmetry.get((*base, 1), set())
        matched += len(original & mirror)
        original_only += len(original - mirror)
        mirror_only += len(mirror - original)
    print(
        f"  sign-normalized mirror sets: matched={matched} "
        f"original-only={original_only} mirror-only={mirror_only}"
    )

    for key in sorted(groups):
        seed_index, mirrored, lane, rc, step = key
        se, sig = seed_values[seed_index]
        print(
            f"  seed={seed_index + 1:02d} {se:04x}:{sig:016x} "
            f"mirror={mirrored} lane={lane} rc={rc} step={step:+d} "
            f"count={len(groups[key])} deltas={format_runs(groups[key])}"
        )


if __name__ == "__main__":
    main()
