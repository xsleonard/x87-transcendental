#!/usr/bin/env python3
"""Score one software candidate against the frozen h1135 hardware bank."""

from __future__ import annotations

import argparse
import csv
import hashlib
import subprocess
from collections import Counter
from pathlib import Path


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def run(binary: Path, mode: str, rows: list[dict[str, str]]) -> list[str]:
    result = subprocess.run(
        [str(binary), "--batch", f"--rc={mode}", "--fcos-standalone"],
        input="".join(row["op"] + "\n" for row in rows),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    values = []
    for line in result.stdout.splitlines():
        fields = line.split()
        if len(fields) != 3 or fields[0] != "OK":
            raise RuntimeError(f"bad model row: {line}")
        values.append(fields[1].lower() + ":" + fields[2].lower())
    if len(values) != len(rows):
        raise RuntimeError(f"model rows {len(values)} != {len(rows)}")
    return values


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("score", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")

    with args.score.open(newline="") as source:
        reader = csv.DictReader(source, delimiter="\t")
        if reader.fieldnames is None:
            raise SystemExit("score has no header")
        source_columns = list(reader.fieldnames)
        rows = list(reader)
    by_mode = {mode: [row for row in rows if row["mode"] == mode]
               for mode in ("rn", "rd", "ru")}
    predictions = {
        mode: iter(run(args.candidate, mode, mode_rows))
        for mode, mode_rows in by_mode.items()
    }
    scored = []
    verdicts = Counter()
    groups = Counter()
    for row in rows:
        output = next(predictions[row["mode"]])
        result = dict(row)
        result["candidate"] = output
        result["candidate_verdict"] = "EXACT" if output == row["hw"] else "MISS"
        result["candidate_endpoint_matches"] = ",".join(
            name
            for name in ("force_minus2", "force_plus1")
            if output == row[name]
        ) or "none"
        scored.append(result)
        verdicts[result["candidate_verdict"]] += 1
        for key in ("mode", "corr_e", "dist", "theta"):
            groups[(key, row[key], result["candidate_verdict"])] += 1

    prefix = ("mode", "op", "hw", "candidate", "candidate_verdict",
              "candidate_endpoint_matches")
    columns = list(prefix) + [name for name in source_columns if name not in prefix]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="") as target:
        writer = csv.DictWriter(target, columns, delimiter="\t")
        writer.writeheader()
        writer.writerows(scored)
    print(f"source_sha256={digest(args.score)} rows={len(rows)}")
    print(f"candidate_sha256={digest(args.candidate)}")
    print(f"output_sha256={digest(args.output)} verdicts={dict(verdicts)}")
    for key, name, verdict in sorted(groups):
        print(f"{key}={name} verdict={verdict} rows={groups[(key, name, verdict)]}")


if __name__ == "__main__":
    main()
