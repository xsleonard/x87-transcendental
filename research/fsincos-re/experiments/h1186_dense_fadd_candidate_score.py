#!/usr/bin/env python3
"""Score the R1186 FADD recurrence on immutable dense cached rows."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import subprocess
from collections import Counter
from pathlib import Path


MODES = ("rn", "rd", "ru")


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def model_outputs(model: Path, mode: str, operands: list[str]) -> list[str]:
    process = subprocess.run(
        [str(model), "--batch", f"--rc={mode}", "--fcos-standalone"],
        input="\n".join(operands) + "\n", capture_output=True, text=True,
        check=True,
    )
    outputs = []
    for line in process.stdout.splitlines():
        fields = line.split()
        if len(fields) >= 3 and fields[0] == "OK":
            outputs.append(fields[1].lower() + ":" + fields[2].lower())
    if len(outputs) != len(operands):
        raise RuntimeError(
            f"model output count {len(outputs)} != {len(operands)}")
    return outputs


def score_chunk(model: Path, rows: list[dict[str, str]], counts: Counter,
                misses: list[tuple[str, ...]]) -> None:
    operands = [row["op"] for row in rows]
    outputs = {
        mode: model_outputs(model, mode, operands) for mode in MODES
    }
    for index, row in enumerate(rows):
        mode_matches = {
            mode: outputs[mode][index] == row[f"hw_{mode}"].lower()
            for mode in MODES
        }
        exact = all(mode_matches.values())
        label = int(row["target_flip"])
        status = row["selector_status"]
        counts["rows"] += 1
        counts[f"label.{label}"] += 1
        counts[f"status.{status}"] += 1
        counts[f"allmode_exact.{int(exact)}"] += 1
        counts[f"label.{label}.allmode_exact.{int(exact)}"] += 1
        counts[f"status.{status}.allmode_exact.{int(exact)}"] += 1
        for mode, match in mode_matches.items():
            counts[f"legs.{mode}.match.{int(match)}"] += 1
        if not exact:
            misses.append((
                row["op"], str(label), status,
                *(f"{mode}:{outputs[mode][index]}:{row[f'hw_{mode}']}"
                  for mode in MODES if not mode_matches[mode]),
            ))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("pairs", nargs="+", metavar="SELECTED,LABELS")
    parser.add_argument("--chunk", type=int, default=10000)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    pairs = []
    for rendered in args.pairs:
        selected_text, separator, labels_text = rendered.partition(",")
        if not separator:
            raise SystemExit(f"bad pair: {rendered}")
        pairs.append((Path(selected_text), Path(labels_text)))

    seen = {}
    counts = Counter()
    misses: list[tuple[str, ...]] = []
    chunk: list[dict[str, str]] = []
    for selected_path, labels_path in pairs:
        with gzip.open(selected_path, "rt", newline="") as selected_source, \
                labels_path.open(newline="") as labels_source:
            selected_rows = csv.DictReader(selected_source, delimiter="\t")
            label_rows = csv.DictReader(labels_source, delimiter="\t")
            for ordinal, (row, label_row) in enumerate(
                    zip(selected_rows, label_rows), 1):
                if row["op"] != label_row["op"]:
                    raise RuntimeError(
                        f"row mismatch {selected_path}:{ordinal}")
                identity = (
                    row["hw_rn"], row["hw_rd"], row["hw_ru"],
                    label_row["target_flip"], label_row["selector_status"],
                )
                if row["op"] in seen:
                    if seen[row["op"]] != identity:
                        raise RuntimeError(
                            f"duplicate disagreement for {row['op']}")
                    counts["duplicates"] += 1
                    continue
                seen[row["op"]] = identity
                row.update(label_row)
                chunk.append(row)
                if len(chunk) == args.chunk:
                    score_chunk(args.model, chunk, counts, misses)
                    chunk.clear()
                    if counts["rows"] % 100000 == 0:
                        print(
                            f"rows={counts['rows']} misses="
                            f"{counts['allmode_exact.0']}", flush=True)
        
    if chunk:
        score_chunk(args.model, chunk, counts, misses)

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as target:
        target.write(f"model_sha256\t{digest(args.model)}\n")
        for index, (selected_path, labels_path) in enumerate(pairs):
            target.write(
                f"pair{index}_selected\t{selected_path}\t{digest(selected_path)}\n"
            )
            target.write(
                f"pair{index}_labels\t{labels_path}\t{digest(labels_path)}\n"
            )
        target.write("\n[counts]\n")
        for name, value in sorted(counts.items()):
            target.write(f"{name}\t{value}\n")
        target.write("\n[all-mode misses]\n")
        target.write("op\tlabel\tstatus\tmode:candidate:hardware...\n")
        for miss in sorted(misses):
            target.write("\t".join(miss) + "\n")

    print(
        f"wrote {args.report} rows={counts['rows']} "
        f"exact={counts['allmode_exact.1']} misses={counts['allmode_exact.0']} "
        f"target_misses={counts['label.1.allmode_exact.0']} "
        f"control_misses={counts['label.0.allmode_exact.0']}",
        flush=True,
    )


if __name__ == "__main__":
    main()
