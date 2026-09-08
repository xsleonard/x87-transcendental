#!/usr/bin/env python3
"""Score the frozen h1135 lower-binade bank after exact-once capture."""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import Counter
from pathlib import Path


MODES = ("rn", "rd", "ru")


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def read_raw(path: Path, expected: int) -> list[str]:
    values = []
    with path.open() as source:
        for number, line in enumerate(source, 1):
            fields = line.split()
            if len(fields) != 3 or fields[0] != "OK":
                raise SystemExit(f"bad hardware row {path}:{number}")
            values.append(fields[1].lower() + ":" + fields[2].lower())
    if len(values) != expected:
        raise SystemExit(f"raw row mismatch {path}: {len(values)} != {expected}")
    return values


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("raw_dir", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")

    with args.manifest.open(newline="") as source:
        reader = csv.DictReader(source, delimiter="\t")
        if reader.fieldnames is None:
            raise SystemExit("manifest has no header")
        columns = list(reader.fieldnames)
        manifest = list(reader)
    rows_by_mode = {
        mode: [row for row in manifest if row["mode"] == mode] for mode in MODES
    }
    raw = {
        mode: read_raw(
            args.raw_dir / f"h1135_hw_cos_{mode}.raw", len(rows_by_mode[mode])
        )
        for mode in MODES
    }

    scored = []
    verdicts = Counter()
    endpoint_matches = Counter()
    groups = Counter()
    for mode in MODES:
        for ordinal, (row, hardware) in enumerate(zip(rows_by_mode[mode], raw[mode])):
            result = dict(row)
            result["hw"] = hardware
            matches = [
                name
                for name in ("base", "force_minus2", "force_plus1")
                if row[name] == hardware
            ]
            result["endpoint_matches"] = ",".join(matches) or "none"
            result["verdict"] = "EXACT" if row["base"] == hardware else "MISS"
            result["wide_verdict"] = (
                "EXACT" if row["wide_rule"] == hardware else "MISS"
            )
            result["mode_ordinal"] = str(ordinal)
            scored.append(result)
            verdicts[result["verdict"]] += 1
            verdicts["wide_" + result["wide_verdict"]] += 1
            endpoint_matches[result["endpoint_matches"]] += 1
            for key in ("mode", "corr_e", "dist", "theta", "base_choice"):
                groups[(key, row[key], result["verdict"])] += 1

    prefix = ("mode", "op", "hw", "base", "wide_rule", "force_minus2",
              "force_plus1", "endpoint_matches", "verdict", "wide_verdict",
              "mode_ordinal")
    output_columns = list(prefix) + [name for name in columns if name not in prefix]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="") as target:
        writer = csv.DictWriter(target, output_columns, delimiter="\t")
        writer.writeheader()
        writer.writerows(scored)

    print(f"manifest_sha256={digest(args.manifest)} rows={len(manifest)}")
    for mode in MODES:
        path = args.raw_dir / f"h1135_hw_cos_{mode}.raw"
        print(f"raw_{mode}_sha256={digest(path)} rows={len(raw[mode])}")
    print(f"score_sha256={digest(args.output)}")
    print(f"verdicts={dict(verdicts)}")
    print(f"endpoint_matches={dict(endpoint_matches)}")
    for key, name, verdict in sorted(groups):
        print(f"{key}={name} verdict={verdict} rows={groups[(key, name, verdict)]}")


if __name__ == "__main__":
    main()
