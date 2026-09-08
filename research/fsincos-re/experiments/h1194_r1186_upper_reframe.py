#!/usr/bin/env python3
"""Recompute upper-R59 coordinates after the R1186 factor recurrence.

The h1163 physical labels were decoded in the pre-R1186 internal coordinate
frame.  R1186 changes a Horner factor for some operands, so those labels
cannot safely be reused as terminal-surface constraints.  This script runs
only software models on the frozen h1163 operands, re-dumps their internal
coordinates, and re-decodes the two exact terminal carry endpoints against
the already cached hardware output.

No hardware instruction is executed and no hardware file is modified.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path


TOKEN = re.compile(r"(\w+)=([0-9a-fA-F,-]+)")
WIDE = re.compile(
    r"(mul|lf|rf|f4|mag|left|right)=([01]):(-?\d+):([0-9a-fA-F]+)")


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


def parse_outputs(text: str, count: int) -> list[str]:
    values = []
    for line in text.splitlines():
        fields = line.split()
        if len(fields) >= 3 and fields[0] == "OK":
            values.append(fields[1].lower() + ":" + fields[2].lower())
    if len(values) != count:
        raise RuntimeError(f"output count {len(values)} != {count}")
    return values


def run_values(binary: Path, mode: str, operands: list[str]) -> list[str]:
    result = subprocess.run(
        [str(binary), "--batch", f"--rc={mode}", "--fcos-standalone"],
        input="".join(operand + "\n" for operand in operands),
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        check=True,
    )
    return parse_outputs(result.stdout, len(operands))


def dump_values(binary: Path, mode: str,
                operands: list[str]) -> list[dict[str, str]]:
    result = subprocess.run(
        [str(binary), "--batch", f"--rc={mode}", "--fcos-standalone",
         "--dump-internals"],
        input="".join(operand + "\n" for operand in operands),
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        check=True,
    )
    records = []
    current = None
    for line in result.stderr.splitlines():
        if line.startswith("DI_IN "):
            if current is not None:
                records.append(current)
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
        records.append(current)
    if len(records) != len(operands):
        raise RuntimeError(f"dump count {len(records)} != {len(operands)}")
    for operand, record in zip(operands, records):
        if record["op"] != operand:
            raise RuntimeError(f"dump desync {record['op']} != {operand}")
    return records


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("physical_rows", type=Path)
    parser.add_argument("current", type=Path)
    parser.add_argument("carry0", type=Path)
    parser.add_argument("carry1", type=Path)
    parser.add_argument("row_output", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("--chunk", type=int, default=2000)
    args = parser.parse_args()
    for path in (args.row_output, args.report):
        if path.exists():
            raise SystemExit(f"refusing to overwrite {path}")

    with args.physical_rows.open(newline="") as source:
        input_rows = list(csv.DictReader(source, delimiter="\t"))
    by_mode = defaultdict(list)
    for row in input_rows:
        by_mode[row["mode"]].append(row)

    output_rows = []
    counts = Counter()
    for mode, mode_rows in sorted(by_mode.items()):
        for start in range(0, len(mode_rows), args.chunk):
            rows = mode_rows[start:start + args.chunk]
            operands = [row["op"] for row in rows]
            current_values = run_values(args.current, mode, operands)
            carry0_values = run_values(args.carry0, mode, operands)
            carry1_values = run_values(args.carry1, mode, operands)
            records = dump_values(args.current, mode, operands)
            for old, current_value, carry0, carry1, record in zip(
                    rows, current_values, carry0_values, carry1_values, records):
                hardware = old["hw"].lower()
                allowed = [carry for carry, value in
                           ((0, carry0), (1, carry1)) if value == hardware]
                status = ("constraining" if len(allowed) == 1
                          else "neutral" if len(allowed) == 2
                          else "unrepresented")
                target = current_value != hardware
                row = {
                    **record,
                    "label": "POS" if target else "NEG",
                    "mode": mode,
                    "op": old["op"],
                    "hw": old["hw"],
                    "old_label": old["label"],
                    "old_status": old["physical_status"],
                    "current": current_value,
                    "carry0": carry0,
                    "carry1": carry1,
                    "allowed_carry": ",".join(map(str, allowed)),
                    "physical_label": (str(allowed[0])
                                       if len(allowed) == 1 else ""),
                    "physical_status": status,
                }
                output_rows.append(row)
                counts["rows"] += 1
                counts[f"target.{int(target)}"] += 1
                counts[f"status.{status}"] += 1
                counts[f"old_target.{int(old['label'] == 'POS')}."
                       f"target.{int(target)}"] += 1
                counts[f"old_status.{old['physical_status']}.status.{status}"] += 1

    preferred = (
        "label", "mode", "op", "hw", "old_label", "old_status",
        "current", "carry0", "carry1", "allowed_carry",
        "physical_label", "physical_status",
    )
    remaining = sorted({key for row in output_rows for key in row}
                       - set(preferred))
    columns = preferred + tuple(remaining)
    args.row_output.parent.mkdir(parents=True, exist_ok=True)
    with args.row_output.open("x", newline="") as target:
        writer = csv.DictWriter(target, columns, delimiter="\t",
                                extrasaction="ignore")
        writer.writeheader()
        writer.writerows(output_rows)

    with args.report.open("x") as target:
        target.write(
            f"physical_rows_sha256\t{digest(args.physical_rows)}\n")
        target.write(f"current_sha256\t{digest(args.current)}\n")
        target.write(f"carry0_sha256\t{digest(args.carry0)}\n")
        target.write(f"carry1_sha256\t{digest(args.carry1)}\n")
        target.write(f"row_output_sha256\t{digest(args.row_output)}\n")
        target.write("\n[counts]\n")
        for name, value in sorted(counts.items()):
            target.write(f"{name}\t{value}\n")
        target.write("\n[remaining targets]\n")
        target.write("mode\top\thw\tcurrent\tstatus\tallowed_carry\tbranch\n")
        for row in output_rows:
            if row["label"] == "POS":
                target.write(
                    f"{row['mode']}\t{row['op']}\t{row['hw']}\t"
                    f"{row['current']}\t{row['physical_status']}\t"
                    f"{row['allowed_carry'] or '-'}\t{row.get('branch', '-')}\n")

    print(
        f"wrote {args.row_output} and {args.report} "
        f"rows={counts['rows']} targets={counts['target.1']} "
        f"constraining={counts['status.constraining']}", flush=True)


if __name__ == "__main__":
    main()
