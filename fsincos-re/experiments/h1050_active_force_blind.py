#!/usr/bin/env python3
"""h1050: fresh wide-annulus truth for the two active carry selectors.

Run on the authorized Skylake host.  Training FIX rows supply centers only;
large deterministic significand offsets are new operands.  The absolute
force binaries prefilter operands where a one-quantum selector is observable,
then silicon labels every changed leg FIX or BREAK against the R95 baseline.
"""

import csv
import gzip
import os
import random
import subprocess
from collections import Counter, defaultdict


MODES = ("rn", "rd", "ru", "rz")
SEED = 0x1050A671
SAMPLES_PER_CENTER = 2048
MAX_CENTERS = {"top1": 72, "low1": 32}
STRATEGY = os.environ.get("H1050_STRATEGY", "wide")
BASE = "./model_r95"
FORCE = {"top1": "./model_force2", "low1": "./model_force3"}


def run(args, operands):
    process = subprocess.run(args, input="\n".join(operands) + "\n",
                             capture_output=True, text=True, check=True)
    output = []
    for line in process.stdout.splitlines():
        fields = line.split()
        output.append("%s:%s" % (fields[1].lower(), fields[2].lower()))
    if len(output) != len(operands):
        raise RuntimeError("output length mismatch for %r" % (args,))
    return output


def model(binary, insn, mode, operands):
    args = [binary, "--batch", "--f%s-standalone" % insn]
    if mode != "rn":
        args.insert(2, "--rc=" + mode)
    return run(args, operands)


def centers(family):
    with open("h1042_%s_union.tsv" % family) as source:
        rows = [row for row in csv.DictReader(source, delimiter="\t")
                if row["label"] == "FIX"]
    # One center per already-observed structural/phase cell maximizes new
    # coverage without weighting the capture toward dense old neighborhoods.
    chosen = {}
    for row in rows:
        qpost = int(row["qpost"])
        qf4 = int(row["qf4"])
        key = (row["sum8"], row["s4"], row["side"], row["dist"],
               row["low3"], row["b1"], row["b2"], row["pdown"],
               (qpost >> 55) & 15, (qf4 >> 41) & 1)
        chosen.setdefault(key, (row["insn"], row["op"]))
    ordered = [chosen[key] for key in sorted(chosen)]
    return ordered[:MAX_CENTERS[family]]


generator = random.Random(SEED)
points = defaultdict(dict)
center_counts = {}
known = set()
if os.path.exists("h989_union_legs.tsv"):
    with open("h989_union_legs.tsv") as source:
        known.update((row["insn"], row["op"])
                     for row in csv.DictReader(source, delimiter="\t"))
if os.path.exists("h1000_sensitive_neighborhoods.tsv.gz"):
    with gzip.open("h1000_sensitive_neighborhoods.tsv.gz", "rt") as source:
        known.update(("cos", row["op"])
                     for row in csv.DictReader(source, delimiter="\t"))
for family in ("top1", "low1"):
    selected_centers = centers(family)
    center_counts[family] = len(selected_centers)
    for center_index, (insn, operand) in enumerate(selected_centers):
        se_text, sig_text = operand.split()
        center = int(sig_text, 16)
        if STRATEGY == "annulus":
            deltas = list(range(-8192, -4096)) \
                + list(range(4097, 8193))
        elif STRATEGY == "micro":
            deltas = list(range(-4096, 0)) + list(range(1, 4097))
        elif STRATEGY == "wide":
            deltas = [generator.randrange(-(1 << 40), 1 << 40)
                      for _ in range(SAMPLES_PER_CENTER)]
        else:
            raise ValueError("unknown strategy %r" % STRATEGY)
        for delta in deltas:
            if STRATEGY == "wide" and -8192 <= delta <= 8192:
                continue
            significand = center + delta
            if not (1 << 63) <= significand < (1 << 64):
                continue
            neighbor = "%s %016x" % (se_text, significand)
            if (insn, neighbor) in known:
                continue
            points[family, insn].setdefault(
                neighbor, (center_index, delta))

truth = []
for family in ("top1", "low1"):
    for insn in ("cos", "sin"):
        operands = sorted(points[family, insn])
        if not operands:
            continue
        changed = {}
        for mode in MODES:
            before = model(BASE, insn, mode, operands)
            after = model(FORCE[family], insn, mode, operands)
            for index, operand in enumerate(operands):
                if before[index] != after[index]:
                    changed.setdefault(operand, {})[mode] = (
                        before[index], after[index])
        selected = sorted(changed)
        hardware = {mode: run(
            ["/root/x87_capture_x86_64", mode, insn], selected)
            for mode in MODES}
        for index, operand in enumerate(selected):
            center_index, delta = points[family, insn][operand]
            for mode, (before, after) in changed[operand].items():
                actual = hardware[mode][index]
                if after == actual and before != actual:
                    outcome = "FIX"
                elif before == actual and after != actual:
                    outcome = "BREAK"
                else:
                    outcome = "OTHER"
                truth.append((outcome, family, insn, mode,
                              str(center_index), str(delta), operand,
                              actual, before, after))
        print(family, insn, "generated", len(operands),
              "selected", len(selected), flush=True)

with open("h1050_active_force_%s.tsv" % STRATEGY, "w") as out:
    out.write("outcome\tfamily\tinsn\tmode\tcenter\tdelta\top\t"
              "hw\tbase\tforce\n")
    for row in truth:
        out.write("\t".join(row) + "\n")

print("strategy", STRATEGY, "centers", center_counts,
      "changed legs", len(truth),
      dict(Counter(row[0] for row in truth)),
      "by family", dict(Counter((row[1], row[0]) for row in truth)))
