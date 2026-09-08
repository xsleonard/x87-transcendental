#!/usr/bin/env python3
"""Score one model against heterogeneous cached hardware TSV banks."""

import argparse
import csv
import subprocess
from collections import Counter, defaultdict


def normalize(value):
    return ":".join(value.lower().split())


def model(binary, insn, mode, operands):
    args = [binary, "--batch", "--f%s-standalone" % insn]
    if mode != "rn":
        args.insert(2, "--rc=" + mode)
    process = subprocess.run(
        args, input="\n".join(operands) + "\n", capture_output=True,
        text=True, check=True)
    outputs = []
    for line in process.stdout.splitlines():
        fields = line.split()
        if len(fields) >= 3:
            outputs.append("%s:%s" % (fields[1].lower(), fields[2].lower()))
    if len(outputs) != len(operands):
        raise RuntimeError("output count mismatch for %r" % (args,))
    return outputs


parser = argparse.ArgumentParser()
parser.add_argument("model")
parser.add_argument("banks", nargs="+")
args = parser.parse_args()

grand = Counter()
for path in args.banks:
    with open(path) as source:
        input_rows = list(csv.DictReader(source, delimiter="\t"))
    groups = defaultdict(list)
    for row in input_rows:
        basename = path.split("/")[-1]
        inferred = (
            "sin" if basename.startswith("h1071_sin_")
            else "cos" if basename.startswith(("h1069_", "h1071_"))
            else None)
        insn = row.get("insn") or inferred
        if not (insn and row.get("mode") and row.get("op") and row.get("hw")):
            continue
        groups[insn, row["mode"]].append(row)
    totals = Counter()
    misses = []
    for (insn, mode), rows in sorted(groups.items()):
        outputs = model(args.model, insn, mode, [row["op"] for row in rows])
        for row, output in zip(rows, outputs):
            hardware = normalize(row["hw"])
            if output == hardware:
                totals["EXACT"] += 1
            else:
                totals["MISS"] += 1
                misses.append((insn, mode, row["op"], hardware, output))
    grand.update(totals)
    print(path, dict(totals))
    for miss in misses[:100]:
        print(" MISS", *miss)
    if len(misses) > 100:
        print(" ...", len(misses) - 100, "additional misses")
print("TOTAL", dict(grand))
