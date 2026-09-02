#!/usr/bin/env python3
"""h1006: score a terminal candidate over every hardware union leg."""

import csv
import subprocess
import sys
from collections import Counter, defaultdict


DATA = "h989_union_legs.tsv"
BASE = sys.argv[1] if len(sys.argv) > 1 else "/tmp/x87-r95-check"
CANDIDATE = (sys.argv[2] if len(sys.argv) > 2
             else "/tmp/x87-r96-res1024")


def norm(value):
    return value.lower().replace(":", " ")


def run_model(binary, insn, mode, operands):
    args = [binary, "--batch",
            "--fsin-standalone" if insn == "sin"
            else "--fcos-standalone"]
    if mode != "rn":
        args.insert(2, "--rc=" + mode)
    process = subprocess.run(args, input="\n".join(operands) + "\n",
                             capture_output=True, text=True, check=True)
    output = [norm(":".join(line.split()[1:3]))
              for line in process.stdout.splitlines()]
    if len(output) != len(operands):
        raise RuntimeError("model output count mismatch")
    return output


with open(DATA) as src:
    rows = list(csv.DictReader(src, delimiter="\t"))

groups = defaultdict(list)
for row in rows:
    groups[(row["insn"], row["mode"])].append(row)

totals = Counter()
changed_ops = set()
examples = []
for (insn, mode), sample in sorted(groups.items()):
    operands = [row["op"] for row in sample]
    baseline = run_model(BASE, insn, mode, operands)
    candidate = run_model(CANDIDATE, insn, mode, operands)
    group = Counter()
    for row, before, after in zip(sample, baseline, candidate):
        hardware = norm(row["hw"])
        if before == after:
            outcome = "UNCHANGED_BAD" if before != hardware else "UNCHANGED_OK"
        elif after == hardware and before != hardware:
            outcome = "FIX"
        elif before == hardware and after != hardware:
            outcome = "BREAK"
        else:
            outcome = "OTHER"
        group[outcome] += 1
        totals[outcome] += 1
        if before != after:
            changed_ops.add((insn, row["op"]))
            if len(examples) < 100:
                examples.append((outcome, insn, row["op"], mode,
                                 hardware, before, after))
    print("%-3s %-2s %s" % (insn, mode, dict(group)))

print("\ntotals", dict(totals))
print("baseline misses", totals["FIX"] + totals["OTHER"]
      + totals["UNCHANGED_BAD"])
print("candidate misses", totals["BREAK"] + totals["OTHER"]
      + totals["UNCHANGED_BAD"])
print("changed ops", len(changed_ops))
print("changed examples:")
for example in examples:
    print("  %s %s %s %s hw=%s base=%s candidate=%s" % example)
