#!/usr/bin/env python3
"""Compare two FCOS models on deduplicated cached hardware TSV rows.

Every input TSV must provide ``mode``, ``op``, and ``hw`` columns.  Duplicate
mode/operand legs are checked for immutable hardware agreement and evaluated
once.  The script invokes only software models; it never executes x87.
"""

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


def normalize(value: str) -> str:
    return ":".join(value.lower().split())


def run(binary: Path, mode: str, rows: list[tuple[str, str]]) -> list[str]:
    result = subprocess.run(
        [str(binary), "--batch", f"--rc={mode}", "--fcos-standalone"],
        input="".join(operand + "\n" for operand, _ in rows),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    values = []
    for ordinal, line in enumerate(result.stdout.splitlines(), 1):
        fields = line.split()
        if len(fields) != 3 or fields[0] != "OK":
            raise RuntimeError(
                f"bad model row {binary}/{mode}/{ordinal}: {line}")
        values.append(fields[1].lower() + ":" + fields[2].lower())
    if len(values) != len(rows):
        raise RuntimeError(
            f"model rows {len(values)} != {len(rows)}: {binary}/{mode}")
    return values


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("candidate", type=Path)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("scores", nargs="+", type=Path)
    args = parser.parse_args()
    expanded_scores = []
    for path in args.scores:
        if path.is_dir():
            expanded_scores.extend(sorted(path.glob("*.tsv")))
        else:
            expanded_scores.append(path)
    changes_path = args.report.with_name(args.report.stem + "_changes.tsv")
    misses_path = args.report.with_name(args.report.stem + "_misses.tsv")
    for path in (args.report, changes_path, misses_path):
        if path.exists():
            raise SystemExit(f"refusing to overwrite {path}")

    counts = Counter()
    seen: dict[tuple[str, str], tuple[str, str]] = {}
    source_rows = Counter()
    accepted_scores = []
    skipped_scores = []
    for path in expanded_scores:
        with path.open(newline="") as source:
            reader = csv.DictReader(source, delimiter="\t")
            if reader.fieldnames is None:
                raise RuntimeError(f"missing TSV header: {path}")
            required = {"mode", "op", "hw"}
            if not required.issubset(reader.fieldnames):
                skipped_scores.append(path)
                continue
            accepted_scores.append(path)
            for row in reader:
                mode = row["mode"].lower()
                operand = row["op"].lower()
                hardware = normalize(row["hw"])
                if not mode or not operand or not hardware:
                    counts["invalid_rows_skipped"] += 1
                    continue
                key = (mode, operand)
                prior = seen.get(key)
                identity = (hardware, path.name)
                source_rows[path.name] += 1
                if prior is not None:
                    if prior[0] != hardware:
                        raise RuntimeError(
                            f"hardware disagreement {key}: {prior} != {identity}")
                    counts["duplicate_rows"] += 1
                    continue
                seen[key] = identity
                counts["unique_legs"] += 1

    by_mode: dict[str, list[tuple[str, str]]] = {}
    for mode, operand in sorted(seen):
        by_mode.setdefault(mode, []).append((operand, seen[(mode, operand)][0]))
    candidate_outputs = {
        mode: run(args.candidate, mode, rows) for mode, rows in by_mode.items()
    }
    baseline_outputs = {
        mode: run(args.baseline, mode, rows) for mode, rows in by_mode.items()
    }

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with changes_path.open("x", newline="") as changes_source, \
            misses_path.open("x", newline="") as misses_source:
        changes = csv.writer(changes_source, delimiter="\t")
        misses = csv.writer(misses_source, delimiter="\t")
        header = ("mode", "op", "source", "classification", "baseline",
                  "candidate", "hardware")
        changes.writerow(header)
        misses.writerow(header)
        for mode, rows in by_mode.items():
            for (operand, hardware), candidate, baseline in zip(
                    rows, candidate_outputs[mode], baseline_outputs[mode]):
                candidate_match = candidate == hardware
                baseline_match = baseline == hardware
                changed = candidate != baseline
                counts[f"mode.{mode}.rows"] += 1
                counts[f"candidate_match.{int(candidate_match)}"] += 1
                counts[f"baseline_match.{int(baseline_match)}"] += 1
                counts[f"changed.{int(changed)}"] += 1
                classification = (
                    "fix" if changed and candidate_match and not baseline_match
                    else "regression" if changed and baseline_match and not candidate_match
                    else "changed_both_wrong" if changed and not candidate_match
                    else "changed_both_right" if changed
                    else "unchanged_exact" if candidate_match
                    else "unchanged_miss"
                )
                counts[f"classification.{classification}"] += 1
                record = (
                    mode, operand, seen[(mode, operand)][1], classification,
                    baseline, candidate, hardware,
                )
                if changed:
                    changes.writerow(record)
                if not candidate_match:
                    misses.writerow(record)

    with args.report.open("x") as target:
        target.write(f"candidate_sha256\t{digest(args.candidate)}\n")
        target.write(f"baseline_sha256\t{digest(args.baseline)}\n")
        target.write("hardware_policy\tcached_files_only_no_x87_execution\n")
        for path in accepted_scores:
            target.write(f"score_sha256.{path.name}\t{digest(path)}\n")
            target.write(f"source_rows.{path.name}\t{source_rows[path.name]}\n")
        target.write(f"accepted_scores\t{len(accepted_scores)}\n")
        target.write(f"skipped_scores\t{len(skipped_scores)}\n")
        target.write(f"changes_sha256\t{digest(changes_path)}\n")
        target.write(f"misses_sha256\t{digest(misses_path)}\n")
        target.write("\n[counts]\n")
        for key, value in sorted(counts.items()):
            target.write(f"{key}\t{value}\n")

    print(
        f"unique={counts['unique_legs']} duplicates={counts['duplicate_rows']} "
        f"changes={counts['changed.1']} fixes={counts['classification.fix']} "
        f"regressions={counts['classification.regression']} "
        f"candidate_misses={counts['candidate_match.0']} report={args.report}")


if __name__ == "__main__":
    main()
