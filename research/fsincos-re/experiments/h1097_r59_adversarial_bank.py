#!/usr/bin/env python3
"""Construct fresh, label-blind adversarial neighbors for every R59 miss.

The two absolute response models make R59 coverage and architectural
visibility observable without consulting hardware.  Generate structured
neighbors around each known miss, keep only rows in the identical R59 cell,
then select signed-Mreg brackets with varied terminal propagate state.  The
output is an RU-only, one-capture-per-operand bank; this program never invokes
x87 hardware.
"""

import argparse
import csv
import os
import random
import re
import subprocess
from collections import defaultdict


CELL_FIELDS = ("branch", "theta", "ce", "s4", "side", "low3", "dist",
               "rsh", "b1", "b2")


def run(binary, operands, dump=False):
    process = subprocess.run(
        [binary, "--batch", "--rc=ru", "--fcos-standalone"]
        + (["--dump-internals"] if dump else []),
        input="\n".join(operands) + "\n", capture_output=True, text=True,
        check=True)
    values = []
    for line in process.stdout.splitlines():
        fields = line.split()
        if len(fields) >= 3 and fields[0] == "OK":
            values.append(fields[1].lower() + ":" + fields[2].lower())
    if len(values) != len(operands):
        raise RuntimeError("output count mismatch for " + binary)
    return values, process.stderr if dump else ""


def parse_tokens(line):
    return {match.group(1): match.group(2)
            for match in re.finditer(r"(\w+)=([0-9a-fA-F,-]+)", line)}


def parse_dump(text):
    records = []
    current = None
    for line in text.splitlines():
        if line.startswith("DI_IN "):
            if current is not None:
                records.append(current)
            fields = line.split()
            current = {"op": (fields[1] + " " + fields[2]).lower()}
        elif current is not None and line.startswith("DI_R59 "):
            current.update(parse_tokens(line))
        elif current is not None and line.startswith("DI_BR "):
            current["branch"] = line.split()[1].split("=", 1)[1]
            current.update({"br_" + key: value
                            for key, value in parse_tokens(line).items()
                            if key != "br"})
    if current is not None:
        records.append(current)
    return records


def signed128(text):
    value = int(text, 16)
    return value - (1 << 128) if value >> 127 else value


def terminal_features(record):
    S = int(record["S"], 16)
    B = int(record["B"], 16)
    k = int(record["k"])
    propagate = ~(S ^ B)
    below = 0
    while k - 1 - below >= 0 and ((propagate >> (k - 1 - below)) & 1):
        below += 1
    above = 0
    while above < 32 and ((propagate >> (k + above)) & 1):
        above += 1
    record["pbelow"] = str(below)
    record["pabove"] = str(above)
    record["mreg_signed"] = str(signed128(record["Mreg"]))
    record["terminal_byte"] = str((int(record["umag"], 16) >> k) & 255)
    return record


