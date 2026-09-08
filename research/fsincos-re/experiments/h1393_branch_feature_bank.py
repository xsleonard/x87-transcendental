#!/usr/bin/env python3
"""Extract fixed R59 branch scopes without changing feature labels."""

import argparse
import csv
import os


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input")
    parser.add_argument("output")
    parser.add_argument("--branch", action="append", required=True)
    args = parser.parse_args()
    if os.path.exists(args.output):
        raise SystemExit("refusing to overwrite " + args.output)
    with open(args.input) as source:
        reader = csv.DictReader(source, delimiter="\t")
        fields = reader.fieldnames
        rows = list(reader)
    if fields is None:
        raise RuntimeError("input has no header")
    selected = [row for row in rows if row["branch"] in args.branch]
    with open(args.output, "w", newline="") as target:
        writer = csv.DictWriter(target, fields, delimiter="\t")
        writer.writeheader()
        writer.writerows(selected)
    print("rows", len(selected), "positive",
          sum(row["label"] == "POS" for row in selected),
          "branches", ",".join(args.branch))


if __name__ == "__main__":
    main()
