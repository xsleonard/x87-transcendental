#!/usr/bin/env python3
"""Decode dense upper-R59 selector truth from archived hardware captures.

No x87 instruction is executed.  For every archived operand, two software
models enumerate the exact carry=0 and carry=1 endpoints in RN/RD/RU.  Their
intersection with the immutable hardware files identifies whether the row is
carry-constraining, neutral, or not representable by this one-bit endpoint.

The output retains every row in a cell occupied by a known residual, plus all
newly discovered current-carry failures anywhere in the scanned corpora.  It
therefore densifies the hard cells without making another hardware capture.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path


MODES = ("rn", "rd", "ru")
CELL = (
    "theta", "ce", "s4", "side", "b1", "b2", "low3", "dist", "rsh",
)
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
        elif current is not None and line.startswith("DI_CRIT "):
            current.update({"crit_" + key: value
                            for key, value in parse_tokens(line).items()})
        elif current is not None and line.startswith("DI_BS "):
            current.update({"bs_" + key: value
                            for key, value in parse_tokens(line).items()})
        elif current is not None and line.startswith("DI_BR "):
            current["branch"] = line.split()[1].split("=", 1)[1]
            current.update({"br_" + key: value
                            for key, value in parse_tokens(line).items()
                            if key != "br"})
    if current is not None:
        yield current


def output_value(line: str, source: str, ordinal: int) -> str:
    fields = line.split()
    if len(fields) < 3 or fields[0] != "OK":
        raise RuntimeError(f"bad output {source}:{ordinal}: {line.rstrip()}")
    return fields[1].lower() + ":" + fields[2].lower()


def signed128(text: str) -> int:
    value = int(text, 16)
    return value - (1 << 128) if value >> 127 else value


def row_cell(row: dict[str, str]) -> tuple[str, ...]:
    return tuple(row.get(name, "") for name in CELL)


def start_model(binary: Path, mode: str, input_path: Path, dump: bool = False):
    command = [str(binary), "--batch", f"--rc={mode}",
               "--fcos-standalone"]
    if dump:
        command.append("--dump-r59-compact")
    source = input_path.open()
    process = subprocess.Popen(
        command,
        stdin=source,
        stdout=subprocess.DEVNULL if dump else subprocess.PIPE,
        stderr=subprocess.PIPE if dump else subprocess.DEVNULL,
        text=True,
        bufsize=1,
    )
    process.input_source = source
    return process


def close_model(process, name: str) -> None:
    if process.stdout is not None:
        extra = process.stdout.readline()
        if extra:
            raise RuntimeError(f"extra output from {name}: {extra.rstrip()}")
    if process.stderr is not None:
        process.stderr.close()
    code = process.wait()
    process.input_source.close()
    if code:
        raise RuntimeError(f"{name} exited {code}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("capture_root", type=Path)
    parser.add_argument("current", type=Path)
    parser.add_argument("carry0", type=Path)
    parser.add_argument("carry1", type=Path)
    parser.add_argument("target_features", type=Path)
    parser.add_argument("output_prefix", type=Path)
    parser.add_argument("corpora", nargs="+")
    args = parser.parse_args()

    target_output = args.output_prefix.with_name(
        args.output_prefix.name + "_target_cells.tsv.gz")
    residual_output = args.output_prefix.with_name(
        args.output_prefix.name + "_residuals.tsv.gz")
    report_output = args.output_prefix.with_name(
        args.output_prefix.name + "_report.txt")
    for path in (target_output, residual_output, report_output):
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

    metadata = (
        "corpus", "index", "selector_status", "allowed_carry",
        "current_carry", "target_flip", "borrow", "current_delta",
    )
    columns = metadata + tuple(name for name in feature_columns
                               if name not in metadata)
    target_output.parent.mkdir(parents=True, exist_ok=True)
    status_counts = Counter()
    cell_counts = Counter()
    corpus_counts = Counter()
    residual_operands = set()

    with gzip.open(target_output, "wt", newline="") as target_stream, \
            gzip.open(residual_output, "wt", newline="") as residual_stream:
        target_writer = csv.DictWriter(
            target_stream, fieldnames=columns, delimiter="\t",
            extrasaction="ignore")
        residual_writer = csv.DictWriter(
            residual_stream, fieldnames=columns, delimiter="\t",
            extrasaction="ignore")
        target_writer.writeheader()
        residual_writer.writeheader()

        for corpus in args.corpora:
            input_path = args.capture_root / f"{corpus}_inputs.txt"
            hardware_paths = {
                mode: args.capture_root / f"{corpus}_{mode}_status.txt"
                for mode in MODES
            }
            missing = [path for path in (input_path, *hardware_paths.values())
                       if not path.exists()]
            if missing:
                raise SystemExit("missing archive files: "
                                 + ", ".join(map(str, missing)))

            dump_process = start_model(args.current, "rn", input_path, dump=True)
            if dump_process.stderr is None:
                raise AssertionError("dump process has no stderr")
            records = dump_records(dump_process.stderr)
            baseline = {
                mode: start_model(args.current, mode, input_path)
                for mode in MODES
            }
            forced = {
                (carry, mode): start_model(
                    args.carry0 if carry == 0 else args.carry1,
                    mode, input_path)
                for carry in (0, 1) for mode in MODES
            }
            hardware = {mode: path.open() for mode, path in hardware_paths.items()}

            with input_path.open() as input_stream:
                for index, input_line in enumerate(input_stream):
                    operand = input_line.strip().lower()
                    record = next(records)
                    if record.get("op") != operand:
                        raise RuntimeError(
                            f"dump desync {corpus}:{index}: "
                            f"{record.get('op')} != {operand}")
                    endpoint = {}
                    truth = {}
                    incumbent = {}
                    for mode in MODES:
                        truth[mode] = output_value(
                            hardware[mode].readline(),
                            str(hardware_paths[mode]), index)
                        for carry in (0, 1):
                            process = forced[carry, mode]
                            if process.stdout is None:
                                raise AssertionError("forced model has no stdout")
                            endpoint[carry, mode] = output_value(
                                process.stdout.readline(),
                                f"carry{carry}/{mode}", index)

                        process = baseline[mode]
                        if process.stdout is None:
                            raise AssertionError("baseline model has no stdout")
                        incumbent[mode] = output_value(
                            process.stdout.readline(),
                            f"baseline/{mode}", index)

                    allowed = [carry for carry in (0, 1)
                               if all(endpoint[carry, mode] == truth[mode]
                                      for mode in MODES)]
                    cut = int(record["k"])
                    mask = (1 << cut) - 1
                    s_value, b_value = int(record["S"], 16), int(record["B"], 16)
                    borrow = int((s_value & mask) < (b_value & mask))
                    current_candidates = [
                        carry for carry in (0, 1)
                        if all(endpoint[carry, mode] == incumbent[mode]
                               for mode in MODES)
                    ]
                    if len(current_candidates) == 1:
                        current_carry = current_candidates[0]
                        current_delta = borrow - 1 + current_carry
                    elif len(current_candidates) == 2 and len(allowed) != 1:
                        # All three architectural modes can collapse the two
                        # adjacent retained values.  Such a row is neutral if
                        # hardware admits them, or unrepresented if it admits
                        # neither; the incumbent bit is unobservable either way.
                        current_carry = -1
                        current_delta = 99
                    else:
                        raise RuntimeError(
                            f"ambiguous incumbent carry {corpus}:{index}:"
                            f"{operand}:{current_candidates}")
                    if len(allowed) == 1:
                        selector_status = "constraining"
                        target_flip = int(current_carry != allowed[0])
                    elif len(allowed) == 2:
                        selector_status = "neutral"
                        target_flip = 0
                    else:
                        selector_status = "unrepresented"
                        target_flip = 1

                    row = {
                        **record,
                        "corpus": corpus,
                        "index": str(index),
                        "selector_status": selector_status,
                        "allowed_carry": ",".join(map(str, allowed)) or "-",
                        "current_carry": (str(current_carry)
                                          if current_carry >= 0 else "-"),
                        "target_flip": str(target_flip),
                        "borrow": str(borrow),
                        "current_delta": (str(current_delta)
                                          if current_carry >= 0 else "-"),
                    }
                    status_counts[selector_status] += 1
                    corpus_counts[(corpus, selector_status)] += 1
                    cell = row_cell(record)
                    if cell in target_cells:
                        target_writer.writerow(row)
                        cell_counts[(cell, selector_status,
                                     tuple(allowed), current_carry)] += 1
                    if target_flip:
                        residual_writer.writerow(row)
                        residual_operands.add(operand)
                    if (index + 1) % 100000 == 0:
                        print(
                            f"{corpus} {index + 1} status={dict(status_counts)} "
                            f"residuals={len(residual_operands)}",
                            flush=True,
                        )

            try:
                next(records)
            except StopIteration:
                pass
            else:
                raise RuntimeError(f"extra dump records for {corpus}")
            close_model(dump_process, f"dump/{corpus}")
            for mode, process in baseline.items():
                close_model(process, f"baseline/{mode}/{corpus}")
            for key, process in forced.items():
                close_model(process, f"carry{key[0]}/{key[1]}/{corpus}")
            for mode, stream in hardware.items():
                if stream.readline():
                    raise RuntimeError(f"extra hardware rows {corpus}/{mode}")
                stream.close()

    with report_output.open("x") as target:
        target.write(f"target_features_sha256\t{digest(args.target_features)}\n")
        target.write(f"current_sha256\t{digest(args.current)}\n")
        target.write(f"carry0_sha256\t{digest(args.carry0)}\n")
        target.write(f"carry1_sha256\t{digest(args.carry1)}\n")
        target.write(f"corpora\t{','.join(args.corpora)}\n")
        target.write(f"target_cells\t{len(target_cells)}\n")
        target.write(f"residual_operands\t{len(residual_operands)}\n")
        for status, count in sorted(status_counts.items()):
            target.write(f"status {status}\t{count}\n")
        for key, count in sorted(corpus_counts.items()):
            target.write(f"corpus {key[0]} {key[1]}\t{count}\n")
        target.write(f"target_cells_sha256\t{digest(target_output)}\n")
        target.write(f"residuals_sha256\t{digest(residual_output)}\n")
        target.write("\n[cell counts]\n")
        target.write("cell\tstatus\tallowed\tcurrent\tcount\n")
        for key, count in sorted(cell_counts.items(), key=str):
            cell, status, allowed, current_carry = key
            target.write(
                f"{'/'.join(cell)}\t{status}\t"
                f"{','.join(map(str, allowed)) or '-'}\t"
                f"{current_carry}\t{count}\n"
            )
    print(
        f"wrote {report_output} target={target_output} "
        f"residuals={residual_output}",
        flush=True,
    )


if __name__ == "__main__":
    main()
