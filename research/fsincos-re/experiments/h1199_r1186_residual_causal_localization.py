#!/usr/bin/env python3
"""Localize the eight post-R1186 FCOS residuals without new hardware runs.

The h1194 reframe contains the cached hardware value for every remaining
failing (mode, operand) leg.  The dense h1186b score proves that every other
RN/RD/RU leg for those operands equals the R1186 model; RZ equals RD because
all eight FCOS results are positive.  Reconstruct that four-mode truth, then
nudge one named materialized producer at a time.  These nudges are causal
diagnostics only, not candidate correction rules.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import subprocess
from collections import defaultdict
from pathlib import Path


MODES = ("rn", "rd", "ru", "rz")
PRODUCERS = (
    "red", "mag", "sq", "f4", "odd", "even", "left", "right",
    "payload", "umag",
)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def run(model: Path, mode: str, operands: list[str],
        producer: str | None = None, delta: int = 0) -> list[str]:
    command = [str(model), "--batch", f"--rc={mode}", "--fcos-standalone"]
    if producer is not None:
        command.append(f"--perturb={producer}:{delta}")
    process = subprocess.run(
        command, input="\n".join(operands) + "\n", text=True,
        capture_output=True, check=True,
    )
    results = []
    for line in process.stdout.splitlines():
        fields = line.split()
        if len(fields) >= 3 and fields[0] == "OK":
            results.append(fields[1].lower() + ":" + fields[2].lower())
    if len(results) != len(operands):
        raise RuntimeError(
            f"output count {len(results)} != {len(operands)} for "
            f"{producer}:{delta}/{mode}"
        )
    return results


def read_residuals(path: Path) -> tuple[list[str], dict[tuple[str, str], str]]:
    replacements = {}
    with path.open(newline="") as source:
        for row in csv.DictReader(source, delimiter="\t"):
            if row["label"] != "POS":
                continue
            key = (row["mode"], row["op"].lower())
            hardware = row["hw"].lower()
            if key in replacements and replacements[key] != hardware:
                raise RuntimeError(f"conflicting residual truth for {key}")
            replacements[key] = hardware
    operands = sorted({operand for _, operand in replacements})
    if len(operands) != 8 or len(replacements) != 8:
        raise RuntimeError(
            f"expected eight residual legs, got {len(operands)} operands "
            f"and {len(replacements)} legs"
        )
    return operands, replacements


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", type=Path)
    parser.add_argument("residual_rows", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    operands, replacements = read_residuals(args.residual_rows)
    truth = {}
    baseline = {}
    for mode in MODES:
        values = run(args.model, mode, operands)
        for operand, value in zip(operands, values):
            baseline[mode, operand] = value
            truth[mode, operand] = replacements.get((mode, operand), value)

    for key, hardware in replacements.items():
        if baseline[key] == hardware:
            raise RuntimeError(f"residual no longer fails in baseline: {key}")
    for operand in operands:
        if truth["rz", operand] != truth["rd", operand]:
            raise RuntimeError(f"positive-result RZ/RD disagreement: {operand}")

    scores = []
    matches = defaultdict(list)
    leg_matches = defaultdict(list)
    for producer in PRODUCERS:
        for delta in range(-4, 5):
            counts = defaultdict(int)
            matched_legs = defaultdict(list)
            for mode in MODES:
                values = run(args.model, mode, operands, producer, delta)
                for operand, value in zip(operands, values):
                    if value == truth[mode, operand]:
                        counts[operand] += 1
                        matched_legs[operand].append(mode)
            exact = {operand for operand, count in counts.items()
                     if count == len(MODES)}
            exact_legs = sum(counts.values())
            scores.append((len(exact), exact_legs, producer, delta))
            for operand in exact:
                matches[operand].append((producer, delta))
            for operand in operands:
                if counts[operand] > baseline_match_count(
                        truth, baseline, operand):
                    leg_matches[operand].append(
                        (producer, delta, tuple(matched_legs[operand])))
            print(
                f"{producer}:{delta:+d} exact={len(exact)}/{len(operands)} "
                f"legs={exact_legs}/{len(operands) * len(MODES)}",
                flush=True,
            )

    scores.sort(key=lambda row: (-row[0], -row[1], row[2],
                                 abs(row[3]), row[3]))
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as target:
        target.write(f"model_sha256\t{digest(args.model)}\n")
        target.write(f"residual_rows_sha256\t{digest(args.residual_rows)}\n")
        target.write(f"operands\t{len(operands)}\n")
        target.write(f"legs\t{len(operands) * len(MODES)}\n")
        target.write("truth_construction\tbaseline_plus_eight_cached_h1194_legs\n")
        target.write("rz_truth\tpositive_result_equals_rd\n")
        target.write("\n[baseline residuals]\n")
        target.write("mode\top\tmodel\thardware\n")
        for (mode, operand), hardware in sorted(replacements.items()):
            target.write(
                f"{mode}\t{operand}\t{baseline[mode, operand]}\t{hardware}\n")
        target.write("\n[variant ranking]\n")
        target.write("exact_operands\texact_legs\tproducer\tdelta\n")
        for score in scores:
            target.write("%d\t%d\t%s\t%d\n" % score)
        target.write("\n[all-mode exact variants per residual]\n")
        target.write("op\tcount\tvariants\n")
        for operand in operands:
            variants = sorted(matches[operand],
                              key=lambda row: (row[0], abs(row[1]), row[1]))
            rendered = ",".join(
                f"{producer}:{delta:+d}" for producer, delta in variants)
            target.write(f"{operand}\t{len(variants)}\t{rendered or '-'}\n")
        target.write("\n[variants improving per-residual leg count]\n")
        target.write("op\tbaseline_legs\tvariants\n")
        for operand in operands:
            entries = sorted(
                leg_matches[operand],
                key=lambda row: (row[0], abs(row[1]), row[1]))
            rendered = ",".join(
                f"{producer}:{delta:+d}:{'/'.join(modes)}"
                for producer, delta, modes in entries)
            target.write(
                f"{operand}\t{baseline_match_count(truth, baseline, operand)}\t"
                f"{rendered or '-'}\n"
            )
    print(f"wrote {args.report} best={scores[0]}", flush=True)


def baseline_match_count(truth: dict[tuple[str, str], str],
                         baseline: dict[tuple[str, str], str],
                         operand: str) -> int:
    return sum(baseline[mode, operand] == truth[mode, operand]
               for mode in MODES)


if __name__ == "__main__":
    main()
