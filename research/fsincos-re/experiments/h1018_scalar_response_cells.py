#!/usr/bin/env python3
"""h1018: exact scalar qualifiers for the corrected response cores."""

from collections import Counter


def load_tsv(path):
    with open(path) as src:
        header = next(src).rstrip("\n").split("\t")
        index = {name: offset for offset, name in enumerate(header)}
        return index, [line.rstrip("\n").split("\t") for line in src]


fix, feature_rows = load_tsv("h970_features.tsv")
nix, nhw_rows = load_tsv("h975_nhw.tsv")
features = {(row[fix["insn"]], row[fix["op"]]): row
            for row in feature_rows}


records = []
for nrow in nhw_rows:
    key = nrow[nix["insn"]], nrow[nix["op"]]
    feature = features[key]
    get = lambda name: feature[fix[name]]
    le, re = int(get("lefte2")), int(get("righte2"))
    left, right = int(get("leftsig"), 16), int(get("rightsig"), 16)
    payload = int(get("pay2")) if get("pay2") != "-" else 0
    scale = min(le, re, le - 8 if payload else le)
    s_value = left << (le - scale)
    if payload:
        s_value += payload << (le - 8 - scale)
    b_value = right << (re - scale)
    magnitude = s_value - b_value
    if magnitude <= 0:
        raise ValueError(key)
    cut = magnitude.bit_length() - 67
    lane_shift = (le - 8) - re
    lane = ((right >> lane_shift) if lane_shift >= 0
            else (right << -lane_shift)) & 0xff
    difference = (lane - payload) & 0xff
    if difference >= 128:
        difference -= 256
    nset = {int(value) for value in nrow[nix["nset"]].split(",")}
    sum8 = int(nrow[nix["sum8"]])
    records.append({
        "key": key, "line": "TOP" if sum8 >= 128 else "LOW",
        "act": int(nrow[nix["act"]]), "nset": nset,
        "pinned": nrow[nix["pinned"]] == "1", "half": get("half"),
        "sum8": sum8, "low3": int(get("low3")),
        "dist": int(get("dist")), "payload": payload,
        "lane": lane, "diff": difference, "cut": cut,
        "P0": (~(s_value ^ b_value) >> cut) & 1,
        "Bm1": (b_value >> (cut - 1)) & 1,
        "Pm8": ((~(s_value ^ b_value) >> (cut - 8)) & 1)
        if cut >= 8 else 0,
        "S": s_value, "B": b_value, "M": magnitude,
    })


def score(name, predicate, line, act, target):
    sample = [row for row in records
              if row["line"] == line and row["act"] == act]
    fired = [row for row in sample if predicate(row)]
    bad = [row for row in fired if target not in row["nset"]]
    fit = [row for row in fired if row["pinned"]
           and row["nset"] == {target} and row["half"] == "FIT"]
    hol = [row for row in fired if row["pinned"]
           and row["nset"] == {target} and row["half"] == "HOL"]
    print("%-58s fires=%4d bad=%4d pinned=%3d FIT/HOL=%d/%d" %
          (name, len(fired), len(bad), len(fit) + len(hol),
           len(fit), len(hol)))
    return fired, bad


print("LOW response-core scalar refinements")
core = lambda row: (row["P0"] == 0 and row["Bm1"] == 0
                    and row["Pm8"] == 0)
predicates = [
    ("core", core),
    ("core && diff==-3", lambda row: core(row) and row["diff"] == -3),
    ("core && diff==-3 && 3<=pay<=6",
     lambda row: core(row) and row["diff"] == -3
     and 3 <= row["payload"] <= 6),
    ("core && diff==-3 && 6<=sum<=8",
     lambda row: core(row) and row["diff"] == -3
     and 6 <= row["sum8"] <= 8),
    ("core && diff==-3 && pay3..6 && sum6..8",
     lambda row: core(row) and row["diff"] == -3
     and 3 <= row["payload"] <= 6 and 6 <= row["sum8"] <= 8),
]
for name, predicate in predicates:
    fired, bad = score(name, predicate, "LOW", 1, 1)
    if name == "core && diff==-3 && pay3..6 && sum6..8":
        print("  fired cells:", Counter(
            (row["sum8"], row["payload"], row["low3"], row["dist"],
             tuple(sorted(row["nset"]))) for row in fired))


print("\nLOW exact scalar-cell search (direction bit included)")
sample = [row for row in records if row["line"] == "LOW"
          and row["act"] == 1 and row["P0"] == 0]
fields = ("sum8", "low3", "dist", "payload", "lane", "diff", "cut")
for first_index, first in enumerate(fields):
    values = sorted({row[first] for row in sample})
    for value in values:
        mask1 = [row for row in sample if row[first] == value]
        for second in fields[first_index + 1:]:
            for second_value in sorted({row[second] for row in mask1}):
                fired = [row for row in mask1
                         if row[second] == second_value]
                bad = [row for row in fired if 1 not in row["nset"]]
                fit = [row for row in fired if row["pinned"]
                       and row["nset"] == {1} and row["half"] == "FIT"]
                hol = [row for row in fired if row["pinned"]
                       and row["nset"] == {1} and row["half"] == "HOL"]
                if not bad and fit and hol:
                    print("  %s==%d && %s==%d fires=%d pinned=%d %d/%d" %
                          (first, value, second, second_value, len(fired),
                           len(fit) + len(hol), len(fit), len(hol)))
