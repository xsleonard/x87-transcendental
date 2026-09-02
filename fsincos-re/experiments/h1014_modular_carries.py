#!/usr/bin/env python3
"""h1014: conservative carry/borrow arms from modular stage fractions."""

from collections import Counter


SCALE = 66
ONE = 1 << SCALE
MASK = ONE - 1


def load_tsv(path):
    with open(path) as src:
        header = next(src).rstrip("\n").split("\t")
        index = {name: offset for offset, name in enumerate(header)}
        return index, [line.rstrip("\n").split("\t") for line in src]


def qdiscard(a, b):
    product = a * b
    shift = product.bit_length() - 67
    return (((product & ((1 << shift) - 1)) << SCALE) >> shift
            if shift > 0 else 0)


def terminal_q(feature, payload_name, fix):
    get = lambda name: feature[fix[name]]
    le, re = int(get("lefte2")), int(get("righte2"))
    left, right = int(get("leftsig"), 16), int(get("rightsig"), 16)
    ls, rs = int(get("leftsign")), int(get("rightsign"))
    payload = int(get(payload_name)) if get(payload_name) != "-" else 0
    scale = min(le, re, le - 8 if payload else le)
    value = ((-1 if ls else 1) * (left << (le - scale))
             + (-1 if rs else 1) * (right << (re - scale)))
    if payload:
        psign = ls ^ (payload < 0)
        value += (-1 if psign else 1) * (
            abs(payload) << (le - 8 - scale))
    magnitude = abs(value)
    cut = magnitude.bit_length() - 67
    residue = magnitude & ((1 << cut) - 1) if cut > 0 else 0
    return (residue << SCALE) >> cut if cut > 0 else 0


fix, feature_rows = load_tsv("h970_features.tsv")
nix, nhw_rows = load_tsv("h975_nhw.tsv")
features = {(row[fix["insn"]], row[fix["op"]]): row
            for row in feature_rows}
rows = []
for nrow in nhw_rows:
    key = nrow[nix["insn"]], nrow[nix["op"]]
    feature = features[key]
    get = lambda name: feature[fix[name]]
    mag = int(get("magsig"), 16)
    sq = int(get("mulsig"), 16)
    fourth = int(get("f4sig"), 16)
    odd = int(get("lfsig"), 16)
    even = int(get("rfsig"), 16)
    rows.append({
        "line": "TOP" if int(nrow[nix["sum8"]]) >= 128 else "LOW",
        "act": int(nrow[nix["act"]]),
        "nset": {int(value) for value in nrow[nix["nset"]].split(",")},
        "pinned": nrow[nix["pinned"]] == "1",
        "half": get("half"),
        "r": {
            "post": terminal_q(feature, "pay2", fix),
            "pre": terminal_q(feature, "payload", fix),
        },
        "q": {
            "sq": qdiscard(mag, mag),
            "f4": qdiscard(sq, sq),
            "left": qdiscard(sq, odd),
            "right": qdiscard(fourth, even),
        },
    })


families = (("TOP", 0, -1), ("TOP", 1, -1), ("LOW", 1, 1))
for line, act, target in families:
    sample = [row for row in rows
              if row["line"] == line and row["act"] == act]
    results = []
    for rname in ("post", "pre"):
        for qname in ("sq", "f4", "left", "right"):
            for coefficient in range(1, 65):
                for negative in (False, True):
                    def term(row):
                        value = coefficient * row["q"][qname]
                        return ((-value) if negative else value) & MASK

                    predicates = (
                        ("carry", lambda row: row["r"][rname] + term(row)
                         >= ONE),
                        ("borrow", lambda row: row["r"][rname] < term(row)),
                    )
                    for kind, predicate in predicates:
                        fired = [row for row in sample if predicate(row)]
                        if any(target not in row["nset"] for row in fired):
                            continue
                        pinned = [row for row in fired if row["pinned"]
                                  and row["nset"] == {target}]
                        halves = Counter(row["half"] for row in pinned)
                        if halves["FIT"] and halves["HOL"]:
                            results.append((
                                len(pinned), min(halves.values()),
                                len(fired), rname, qname, coefficient,
                                negative, kind,
                                halves["FIT"], halves["HOL"]))
    print("\n%s act%d target=%+d modular zero-contradiction arms:" %
          (line, act, target))
    for result in sorted(results, reverse=True)[:80]:
        total, minimum, fires, rname, qname, coefficient, negative, kind, fit, hol = result
        print("  %-6s(%s_r, (%s%d*q_%s) mod 1): "
              "pinned=%d FIT/HOL=%d/%d fires=%d" %
              (kind, rname, "-" if negative else "+", coefficient,
               qname, total, fit, hol, fires))
