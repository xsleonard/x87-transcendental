#!/usr/bin/env python3
"""Open and score the frozen h1127b support-boundary holdout."""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import Counter, defaultdict
from pathlib import Path


EXPECTED_FREEZE_SHA256 = (
    "1585da023fd20db5e2cf038b2beea15ccccf1f032d4a1a5ec6f4a8b4ac6750a7"
)
EXPECTED_FEATURES_SHA256 = (
    "33bb0c43dd953ee1f30e640d276129d2e62aa91c77314eac46d076fc26f71958"
)
EXPECTED_PARTITION_SHA256 = (
    "4ea647b3a8faeb6ef9b3a374138ab608ce81a326af7f0485bccbe443f289ec69"
)
EXPECTED_RAW_SHA256 = {
    "rd": "f7f58df0f56b636a1bc50141c99dc34044301dd4f8a901bd076d964d663e3763",
    "rn": "97eeaea80187b053315877629d5cdde51c4da76c5982166e9cc0ea36cc58b6cb",
    "ru": "7e27e3799e1cd6bff10d89d9b538b08fb420ed098d422babd5fb3204e8f6f9e6",
}
EXPECTED_ROWS = {"rd": 176, "rn": 257, "ru": 238}
EXPECTED_HOLDOUT_ROWS = 542


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
    values: list[str] = []
    with path.open() as stream:
        for line_number, line in enumerate(stream, 1):
            fields = line.split()
            if len(fields) != 3 or fields[0] != "OK":
                raise SystemExit(f"bad hardware row {path}:{line_number}")
            values.append(fields[1].lower() + ":" + fields[2].lower())
    if len(values) != expected:
        raise SystemExit(f"unexpected row count for {path}: {len(values)} != {expected}")
    return values


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--freeze",
        type=Path,
        default=Path("tmp/ledger33/current/h1132_r59_candidate_freeze.txt"),
    )
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
        default=Path("tmp/ledger33/current/h1133_r59_holdout_score.tsv"),
    )
    args = parser.parse_args()

    if args.out.exists():
        raise SystemExit(f"refusing to overwrite {args.out}")
    expected_hashes = (
        (args.freeze, EXPECTED_FREEZE_SHA256),
        (args.partition, EXPECTED_PARTITION_SHA256),
        (args.features, EXPECTED_FEATURES_SHA256),
    )
    for path, expected_hash in expected_hashes:
        actual_hash = digest(path)
        if actual_hash != expected_hash:
            raise SystemExit(f"frozen input changed: {path} {actual_hash} != {expected_hash}")

    partition_fields, partition = read_tsv(args.partition)
    feature_fields, features = read_tsv(args.features)
    feature_by_key = {(row["mode"], row["op"]): row for row in features}
    if len(feature_by_key) != len(features):
        raise SystemExit("duplicate key in feature table")

    hardware: dict[str, list[str]] = {}
    for mode, expected_rows in EXPECTED_ROWS.items():
        path = args.raw_dir / f"h1127b_hw_cos_{mode}.raw"
        actual_hash = digest(path)
        if actual_hash != EXPECTED_RAW_SHA256[mode]:
            raise SystemExit(f"raw capture changed: {path} {actual_hash}")
        hardware[mode] = read_raw(path, expected_rows)

    holdout: list[dict[str, str]] = []
    verdicts: Counter[str] = Counter()
    endpoint_matches: Counter[str] = Counter()
    grouped: defaultdict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    for assignment in partition:
        if assignment["partition"] != "sealed-holdout":
            continue
        mode = assignment["mode"]
        key = (mode, assignment["op"])
        feature = feature_by_key.get(key)
        if feature is None:
            raise SystemExit(f"missing feature row for {key}")
        ordinal = int(assignment["mode_ordinal"])
        hw = hardware[mode][ordinal]
        row = dict(feature)
        row["partition"] = "opened-holdout"
        row["mode_ordinal"] = str(ordinal)
        row["hw"] = hw
        matches = [
            name
            for name in ("base", "force_minus2", "force_plus1")
            if row[name] == hw
        ]
        row["endpoint_matches"] = ",".join(matches) or "none"
        row["verdict"] = "EXACT" if row["base"] == hw else "MISS"
        holdout.append(row)
        verdicts[row["verdict"]] += 1
        endpoint_matches[row["endpoint_matches"]] += 1
        grouped[("mode", mode)][row["verdict"]] += 1
        grouped[("branch", row["branch"])][row["verdict"]] += 1
        grouped[("anchor", row["anchor"])][row["verdict"]] += 1
        grouped[("upstream", row["upstream_anchor"])][row["verdict"]] += 1

    if len(holdout) != EXPECTED_HOLDOUT_ROWS:
        raise SystemExit(f"unexpected holdout count: {len(holdout)}")

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
        writer.writerows(holdout)

    print(f"holdout_output_sha256={digest(args.out)}")
    print(f"holdout_rows={len(holdout)} verdicts={dict(verdicts)}")
    print(f"endpoint_matches={dict(endpoint_matches)}")
    for (kind, name), counts in sorted(grouped.items()):
        print(f"{kind}={name or '-'} exact={counts['EXACT']} miss={counts['MISS']}")
    for row in holdout:
        if row["verdict"] == "MISS":
            print(
                "MISS",
                row["mode"],
                row["op"],
                "anchor=" + row["anchor"],
                "matches=" + row["endpoint_matches"],
                "branch=" + row["branch"],
                "selection=" + row["selection"],
            )


if __name__ == "__main__":
    main()
