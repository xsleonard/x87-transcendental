#!/usr/bin/env python3
"""h1011: one-sided, zero-contradiction thresholds on physical fractions."""

from collections import Counter


SCALE = 66
ONE = 1 << SCALE


def load_tsv(path):
    with open(path) as src:
        header = next(src).rstrip("\n").split("\t")
        index = {name: offset for offset, name in enumerate(header)}
        return index, [line.rstrip("\n").split("\t") for line in src]


fix, feature_rows = load_tsv("h970_features.tsv")
nix, nhw_rows = load_tsv("h975_nhw.tsv")
features = {(row[fix["insn"]], row[fix["op"]]): row
            for row in feature_rows}


def normalized_discard(a, b):
    product = a * b
    shift = product.bit_length() - 67
    if shift <= 0:
        return 0
    return ((product & ((1 << shift) - 1)) << SCALE) >> shift


def terminal_fraction(feature, payload_name):
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
    return (residue << SCALE) >> cut if cut > 0 else 0


records = []
for nrow in nhw_rows:
    key = nrow[nix["insn"]], nrow[nix["op"]]
    feature = features[key]
    get = lambda name: feature[fix[name]]
    mag = int(get("magsig"), 16)
    sq = int(get("mulsig"), 16)
    fourth = int(get("f4sig"), 16)
    odd = int(get("lfsig"), 16)
    even = int(get("rfsig"), 16)
    records.append({
        "line": "TOP" if int(nrow[nix["sum8"]]) >= 128 else "LOW",
        "act": int(nrow[nix["act"]]),
        "nset": {int(value) for value in nrow[nix["nset"]].split(",")},
        "pinned": nrow[nix["pinned"]] == "1",
        "half": get("half"),
        "scores": {
            "post_r": terminal_fraction(feature, "pay2"),
            "pre_r": terminal_fraction(feature, "payload"),
            "q_sq": normalized_discard(mag, mag),
            "q_f4": normalized_discard(sq, sq),
            "q_left": normalized_discard(sq, odd),
            "q_right": normalized_discard(fourth, even),
        },
    })


families = (("TOP", 0, -1), ("TOP", 1, -1), ("LOW", 1, 1))
for line, act, target in families:
    sample = [row for row in records
              if row["line"] == line and row["act"] == act]
    print("\n%s act%d target=%+d rows=%d" %
          (line, act, target, len(sample)))
    results = []
    for name in sorted(sample[0]["scores"]):
        bad_values = [row["scores"][name] for row in sample
                      if target not in row["nset"]]
        if not bad_values:
            continue
        candidates = (("gt", max(bad_values)),
                      ("lt", min(bad_values)))
        for sense, boundary in candidates:
            if sense == "gt":
                fired = [row for row in sample
                         if row["scores"][name] > boundary]
            else:
                fired = [row for row in sample
                         if row["scores"][name] < boundary]
            pinned = [row for row in fired
                      if row["pinned"] and row["nset"] == {target}]
            halves = Counter(row["half"] for row in pinned)
            if halves["FIT"] and halves["HOL"]:
                results.append((len(pinned), min(halves.values()),
                                len(fired), name, sense, boundary,
                                halves["FIT"], halves["HOL"]))
    for result in sorted(results, reverse=True):
        total, minimum, fires, name, sense, boundary, fit, hol = result
        print("  %-8s %s %20d /2^66: pinned=%3d FIT/HOL=%2d/%2d "
              "fires=%d" %
              (name, sense, boundary, total, fit, hol, fires))
