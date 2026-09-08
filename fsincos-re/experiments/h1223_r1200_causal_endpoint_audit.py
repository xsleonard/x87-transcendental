#!/usr/bin/env python3
"""Test whether an R1200 factor change is compatible with cached truth.

An output-level fix is not by itself evidence that the corresponding Horner
factor changed in hardware: the terminal subtractor has two exact carry
endpoints.  For every unique R1200-changed operand, this script recovers all
three architectural rounding-mode results from the immutable stage-A files
and asks whether carry 0 or carry 1 can reproduce them before and after the
factor recurrence.  RZ is equal to RD for these positive FCOS results.

The change file already contains a verified corpus/index location for every
operand, so the hardware streams can be read directly without rebuilding or
recapturing their input sequences.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import Counter, defaultdict
from pathlib import Path

from h1210_stagea_residual_reframe import run


MODES = ("rn", "rd", "ru", "rz")
CAPTURE_MODES = ("rn", "rd", "ru")


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def parse_output(line: str, source: Path, index: int) -> str:
    fields = line.split()
    if len(fields) < 3 or fields[0] != "OK":
        raise RuntimeError(f"bad output {source}:{index + 1}: {line.rstrip()}")
    return fields[1].lower() + ":" + fields[2].lower()


def read_locations(path: Path) -> tuple[
        dict[str, str], dict[str, list[str]],
        dict[str, dict[int, str]]]:
    classifications: dict[str, str] = {}
    changed_modes: dict[str, list[str]] = defaultdict(list)
    locations: dict[str, dict[int, str]] = defaultdict(dict)
    with path.open(newline="") as source:
        for row in csv.DictReader(source, delimiter="\t"):
            operand = row["op"].lower()
            classification = row["classification"]
            previous = classifications.setdefault(operand, classification)
            if previous != classification:
                raise RuntimeError(f"classification conflict for {operand}")
            changed_modes[operand].append(row["mode"].lower())
            corpus = row["corpus"]
            index = int(row["index"])
            occupied = locations[corpus].setdefault(index, operand)
            if occupied != operand:
                raise RuntimeError(f"location collision {corpus}:{index}")
    return classifications, changed_modes, locations


def recover_truth(capture_root: Path, locations: dict[str, dict[int, str]],
                  operands: set[str]) -> dict[tuple[str, str], str]:
    observed: dict[tuple[str, str], set[str]] = defaultdict(set)
    for corpus, indexed in sorted(locations.items()):
        wanted = set(indexed)
        last = max(wanted)
        for mode in CAPTURE_MODES:
            path = capture_root / f"{corpus}_{mode}_status.txt"
            found = 0
            with path.open() as source:
                for index, line in enumerate(source):
                    if index in wanted:
                        operand = indexed[index]
                        observed[mode, operand].add(
                            parse_output(line, path, index))
                        found += 1
                    if index >= last:
                        break
            if found != len(wanted):
                raise RuntimeError(
                    f"short hardware stream {corpus}/{mode}: "
                    f"found {found}/{len(wanted)}")
    truth = {}
    for operand in sorted(operands):
        for mode in CAPTURE_MODES:
            values = observed[mode, operand]
            if len(values) != 1:
                raise RuntimeError(
                    f"hardware disagreement/missing {mode}/{operand}: {values}")
            truth[mode, operand] = next(iter(values))
        truth["rz", operand] = truth["rd", operand]
    return truth


def model_outputs(model: Path, operands: list[str]
                  ) -> dict[tuple[str, str], str]:
    outputs = {}
    for mode in MODES:
        values, _ = run(model, mode, operands)
        for operand, value in zip(operands, values):
            outputs[mode, operand] = value
    return outputs


def allowed_carries(
        truth: dict[tuple[str, str], str],
        carry0: dict[tuple[str, str], str],
        carry1: dict[tuple[str, str], str],
        operand: str,
        ) -> list[int]:
    return [
        carry for carry, outputs in ((0, carry0), (1, carry1))
        if all(outputs[mode, operand] == truth[mode, operand]
               for mode in MODES)
    ]


def status(allowed: list[int]) -> str:
    return ("constraining" if len(allowed) == 1
            else "neutral" if len(allowed) == 2
            else "unrepresented")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("capture_root", type=Path)
    parser.add_argument("changes", type=Path)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("baseline_carry0", type=Path)
    parser.add_argument("baseline_carry1", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("candidate_carry0", type=Path)
    parser.add_argument("candidate_carry1", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    classifications, changed_modes, locations = read_locations(args.changes)
    operands = sorted(classifications)
    truth = recover_truth(args.capture_root, locations, set(operands))
    models = {
        "baseline": model_outputs(args.baseline, operands),
        "baseline_carry0": model_outputs(args.baseline_carry0, operands),
        "baseline_carry1": model_outputs(args.baseline_carry1, operands),
        "candidate": model_outputs(args.candidate, operands),
        "candidate_carry0": model_outputs(args.candidate_carry0, operands),
        "candidate_carry1": model_outputs(args.candidate_carry1, operands),
    }

    diagnostics = []
    counts = Counter()
    for operand in operands:
        baseline_allowed = allowed_carries(
            truth, models["baseline_carry0"], models["baseline_carry1"],
            operand)
        candidate_allowed = allowed_carries(
            truth, models["candidate_carry0"], models["candidate_carry1"],
            operand)
        baseline_status = status(baseline_allowed)
        candidate_status = status(candidate_allowed)
        classification = classifications[operand]
        baseline_exact_modes = ",".join(
            mode for mode in MODES
            if models["baseline"][mode, operand] == truth[mode, operand]
        ) or "-"
        candidate_exact_modes = ",".join(
            mode for mode in MODES
            if models["candidate"][mode, operand] == truth[mode, operand]
        ) or "-"
        counts[f"classification.{classification}"] += 1
        counts[f"baseline.{baseline_status}"] += 1
        counts[f"candidate.{candidate_status}"] += 1
        counts[f"transition.{baseline_status}.{candidate_status}"] += 1
        counts[f"classification.{classification}.candidate.{candidate_status}"] += 1
        diagnostics.append((
            operand, classification,
            ",".join(sorted(set(changed_modes[operand]), key=MODES.index)),
            baseline_status, ",".join(map(str, baseline_allowed)) or "-",
            candidate_status, ",".join(map(str, candidate_allowed)) or "-",
            baseline_exact_modes, candidate_exact_modes,
        ))

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as target:
        target.write(f"changes_sha256\t{digest(args.changes)}\n")
        target.write(f"capture_root\t{args.capture_root.resolve()}\n")
        target.write("hardware_policy\tcached_files_only_no_x87_execution\n")
        for name in (
                "baseline", "baseline_carry0", "baseline_carry1",
                "candidate", "candidate_carry0", "candidate_carry1"):
            target.write(f"{name}_sha256\t{digest(getattr(args, name))}\n")
        target.write(f"unique_operands\t{len(operands)}\n")
        target.write("\n[counts]\n")
        for name, value in sorted(counts.items()):
            target.write(f"{name}\t{value}\n")
        target.write("\n[all-mode endpoint diagnostics]\n")
        target.write(
            "op\tclassification\tchanged_modes\tbaseline_status\t"
            "baseline_carries\tcandidate_status\tcandidate_carries\t"
            "baseline_exact_modes\tcandidate_exact_modes\n"
        )
        for diagnostic in diagnostics:
            target.write("\t".join(map(str, diagnostic)) + "\n")
        target.write("\n[truth]\n")
        target.write("op\trn\trd\tru\trz\n")
        for operand in operands:
            target.write(
                operand + "\t" + "\t".join(
                    truth[mode, operand] for mode in MODES) + "\n")

    print(
        f"wrote {args.report} operands={len(operands)} "
        f"candidate_unrepresented={counts['candidate.unrepresented']}",
        flush=True,
    )


if __name__ == "__main__":
    main()
