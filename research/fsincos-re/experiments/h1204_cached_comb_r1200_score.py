#!/usr/bin/env python3
"""Score R1200 on complete cached near-tie corpora without recapture.

The surviving comb corpora store each direct-binade operand as the first
field of ``ties_CORPUS.txt`` and the aligned Skylake result in
``CORPUS_MODE_status.txt``.  This pass reconstructs the input stream, runs
only software models, and compares the operation-level R1200 candidate both
to its ledger-off predecessor and to immutable hardware output.

The implementation streams model output and never materializes a multi-
million-row corpus in memory.  It emits every model change and every
candidate miss so unexpected early-FADD reach cannot hide behind aggregate
counts.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import tempfile
from collections import Counter
from pathlib import Path


MODES = ("rn", "rd", "ru")


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def parse_output(line: str, source: str, ordinal: int) -> str:
    fields = line.split()
    if len(fields) < 3 or fields[0] != "OK":
        raise RuntimeError(f"bad output {source}:{ordinal}: {line.rstrip()}")
    return fields[1].lower() + ":" + fields[2].lower()


def write_inputs(ties_path: Path, input_path: Path, limit: int) -> int:
    raw_path = input_path.with_name(input_path.stem + "_unsorted.txt")
    sorted_path = input_path.with_name(input_path.stem + "_sorted.txt")
    with ties_path.open() as source, raw_path.open("x") as target:
        for line in source:
            fields = line.split()
            if not fields:
                continue
            if len(fields[0]) != 16:
                raise RuntimeError(
                    f"bad tie operand {ties_path}: {fields[0]}")
            target.write("3ffc " + fields[0].lower() + "\n")
    environment = os.environ.copy()
    environment["LC_ALL"] = "C"
    with sorted_path.open("x") as target:
        subprocess.run(
            ["sort", "-u", str(raw_path)], stdout=target,
            env=environment, check=True)
    rows = 0
    with sorted_path.open() as source, input_path.open("x") as target:
        for line in source:
            target.write(line)
            rows += 1
            if limit and rows >= limit:
                break
    return rows


def score_mode(
        candidate: Path, baseline: Path, mode: str, input_path: Path,
        hardware_path: Path, rows: int, corpus: str,
        changes, misses, counts: Counter, limited: bool,
        ) -> None:
    candidate_input = input_path.open()
    baseline_input = input_path.open()
    candidate_process = subprocess.Popen(
        [str(candidate), "--batch", f"--rc={mode}", "--fcos-standalone"],
        stdin=candidate_input, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, bufsize=1,
    )
    baseline_process = subprocess.Popen(
        [str(baseline), "--batch", f"--rc={mode}", "--fcos-standalone"],
        stdin=baseline_input, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, bufsize=1,
    )
    if candidate_process.stdout is None or baseline_process.stdout is None:
        raise AssertionError("model stdout pipe unavailable")
    with input_path.open() as inputs, hardware_path.open() as hardware:
        for ordinal in range(1, rows + 1):
            operand = inputs.readline().strip().lower()
            hardware_line = hardware.readline()
            if not operand or not hardware_line:
                raise RuntimeError(
                    f"short aligned input/hardware stream {corpus}/{mode}:"
                    f"{ordinal}")
            candidate_value = parse_output(
                candidate_process.stdout.readline(),
                f"candidate/{corpus}/{mode}", ordinal)
            baseline_value = parse_output(
                baseline_process.stdout.readline(),
                f"baseline/{corpus}/{mode}", ordinal)
            hardware_value = parse_output(
                hardware_line, str(hardware_path), ordinal)
            changed = candidate_value != baseline_value
            candidate_match = candidate_value == hardware_value
            baseline_match = baseline_value == hardware_value
            counts["rows"] += 1
            counts[f"mode.{mode}.rows"] += 1
            counts[f"changed.{int(changed)}"] += 1
            counts[f"candidate_match.{int(candidate_match)}"] += 1
            counts[f"baseline_match.{int(baseline_match)}"] += 1
            if changed:
                classification = (
                    "fix" if candidate_match and not baseline_match
                    else "regression" if baseline_match and not candidate_match
                    else "changed_both_wrong" if not candidate_match
                    else "changed_both_right"
                )
                counts[f"change.{classification}"] += 1
                changes.write(
                    f"{corpus}\t{mode}\t{ordinal - 1}\t{operand}\t"
                    f"{classification}\t{baseline_value}\t"
                    f"{candidate_value}\t{hardware_value}\n")
            if not candidate_match:
                misses.write(
                    f"{corpus}\t{mode}\t{ordinal - 1}\t{operand}\t"
                    f"{int(changed)}\t{baseline_value}\t"
                    f"{candidate_value}\t{hardware_value}\n")
            if ordinal % 1000000 == 0:
                print(
                    f"{corpus}/{mode} rows={ordinal} "
                    f"changes={counts['changed.1']} "
                    f"candidate_misses={counts['candidate_match.0']}",
                    flush=True,
                )
        if inputs.readline():
            raise RuntimeError(f"extra input rows {corpus}/{mode}")
        if not limited and hardware.readline():
            raise RuntimeError(f"extra hardware rows {corpus}/{mode}")
    candidate_extra = candidate_process.stdout.readline()
    baseline_extra = baseline_process.stdout.readline()
    candidate_stdout = candidate_process.stdout
    baseline_stdout = baseline_process.stdout
    candidate_stdout.close()
    baseline_stdout.close()
    candidate_stderr = (
        candidate_process.stderr.read() if candidate_process.stderr else "")
    baseline_stderr = (
        baseline_process.stderr.read() if baseline_process.stderr else "")
    candidate_code = candidate_process.wait()
    baseline_code = baseline_process.wait()
    candidate_input.close()
    baseline_input.close()
    if candidate_code or baseline_code:
        raise RuntimeError(
            f"model exit {corpus}/{mode}: candidate={candidate_code} "
            f"baseline={baseline_code} candidate_stderr={candidate_stderr!r} "
            f"baseline_stderr={baseline_stderr!r}")
    if candidate_extra or baseline_extra:
        raise RuntimeError(f"extra model output {corpus}/{mode}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("candidate", type=Path)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("capture_root", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("corpora", nargs="+")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()
    changes_path = args.report.with_name(args.report.stem + "_changes.tsv")
    misses_path = args.report.with_name(args.report.stem + "_misses.tsv")
    for path in (args.report, changes_path, misses_path):
        if path.exists():
            raise SystemExit(f"refusing to overwrite {path}")

    counts = Counter()
    source_rows = {}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with changes_path.open("x") as changes, misses_path.open("x") as misses:
        changes.write(
            "corpus\tmode\tindex\top\tclassification\tbaseline\t"
            "candidate\thardware\n")
        misses.write(
            "corpus\tmode\tindex\top\tchanged\tbaseline\tcandidate\t"
            "hardware\n")
        with tempfile.TemporaryDirectory(prefix="h1204-") as temporary:
            temporary_root = Path(temporary)
            for corpus in args.corpora:
                ties_path = args.capture_root / f"ties_{corpus}.txt"
                input_path = temporary_root / f"{corpus}_inputs.txt"
                rows = write_inputs(ties_path, input_path, args.limit)
                source_rows[corpus] = rows
                print(f"{corpus} reconstructed_inputs={rows}", flush=True)
                for mode in MODES:
                    hardware_path = (
                        args.capture_root / f"{corpus}_{mode}_status.txt")
                    score_mode(
                        args.candidate, args.baseline, mode, input_path,
                        hardware_path, rows, corpus, changes, misses, counts,
                        bool(args.limit))

    with args.report.open("x") as target:
        target.write(f"candidate_sha256\t{digest(args.candidate)}\n")
        target.write(f"baseline_sha256\t{digest(args.baseline)}\n")
        target.write(f"capture_root\t{args.capture_root.resolve()}\n")
        target.write(f"corpora\t{','.join(args.corpora)}\n")
        target.write(f"limit\t{args.limit}\n")
        target.write("hardware_policy\tcached_files_only_no_x87_execution\n")
        for corpus, rows in source_rows.items():
            target.write(f"source_rows.{corpus}\t{rows}\n")
        target.write(f"changes_sha256\t{digest(changes_path)}\n")
        target.write(f"misses_sha256\t{digest(misses_path)}\n")
        target.write("\n[counts]\n")
        for name, value in sorted(counts.items()):
            target.write(f"{name}\t{value}\n")
    print(
        f"wrote {args.report} rows={counts['rows']} "
        f"changes={counts['changed.1']} "
        f"fixes={counts['change.fix']} "
        f"regressions={counts['change.regression']} "
        f"candidate_misses={counts['candidate_match.0']}",
        flush=True,
    )


if __name__ == "__main__":
    main()
