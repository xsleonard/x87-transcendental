#!/usr/bin/env python3
"""Join an h1078 feature selection with its one-pass hardware captures."""

import argparse
import csv
import subprocess
from collections import Counter


MODES = ("rn", "rd", "ru", "rz")


def run_model(binary, insn, mode, operands):
    args = [binary, "--batch", "--f%s-standalone" % insn]
    if mode != "rn":
        args.insert(2, "--rc=" + mode)
    process = subprocess.run(
        args, input="\n".join(operands) + "\n", capture_output=True,
        text=True, check=True)
    outputs = []
    for line in process.stdout.splitlines():
        fields = line.split()
        if len(fields) >= 3 and fields[0] == "OK":
            outputs.append("%s:%s" % (fields[1].lower(), fields[2].lower()))
    if len(outputs) != len(operands):
        raise RuntimeError("output count mismatch for %r" % (args,))
    return outputs


def read_capture(path):
    values = []
    with open(path) as source:
        for line in source:
            fields = line.split()
            if len(fields) != 3 or fields[0] != "OK":
                raise ValueError("bad capture line in %s: %r" % (path, line))
            values.append("%s:%s" % (fields[1].lower(), fields[2].lower()))
    return values


parser = argparse.ArgumentParser()
parser.add_argument("features")
parser.add_argument("candidate")
parser.add_argument("force3")
parser.add_argument("force9")
parser.add_argument("capture_prefix",
                    help="raw capture files are PREFIX_rn.txt, etc.")
parser.add_argument("output")
parser.add_argument("--insn", choices=("sin", "cos"), default="cos")
args = parser.parse_args()

with open(args.features) as source:
    features = list(csv.DictReader(source, delimiter="\t"))
operands = [row["op"] for row in features]
feature_columns = tuple(name for name in features[0] if name != "op")

rows = []
totals = Counter()
for mode in MODES:
    hardware = read_capture("%s_%s.txt" % (args.capture_prefix, mode))
    base = run_model(args.candidate, args.insn, mode, operands)
    force3 = run_model(args.force3, args.insn, mode, operands)
    force9 = run_model(args.force9, args.insn, mode, operands)
    if len(hardware) != len(operands):
        raise RuntimeError("hardware count mismatch in mode " + mode)
    for feature, hw, ordinary, f3, f9 in zip(
            features, hardware, base, force3, force9):
        matches = []
        if hw == ordinary:
            matches.append("BASE")
        if hw == f3:
            matches.append("F3")
        if hw == f9:
            matches.append("F9")
        label = ",".join(matches) if matches else "OTHER"
        totals[mode, label] += 1
        rows.append({
            "insn": args.insn, "mode": mode, "op": feature["op"],
            "hw": hw, "base": ordinary, "force3": f3, "force9": f9,
            "label": label, **{name: feature[name]
                               for name in feature_columns},
        })

columns = ("insn", "mode", "op", "hw", "base", "force3", "force9",
           "label") + feature_columns
with open(args.output, "w", newline="") as target:
    writer = csv.DictWriter(target, columns, delimiter="\t")
    writer.writeheader()
    writer.writerows(rows)

print("rows", len(rows), "operands", len(operands))
for key in sorted(totals):
    print(key, totals[key])
print("\nRU response map")
for row in rows:
    if row["mode"] == "ru":
        print("%(op)s label=%(label)s l=%(low3)s q=%(qpost11)s "
              "p=%(pcut)s pbelow=%(pbelow)s m128=%(m128)s "
              "phase8=%(phase8)s" % row)
