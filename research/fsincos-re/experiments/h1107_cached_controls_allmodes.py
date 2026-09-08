#!/usr/bin/env python3
"""Join all four already-captured hardware modes for h1094 controls.

This script performs no x87 instruction.  It verifies each sampled operand
against its banked corpus index, then reads the four immutable status files.
The result lets later response models intersect all architectural rounding
modes instead of treating the h1094 endpoint label as a unique internal
retained correction.
"""

import argparse
import csv
import os
from collections import defaultdict


MODES = ("rn", "rd", "ru", "rz")


parser = argparse.ArgumentParser()
parser.add_argument("controls")
parser.add_argument("capture_root")
parser.add_argument("output")
args = parser.parse_args()
if os.path.exists(args.output):
    raise SystemExit("refusing to overwrite " + args.output)

targets = {}
with open(args.controls) as source:
    for row in csv.DictReader(source, delimiter="\t"):
        key = row["corpus"], int(row["index"])
        value = row["op"].lower()
        prior = targets.setdefault(key, value)
        if prior != value:
            raise RuntimeError("conflicting operand for %r" % (key,))

by_corpus = defaultdict(dict)
for (corpus, index), operand in targets.items():
    by_corpus[corpus][index] = operand

rows = []
for corpus in sorted(by_corpus):
    wanted = by_corpus[corpus]
    observed_inputs = {}
    input_path = os.path.join(
        args.capture_root, corpus + "_inputs.txt")
    with open(input_path) as source:
        for index, line in enumerate(source):
            if index in wanted:
                observed_inputs[index] = line.strip().lower()
    if set(observed_inputs) != set(wanted):
        raise RuntimeError("missing input rows for " + corpus)
    for index, operand in wanted.items():
        if observed_inputs[index] != operand:
            raise RuntimeError(
                "input mismatch %s:%d: %s != %s" %
                (corpus, index, observed_inputs[index], operand))

    for mode in MODES:
        observed_status = {}
        status_path = os.path.join(
            args.capture_root, "%s_%s_status.txt" % (corpus, mode))
        with open(status_path) as source:
            for index, line in enumerate(source):
                if index not in wanted:
                    continue
                fields = line.split()
                if len(fields) < 3 or fields[0] != "OK":
                    raise RuntimeError(
                        "bad status %s:%d" % (status_path, index))
                observed_status[index] = (
                    fields[1].lower() + ":" + fields[2].lower())
        if set(observed_status) != set(wanted):
            raise RuntimeError("missing status rows for " + status_path)
        for index in sorted(wanted):
            rows.append({
                "insn": "cos",
                "mode": mode,
                "op": wanted[index],
                "hw": observed_status[index],
                "corpus": corpus,
                "index": index,
            })

with open(args.output, "w", newline="") as target:
    writer = csv.DictWriter(
        target, ("insn", "mode", "op", "hw", "corpus", "index"),
        delimiter="\t")
    writer.writeheader()
    writer.writerows(rows)
print("operands", len(targets), "legs", len(rows))
