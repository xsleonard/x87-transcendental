#!/usr/bin/env python3
"""Score the one-pass h1097 R59 adversarial capture."""

import argparse
import csv
import os
import subprocess
from collections import Counter


def model(binary, operands):
    process = subprocess.run(
        [binary, "--batch", "--rc=ru", "--fcos-standalone"],
        input="\n".join(operands) + "\n", capture_output=True, text=True,
        check=True)
    values = []
    for line in process.stdout.splitlines():
        fields = line.split()
        if len(fields) >= 3 and fields[0] == "OK":
            values.append(fields[1].lower() + ":" + fields[2].lower())
    if len(values) != len(operands):
        raise RuntimeError("model output count mismatch for " + binary)
    return values


parser = argparse.ArgumentParser()
parser.add_argument("features")
parser.add_argument("raw")
parser.add_argument("baseline")
parser.add_argument("force_pattern")
parser.add_argument("output")
args = parser.parse_args()
if os.path.exists(args.output):
    raise SystemExit("refusing to overwrite " + args.output)

with open(args.features) as source:
    rows = list(csv.DictReader(source, delimiter="\t"))
operands = [row["op"] for row in rows]
hardware = []
with open(args.raw) as source:
    for line in source:
        fields = line.split()
        if len(fields) != 3 or fields[0] != "OK":
            raise RuntimeError("bad hardware row " + repr(line))
        hardware.append(fields[1].lower() + ":" + fields[2].lower())
if len(hardware) != len(rows):
    raise RuntimeError("hardware count mismatch")

outputs = {"base": model(args.baseline, operands)}
for number in range(1, 6):
    outputs["f%d" % number] = model(args.force_pattern % number, operands)

counts = Counter()
for index, (row, hw) in enumerate(zip(rows, hardware)):
    row["insn"] = "cos"
    row["mode"] = "ru"
    row["hw"] = hw
    row["base"] = outputs["base"][index]
    matches = []
    for number in range(1, 6):
        name = "f%d" % number
        row[name] = outputs[name][index]
        if row[name] == hw:
            matches.append(number - 3)
    row["matches"] = ",".join(map(str, matches)) or "-"
    row["verdict"] = "EXACT" if row["base"] == hw else "MISS"
    counts[row["verdict"], row["matches"]] += 1

prefix = ("insn", "mode", "op", "hw", "base", "f1", "f2", "f3",
          "f4", "f5", "matches", "verdict")
columns = prefix + tuple(name for name in rows[0] if name not in prefix)
with open(args.output, "w", newline="") as target:
    writer = csv.DictWriter(target, columns, delimiter="\t",
                            extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
print("rows", len(rows), dict(counts))
for row in rows:
    if row["verdict"] == "MISS":
        print(row["op"], "anchor=" + row["anchor"],
              "matches=" + row["matches"],
              "dM=" + row["mreg_delta"],
              "p=" + row["pbelow"] + "/" + row["pabove"])
