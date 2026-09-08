#!/usr/bin/env python3
"""Score h1127b discovery rows while keeping support-boundary labels sealed."""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import Counter, defaultdict
from pathlib import Path


EXPECTED_PARTITION_SHA256 = (
    "4ea647b3a8faeb6ef9b3a374138ab608ce81a326af7f0485bccbe443f289ec69"
)
EXPECTED_ROWS = {"rd": 176, "rn": 257, "ru": 238}
EXPECTED_PARTITIONS = {"discovery": 129, "sealed-holdout": 542}


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


def read_raw(path: Path, expected: int) -> list[str]:
    results: list[str] = []
    with path.open() as stream:
        for line_number, line in enumerate(stream, 1):
            fields = line.split()
            if len(fields) != 3 or fields[0] != "OK":
                raise SystemExit(f"bad hardware row {path}:{line_number}")
            se, sig = fields[1].lower(), fields[2].lower()
            if len(se) != 4 or len(sig) != 16:
                raise SystemExit(f"bad hardware value {path}:{line_number}")
            results.append(f"{se}:{sig}")
    if len(results) != expected:
        raise SystemExit(f"unexpected row count for {path}: {len(results)} != {expected}")
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--partition",
        type=Path,
        default=Path("tmp/ledger33/current/h1130_r59_frozen_partition.tsv"),
    )
    parser.add_argument(
        "--features",
        type=Path,
        default=Path("tmp/ledger33/current/h1127b_r59_challenge_features.tsv"),
    )
    parser.add_argument(
        "--raw-dir", type=Path, default=Path("tmp/ledger33/current")
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("tmp/ledger33/current/h1131_r59_discovery_score.tsv"),
    )
    args = parser.parse_args()

    if args.out.exists():
        raise SystemExit(f"refusing to overwrite {args.out}")
    partition_hash = digest(args.partition)
    if partition_hash != EXPECTED_PARTITION_SHA256:
        raise SystemExit(
            f"partition hash changed: {partition_hash} != {EXPECTED_PARTITION_SHA256}"
        )

    partition_fields, partition = read_tsv(args.partition)
    feature_fields, features = read_tsv(args.features)
    feature_by_key = {(row["mode"], row["op"]): row for row in features}
    if len(feature_by_key) != len(features):
        raise SystemExit("duplicate key in feature table")
    if len(partition) != len(features):
        raise SystemExit("partition/features row-count mismatch")

    hardware = {
        mode: read_raw(
            args.raw_dir / f"h1127b_hw_cos_{mode}.raw", expected
        )
        for mode, expected in EXPECTED_ROWS.items()
    }

    partition_counts = Counter(row["partition"] for row in partition)
    if dict(partition_counts) != EXPECTED_PARTITIONS:
        raise SystemExit(f"partition counts changed: {dict(partition_counts)}")

    discovery: list[dict[str, str]] = []
    verdicts: Counter[str] = Counter()
    endpoint_matches: Counter[str] = Counter()
    grouped: defaultdict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    for assignment in partition:
        key = (assignment["mode"], assignment["op"])
        feature = feature_by_key.get(key)
        if feature is None:
            raise SystemExit(f"missing feature row for {key}")
        if assignment["partition"] == "sealed-holdout":
            continue

        mode = assignment["mode"]
        ordinal = int(assignment["mode_ordinal"])
        hw = hardware[mode][ordinal]
        row = dict(feature)
        row["partition"] = "discovery"
        row["mode_ordinal"] = str(ordinal)
        row["hw"] = hw
        matches = [
            name
            for name in ("base", "force_minus2", "force_plus1")
            if row[name] == hw
        ]
        row["endpoint_matches"] = ",".join(matches) or "none"
        row["verdict"] = "EXACT" if row["base"] == hw else "MISS"
        discovery.append(row)
        verdicts[row["verdict"]] += 1
        endpoint_matches[row["endpoint_matches"]] += 1
        grouped[("mode", mode)][row["verdict"]] += 1
        grouped[("tier", row["challenge_tier"])][row["verdict"]] += 1
        grouped[("branch", row["branch"])][row["verdict"]] += 1
        grouped[("anchor", row["anchor"])][row["verdict"]] += 1

    prefix = [
        "mode",
        "op",
        "hw",
        "base",
        "force_minus2",
        "force_plus1",
        "endpoint_matches",
        "verdict",
        "partition",
        "mode_ordinal",
    ]
    columns = prefix + [name for name in feature_fields if name not in prefix]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="") as stream:
        writer = csv.DictWriter(
            stream, fieldnames=columns, delimiter="\t", extrasaction="ignore"
        )
        writer.writeheader()
        writer.writerows(discovery)

    print(f"partition_sha256={partition_hash}")
    for mode in sorted(hardware):
        path = args.raw_dir / f"h1127b_hw_cos_{mode}.raw"
        print(f"raw_{mode}_sha256={digest(path)} rows={len(hardware[mode])}")
    print(f"discovery_output_sha256={digest(args.out)}")
    print(f"discovery_rows={len(discovery)} verdicts={dict(verdicts)}")
    print(f"endpoint_matches={dict(endpoint_matches)}")
    print(f"sealed_holdout_rows={partition_counts['sealed-holdout']} labels_not_emitted")
    for (kind, name), counts in sorted(grouped.items()):
        print(f"{kind}={name or '-'} exact={counts['EXACT']} miss={counts['MISS']}")


if __name__ == "__main__":
    main()
