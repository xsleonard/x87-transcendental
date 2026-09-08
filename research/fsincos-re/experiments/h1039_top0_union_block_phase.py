#!/usr/bin/env python3
"""h1039: recover the absolute carry-predict block phase from union rows.

The h1038 candidate fixes the complete h975/h1000 populations but its first
full h989 score produces both FIX and BREAK changes.  Those changes are an
ideal response set for the missing qualification.  Reconstruct terminal
propagate runs and test fixed-width absolute block-start laws instead of
adding another fitted product predicate.
"""

import csv
import subprocess
from collections import Counter, defaultdict

import h1035_top0_response_score as response_score


BASE = "/tmp/x87-r95-check"
CANDIDATE = "/tmp/x87-r96-topclosed"
DATA = "stageA/h991/h989_union_legs.tsv"


def norm(value):
    return value.lower().replace(":", " ")


def run(binary, insn, mode, operands, dump=False):
    args = [binary, "--batch", "--f%s-standalone" % insn]
    if mode != "rn":
        args.insert(2, "--rc=" + mode)
    if dump:
        args.append("--dump-internals")
    process = subprocess.run(args, input="\n".join(operands) + "\n",
                             capture_output=True, text=True, check=True)
    output = [norm(":".join(line.split()[1:3]))
              for line in process.stdout.splitlines()]
    return output, process.stderr


def terminal_features(record):
    result = response_score.reconstructed(record)
    left, right = record["left"], record["right"]
    payload = int(record.get("pay2", record["payload"]))
    scale = min(left[1], right[1], left[1] - 8 if payload else left[1])
    s_value = left[2] << (left[1] - scale)
    if payload:
        s_value += payload << (left[1] - 8 - scale)
    b_value = right[2] << (right[1] - scale)
    magnitude = s_value - b_value
    cut = magnitude.bit_length() - 67
    propagate = ~(s_value ^ b_value)
    pup = 0
    while pup < 64 and ((propagate >> (cut + pup)) & 1):
        pup += 1
    result.update(
        scale=scale, cut=cut, ce=scale + cut, pup=pup,
        pbits=sum(((propagate >> (cut - offset)) & 1) << offset
                  for offset in range(min(cut + 1, 32))),
        mbits=sum(((magnitude >> (cut - offset)) & 1) << offset
                  for offset in range(min(cut + 1, 32))),
    )
    return result


def main():
    with open(DATA) as source:
        rows = list(csv.DictReader(source, delimiter="\t"))
    groups = defaultdict(list)
    for row in rows:
        groups[(row["insn"], row["mode"])].append(row)

    changes = []
    for (insn, mode), sample in sorted(groups.items()):
        operands = [row["op"] for row in sample]
        before, _ = run(BASE, insn, mode, operands)
        after, _ = run(CANDIDATE, insn, mode, operands)
        for datum, baseline, candidate in zip(sample, before, after):
            if baseline == candidate:
                continue
            hardware = norm(datum["hw"])
            if candidate == hardware and baseline != hardware:
                label = "FIX"
            elif baseline == hardware and candidate != hardware:
                label = "BREAK"
            else:
                label = "OTHER"
            changes.append((insn, mode, datum["op"], label))

    by_operand = defaultdict(set)
    for insn, mode, operand, label in changes:
        by_operand[(insn, operand)].add(label)
    print("legs", Counter(label for _, _, _, label in changes))
    print("operand label sets", Counter(tuple(sorted(labels))
                                        for labels in by_operand.values()))

    featured = []
    for insn in ("cos", "sin"):
        chosen = sorted((operand, next(iter(labels)))
                        for (which, operand), labels in by_operand.items()
                        if which == insn and len(labels) == 1
                        and labels <= {"FIX", "BREAK"})
        if not chosen:
            continue
        operands = [operand for operand, _ in chosen]
        _, dump = run(BASE, insn, "rn", operands, dump=True)
        records = response_score.parse_dumps(dump)
        if len(records) != len(chosen):
            raise RuntimeError("dump count mismatch")
        for (operand, label), record in zip(chosen, records):
            featured.append((label, insn, operand, terminal_features(record)))

    print("featured", Counter(label for label, _, _, _ in featured))
    print("pdown", Counter((label, row["pdown"])
                            for label, _, _, row in featured))
    print("ce8", Counter((label, row["ce"] & 7)
                          for label, _, _, row in featured))
    print("cut8", Counter((label, row["cut"] & 7)
                           for label, _, _, row in featured))

    print("\nfixed block-start gates: selected FIX/BREAK/missed FIX")
    for width in range(4, 17):
        for origin in range(width):
            selected = Counter()
            missed = 0
            for label, _, _, row in featured:
                # Number of propagate columns from the block start through
                # the retained cut, with `origin` expressed in absolute ce.
                need = ((row["ce"] - origin) % width) + 1
                gate = row["pdown"] >= need
                if gate:
                    selected[label] += 1
                elif label == "FIX":
                    missed += 1
            if selected["BREAK"] <= 8 or missed <= 8:
                print(width, origin, dict(selected), "missed", missed)

    print("\nrun thresholds by ce phase")
    for phase in range(8):
        subset = [(label, row) for label, _, _, row in featured
                  if (row["ce"] & 7) == phase]
        if not subset:
            continue
        ranked = []
        for need in range(1, 33):
            score = Counter(label for label, row in subset
                            if row["pdown"] >= need)
            missed = sum(label == "FIX" and row["pdown"] < need
                         for label, row in subset)
            ranked.append((score["BREAK"], missed, need, score["FIX"]))
        print(" phase", phase, "labels", Counter(label for label, _ in subset),
              "best", sorted(ranked)[:10])

    with open("/tmp/h1039_top0_union_features.tsv", "w") as out:
        fields = ("label", "insn", "op", "sum8", "low3", "dist", "s4",
                  "side", "b1", "b2", "mreg", "pdown", "pup", "scale",
                  "cut", "ce", "pbits", "mbits")
        out.write("\t".join(fields) + "\n")
        for label, insn, operand, row in featured:
            values = dict(row, label=label, insn=insn, op=operand)
            out.write("\t".join(str(values[field]) for field in fields) + "\n")


if __name__ == "__main__":
    main()
