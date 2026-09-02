#!/usr/bin/env python3
"""h1010: conservative dyadic residue wings for all residual families."""

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


def terminal(feature, payload_name):
    get = lambda name: feature[fix[name]]
    le, re = int(get("lefte2")), int(get("righte2"))
    left, right = int(get("leftsig"), 16), int(get("rightsig"), 16)
    ls, rs = int(get("leftsign")), int(get("rightsign"))
    payload = int(get(payload_name)) if get(payload_name) != "-" else 0
    scale = min(le, re, le - 8 if payload else le)
    value = ((-1 if ls else 1) * (left << (le - scale))
             + (-1 if rs else 1) * (right << (re - scale)))
    if payload:
        payload_sign = ls ^ (payload < 0)
        value += (-1 if payload_sign else 1) * (
            abs(payload) << (le - 8 - scale))
    magnitude = abs(value)
    cut = magnitude.bit_length() - 67
    residue = magnitude & ((1 << cut) - 1) if cut > 0 else 0
    return cut, residue


records = []
for nrow in nhw_rows:
    key = nrow[nix["insn"]], nrow[nix["op"]]
    feature = features[key]
    get = lambda name: feature[fix[name]]
    records.append({
        "line": "TOP" if int(nrow[nix["sum8"]]) >= 128 else "LOW",
        "act": int(nrow[nix["act"]]),
        "nset": {int(value) for value in nrow[nix["nset"]].split(",")},
        "pinned": nrow[nix["pinned"]] == "1",
        "half": get("half"),
        "post": terminal(feature, "pay2"),
        "pre": terminal(feature, "payload"),
    })


families = (("TOP", 0, -1, "high"),
            ("TOP", 1, -1, "high"),
            ("LOW", 1, 1, "low"))
for line, act, target, wing in families:
    print("\n%s act%d target=%+d %s residue wing" %
          (line, act, target, wing))
    for coordinate in ("post", "pre"):
        print(" ", coordinate)
        for k in range(1, 21):
            fired = []
            for row in records:
                if row["line"] != line or row["act"] != act:
                    continue
                cut, residue = row[coordinate]
                if cut <= 0:
                    continue
                if wing == "high":
                    fire = (residue * (1 << k)
                            > ((1 << k) - 1) * (1 << cut))
                else:
                    fire = residue * (1 << k) < (1 << cut)
                if fire:
                    fired.append(row)
            bad = sum(target not in row["nset"] for row in fired)
            pinned = [row for row in fired
                      if row["pinned"] and row["nset"] == {target}]
            halves = Counter(row["half"] for row in pinned)
            if bad == 0 or k in (8, 9, 10):
                print("    k=%2d fires=%4d bad=%4d pinned=%3d "
                      "FIT/HOL=%2d/%2d" %
                      (k, len(fired), bad, len(pinned),
                       halves["FIT"], halves["HOL"]))
