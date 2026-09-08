#!/usr/bin/env python3
"""Recover all four cached hardware legs for the R59 ledger operands.

Run on the authorized host.  The suite-wall rows provide corpus indices; this
script verifies each operand against the corresponding input file and joins
the already-banked per-mode hardware status files.  It never invokes x87.
"""

import csv
import os
import sys


if len(sys.argv) != 3:
    raise SystemExit("usage: h1091_r59_allmodes_cached.py WALL_TSV OUT_TSV")
wall_path, output_path = sys.argv[1:]
if os.path.exists(output_path):
    raise SystemExit("refusing to overwrite " + output_path)

targets = {}
with open(wall_path) as source:
    for fields in csv.reader(source, delimiter="\t"):
        if len(fields) < 7:
            continue
        corpus, insn, _, index_text, operand = fields[:5]
        if insn != "cos":
            continue
        key = (corpus, int(index_text))
        prior = targets.setdefault(key, operand.lower())
        if prior != operand.lower():
            raise RuntimeError("conflicting operand at %r" % (key,))

rows = []
for corpus in sorted({corpus for corpus, _ in targets}):
    wanted = {index for corp, index in targets if corp == corpus}
    inputs = {}
    with open("/root/h491/%s_inputs.txt" % corpus) as source:
        for index, line in enumerate(source):
            if index in wanted:
                inputs[index] = line.strip().lower()
    if set(inputs) != wanted:
        raise RuntimeError("missing input indices for " + corpus)
    for index in wanted:
        expected = targets[corpus, index]
        if inputs[index] != expected:
            raise RuntimeError("input mismatch %s:%d: %s != %s" %
                               (corpus, index, inputs[index], expected))
    for mode in ("rn", "rd", "ru", "rz"):
        values = {}
        path = "/root/h491/%s_%s_status.txt" % (corpus, mode)
        with open(path) as source:
            for index, line in enumerate(source):
                if index in wanted:
                    fields = line.split()
                    if len(fields) < 3 or fields[0] != "OK":
                        raise RuntimeError("bad status %s:%d" %
                                           (path, index))
                    values[index] = fields[1].lower() + ":" \
                        + fields[2].lower()
        if set(values) != wanted:
            raise RuntimeError("missing status indices for " + path)
        for index in sorted(wanted):
            rows.append(("cos", mode, inputs[index], values[index],
                         corpus, str(index)))

with open(output_path, "w", newline="") as target:
    writer = csv.writer(target, delimiter="\t")
    writer.writerow(("insn", "mode", "op", "hw", "corpus", "index"))
    writer.writerows(rows)
print("operands", len(targets), "legs", len(rows))
