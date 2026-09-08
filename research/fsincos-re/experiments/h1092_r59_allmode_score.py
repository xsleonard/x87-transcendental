#!/usr/bin/env python3
"""Disambiguate absolute R59 corrections with cached four-mode legs."""

import argparse
import csv
import os
import subprocess
from collections import Counter, defaultdict


def run(binary, mode, operands):
    args = [binary, "--batch", "--fcos-standalone"]
    if mode != "rn":
        args.insert(2, "--rc=" + mode)
    process = subprocess.run(args, input="\n".join(operands) + "\n",
                             capture_output=True, text=True, check=True)
    values = []
    for line in process.stdout.splitlines():
        fields = line.split()
        if len(fields) >= 3 and fields[0] == "OK":
            values.append(fields[1].lower() + ":" + fields[2].lower())
    if len(values) != len(operands):
        raise RuntimeError("output count mismatch for " + binary)
    return values


parser = argparse.ArgumentParser()
parser.add_argument("bank")
parser.add_argument("baseline")
parser.add_argument("force_pattern")
parser.add_argument("output")
args = parser.parse_args()
if os.path.exists(args.output):
    raise SystemExit("refusing to overwrite " + args.output)

with open(args.bank) as source:
    rows = list(csv.DictReader(source, delimiter="\t"))
groups = defaultdict(list)
for index, row in enumerate(rows):
    groups[row["mode"]].append((index, row))
binaries = [(0, args.baseline)] + [
    (number, args.force_pattern % number) for number in range(1, 6)]
for number, binary in binaries:
    for mode, indexed in groups.items():
        outputs = run(binary, mode, [row["op"] for _, row in indexed])
        for (index, _), output in zip(indexed, outputs):
            rows[index]["f%d" % number] = output

by_operand = defaultdict(list)
for row in rows:
    matches = [number for number in range(1, 6)
               if row["f%d" % number] == row["hw"]]
    row["matches"] = ",".join(map(str, matches)) or "-"
    by_operand[row["op"]].append(set(matches))

columns = tuple(rows[0]) + ("matches",)
with open(args.output, "w", newline="") as target:
    writer = csv.DictWriter(target, columns, delimiter="\t",
                            extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)

summary = Counter()
for operand in sorted(by_operand):
    exact = set.intersection(*by_operand[operand])
    deltas = sorted(number - 3 for number in exact)
    summary[tuple(deltas)] += 1
    print(operand, "force=" + (",".join(map(str, sorted(exact))) or "-"),
          "delta=" + (",".join(map(str, deltas)) or "-"))
print("summary", dict(summary))
