#!/usr/bin/env python3
"""Attribute h1022 blind failures to independently compiled R96 arms."""

import csv
import subprocess
from collections import Counter, defaultdict


ROWS = "/tmp/h1022_r96_annulus_changes.tsv"
BINARIES = {
    "res": "/tmp/x87-r96-res-only",
    "top": "/tmp/x87-r96-top-only",
    "low": "/tmp/x87-r96-low-only",
    "pair": "/tmp/x87-r96-pair-only",
}


def run(binary, insn, mode, operands):
    args = [binary, "--batch", "--f%s-standalone" % insn]
    if mode != "rn":
        args.insert(2, "--rc=" + mode)
    process = subprocess.run(args, input="\n".join(operands) + "\n",
                             capture_output=True, text=True, check=True)
    return ["%s:%s" % tuple(line.split()[1:3])
            for line in process.stdout.splitlines()]


with open(ROWS) as src:
    rows = list(csv.DictReader(src, delimiter="\t"))
groups = defaultdict(list)
for row in rows:
    groups[(row["insn"], row["mode"])].append(row)

totals = Counter()
attributed = []
for (insn, mode), sample in sorted(groups.items()):
    operands = [row["op"] for row in sample]
    outputs = {name: run(binary, insn, mode, operands)
               for name, binary in BINARIES.items()}
    for index, row in enumerate(sample):
        actors = tuple(name for name in BINARIES
                       if outputs[name][index] != row["base"])
        totals[actors] += 1
        attributed.append((actors[0] if len(actors) == 1 else "+".join(actors),
                           row["insn"], row["mode"], row["op"]))
        print(row["insn"], row["mode"], row["op"], ",".join(actors))
print("totals", dict(totals))
with open("/tmp/h1022_attributed.tsv", "w") as out:
    out.write("arm\tinsn\tmode\top\n")
    for row in attributed:
        out.write("\t".join(row) + "\n")
