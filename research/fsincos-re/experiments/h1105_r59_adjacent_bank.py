#!/usr/bin/env python3
"""Build a one-capture-only adjacent-input challenge for every R59 miss.

Unlike h1097's broad randomized controls, this bank stays at exact x87
significand offsets around each miss.  Selection is hardware-label blind: an
operand must remain in the same derived R59 cell and the two absolute response
models must remain distinguishable.  Every selected operand is fresh with
respect to the supplied inventories and is assigned only the anchor's known
sensitive rounding mode.
"""

import argparse
import csv
import os
import re
import subprocess
from collections import defaultdict


CELL_FIELDS = ("branch", "theta", "ce", "s4", "side", "low3", "dist",
               "rsh", "b1", "b2")


def model(binary, mode, operands, dump=False):
    args = [binary, "--batch", "--fcos-standalone"]
    if mode != "rn":
        args.insert(2, "--rc=" + mode)
    if dump:
        args.append("--dump-internals")
    process = subprocess.run(args, input="\n".join(operands) + "\n",
                             capture_output=True, text=True, check=True)
    values = []
    for line in process.stdout.splitlines():
        fields = line.split()
        if len(fields) >= 3 and fields[0] == "OK":
            values.append(fields[1].lower() + ":" + fields[2].lower())
    if len(values) != len(operands):
        raise RuntimeError("output count mismatch for " + binary)
    return values, process.stderr


def tokens(line):
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
            current.update(tokens(line))
        elif current is not None and line.startswith("DI_BR "):
            current["branch"] = line.split()[1].split("=", 1)[1]
            current.update({"br_" + key: value
                            for key, value in tokens(line).items()
                            if key != "br"})
    if current is not None:
        records.append(current)
    return records


def signed128(text):
    value = int(text, 16)
    return value - (1 << 128) if value >> 127 else value


def add_inventory(path, known):
    with open(path) as source:
        if path.endswith(".tsv"):
            reader = csv.DictReader(source, delimiter="\t")
            if reader.fieldnames and "op" in reader.fieldnames:
                known.update(row["op"].lower() for row in reader)
                return
        source.seek(0)
        for line in source:
            fields = line.lower().split()
            if len(fields) >= 2 and re.fullmatch(r"[0-9a-f]{4}", fields[0]) \
                    and re.fullmatch(r"[0-9a-f]{16}", fields[1]):
                known.add(fields[0] + " " + fields[1])


parser = argparse.ArgumentParser()
parser.add_argument("features")
parser.add_argument("baseline")
parser.add_argument("force_minus2")
parser.add_argument("force_plus1")
parser.add_argument("output_prefix")
parser.add_argument("--known", action="append", default=[])
parser.add_argument("--radius", type=int, default=8192)
parser.add_argument("--limit-per-anchor", type=int, default=12)
args = parser.parse_args()

outputs = [args.output_prefix + "_features.tsv"] + [
    args.output_prefix + "_" + mode + "_ops.txt"
    for mode in ("rn", "rd", "ru", "rz")
]
for path in outputs:
    if os.path.exists(path):
        raise SystemExit("refusing to overwrite " + path)

with open(args.features) as source:
    all_rows = list(csv.DictReader(source, delimiter="\t"))
anchors = [row for row in all_rows if row["label"] == "POS"]
known = {row["op"].lower() for row in all_rows}
for path in args.known:
    add_inventory(path, known)

selected = {}
offset_order = []
for magnitude in range(1, args.radius + 1):
    offset_order.extend((-magnitude, magnitude))

for number, anchor in enumerate(anchors, 1):
    se_text, sig_text = anchor["op"].split()
    anchor_sig = int(sig_text, 16)
    candidates = []
    offsets = {}
    for offset in offset_order:
        sig = anchor_sig + offset
        if not (1 << 63) <= sig < (1 << 64):
            continue
        operand = se_text + " " + ("%016x" % sig)
        if operand in known:
            continue
        candidates.append(operand)
        offsets[operand] = offset
    minus, _ = model(args.force_minus2, anchor["mode"], candidates)
    plus, _ = model(args.force_plus1, anchor["mode"], candidates)
    visible = [operand for operand, first, second in zip(
        candidates, minus, plus) if first != second]
    _, stderr = model(args.baseline, anchor["mode"], visible, dump=True)
    parsed = parse_dump(stderr)
    if len(parsed) != len(visible):
        raise RuntimeError("dump count mismatch at " + anchor["op"])
    cell = tuple(anchor[name] for name in CELL_FIELDS)
    target_m = signed128(anchor["Mreg"])
    eligible = []
    for operand, record in zip(visible, parsed):
        if record["op"] != operand:
            raise RuntimeError("dump desynchronization")
        if not all(name in record for name in CELL_FIELDS +
                   ("Mreg", "S", "B", "k", "umag")):
            continue
        if tuple(record[name] for name in CELL_FIELDS) != cell:
            continue
        record["offset"] = str(offsets[operand])
        record["mreg_delta"] = str(signed128(record["Mreg"]) - target_m)
        record["mode"] = anchor["mode"]
        record["anchor"] = anchor["op"]
        record["anchor_desired"] = anchor["desired"]
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
        eligible.append(record)

    # First take the exact closest neighbors symmetrically.  Then add rows
    # nearest in the independently changing M coordinate and new carry bins.
    chosen = []
    for record in sorted(eligible, key=lambda row: (
            abs(int(row["offset"])), int(row["offset"]) < 0,
            row["op"])):
        if record not in chosen:
            chosen.append(record)
        if len(chosen) >= min(8, args.limit_per_anchor):
            break
    carry_bins = set((row["pbelow"], row["pabove"]) for row in chosen)
    for record in sorted(eligible, key=lambda row: (
            abs(int(row["mreg_delta"])), abs(int(row["offset"])),
            row["op"])):
        carry = (record["pbelow"], record["pabove"])
        if carry in carry_bins:
            continue
        carry_bins.add(carry)
        chosen.append(record)
        if len(chosen) >= args.limit_per_anchor:
            break
    for record in eligible:
        if len(chosen) >= args.limit_per_anchor:
            break
        if record not in chosen:
            chosen.append(record)
    for record in chosen:
        selected.setdefault(record["op"], record)
        known.add(record["op"])
    print("anchor", number, "of", len(anchors), anchor["op"],
          "mode", anchor["mode"], "eligible", len(eligible),
          "chosen", len(chosen), flush=True)

if not selected:
    raise RuntimeError("no fresh adjacent operands selected")
rows = sorted(selected.values(), key=lambda row: (
    row["mode"], row["anchor"], abs(int(row["offset"])),
    int(row["offset"])))
prefix = ("mode", "op", "anchor", "anchor_desired", "offset",
          "mreg_delta", "pbelow", "pabove")
columns = prefix + tuple(sorted(
    {name for row in rows for name in row} - set(prefix)))
with open(args.output_prefix + "_features.tsv", "w", newline="") as target:
    writer = csv.DictWriter(target, columns, delimiter="\t",
                            extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
for mode in ("rn", "rd", "ru", "rz"):
    with open(args.output_prefix + "_" + mode + "_ops.txt", "w") as target:
        for row in rows:
            if row["mode"] == mode:
                target.write(row["op"] + "\n")
print("anchors", len(anchors), "selected", len(rows),
      "modes", {mode: sum(row["mode"] == mode for row in rows)
                for mode in ("rn", "rd", "ru", "rz")})