def generated_operand(anchor, index, generator):
    se_text, sig_text = anchor.split()
    sig = int(sig_text, 16)
    style = index % 3
    if style == 0:
        widths = (12, 16, 20, 24, 28, 32, 36, 40, 44, 48)
        width = widths[(index // 3) % len(widths)]
        mask = (1 << width) - 1
        sig = (sig & ~mask) | generator.getrandbits(width)
    elif style == 1:
        widths = (16, 20, 24, 28, 32, 36, 40, 44)
        width = widths[(index // 3) % len(widths)]
        count = 1 + ((index // (3 * len(widths))) % 5)
        for bit in generator.sample(range(width), count):
            sig ^= 1 << bit
    else:
        width = (12, 16, 20, 24, 28, 32, 36, 40)[
            (index // 3) % 8]
        delta = generator.randrange(1, 1 << width)
        sig += delta if generator.getrandbits(1) else -delta
    if not (1 << 63) <= sig < (1 << 64):
        return anchor
    return se_text + " " + ("%016x" % sig)


parser = argparse.ArgumentParser()
parser.add_argument("features")
parser.add_argument("baseline")
parser.add_argument("force_minus2")
parser.add_argument("force_plus1")
parser.add_argument("feature_output")
parser.add_argument("operand_output")
parser.add_argument("--samples-per-anchor", type=int, default=50000)
parser.add_argument("--limit-per-anchor", type=int, default=12)
parser.add_argument("--seed", type=lambda value: int(value, 0),
                    default=0x1097A6B3)
parser.add_argument("--chunk", type=int, default=20000)
args = parser.parse_args()
for path in (args.feature_output, args.operand_output):
    if os.path.exists(path):
        raise SystemExit("refusing to overwrite " + path)

with open(args.features) as source:
    all_features = list(csv.DictReader(source, delimiter="\t"))
anchors = [row for row in all_features if row["label"] == "POS"]
known = {row["op"].lower() for row in all_features}
target_by_cell = defaultdict(list)
for anchor in anchors:
    target_by_cell[tuple(anchor[name] for name in CELL_FIELDS)].append(anchor)

generator = random.Random(args.seed)
visible_sources = {}
for anchor_index, anchor in enumerate(anchors):
    operand = anchor["op"].lower()
    candidates = []
    for index in range(args.samples_per_anchor):
        candidate = generated_operand(operand, index, generator)
        if candidate not in known:
            candidates.append(candidate)
    candidates = sorted(set(candidates))
    for start in range(0, len(candidates), args.chunk):
        chunk = candidates[start:start + args.chunk]
        minus2, _ = run(args.force_minus2, chunk)
        plus1, _ = run(args.force_plus1, chunk)
        for candidate, first, second in zip(chunk, minus2, plus1):
            if first != second:
                visible_sources.setdefault(candidate, set()).add(operand)
    print("anchor", anchor_index + 1, "of", len(anchors), operand,
          "visible-total", len(visible_sources), flush=True)

records = {}
visible = sorted(visible_sources)
for start in range(0, len(visible), args.chunk):
    chunk = visible[start:start + args.chunk]
    _, dump = run(args.baseline, chunk, dump=True)
    parsed = parse_dump(dump)
    if len(parsed) != len(chunk):
        raise RuntimeError("dump count mismatch")
    for operand, record in zip(chunk, parsed):
        if record["op"] != operand:
            raise RuntimeError("dump desynchronization")
        if all(name in record for name in CELL_FIELDS +
               ("Mreg", "S", "B", "k", "umag")):
            records[operand] = terminal_features(record)

per_anchor = defaultdict(list)
for operand, record in records.items():
    cell = tuple(record[name] for name in CELL_FIELDS)
    if cell not in target_by_cell:
        continue
    for anchor in target_by_cell[cell]:
        per_anchor[anchor["op"]].append(record)

selected = {}
for anchor in anchors:
    anchor_op = anchor["op"]
    target = signed128(anchor["Mreg"])
    population = per_anchor[anchor_op]
    ordered = sorted(population, key=lambda row: (
        abs(int(row["mreg_signed"]) - target),
        int(row["mreg_signed"]) < target, row["op"]))
    # One representative from each structural bin, nearest first.  This
    # makes selection independent of future hardware labels.
    bins = set()
    chosen = []
    for row in ordered:
        sig = int(row["op"].split()[1], 16)
        key = (int(row["mreg_signed"]) >= target, row["pbelow"],
               row["pabove"], row["terminal_byte"], sig & 15)
        if key in bins:
            continue
        bins.add(key)
        chosen.append(row)
        if len(chosen) >= args.limit_per_anchor:
            break
    if len(chosen) < args.limit_per_anchor:
        for row in ordered:
            if row not in chosen:
                chosen.append(row)
            if len(chosen) >= args.limit_per_anchor:
                break
    for row in chosen:
        copy = dict(row)
        copy["anchor"] = anchor_op
        copy["anchor_desired"] = anchor["desired"]
        copy["mreg_delta"] = str(int(row["mreg_signed"]) - target)
        selected.setdefault(row["op"], copy)
    print("select", anchor_op, "population", len(population),
          "chosen", len(chosen), flush=True)

if not selected:
    raise RuntimeError("no adversarial operands selected")
order = sorted(selected, key=lambda operand: (
    selected[operand]["anchor"], abs(int(selected[operand]["mreg_delta"])),
    operand))
metadata = ("op", "anchor", "anchor_desired", "mreg_delta",
            "mreg_signed", "pbelow", "pabove", "terminal_byte")
columns = metadata + tuple(sorted(
    {name for row in selected.values() for name in row} - set(metadata)))
with open(args.feature_output, "w", newline="") as target:
    writer = csv.DictWriter(target, columns, delimiter="\t",
                            extrasaction="ignore")
    writer.writeheader()
    writer.writerows(selected[operand] for operand in order)
with open(args.operand_output, "w") as target:
    for operand in order:
        target.write(operand + "\n")
print("anchors", len(anchors), "cells", len(target_by_cell),
      "visible", len(visible), "matched", len(records),
      "selected", len(order))
