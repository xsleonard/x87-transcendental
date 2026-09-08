#!/usr/bin/env python3
"""Score frozen QX-run separators after their one-shot hardware capture."""

import argparse
import csv
import hashlib
from collections import Counter
from pathlib import Path


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def rows(path):
    with path.open(newline="") as source:
        return list(csv.DictReader(source, delimiter="\t"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("hardware", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("refusing to overwrite " + str(args.output))
    manifest = rows(args.manifest)
    labels = {(row["mode"], row["op"]): row["hardware"].lower()
              for row in rows(args.hardware)}
    if len(labels) != len(manifest):
        raise RuntimeError("hardware/manifest count mismatch")
    counts = Counter()
    scored = []
    for row in manifest:
        key = row["mode"], row["op"]
        if key not in labels:
            raise RuntimeError("missing hardware label for " + str(key))
        hardware = labels[key]
        current = row["current"].lower()
        candidate = row["candidate"].lower()
        if hardware not in (current, candidate):
            verdict = "other"
        elif hardware == current:
            verdict = "current"
        else:
            verdict = "candidate"
        counts[verdict] += 1
        scored.append({**row, "hardware": hardware, "verdict": verdict})
    fields = tuple(scored[0])
    with args.output.open("x", newline="") as target:
        target.write("manifest_sha256\t" + digest(args.manifest) + "\n")
        target.write("hardware_sha256\t" + digest(args.hardware) + "\n")
        target.write("capture_policy\tone_observation_per_fresh_mode_operand_pair\n")
        for name in ("current", "candidate", "other"):
            target.write(f"{name}\t{counts[name]}\n")
        target.write("\n")
        writer = csv.DictWriter(target, fields, delimiter="\t")
        writer.writeheader()
        writer.writerows(scored)
    print("rows", len(scored), "current", counts["current"],
          "candidate", counts["candidate"], "other", counts["other"])


if __name__ == "__main__":
    main()
