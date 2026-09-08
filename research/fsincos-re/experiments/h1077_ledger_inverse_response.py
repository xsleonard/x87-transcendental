#!/usr/bin/env python3
"""Classify the current captured ledger by terminal endpoint response.

The hardware values are read from the already-banked probe-key file.  No
hardware capture is performed.  The baseline must have G_ROUND84=0, and the
ten response binaries must additionally set G_R96FORCE=1..10.  A force match
means that the residual is representable by one of the terminal selector's
existing neighboring endpoints; no match localizes it upstream (or outside
the ten exposed endpoint alternatives).
"""

import argparse
import csv
import subprocess
from collections import Counter, defaultdict


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


def read_keys(path):
    rows = []
    with open(path) as source:
        for fields in csv.reader(source, delimiter="\t"):
            if not fields:
                continue
            if len(fields) != 6:
                raise ValueError("expected six fields: %r" % (fields,))
            insn, mode, se, sig, hw_se, hw_sig = fields
            if mode not in MODES:
                raise ValueError("bad rounding mode %r" % mode)
            rows.append({
                "insn": insn, "mode": mode, "se": se.lower(),
                "sig": sig.lower(), "op": "%s %s" % (se, sig),
                "hw": "%s:%s" % (hw_se.lower(), hw_sig.lower()),
            })
    return rows


parser = argparse.ArgumentParser()
parser.add_argument("keys")
parser.add_argument("baseline")
parser.add_argument("force_pattern",
                    help="printf pattern for force number, for example model_force%%d")
parser.add_argument("--forces", type=int, default=10)
parser.add_argument("--out")
args = parser.parse_args()

rows = read_keys(args.keys)
groups = defaultdict(list)
for index, row in enumerate(rows):
    groups[row["insn"], row["mode"]].append((index, row))

binaries = [(0, args.baseline)] + [
    (force, args.force_pattern % force)
    for force in range(1, args.forces + 1)]
for force, binary in binaries:
    for (insn, mode), indexed in groups.items():
        outputs = run_model(binary, insn, mode,
                            [row["op"] for _, row in indexed])
        for (index, _), output in zip(indexed, outputs):
            rows[index]["f%d" % force] = output

summary = Counter()
for row in rows:
    matches = [force for force in range(1, args.forces + 1)
               if row["f%d" % force] == row["hw"]]
    changed = [force for force in range(1, args.forces + 1)
               if row["f%d" % force] != row["f0"]]
    distinct = defaultdict(list)
    for force in range(0, args.forces + 1):
        distinct[row["f%d" % force]].append(force)
    row["matches"] = ",".join(map(str, matches)) or "-"
    row["changed"] = ",".join(map(str, changed)) or "-"
    row["responses"] = ";".join(
        "%s=%s" % (",".join(map(str, forces)), output)
        for output, forces in distinct.items())
    if row["f0"] == row["hw"]:
        summary["baseline_exact"] += 1
    elif matches:
        summary["force_representable"] += 1
    else:
        summary["no_force_match"] += 1

columns = ("insn", "mode", "se", "sig", "hw", "f0", "matches",
           "changed", "responses")
if args.out:
    with open(args.out, "w", newline="") as target:
        writer = csv.DictWriter(target, columns, delimiter="\t",
                                extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

print("rows", len(rows), dict(summary))
for row in rows:
    print("%(insn)s %(mode)s %(se)s %(sig)s hw=%(hw)s base=%(f0)s "
          "match=%(matches)s changed=%(changed)s" % row)
    print("  " + row["responses"])
