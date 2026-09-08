#!/usr/bin/env python3
"""Score the one-pass h1083 RU carry-coordinate bank."""

import csv
import os
import subprocess
import sys
from collections import Counter


if len(sys.argv) != 7:
    raise SystemExit("usage: h1083_carry_score.py FEATURES RAW BASE FORCE3 "
                     "FORCE9 OUTPUT")
features_path, raw_path, base_path, force3_path, force9_path, output = \
    sys.argv[1:]
if os.path.exists(output):
    raise SystemExit("refusing to overwrite " + output)


def model(binary, operands):
    process = subprocess.run(
        [binary, "--batch", "--rc=ru", "--fcos-standalone"],
        input="\n".join(operands) + "\n", capture_output=True,
        text=True, check=True)
    values = []
    for line in process.stdout.splitlines():
        fields = line.split()
        if len(fields) >= 3 and fields[0] == "OK":
            values.append(fields[1].lower() + ":" + fields[2].lower())
    if len(values) != len(operands):
        raise RuntimeError("model output count mismatch")
    return values


with open(features_path) as source:
    features = list(csv.DictReader(source, delimiter="\t"))
operands = [row["op"] for row in features]
hardware = []
with open(raw_path) as source:
    for line in source:
        fields = line.split()
        if len(fields) != 3 or fields[0] != "OK":
            raise ValueError("bad capture line " + repr(line))
        hardware.append(fields[1].lower() + ":" + fields[2].lower())
if len(hardware) != len(operands):
    raise RuntimeError("hardware output count mismatch")
base = model(base_path, operands)
force3 = model(force3_path, operands)
force9 = model(force9_path, operands)

columns = ("insn", "mode", "op", "hw", "base", "force3", "force9",
           "label") + tuple(name for name in features[0] if name != "op")
rows = []
counts = Counter()
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
    counts[label] += 1
    rows.append({"insn": "cos", "mode": "ru", "op": feature["op"],
                 "hw": hw, "base": ordinary, "force3": f3,
                 "force9": f9, "label": label,
                 **{name: value for name, value in feature.items()
                    if name != "op"}})
with open(output, "w", newline="") as target:
    writer = csv.DictWriter(target, columns, delimiter="\t")
    writer.writeheader()
    writer.writerows(rows)

print("rows", len(rows), dict(counts))
for row in rows:
    print(row["op"], row["label"], "p=" + row["pcut"],
          "mi=" + row["mi"], "b=" + row["b1"] + row["b2"],
          "m128=" + row["m128"], "oldfire=" + row["fire"])
