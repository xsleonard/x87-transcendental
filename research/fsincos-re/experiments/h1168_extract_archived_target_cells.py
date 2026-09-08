#!/usr/bin/env python3
"""Extract dense hard-cell rows from immutable comb capture archives.

This is phase one of the no-recapture upper-R59 densification.  One compact
software-model pass reconstructs the selector coordinates.  Hardware files
are only read, and only rows occupying one of the known residual cells are
retained for exact carry-endpoint decoding in h1169.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import re
import subprocess
from collections import Counter
from pathlib import Path


MODES = ("rn", "rd", "ru")
CELL = ("theta", "ce", "s4", "side", "b1", "b2", "low3", "dist", "rsh")
TOKEN = re.compile(r"(\w+)=([0-9a-fA-F,-]+)")
WIDE = re.compile(
    r"(mul|lf|rf|f4|mag|left|right)=([01]):(-?\d+):([0-9a-fA-F]+)"
)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def output_value(line: str, source: str, ordinal: int) -> str:
    fields = line.split()
    if len(fields) < 3 or fields[0] != "OK":
        raise RuntimeError(f"bad output {source}:{ordinal}: {line.rstrip()}")
    return fields[1].lower() + ":" + fields[2].lower()


def parse_tokens(line: str) -> dict[str, str]:
    return {match.group(1): match.group(2) for match in TOKEN.finditer(line)}


def parse_wide(line: str) -> dict[str, str]:
    values = {}
    for match in WIDE.finditer(line):
        name, sign, exponent, significand = match.groups()
        values[f"tc_{name}_sign"] = sign
        values[f"tc_{name}_exp"] = exponent
        values[f"tc_{name}_sig"] = significand.lower()
    return values


def dump_records(stream):
    current = None
    for line in stream:
        if line.startswith("DI_IN "):
            if current is not None:
                yield current
            fields = line.split()
            current = {"op": (fields[1] + " " + fields[2]).lower()}
        elif current is not None and line.startswith("DI_R59 "):
            current.update(parse_tokens(line))
        elif current is not None and line.startswith("DI_TC "):
            current.update({"tc_" + key: value
                            for key, value in parse_tokens(line).items()})
            current.update(parse_wide(line))
    if current is not None:
        yield current


def row_cell(row: dict[str, str]) -> tuple[str, ...]:
    return tuple(row.get(name, "") for name in CELL)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("capture_root", type=Path)
    parser.add_argument("model", type=Path)
    parser.add_argument("target_features", type=Path)
    parser.add_argument("output_prefix", type=Path)
    parser.add_argument("corpora", nargs="+")
    args = parser.parse_args()

    selected_path = args.output_prefix.with_name(
        args.output_prefix.name + "_selected.tsv.gz")
    truth_path = args.output_prefix.with_name(
        args.output_prefix.name + "_truth.tsv")
    ops_path = args.output_prefix.with_name(
        args.output_prefix.name + "_ops.txt")
    report_path = args.output_prefix.with_name(
        args.output_prefix.name + "_report.txt")
    for path in (selected_path, truth_path, ops_path, report_path):
        if path.exists():
            raise SystemExit(f"refusing to overwrite {path}")

    with args.target_features.open(newline="") as source:
        reader = csv.DictReader(source, delimiter="\t")
        feature_columns = tuple(reader.fieldnames or ())
        target_cells = {row_cell(row) for row in reader
                        if row.get("label") == "POS"}
    if not target_cells:
        raise SystemExit("no positive target cells")

    metadata = ("corpus", "index", "hw_rn", "hw_rd", "hw_ru")
    columns = metadata + tuple(name for name in feature_columns
                               if name not in metadata)
    args.output_prefix.parent.mkdir(parents=True, exist_ok=True)
    selected_count = 0
    scanned_count = 0
    duplicate_count = 0
    corpus_counts = Counter()
    cell_counts = Counter()
    seen = {}

    with gzip.open(selected_path, "wt", newline="") as selected_stream, \
            truth_path.open("x", newline="") as truth_stream, \
            ops_path.open("x") as ops_stream:
        selected_writer = csv.DictWriter(
            selected_stream, columns, delimiter="\t", extrasaction="ignore")
        truth_columns = ("op", "hw_rn", "hw_rd", "hw_ru", "corpus", "index")
        truth_writer = csv.DictWriter(
            truth_stream, truth_columns, delimiter="\t")
        selected_writer.writeheader()
        truth_writer.writeheader()

        for corpus in args.corpora:
            input_path = args.capture_root / f"{corpus}_inputs.txt"
            hardware_paths = {mode: args.capture_root /
                              f"{corpus}_{mode}_status.txt" for mode in MODES}
            command = [str(args.model), "--batch", "--rc=rn",
                       "--fcos-standalone", "--dump-r59-compact"]
            input_source = input_path.open()
            process = subprocess.Popen(
                command, stdin=input_source, stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE, text=True, bufsize=1)
            if process.stderr is None:
                raise AssertionError("model has no compact trace")
            records = dump_records(process.stderr)
            hardware = {mode: path.open() for mode, path in hardware_paths.items()}

            with input_path.open() as source:
                for index, line in enumerate(source):
                    operand = line.strip().lower()
                    record = next(records)
                    if record.get("op") != operand:
                        raise RuntimeError(
                            f"dump desync {corpus}:{index}:"
                            f"{record.get('op')} != {operand}")
                    hw = {mode: output_value(
                        hardware[mode].readline(), str(hardware_paths[mode]), index)
                        for mode in MODES}
                    scanned_count += 1
                    if row_cell(record) not in target_cells:
                        if (index + 1) % 500000 == 0:
                            print(f"{corpus} {index + 1} selected={selected_count}",
                                  flush=True)
                        continue
                    truth = tuple(hw[mode] for mode in MODES)
                    if operand in seen:
                        duplicate_count += 1
                        if seen[operand] != truth:
                            raise RuntimeError(f"hardware disagreement for {operand}")
                        continue
                    seen[operand] = truth
                    row = {
                        **record, "corpus": corpus, "index": str(index),
                        **{f"hw_{mode}": hw[mode] for mode in MODES},
                    }
                    selected_writer.writerow(row)
                    truth_writer.writerow({name: row[name]
                                           for name in truth_columns})
                    ops_stream.write(operand + "\n")
                    selected_count += 1
                    corpus_counts[corpus] += 1
                    cell_counts[row_cell(record)] += 1
                    if (index + 1) % 500000 == 0:
                        print(f"{corpus} {index + 1} selected={selected_count}",
                              flush=True)

            try:
                next(records)
            except StopIteration:
                pass
            else:
                raise RuntimeError(f"extra dump records for {corpus}")
            process.stderr.close()
            code = process.wait()
            input_source.close()
            if code:
                raise RuntimeError(f"model exited {code} for {corpus}")
            for mode, stream in hardware.items():
                if stream.readline():
                    raise RuntimeError(f"extra hardware rows {corpus}/{mode}")
                stream.close()

    with report_path.open("x") as target:
        target.write(f"target_features_sha256\t{digest(args.target_features)}\n")
        target.write(f"model_sha256\t{digest(args.model)}\n")
        target.write(f"corpora\t{','.join(args.corpora)}\n")
        target.write(f"target_cells\t{len(target_cells)}\n")
        target.write(f"scanned_rows\t{scanned_count}\n")
        target.write(f"selected_operands\t{selected_count}\n")
        target.write(f"duplicate_operands\t{duplicate_count}\n")
        target.write(f"selected_sha256\t{digest(selected_path)}\n")
        target.write(f"truth_sha256\t{digest(truth_path)}\n")
        target.write(f"ops_sha256\t{digest(ops_path)}\n")
        for corpus, count in sorted(corpus_counts.items()):
            target.write(f"corpus {corpus}\t{count}\n")
        target.write("\n[cell counts]\n")
        for cell, count in sorted(cell_counts.items()):
            target.write(f"{'/'.join(cell)}\t{count}\n")
    print(f"wrote {report_path} selected={selected_count}", flush=True)


if __name__ == "__main__":
    main()
