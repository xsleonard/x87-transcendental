#!/usr/bin/env python3
"""Label h1168 rows by exact carry endpoint using archived RN/RD/RU truth."""

from __future__ import annotations

import argparse
import csv
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


def output_value(line: str, source: str, ordinal: int) -> str:
    fields = line.split()
    if len(fields) < 3 or fields[0] != "OK":
        raise RuntimeError(f"bad output {source}:{ordinal}: {line.rstrip()}")
    return fields[1].lower() + ":" + fields[2].lower()


def start_model(binary: Path, mode: str, ops: Path):
    source = ops.open()
    process = subprocess.Popen(
        [str(binary), "--batch", f"--rc={mode}", "--fcos-standalone"],
        stdin=source, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        text=True, bufsize=1)
    process.input_source = source
    return process


def close_model(process, name: str) -> None:
    if process.stdout is not None and process.stdout.readline():
        raise RuntimeError(f"extra output from {name}")
    code = process.wait()
    process.input_source.close()
    if code:
        raise RuntimeError(f"{name} exited {code}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("truth", type=Path)
    parser.add_argument("ops", type=Path)
    parser.add_argument("current", type=Path)
    parser.add_argument("carry0", type=Path)
    parser.add_argument("carry1", type=Path)
    parser.add_argument("output_prefix", type=Path)
    args = parser.parse_args()
    labels_path = args.output_prefix.with_name(args.output_prefix.name + "_labels.tsv")
    report_path = args.output_prefix.with_name(args.output_prefix.name + "_report.txt")
    for path in (labels_path, report_path):
        if path.exists():
            raise SystemExit(f"refusing to overwrite {path}")

    processes = {
        (name, mode): start_model(binary, mode, args.ops)
        for name, binary in (("current", args.current),
                             ("carry0", args.carry0),
                             ("carry1", args.carry1))
        for mode in MODES
    }
    counts = Counter()
    columns = (
        "op", "corpus", "index", "selector_status", "allowed_carry",
        "current_carry", "target_flip",
    )
    with args.truth.open(newline="") as source, \
            labels_path.open("x", newline="") as target:
        reader = csv.DictReader(source, delimiter="\t")
        writer = csv.DictWriter(target, columns, delimiter="\t")
        writer.writeheader()
        for ordinal, row in enumerate(reader):
            values = {}
            for key, process in processes.items():
                if process.stdout is None:
                    raise AssertionError("model has no stdout")
                values[key] = output_value(
                    process.stdout.readline(), "/".join(key), ordinal)
            allowed = [carry for carry in (0, 1)
                       if all(values[f"carry{carry}", mode] == row[f"hw_{mode}"]
                              for mode in MODES)]
            current = [carry for carry in (0, 1)
                       if all(values[f"carry{carry}", mode]
                              == values["current", mode] for mode in MODES)]
            if len(current) == 1:
                current_value = current[0]
            elif len(current) == 2 and len(allowed) != 1:
                current_value = -1
            else:
                raise RuntimeError(
                    f"ambiguous current endpoint {ordinal}:{row['op']}:{current}")
            if len(allowed) == 1:
                status = "constraining"
                target_flip = int(current_value != allowed[0])
            elif len(allowed) == 2:
                status = "neutral"
                target_flip = 0
            else:
                status = "unrepresented"
                target_flip = 1
            writer.writerow({
                "op": row["op"], "corpus": row["corpus"],
                "index": row["index"], "selector_status": status,
                "allowed_carry": ",".join(map(str, allowed)) or "-",
                "current_carry": (str(current_value)
                                  if current_value >= 0 else "-"),
                "target_flip": str(target_flip),
            })
            counts[(status, tuple(allowed), current_value, target_flip)] += 1
            if (ordinal + 1) % 100000 == 0:
                print(f"decoded {ordinal + 1} counts={dict(counts)}", flush=True)

    for key, process in processes.items():
        close_model(process, "/".join(key))
    with report_path.open("x") as target:
        for name, path in (("truth", args.truth), ("ops", args.ops),
                           ("current", args.current), ("carry0", args.carry0),
                           ("carry1", args.carry1), ("labels", labels_path)):
            target.write(f"{name}_sha256\t{digest(path)}\n")
        target.write("\n[counts]\n")
        for key, count in sorted(counts.items(), key=str):
            status, allowed, current_value, target_flip = key
            target.write(
                f"{status}\t{','.join(map(str, allowed)) or '-'}\t"
                f"{current_value if current_value >= 0 else '-'}\t"
                f"{target_flip}\t{count}\n")
    print(f"wrote {report_path}", flush=True)


if __name__ == "__main__":
    main()
