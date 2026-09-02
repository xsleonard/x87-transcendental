#!/usr/bin/env python3
"""h1031: does exact lower-array state determine the missing carry bit?

h1030 establishes that the remaining integer decision is equivalent to a
single speculative carry bit: the exact carry into the retained cut is zero
on TOP and one on LOW, while a miss substitutes P[cut].  Before fitting an
arithmetic expression, test whether the four exact lower-product states from
h1028 contain that predictor deterministically and transfer FIT to HOL.
"""

import contextlib
import csv
import io
from collections import Counter, defaultdict


# Reuse the already-verified staged radix-8 reconstruction.  Its module has a
# reporting main body, so suppress that output; all assertions still execute.
with contextlib.redirect_stdout(io.StringIO()):
    import h1028_lower_wire_response as lower


def load_tsv(path):
    with open(path) as source:
        return list(csv.DictReader(source, delimiter="\t"))


feature_rows = load_tsv("h970_features.tsv")
integer_rows = load_tsv("h975_nhw.tsv")
features = {(row["insn"], row["op"]): row for row in feature_rows}

rows = []
for integer in integer_rows:
    feature = features[integer["insn"], integer["op"]]
    values = {
        "mag": int(feature["magsig"], 16),
        "mul": int(feature["mulsig"], 16),
        "lf": int(feature["lfsig"], 16),
        "f4": int(feature["f4sig"], 16),
        "rf": int(feature["rfsig"], 16),
    }
    states = lower.product_states(values)
    pay2 = int(feature["pay2"]) if feature["pay2"] != "-" else 0
    nset = {int(value) for value in integer["nset"].split(",")}
    sum8 = int(integer["sum8"])
    line = "TOP" if sum8 >= 128 else "LOW"
    pcut = lower.terminal_frame(feature)
    state_tuple = tuple(states[name] for name in lower.PRODUCTS)
    rows.append({
        "line": line, "act": int(integer["act"]),
        "half": feature["half"], "nset": nset,
        "pinned": integer["pinned"] == "1",
        "n": int(integer["nset"]) if integer["pinned"] == "1" else None,
        "state": state_tuple, "sqstate": states["sq"],
        "f4state": states["f4"], "leftstate": states["left"],
        "rightstate": states["right"], "pcut": pcut,
        "ce8": (int(feature["lefte2"]) + 67) & 7,
        "sum8": sum8, "low3": int(feature["low3"]),
        "dist": int(feature["dist"]), "rsh": int(feature["rsh"]),
        "rud": int(feature["rud"]), "payload": pay2,
        "d": int(feature["d"]), "me2": int(feature["me2"]),
        "g": int(feature["g"]), "s4":
            (values["mul"] * values["mul"]).bit_length() - 67,
    })


families = (
    ("top0", "TOP", 0, -1),
    ("top1", "TOP", 1, -1),
    ("low1", "LOW", 1, 1),
)


def transfer(sample, target, fields):
    fit_cells = defaultdict(Counter)
    for row in sample:
        if row["half"] != "FIT":
            continue
        positive = row["pinned"] and row["n"] == target
        negative = target not in row["nset"]
        if positive == negative:
            continue
        state = tuple(row[field] for field in fields)
        fit_cells[state][positive] += 1

    # Select only cells with FIT positives and no FIT counterexample.  Then
    # apply that unchanged selection to HOL and every admissibility row.
    selected = {state for state, labels in fit_cells.items()
                if labels[True] and not labels[False]}
    fired = [row for row in sample
             if tuple(row[field] for field in fields) in selected]
    counts = Counter()
    for row in fired:
        counts["bad"] += target not in row["nset"]
        counts["fires"] += 1
        counts[row["half"] + "_positive"] += (
            row["pinned"] and row["n"] == target)
        counts[row["half"] + "_negative"] += target not in row["nset"]
    return len(fit_cells), len(selected), counts


specs = (
    ("state",),
    ("state", "ce8"),
    ("state", "sum8"),
    ("state", "low3"),
    ("state", "s4"),
    ("state", "ce8", "s4"),
    ("state", "sum8", "s4"),
    ("state", "sum8", "low3"),
    ("state", "dist", "low3"),
    ("state", "sum8", "dist", "low3"),
    ("state", "sum8", "d", "me2", "g"),
    ("state", "sum8", "d", "me2", "g", "low3"),
    ("state", "sum8", "d", "me2", "g", "low3", "payload"),
)


print("rows", len(rows), "lower-state support",
      len({row["state"] for row in rows}))
for family, line, act, target in families:
    sample = [row for row in rows
              if row["line"] == line and row["act"] == act
              and row["pcut"] == (1 if line == "TOP" else 0)]
    print("\n%s candidate rows=%d pinned=%s" % (
        family, len(sample), dict(Counter(
            row["n"] for row in sample if row["pinned"]))))
    for fields in specs:
        cells, selected, counts = transfer(sample, target, fields)
        print("  %-58s cells=%4d selected=%3d fires=%4d bad=%4d "
              "FIT +/−=%3d/%3d HOL +/−=%3d/%3d" % (
                  ",".join(fields), cells, selected, counts["fires"],
                  counts["bad"], counts["FIT_positive"],
                  counts["FIT_negative"], counts["HOL_positive"],
                  counts["HOL_negative"]))

    print("  target lower-state tuples:")
    targets = Counter(row["state"] for row in sample
                      if row["pinned"] and row["n"] == target)
    negatives = Counter(row["state"] for row in sample
                        if target not in row["nset"])
    for state, count in targets.most_common(20):
        print("    %s target=%d contradictions=%d" %
              (state, count, negatives[state]))
