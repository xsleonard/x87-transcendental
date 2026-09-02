#!/usr/bin/env python3
"""h1055: frozen combined-selector blind on fresh Skylake operands.

The candidate was frozen before this generator was written.  Union operands
where the combined closed form is visible provide centers only.  The default
bank is the never-before-used 8193..12288 significand annulus; ``wide`` uses
a new deterministic seed and offsets outside every earlier micro-annulus.
Only candidate-vs-R95 differences are sent to hardware, but every selected
operand is captured in all four rounding modes.
"""

import csv
import gzip
import os
import random
import subprocess
from collections import Counter


MODES = ("rn", "rd", "ru", "rz")
INNER = int(os.environ.get("H1055_INNER", "8192"))
OUTER = int(os.environ.get("H1055_OUTER", "12288"))
CHUNK = 100000
BASE = "./model_r95"
CANDIDATE = "./model_r96_allclosed"
STRATEGY = os.environ.get("H1055_STRATEGY", "annulus")
TAG = os.environ.get("H1055_TAG", STRATEGY)
WIDE_SAMPLES = int(os.environ.get("H1055_WIDE_SAMPLES", "4096"))
WIDE_SEED = int(os.environ.get("H1055_WIDE_SEED", "0x1055C105ED"), 0)


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


with open("h989_union_legs.tsv") as source:
    union_rows = list(csv.DictReader(source, delimiter="\t"))
union_ops = sorted({(row["insn"], row["op"]) for row in union_rows})
known = set(union_ops)
if os.path.exists("h1000_sensitive_neighborhoods.tsv.gz"):
    with gzip.open("h1000_sensitive_neighborhoods.tsv.gz", "rt") as source:
        known.update(("cos", row["op"])
                     for row in csv.DictReader(source, delimiter="\t"))
for path in (
        "h1050_active_force_blind.tsv",
        "h1050_active_force_annulus.tsv",
        "h1050_active_force_micro.tsv"):
    if os.path.exists(path):
        with open(path) as source:
            known.update((row["insn"], row["op"])
                         for row in csv.DictReader(source, delimiter="\t"))

centers = []
for insn in ("cos", "sin"):
    operands = [op for row_insn, op in union_ops if row_insn == insn]
    changed = [False] * len(operands)
    for mode in MODES:
        before = model(BASE, insn, mode, operands)
        after = model(CANDIDATE, insn, mode, operands)
        for index, (old, new) in enumerate(zip(before, after)):
            changed[index] |= old != new
    centers.extend((insn, op) for op, differs in zip(operands, changed)
                   if differs)

points = {"cos": {}, "sin": {}}
generator = random.Random(WIDE_SEED)
for center_index, (insn, operand) in enumerate(centers):
    se_text, sig_text = operand.split()
    center = int(sig_text, 16)
    if STRATEGY == "annulus":
        deltas = list(range(-OUTER, -INNER)) \
            + list(range(INNER + 1, OUTER + 1))
    elif STRATEGY == "wide":
        deltas = [generator.randrange(-(1 << 44), 1 << 44)
                  for _ in range(WIDE_SAMPLES)]
    else:
        raise ValueError("unknown H1055_STRATEGY %r" % STRATEGY)
    for delta in deltas:
        if -INNER <= delta <= INNER:
            continue
        significand = center + delta
        if not (1 << 63) <= significand < (1 << 64):
            continue
        neighbor = "%s %016x" % (se_text, significand)
        if (insn, neighbor) in known:
            continue
        points[insn].setdefault(neighbor, (center_index, delta))

selected = {}
for insn in ("cos", "sin"):
    operands = sorted(points[insn])
    for start in range(0, len(operands), CHUNK):
        chunk = operands[start:start + CHUNK]
        outputs = {}
        for mode in MODES:
            outputs[mode] = (model(BASE, insn, mode, chunk),
                             model(CANDIDATE, insn, mode, chunk))
        for index, operand in enumerate(chunk):
            if any(outputs[mode][0][index] != outputs[mode][1][index]
                   for mode in MODES):
                selected[(insn, operand)] = {
                    mode: (outputs[mode][0][index],
                           outputs[mode][1][index]) for mode in MODES}
        print("filter", insn, start + len(chunk), "of", len(operands),
              "selected", len(selected), flush=True)

totals = Counter()
rows = []
for insn in ("cos", "sin"):
    keys = sorted(key for key in selected if key[0] == insn)
    operands = [key[1] for key in keys]
    hardware = {
        mode: run(["/root/x87_capture_x86_64", mode, insn], operands)
        for mode in MODES
    }
    for index, key in enumerate(keys):
        center_index, delta = points[insn][key[1]]
        for mode in MODES:
            before, after = selected[key][mode]
            if before == after:
                continue
            actual = hardware[mode][index]
            if after == actual and before != actual:
                outcome = "FIX"
            elif before == actual and after != actual:
                outcome = "BREAK"
            else:
                outcome = "OTHER"
            totals[outcome] += 1
            rows.append((outcome, insn, mode, str(center_index), str(delta),
                         key[1], actual, before, after))

output_path = "h1055_allclosed_%s.tsv" % TAG
with open(output_path, "w") as out:
    out.write("outcome\tinsn\tmode\tcenter\tdelta\top\thw\tbase\tcandidate\n")
    for row in rows:
        out.write("\t".join(row) + "\n")

print("strategy", STRATEGY, "tag", TAG, "inner", INNER, "outer", OUTER,
      "centers", len(centers),
      "generated", sum(map(len, points.values())),
      "selected operands", len(selected),
      "changed legs", len(rows), dict(totals))
