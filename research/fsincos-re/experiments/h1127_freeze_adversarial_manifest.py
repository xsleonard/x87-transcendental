#!/usr/bin/env python3
"""Freeze h1126's model-only candidates into a nonredundant manifest.

FCOS is positive throughout this residual domain, so round-down and
round-toward-zero are architecturally identical.  h1126 confirms this by
producing byte-identical RD/RZ operand lists.  This pass drops RZ, labels the
actual cell relationship to each residual anchor, and emits a one-row-per-
(mode, operand) manifest.  It performs no model evaluation and no capture.
"""

import argparse
import csv
import hashlib
import os
from collections import Counter


CORE_FIELDS = ("branch", "theta", "ce", "s4", "side", "low3",
               "dist", "rsh")
STRICT_FIELDS = CORE_FIELDS + ("b1", "b2")
MODES = ("rn", "rd", "ru")
UPSTREAM_ANCHORS = {
    "3ffc ffffff80075216a0",
    "3ffc be6000000688f849",
    "3ffc fb900000030c1fc9",
}


def same_fields(left, right, fields):
    return all(left.get(name) == right.get(name) for name in fields)


def digest(path):
    value = hashlib.sha256()
    with open(path, "rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("candidates")
    parser.add_argument("anchors")
    parser.add_argument("output_prefix")
    args = parser.parse_args()
    outputs = [args.output_prefix + "_features.tsv",
               args.output_prefix + "_manifest.tsv"] + [
        args.output_prefix + "_" + mode + "_ops.txt" for mode in MODES]
    for path in outputs:
        if os.path.exists(path):
            raise SystemExit("refusing to overwrite " + path)

    with open(args.anchors) as source:
        anchors = {row["op"]: row for row in
                   csv.DictReader(source, delimiter="\t")
                   if row["label"] == "POS"}
    with open(args.candidates) as source:
        input_rows = list(csv.DictReader(source, delimiter="\t"))
        input_columns = tuple(input_rows[0])

    selected = {}
    for source_row in input_rows:
        if source_row["mode"] not in MODES:
            continue
        row = dict(source_row)
        anchor = anchors[row["anchor"]]
        if same_fields(row, anchor, STRICT_FIELDS):
            relation = "strict"
            tier = "same-cell-netlist"
        elif same_fields(row, anchor, CORE_FIELDS):
            relation = "core"
            tier = "discrete-sibling"
        else:
            relation = "neighbor"
            tier = "support-boundary"
        selection = set(row["selection"].split(","))
        if "same_cell_far_netlist" in selection:
            selection.remove("same_cell_far_netlist")
            selection.add({
                "strict": "same_strict_cell_far_netlist",
                "core": "same_core_cell_far_netlist",
                "neighbor": "near_cell_far_netlist",
            }[relation])
        row["selection"] = ",".join(sorted(selection))
        row["cell_relation"] = relation
        row["challenge_tier"] = tier
        row["upstream_anchor"] = str(int(row["anchor"] in UPSTREAM_ANCHORS))
        key = (row["mode"], row["op"])
        if key in selected:
            raise AssertionError("duplicate mode/operand in candidates")
        selected[key] = row

    rows = [selected[key] for key in sorted(selected)]
    if {row["anchor"] for row in rows} != set(anchors):
        missing = sorted(set(anchors) - {row["anchor"] for row in rows})
        raise AssertionError("anchors lost during freeze: " + ",".join(missing))
    prefix = ("mode", "op", "anchor", "anchor_mode", "anchor_desired",
              "challenge_tier", "cell_relation", "upstream_anchor",
              "selection")
    columns = prefix + tuple(name for name in input_columns
                             if name not in prefix)
    feature_path = args.output_prefix + "_features.tsv"
    with open(feature_path, "w", newline="") as target:
        writer = csv.DictWriter(target, columns, delimiter="\t",
                                extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    manifest_path = args.output_prefix + "_manifest.tsv"
    manifest_columns = ("insn", "mode", "op", "anchor",
                        "challenge_tier", "cell_relation", "selection")
    with open(manifest_path, "w", newline="") as target:
        writer = csv.DictWriter(target, manifest_columns, delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow({
                "insn": "cos", "mode": row["mode"], "op": row["op"],
                "anchor": row["anchor"],
                "challenge_tier": row["challenge_tier"],
                "cell_relation": row["cell_relation"],
                "selection": row["selection"],
            })
    for mode in MODES:
        with open(args.output_prefix + "_" + mode + "_ops.txt", "w") as target:
            for row in rows:
                if row["mode"] == mode:
                    target.write(row["op"] + "\n")

    print("rows", len(rows), "unique_operands",
          len({row["op"] for row in rows}), "anchors",
          len({row["anchor"] for row in rows}))
    print("modes", dict(Counter(row["mode"] for row in rows)))
    print("tiers", dict(Counter(row["challenge_tier"] for row in rows)))
    print("relations", dict(Counter(row["cell_relation"] for row in rows)))
    print("upstream_rows", sum(row["upstream_anchor"] == "1" for row in rows))
    for path in outputs:
        print(os.path.basename(path), digest(path))


if __name__ == "__main__":
    main()
