#!/usr/bin/env python3
"""h1057: emit the pcut-complete active selector comparison trees."""

import csv
from collections import Counter

import h1047_active_selector_tree as tree
import h1051_active_blind_score as blind
import h1054_active_tree_codegen as emit


ONE = 1 << 66
FIELDS = ("mi", "low3", "b1", "b2", "lp", "d7", "s4", "side",
          "qpost11", "pcut")
# The shared DNF emitter iterates its module-level field order.
emit.FIELDS = FIELDS
BANKS = (
    "/tmp/h1050_active_force_blind.tsv",
    "/tmp/h1050_active_force_annulus.tsv",
    "/tmp/h1050_active_force_micro.tsv",
)


def read_rows(path):
    with open(path) as source:
        rows = list(csv.DictReader(source, delimiter="\t"))
    for row in rows:
        for field in row.keys() - {"label", "insn", "op"}:
            row[field] = int(row[field])
    return rows


def support(family, row):
    d, low, q = row["dist"], row["low3"], row["qpost11"]
    if family == "top1":
        return (
            (d == 9 and low == 1 and q == 2036)
            or (d == 10 and (
                (low == 1 and q in (2042, 2044, 2046))
                or (low == 2 and q in (2040, 2042, 2044, 2046))
                or (low == 6 and q in (2028, 2030, 2034, 2036))
                or (low == 7 and q in (2026, 2032))))
            or (d == 11 and (
                (low == 1 and q in (2046, 2047))
                or (low == 2 and 2044 <= q <= 2047)
                or (low == 3 and 2042 <= q <= 2047)
                or (low == 4 and q == 2045)
                or (low == 6 and q in (2042, 2044, 2046, 2047))))
            or (d == 12 and (
                (low == 1 and q == 2047)
                or (low in (2, 3) and q >= 2046)
                or (low == 4 and q >= 2045)
                or (low == 5 and q >= 2046)
                or (low == 7 and q >= 2045)))
            or (d == 13 and (
                (low in (1, 2, 3) and q == 2047)
                or (low in (4, 5, 7) and q >= 2046)
                or (low == 6 and q == 2046)))
            or (d == 14 and (
                (low in (2, 4) and q == 2047)
                or (low == 7 and q == 2046)))
            or (d == 15 and low in (2, 6) and q == 2047))
    return (
        (d == 9 and (
            (low == 5 and q == 20)
            or (low in (6, 7) and q in (20, 24))))
        or (d == 10 and (
            (low == 5 and q == 18)
            or (low == 6 and q == 22)
            or (low == 7 and q == 20)))
        or (d == 11 and (
            (low == 6 and q in (17, 19))
            or (low == 7 and q in (21, 22)))))


def load(family):
    paths = (("/tmp/h1042_top1_union.tsv", "/tmp/h1056_top1_p0.tsv")
             if family == "top1" else
             ("/tmp/h1042_low1_union.tsv", "/tmp/h1056_low1_p1.tsv"))
    rows = []
    for path in paths:
        rows.extend(read_rows(path))
    for path in BANKS:
        rows.extend(blind.blind_rows(family, path))
    unique = {}
    for row in rows:
        row["mi"] = row["mreg"] // ONE
        row["lp"] = row["low3"] & 1
        row["d7"] = row["dist"] - 7
        row["qpost11"] = row["qpost"] >> 55
        key = row["insn"], row["op"]
        if key in unique and unique[key]["label"] != row["label"]:
            raise AssertionError((family, key, unique[key]["label"],
                                  row["label"]))
        unique[key] = row
    return list(unique.values())


for family in ("top1", "low1"):
    all_rows = load(family)
    rows = [row for row in all_rows if support(family, row)]
    selector = tree.build(rows, FIELDS, 0, 40)
    mistakes = [row for row in all_rows
                if (support(family, row)
                    and emit.predict(selector, row))
                != (row["label"] == "FIX")]
    print("/*", family, "support rows", len(rows),
          dict(Counter(row["label"] for row in rows)),
          "all", dict(Counter(row["label"] for row in all_rows)),
          "leaves/depth/mixed/errors", tree.stats(selector),
          "mistakes", len(mistakes), "*/")
    print(emit.emit_dnf(selector))
