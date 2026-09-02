#!/usr/bin/env python3
"""h1007: score a candidate on the fresh h1000 dense neighborhoods."""

import csv
import gzip
import subprocess
import sys
from collections import Counter


DATA = "h1000_sensitive_neighborhoods.tsv.gz"
CANDIDATE = (sys.argv[1] if len(sys.argv) > 1
             else "/tmp/x87-r96-res1024")
MODES = ("rn", "rd", "ru", "rz")


def norm(value):
    return value.lower().replace(":", " ")


def run_model(mode, operands):
    args = [CANDIDATE, "--batch", "--fcos-standalone"]
    if mode != "rn":
        args.insert(2, "--rc=" + mode)
    process = subprocess.run(args, input="\n".join(operands) + "\n",
                             capture_output=True, text=True, check=True)
    output = [norm(":".join(line.split()[1:3]))
              for line in process.stdout.splitlines()]
    if len(output) != len(operands):
        raise RuntimeError("model output count mismatch")
    return output


with gzip.open(DATA, "rt") as src:
    rows = list(csv.DictReader(src, delimiter="\t"))
operands = [row["op"] for row in rows]

totals = Counter()
by_family = Counter()
changed_ops = set()
examples = []
for mode in MODES:
    candidate = run_model(mode, operands)
    for row, after in zip(rows, candidate):
        before, hardware = norm(row["m_" + mode]), norm(row["h_" + mode])
        if after == before:
            continue
        if after == hardware and before != hardware:
            outcome = "FIX"
        elif before == hardware and after != hardware:
            outcome = "BREAK"
        else:
            outcome = "OTHER"
        totals[outcome] += 1
        by_family[(row["family"], outcome)] += 1
        changed_ops.add((row["seed"], row["op"]))
        if len(examples) < 30:
            examples.append((outcome, row["family"], row["seed"],
                             row["delta"], row["op"], mode,
                             hardware, before, after))

print("operands", len(rows), "legs", len(rows) * len(MODES))
print("totals", dict(totals), "changed ops", len(changed_ops))
print("by family", dict(sorted(by_family.items())))
print("changed examples:")
for example in examples:
    print("  %s %s seed=%s delta=%s %s %s "
          "hw=%s base=%s candidate=%s" % example)
