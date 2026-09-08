#!/usr/bin/env python3
"""Open and score the frozen h1160 lower-binade boundary blind."""

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
        raise SystemExit(f"raw rows {len(values)} != {expected}: {path}")
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
        rows = list(reader)
    by_mode = {mode: [row for row in rows if row["mode"] == mode]
               for mode in MODES}
    raw = {
        mode: read_raw(
            args.raw_dir / f"h1160_hw_cos_{mode}.raw", len(by_mode[mode]))
        for mode in MODES
    }

    output = []
    verdicts = Counter()
    groups = Counter()
    for mode in MODES:
        for ordinal, (row, hardware) in enumerate(zip(by_mode[mode], raw[mode])):
            result = dict(row)
            result["hw"] = hardware
            result["verdict"] = (
                "EXACT" if hardware == row["candidate"] else "MISS")
            result["counterfactual_verdict"] = (
                "EXACT" if hardware == row["counterfactual"] else "MISS")
            result["base_verdict"] = (
                "EXACT" if hardware == row["base"] else "MISS")
            result["hw_choice"] = (
                "candidate" if hardware == row["candidate"]
                else "counterfactual" if hardware == row["counterfactual"]
                else "other"
            )
            result["mode_ordinal"] = str(ordinal)
            output.append(result)
            verdicts[result["verdict"]] += 1
            verdicts["counterfactual_" + result["counterfactual_verdict"]] += 1
            verdicts["base_" + result["base_verdict"]] += 1
            verdicts["choice_" + result["hw_choice"]] += 1
            for key in ("mode", "corr_e", "theta", "boundary_side",
                        "candidate_fire"):
                groups[(key, row[key], result["verdict"])] += 1

    prefix = (
        "mode", "op", "hw", "candidate", "counterfactual", "verdict",
        "counterfactual_verdict", "base_verdict", "hw_choice", "mode_ordinal",
    )
    output_columns = list(prefix) + [name for name in columns if name not in prefix]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="") as target:
        writer = csv.DictWriter(target, output_columns, delimiter="\t")
        writer.writeheader()
        writer.writerows(output)

    print(f"manifest_sha256={digest(args.manifest)} rows={len(rows)}")
    for mode in MODES:
        path = args.raw_dir / f"h1160_hw_cos_{mode}.raw"
        print(f"raw_{mode}_sha256={digest(path)} rows={len(raw[mode])}")
    print(f"score_sha256={digest(args.output)}")
    print(f"verdicts={dict(verdicts)}")
    for key, name, verdict in sorted(groups):
        print(f"{key}={name} verdict={verdict} rows={groups[(key, name, verdict)]}")


if __name__ == "__main__":
    main()
