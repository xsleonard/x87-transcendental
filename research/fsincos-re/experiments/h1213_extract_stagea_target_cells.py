#!/usr/bin/env python3
"""Extract the new R59 target cells from immutable stage-A archives.

Stage A stores sorted direct-binade operands indirectly in ``ties_*.txt``.
This cached-only pass reconstructs those streams exactly as h1204 did, emits
compact model state, and retains every operand in a cell occupied by one of
the h1210 residuals.  Hardware files are read but no x87 instruction is run.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import subprocess
import tempfile
from collections import Counter
from pathlib import Path

from h1168_extract_archived_target_cells import (
    CELL, MODES, digest, dump_records, output_value, row_cell,
)
from h1204_cached_comb_r1200_score import write_inputs


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
        target_cells = {
            row_cell(row) for row in reader if row.get("label") == "POS"
        }
    if not target_cells:
        raise SystemExit("no positive target cells")

    metadata = ("corpus", "index", "hw_rn", "hw_rd", "hw_ru")
    columns = metadata + tuple(
        name for name in feature_columns if name not in metadata
    )
    args.output_prefix.parent.mkdir(parents=True, exist_ok=True)
    selected_count = 0
    scanned_count = 0
    duplicate_count = 0
    corpus_counts = Counter()
    cell_counts = Counter()
    source_rows = {}
    seen = {}

    with gzip.open(selected_path, "xt", newline="") as selected_stream, \
            truth_path.open("x", newline="") as truth_stream, \
            ops_path.open("x") as ops_stream, \
            tempfile.TemporaryDirectory(prefix="h1213-") as temporary:
        selected_writer = csv.DictWriter(
            selected_stream, columns, delimiter="\t", extrasaction="ignore"
        )
        truth_columns = ("op", "hw_rn", "hw_rd", "hw_ru", "corpus", "index")
        truth_writer = csv.DictWriter(
            truth_stream, truth_columns, delimiter="\t"
        )
        selected_writer.writeheader()
        truth_writer.writeheader()
        temporary_root = Path(temporary)

        for corpus in args.corpora:
            input_path = temporary_root / f"{corpus}_inputs.txt"
            rows = write_inputs(
                args.capture_root / f"ties_{corpus}.txt", input_path, 0
            )
            source_rows[corpus] = rows
            hardware_paths = {
                mode: args.capture_root / f"{corpus}_{mode}_status.txt"
                for mode in MODES
            }
            command = [
                str(args.model), "--batch", "--rc=rn", "--fcos-standalone",
                "--dump-r59-compact",
            ]
            input_source = input_path.open()
            process = subprocess.Popen(
                command, stdin=input_source, stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE, text=True, bufsize=1,
            )
            if process.stderr is None:
                raise AssertionError("model has no compact trace")
            records = dump_records(process.stderr)
            hardware = {
                mode: path.open() for mode, path in hardware_paths.items()
            }

            with input_path.open() as source:
                for index, line in enumerate(source):
                    operand = line.strip().lower()
                    record = next(records)
                    if record.get("op") != operand:
                        raise RuntimeError(
                            f"dump desync {corpus}:{index}:"
                            f"{record.get('op')} != {operand}"
                        )
                    hw = {
                        mode: output_value(
                            hardware[mode].readline(),
                            str(hardware_paths[mode]), index,
                        ) for mode in MODES
                    }
                    scanned_count += 1
                    if row_cell(record) not in target_cells:
                        if (index + 1) % 1000000 == 0:
                            print(
                                f"{corpus} {index + 1}/{rows} "
                                f"selected={selected_count}", flush=True,
                            )
                        continue
                    truth = tuple(hw[mode] for mode in MODES)
                    if operand in seen:
                        duplicate_count += 1
                        if seen[operand] != truth:
                            raise RuntimeError(
                                f"hardware disagreement for {operand}"
                            )
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
                    if (index + 1) % 1000000 == 0:
                        print(
                            f"{corpus} {index + 1}/{rows} "
                            f"selected={selected_count}", flush=True,
                        )

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
        target.write("hardware_policy\tcached_files_only_no_x87_execution\n")
        target.write(f"target_cells\t{len(target_cells)}\n")
        target.write(f"scanned_rows\t{scanned_count}\n")
        target.write(f"selected_operands\t{selected_count}\n")
        target.write(f"duplicate_operands\t{duplicate_count}\n")
        target.write(f"selected_sha256\t{digest(selected_path)}\n")
        target.write(f"truth_sha256\t{digest(truth_path)}\n")
        target.write(f"ops_sha256\t{digest(ops_path)}\n")
        for corpus, rows in source_rows.items():
            target.write(f"source_rows.{corpus}\t{rows}\n")
        for corpus, count in sorted(corpus_counts.items()):
            target.write(f"selected.{corpus}\t{count}\n")
        target.write("\n[cell counts]\n")
        for cell, count in sorted(cell_counts.items()):
            target.write(f"{'/'.join(cell)}\t{count}\n")
    print(f"wrote {report_path} selected={selected_count}", flush=True)


if __name__ == "__main__":
    main()
