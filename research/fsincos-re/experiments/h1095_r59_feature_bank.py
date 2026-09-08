#!/usr/bin/env python3
"""Build a raw R59 feature bank for ledger errors and cached controls."""

import argparse
import csv
import os
import re
import subprocess


def parse_tokens(line):
    values = {}
    for match in re.finditer(r"(\w+)=([0-9a-fA-F,-]+)", line):
        values[match.group(1)] = match.group(2)
    return values


def parse_wide_values(line):
    values = {}
    for match in re.finditer(
            r"(mul|lf|rf|f4|mag|left|right)=([01]):(-?\d+):([0-9a-fA-F]+)",
            line):
        name, sign, exponent, significand = match.groups()
        values["tc_" + name + "_sign"] = sign
        values["tc_" + name + "_exp"] = exponent
        values["tc_" + name + "_sig"] = significand.lower()
    return values


def dump(binary, mode, operands):
    args = [binary, "--batch", "--fcos-standalone", "--dump-internals"]
    if mode != "rn":
        args.insert(2, "--rc=" + mode)
    process = subprocess.run(args, input="\n".join(operands) + "\n",
                             capture_output=True, text=True, check=True)
    records = []
    current = None
    for line in process.stderr.splitlines():
        if line.startswith("DI_IN "):
            if current is not None:
                records.append(current)
            current = {"op": " ".join(line.split()[1:3]).lower()}
        elif current is not None and line.startswith("DI_R59 "):
            current.update(parse_tokens(line))
        elif current is not None and line.startswith("DI_TC "):
            current.update({"tc_" + key: value
                            for key, value in parse_tokens(line).items()})
            current.update(parse_wide_values(line))
        elif current is not None and line.startswith("DI_CRIT "):
            current.update({"crit_" + key: value
                            for key, value in parse_tokens(line).items()})
        elif current is not None and line.startswith("DI_BS "):
            current.update({"bs_" + key: value
                            for key, value in parse_tokens(line).items()})
        elif current is not None and line.startswith("DI_BR "):
            current["branch"] = line.split()[1].split("=", 1)[1]
            current.update({"br_" + key: value
                            for key, value in parse_tokens(line).items()
                            if key != "br"})
    if current is not None:
        records.append(current)
    if len(records) != len(operands):
        raise RuntimeError("dump count mismatch %d != %d in %s" %
                           (len(records), len(operands), mode))
    return records


parser = argparse.ArgumentParser()
parser.add_argument("controls")
parser.add_argument("allmode_score")
parser.add_argument("model")
parser.add_argument("output")
args = parser.parse_args()
if os.path.exists(args.output):
    raise SystemExit("refusing to overwrite " + args.output)

with open(args.allmode_score) as source:
    scored = list(csv.DictReader(source, delimiter="\t"))
positive = {}
for row in scored:
    if row["hw"] == row["f0"]:
        continue
    matches = []
    if row["hw"] == row["f1"]:
        matches.append("minus2")
    if row["hw"] == row["f4"]:
        matches.append("plus1")
    if len(matches) != 1:
        raise RuntimeError("ambiguous canonical endpoint for " + row["op"])
    prior = positive.setdefault(row["op"], (row["mode"], matches[0],
                                             row["hw"]))
    if prior[1] != matches[0]:
        raise RuntimeError("mode-dependent endpoint for " + row["op"])

selected = {}
for operand, (mode, endpoint, hw) in positive.items():
    selected[operand] = {"label": "POS", "desired": endpoint,
                         "mode": mode, "hw": hw}
with open(args.controls) as source:
    for row in csv.DictReader(source, delimiter="\t"):
        if row["op"] in positive:
            continue
        endpoint_matches = []
        if row["hw"] == row["fminus2"]:
            endpoint_matches.append("minus2")
        if row["hw"] == row["fplus1"]:
            endpoint_matches.append("plus1")
        if len(endpoint_matches) != 1:
            raise RuntimeError("ambiguous control endpoint for " + row["op"])
        endpoint = endpoint_matches[0]
        prior = selected.setdefault(row["op"], {
            "label": "NEG", "desired": endpoint, "mode": row["mode"],
            "hw": row["hw"]})
        if prior["desired"] != endpoint:
            raise RuntimeError("mode-dependent control endpoint for " +
                               row["op"])

for mode in ("rn", "rd", "ru", "rz"):
    operands = sorted(operand for operand, row in selected.items()
                      if row["mode"] == mode)
    for start in range(0, len(operands), 2000):
        chunk = operands[start:start + 2000]
        records = dump(args.model, mode, chunk)
        for operand, record in zip(chunk, records):
            if record["op"] != operand:
                raise RuntimeError("dump desynchronization")
            selected[operand].update(record)

required = ("theta", "k", "ce", "s4", "side", "b1", "b2", "low3",
            "dist", "rsh", "payload", "rscale", "dl", "dr", "dp",
            "umag", "S", "B", "Mreg", "t4", "sqlow", "rd3", "disc",
            "branch")
kept = []
for operand, row in selected.items():
    if all(name in row for name in required):
        kept.append(row)
if len(kept) != len(selected):
    raise RuntimeError("%d selected rows did not reach R59" %
                       (len(selected) - len(kept)))

metadata = ("label", "desired", "mode", "op", "hw")
extras = sorted({key for row in kept for key in row}
                - set(metadata) - set(required))
columns = metadata + required + tuple(extras)
with open(args.output, "w", newline="") as target:
    writer = csv.DictWriter(target, columns, delimiter="\t",
                            extrasaction="ignore")
    writer.writeheader()
    writer.writerows(sorted(kept, key=lambda row: (
        row["label"], row["branch"], row["op"])))
print("rows", len(kept), "positive", len(positive),
      "negative", len(kept) - len(positive), "columns", len(columns))
