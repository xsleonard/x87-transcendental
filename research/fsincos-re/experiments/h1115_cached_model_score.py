#!/usr/bin/env python3
"""Score one model against cached hardware rows without new captures."""

import argparse
import csv
import os
import subprocess
from collections import Counter, defaultdict


def run(binary, instruction, mode, operands):
    operation = ("--fcos-standalone" if instruction in ("cos", "fcos")
                 else "--fsin-standalone")
    command = [binary, "--batch", operation]
    if mode != "rn":
        command.insert(2, "--rc=" + mode)
    process = subprocess.run(command, input="\n".join(operands) + "\n",
                             capture_output=True, text=True, check=True)
    outputs = []
    for line in process.stdout.splitlines():
        fields = line.split()
        if len(fields) >= 3 and fields[0] == "OK":
            outputs.append(fields[1].lower() + ":" + fields[2].lower())
    if len(outputs) != len(operands):
        raise RuntimeError("output count mismatch for %s/%s" %
                           (instruction, mode))
    return outputs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("bank")
    parser.add_argument("model")
    parser.add_argument("output")
    args = parser.parse_args()
    if os.path.exists(args.output):
        raise SystemExit("refusing to overwrite " + args.output)

    with open(args.bank) as source:
        rows = list(csv.DictReader(source, delimiter="\t"))
    groups = defaultdict(list)
    for index, row in enumerate(rows):
        instruction = row.get("insn", "cos")
        groups[(instruction, row["mode"])].append((index, row))
    for (instruction, mode), indexed in groups.items():
        operands = [row["op"] for _, row in indexed]
        for start in range(0, len(operands), 4000):
            chunk = indexed[start:start + 4000]
            outputs = run(args.model, instruction, mode,
                          [row["op"] for _, row in chunk])
            for (index, _), output in zip(chunk, outputs):
                rows[index]["candidate"] = output
                rows[index]["candidate_match"] = int(
                    output == rows[index]["hw"].lower())

    columns = tuple(rows[0]) + ("candidate", "candidate_match")
    with open(args.output, "w", newline="") as target:
        writer = csv.DictWriter(target, columns, delimiter="\t",
                                extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    counts = Counter()
    operands = defaultdict(list)
    for row in rows:
        match = bool(row["candidate_match"])
        counts["match" if match else "miss"] += 1
        operands[row["op"]].append(match)
    exact_operands = sum(all(matches) for matches in operands.values())
    print("rows", len(rows), "operands", len(operands),
          "match", counts["match"], "miss", counts["miss"],
          "allmode_exact_operands", exact_operands)
    for row in rows:
        if not row["candidate_match"]:
            print("MISS", row.get("insn", "cos"), row["mode"], row["op"],
                  "hw=" + row["hw"], "candidate=" + row["candidate"])


if __name__ == "__main__":
    main()
