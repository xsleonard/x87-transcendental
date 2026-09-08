#!/usr/bin/env python3
"""Find architecturally visible response legs in the h1301 tree bank.

The candidate binary admits the already-qualified q=5/6 FADD response; the
baseline is R1237.  Their differences are the only hardware-observable legs
that can label h1301's ten internal-wire hypotheses.  This pass is entirely
software-only and records every difference before capture.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import subprocess
from collections import Counter
from pathlib import Path


MODES = ("rn", "rd", "ru", "rz")


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def run(binary: Path, mode: str, operands: list[str]) -> list[str]:
    process = subprocess.run(
        [str(binary.resolve()), "--batch", f"--rc={mode}",
         "--fcos-standalone"],
        input="".join(operand + "\n" for operand in operands),
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        check=True,
    )
    values = []
    for line in process.stdout.splitlines():
        fields = line.lower().split()
        if len(fields) != 3 or fields[0] != "ok":
            raise RuntimeError(f"bad model output: {line}")
        values.append(f"{fields[1]}:{fields[2]}")
    if len(values) != len(operands):
        raise RuntimeError(
            f"model returned {len(values)} rows for {len(operands)} inputs")
    return values


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    changes_path = args.report.with_name(args.report.stem + "_changes.tsv")
    for path in (args.report, changes_path):
        if path.exists():
            raise SystemExit(f"refusing to overwrite {path}")

    with args.manifest.open(newline="") as source:
        rows = list(csv.DictReader(source, delimiter="\t"))
    operands = [row["op"] for row in rows]
    if len(operands) != len(set(operands)):
        raise RuntimeError("h1301 bank must contain unique operands")

    changes = []
    counts = Counter()
    for mode in MODES:
        candidate_values = run(args.candidate, mode, operands)
        baseline_values = run(args.baseline, mode, operands)
        for row, baseline, candidate in zip(
                rows, baseline_values, candidate_values):
            changed = baseline != candidate
            counts[f"mode.{mode}.changed.{int(changed)}"] += 1
            counts[f"q.{int(row['q']):+d}.changed.{int(changed)}"] += 1
            if changed:
                changes.append({
                    "mode": mode,
                    "op": row["op"],
                    "chain": row["chain"],
                    "q": row["q"],
                    "word": row["word"],
                    "cut": row["cut"],
                    "tree_mask": row["tree_mask"],
                    "baseline": baseline,
                    "candidate": candidate,
                })

    columns = (
        "mode", "op", "chain", "q", "word", "cut", "tree_mask",
        "baseline", "candidate",
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with changes_path.open("x", newline="") as target:
        writer = csv.DictWriter(target, columns, delimiter="\t")
        writer.writeheader()
        writer.writerows(changes)
    with args.report.open("x") as target:
        target.write(f"manifest_sha256\t{digest(args.manifest)}\n")
        target.write(f"candidate_sha256\t{digest(args.candidate)}\n")
        target.write(f"baseline_sha256\t{digest(args.baseline)}\n")
        target.write("hardware_policy\tsoftware_only_no_hardware_oracle\n")
        target.write(f"operands\t{len(operands)}\n")
        target.write(f"mode_legs\t{len(operands) * len(MODES)}\n")
        target.write(f"architectural_changes\t{len(changes)}\n")
        target.write(
            f"change_operands\t{len(set(row['op'] for row in changes))}\n")
        target.write(f"changes_sha256\t{digest(changes_path)}\n")
        target.write("\n[counts]\n")
        for name, value in sorted(counts.items()):
            target.write(f"{name}\t{value}\n")

    print(
        f"wrote {args.report}: operands={len(operands)} "
        f"changes={len(changes)}", flush=True)


if __name__ == "__main__":
    main()
