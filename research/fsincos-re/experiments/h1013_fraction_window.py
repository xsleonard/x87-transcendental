#!/usr/bin/env python3
"""h1013: exact small-integer fraction adders at the upper byte wall."""

from collections import Counter


SCALE = 66
ONE = 1 << SCALE


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
        "act": int(nrow[nix["act"]]),
        "sum8": int(nrow[nix["sum8"]]),
        "nset": {int(value) for value in nrow[nix["nset"]].split(",")},
        "pinned": nrow[nix["pinned"]] == "1",
        "half": get("half"),
        "q": {
            "q_sq": qdiscard(mag, mag),
            "q_f4": qdiscard(sq, sq),
            "q_left": qdiscard(sq, odd),
            "q_right": qdiscard(fourth, even),
        },
    })

sample = [row for row in rows if row["act"] == 0 and row["sum8"] >= 128]
results = []
for name in sorted(sample[0]["q"]):
    for complement in (False, True):
        for multiplier in range(1, 65):
            for rounding in ("floor", "ceil"):
                fired = []
                for row in sample:
                    fraction = row["q"][name]
                    if complement:
                        fraction = ONE - 1 - fraction
                    numerator = fraction * multiplier
                    digit = numerator >> SCALE
                    if rounding == "ceil" and numerator & (ONE - 1):
                        digit += 1
                    if row["sum8"] + digit >= 256:
                        fired.append(row)
                bad = sum(-1 not in row["nset"] for row in fired)
                pinned = [row for row in fired
                          if row["pinned"] and row["nset"] == {-1}]
                halves = Counter(row["half"] for row in pinned)
                if not bad and halves["FIT"] and halves["HOL"]:
                    results.append((len(pinned), min(halves.values()),
                                    len(fired), name, complement,
                                    multiplier, rounding,
                                    halves["FIT"], halves["HOL"]))

print("TOP act0 zero-contradiction fraction-window arms:")
for result in sorted(results, reverse=True)[:80]:
    total, minimum, fires, name, complement, multiplier, rounding, fit, hol = result
    print("  sum8 + %s(%d*(%s%s)) >= 256: "
          "pinned=%d FIT/HOL=%d/%d fires=%d" %
          (rounding, multiplier, "1-" if complement else "", name,
           total, fit, hol, fires))

linear = []
for name in sorted(sample[0]["q"]):
    for coefficient in range(-64, 65):
        if coefficient == 0:
            continue
        scores = [(row["sum8"] * ONE
                   + coefficient * row["q"][name], row)
                  for row in sample]
        boundary = max(score for score, row in scores
                       if -1 not in row["nset"])
        fired = [row for score, row in scores if score > boundary]
        pinned = [row for row in fired
                  if row["pinned"] and row["nset"] == {-1}]
        halves = Counter(row["half"] for row in pinned)
        if halves["FIT"] and halves["HOL"]:
            linear.append((len(pinned), min(halves.values()), len(fired),
                           name, coefficient, boundary,
                           halves["FIT"], halves["HOL"]))

print("\nTOP act0 conservative linear fraction tails:")
for result in sorted(linear, reverse=True)[:80]:
    total, minimum, fires, name, coefficient, boundary, fit, hol = result
    whole, fraction = divmod(boundary, ONE)
    print("  sum8 %+d*%s > %d + %d/2^66: "
          "pinned=%d FIT/HOL=%d/%d fires=%d" %
          (coefficient, name, whole, fraction,
           total, fit, hol, fires))
