#!/usr/bin/env python3
"""Rescore frozen h1055 blind captures without recapturing hardware.

Each input TSV contains only legs changed by the candidate that was frozen
when the bank was generated.  A later candidate may deliberately leave one
of those legs unchanged, so UNCHANGED_OK is distinct from FIX.
"""

import argparse
import csv
import subprocess
from collections import Counter, defaultdict


def model(binary, insn, mode, operands):
    args = [binary, "--batch", "--f%s-standalone" % insn]
    if mode != "rn":
        args.insert(2, "--rc=" + mode)
    process = subprocess.run(args, input="\n".join(operands) + "\n",
                             capture_output=True, text=True, check=True)
    result = []
    for line in process.stdout.splitlines():
        fields = line.split()
        result.append("%s:%s" % (fields[1].lower(), fields[2].lower()))
    if len(result) != len(operands):
        raise RuntimeError("output length mismatch for %r" % (args,))
    return result


parser = argparse.ArgumentParser()
parser.add_argument("candidate")
parser.add_argument("captures", nargs="+")
args = parser.parse_args()

grand = Counter()
for path in args.captures:
    with open(path) as source:
        rows = list(csv.DictReader(source, delimiter="\t"))
    groups = defaultdict(list)
    for row in rows:
        groups[(row["insn"], row["mode"])].append(row)
    totals = Counter()
    failures = []
    for (insn, mode), group in groups.items():
        outputs = model(args.candidate, insn, mode,
                        [row["op"] for row in group])
        for row, current in zip(group, outputs):
            hardware = row["hw"].lower()
            baseline = row["base"].lower()
            if current == hardware and baseline != hardware:
                outcome = "FIX"
            elif current == hardware and baseline == hardware:
                outcome = "UNCHANGED_OK"
            elif current != hardware and baseline == hardware:
                outcome = "BREAK"
            else:
                outcome = "OTHER"
            totals[outcome] += 1
            if outcome in ("BREAK", "OTHER"):
                failures.append((outcome, insn, mode, row["op"], hardware,
                                 baseline, current))
    grand.update(totals)
    print(path, dict(totals))
    for failure in failures:
        print(" ", *failure)
print("total", dict(grand))
