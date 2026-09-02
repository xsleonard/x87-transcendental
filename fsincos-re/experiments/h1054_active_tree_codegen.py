#!/usr/bin/env python3
"""h1054: generate table-free C logic for the active endpoint selectors."""

from collections import Counter
import math

import h1047_active_selector_tree as tree
import h1051_active_blind_score as blind


ONE = 1 << 66
BANKS = (
    "/tmp/h1050_active_force_blind.tsv",
    "/tmp/h1050_active_force_annulus.tsv",
    "/tmp/h1050_active_force_micro.tsv",
)
FIELDS = ("mi", "low3", "b1", "b2", "lp", "d7", "s4", "side",
          "retained", "qpost11")


def load(family):
    rows = blind.load_training(family)
    for path in BANKS:
        rows.extend(blind.blind_rows(family, path))
    result = []
    for row in rows:
        row["mi"] = row["mreg"] // ONE
        row["lp"] = row["low3"] & 1
        row["d7"] = row["dist"] - 7
        row["retained"] = row["sum8"] - row["low3"]
        row["qpost11"] = row["qpost"] >> 55
        if row["pcut"] != (1 if family == "top1" else 0):
            continue
        if family == "top1" and row["qpost11"] < 2024:
            continue
        if family == "low1" and row["qpost11"] > 27:
            continue
        result.append(row)
    return result


def c_value(field, threshold):
    # Every training feature is integer, so half-integer CART cuts become an
    # inclusive integer comparison without floating point in the model.
    # floor is significant for the M-coordinate's negative half-integer
    # splits; int() would truncate -0.5 to zero and widen a positive leaf.
    return math.floor(threshold)


def emit_c(node, indent="        "):
    if node[0] == "leaf":
        labels = node[1]
        if len(labels) != 1:
            raise AssertionError(labels)
        return indent + ("fire96 = 1;\n" if "FIX" in labels else "")
    _, field, threshold, left, right = node
    value = c_value(field, threshold)
    output = indent + f"if ({field}96 <= {value}) {{\n"
    output += emit_c(left, indent + "    ")
    output += indent + "} else {\n"
    output += emit_c(right, indent + "    ")
    output += indent + "}\n"
    return output


def positive_ranges(node, bounds=None):
    bounds = dict(bounds or {})
    if node[0] == "leaf":
        return [bounds] if "FIX" in node[1] else []
    _, field, threshold, left, right = node
    edge = c_value(field, threshold)
    left_bounds = dict(bounds)
    lo, hi = left_bounds.get(field, (None, None))
    left_bounds[field] = lo, edge if hi is None else min(hi, edge)
    right_bounds = dict(bounds)
    lo, hi = right_bounds.get(field, (None, None))
    right_bounds[field] = (edge + 1 if lo is None else max(lo, edge + 1)), hi
    return (positive_ranges(left, left_bounds)
            + positive_ranges(right, right_bounds))


def emit_dnf(node, indent="        "):
    rendered = []
    for bounds in positive_ranges(node):
        terms = []
        for field in FIELDS:
            if field not in bounds:
                continue
            lower, upper = bounds[field]
            if lower is not None:
                terms.append(f"{field}96 >= {lower}")
            if upper is not None:
                terms.append(f"{field}96 <= {upper}")
        rendered.append(" && ".join(terms) if terms else "1")
    lines = [indent + "fire96 ="]
    for index, expression in enumerate(rendered):
        prefix = "    " if index == 0 else " || "
        lines.append(indent + prefix + "(" + expression + ")")
    lines[-1] += ";"
    return "\n".join(lines) + "\n"


def predict(node, row):
    while node[0] != "leaf":
        node = node[3] if row[node[1]] <= node[2] else node[4]
    return "FIX" in node[1]


def main():
    for family in ("top1", "low1"):
        rows = load(family)
        selector = tree.build(rows, FIELDS, 0, 32)
        mistakes = [row for row in rows
                    if predict(selector, row) != (row["label"] == "FIX")]
        print("/*", family, "rows", len(rows),
              dict(Counter(row["label"] for row in rows)),
              "leaves/depth/mixed/errors", tree.stats(selector),
              "mistakes", len(mistakes), "*/")
        print(emit_dnf(selector))


if __name__ == "__main__":
    main()
