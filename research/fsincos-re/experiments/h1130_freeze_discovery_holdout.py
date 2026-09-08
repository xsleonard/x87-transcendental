#!/usr/bin/env python3
"""Freeze the label-blind h1127b discovery/holdout partition.

The partition is structural, not random and not hardware-label dependent:

* same-cell-netlist and discrete-sibling rows are discovery rows;
* support-boundary rows are a sealed holdout until a candidate is frozen.

The output also records the zero-based input ordinal within each rounding-mode
capture file.  That makes the later hardware join mechanical and auditable.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import Counter, defaultdict
from pathlib import Path


DISCOVERY_TIERS = frozenset({"same-cell-netlist", "discrete-sibling"})
HOLDOUT_TIERS = frozenset({"support-boundary"})
EXPECTED_COUNTS = {
    "all": 671,
    "discovery": 129,
    "sealed-holdout": 542,
}


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def read_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        if reader.fieldnames is None:
            raise SystemExit(f"missing header: {path}")
        return list(reader.fieldnames), list(reader)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("tmp/ledger33/current/h1127b_r59_challenge_manifest.tsv"),
    )
    parser.add_argument(
        "--features",
        type=Path,
        default=Path("tmp/ledger33/current/h1127b_r59_challenge_features.tsv"),
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("tmp/ledger33/current/h1130_r59_frozen_partition.tsv"),
    )
    args = parser.parse_args()

    manifest_fields, manifest = read_tsv(args.manifest)
    _, features = read_tsv(args.features)
    if len(manifest) != EXPECTED_COUNTS["all"] or len(features) != len(manifest):
        raise SystemExit(
            f"unexpected row counts: manifest={len(manifest)} features={len(features)}"
        )

    keys = [(row["mode"], row["op"]) for row in manifest]
    feature_keys = [(row["mode"], row["op"]) for row in features]
    if len(set(keys)) != len(keys):
        raise SystemExit("duplicate (mode, operand) pair in manifest")
    if keys != feature_keys:
        raise SystemExit("manifest/features row order differs")

    forbidden = {"hw", "hardware", "actual", "verdict", "match"}
    present_forbidden = forbidden.intersection(field.lower() for field in manifest_fields)
    if present_forbidden:
        raise SystemExit(f"manifest unexpectedly contains labels: {sorted(present_forbidden)}")

    ordinals: defaultdict[str, int] = defaultdict(int)
    output: list[dict[str, str]] = []
    for row in manifest:
        tier = row["challenge_tier"]
        if tier in DISCOVERY_TIERS:
            partition = "discovery"
        elif tier in HOLDOUT_TIERS:
            partition = "sealed-holdout"
        else:
            raise SystemExit(f"unassigned challenge tier: {tier!r}")

        mode = row["mode"]
        enriched = dict(row)
        enriched["partition"] = partition
        enriched["mode_ordinal"] = str(ordinals[mode])
        ordinals[mode] += 1
        output.append(enriched)

    counts = Counter(row["partition"] for row in output)
    for name, expected in EXPECTED_COUNTS.items():
        actual = len(output) if name == "all" else counts[name]
        if actual != expected:
            raise SystemExit(f"unexpected {name} count: {actual}, expected {expected}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    output_fields = manifest_fields + ["partition", "mode_ordinal"]
    with args.out.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=output_fields, delimiter="\t")
        writer.writeheader()
        writer.writerows(output)

    print(f"manifest_sha256={digest(args.manifest)}")
    print(f"features_sha256={digest(args.features)}")
    print(f"partition_sha256={digest(args.out)}")
    print(f"partition_rows={len(output)}")
    print(f"discovery_rows={counts['discovery']}")
    print(f"sealed_holdout_rows={counts['sealed-holdout']}")
    print("mode_rows=" + ",".join(f"{mode}:{ordinals[mode]}" for mode in sorted(ordinals)))


if __name__ == "__main__":
    main()
