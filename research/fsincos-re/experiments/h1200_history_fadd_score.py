#!/usr/bin/env python3
"""Score an operation-level FADD-history candidate on cached h1194 rows."""

from __future__ import annotations

import argparse
import csv
import hashlib
import subprocess
from collections import Counter, defaultdict
from pathlib import Path


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def run(model: Path, mode: str, operands: list[str]) -> list[str]:
    process = subprocess.run(
        [str(model), "--batch", f"--rc={mode}", "--fcos-standalone"],
        input="\n".join(operands) + "\n", text=True,
        capture_output=True, check=True,
    )
    values = []
    for line in process.stdout.splitlines():
        fields = line.split()
        if len(fields) >= 3 and fields[0] == "OK":
            values.append(fields[1].lower() + ":" + fields[2].lower())
    if len(values) != len(operands):
        raise RuntimeError(
            f"output count {len(values)} != {len(operands)} for {mode}")
    return values


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("candidate", type=Path)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("rows", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("--chunk", type=int, default=4000)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    by_mode = defaultdict(list)
    with args.rows.open(newline="") as source:
        for row in csv.DictReader(source, delimiter="\t"):
            by_mode[row["mode"]].append(row)

    counts = Counter()
    diagnostics = []
    for mode, mode_rows in sorted(by_mode.items()):
        for start in range(0, len(mode_rows), args.chunk):
            rows = mode_rows[start:start + args.chunk]
            operands = [row["op"] for row in rows]
            candidate = run(args.candidate, mode, operands)
            baseline = run(args.baseline, mode, operands)
            for row, value, old in zip(rows, candidate, baseline):
                hardware = row["hw"].lower()
                recorded_baseline = row["current"].lower()
                if old != recorded_baseline:
                    raise RuntimeError(
                        "baseline configuration mismatch: "
                        f"mode={mode} op={row['op']} "
                        f"recorded={recorded_baseline} observed={old}"
                    )
                target = row["label"] == "POS"
                match = value == hardware
                old_match = old == hardware
                changed = value != old
                counts["rows"] += 1
                counts[f"target.{int(target)}"] += 1
                counts[f"match.{int(match)}"] += 1
                counts[f"target.{int(target)}.match.{int(match)}"] += 1
                counts[f"baseline_match.{int(old_match)}"] += 1
                counts[f"changed.{int(changed)}"] += 1
                counts[f"target.{int(target)}.changed.{int(changed)}"] += 1
                if changed or not match:
                    diagnostics.append((
                        mode, row["op"], int(target), int(old_match),
                        int(match), old, value, hardware,
                    ))

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as target:
        target.write(f"candidate_sha256\t{digest(args.candidate)}\n")
        target.write(f"baseline_sha256\t{digest(args.baseline)}\n")
        target.write(f"rows_sha256\t{digest(args.rows)}\n")
        target.write("\n[counts]\n")
        for name, value in sorted(counts.items()):
            target.write(f"{name}\t{value}\n")
        target.write("\n[changed-or-missed]\n")
        target.write(
            "mode\top\ttarget\tbaseline_match\tcandidate_match\t"
            "baseline\tcandidate\thardware\n")
        for row in diagnostics:
            target.write("\t".join(map(str, row)) + "\n")

    print(
        f"wrote {args.report} rows={counts['rows']} "
        f"misses={counts['match.0']} changes={counts['changed.1']} "
        f"target_misses={counts['target.1.match.0']} "
        f"control_misses={counts['target.0.match.0']}",
        flush=True,
    )


if __name__ == "__main__":
    main()
