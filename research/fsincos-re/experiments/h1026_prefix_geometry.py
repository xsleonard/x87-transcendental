#!/usr/bin/env python3
"""h1026: test whether the residual decision is a range-reduction prefix law.

The strongest h1024 Booth features at the top of the fourth-power multiplier
are merely high bits of the chopped square.  Test that geometry directly,
using target-absent admissibility rows as hard negatives and the frozen
FIT/HOL split for transfer.  A real ROM-index or interval law should stabilize
at a short prefix; memorization grows only at long prefixes.
"""

from collections import Counter, defaultdict


def load_tsv(path):
    with open(path) as src:
        header = next(src).rstrip("\n").split("\t")
        index = {name: offset for offset, name in enumerate(header)}
        return index, [line.rstrip("\n").split("\t") for line in src]


def terminal_pcut(feature, fix):
    get = lambda name: feature[fix[name]]
    left = int(get("leftsig"), 16)
    right = int(get("rightsig"), 16)
    left_exp, right_exp = int(get("lefte2")), int(get("righte2"))
    payload = int(get("pay2")) if get("pay2") != "-" else 0
    scale = min(left_exp, right_exp,
                left_exp - 8 if payload else left_exp)
    left_value = (-1 if int(get("leftsign")) else 1) * (
        left << (left_exp - scale))
    right_value = (-1 if int(get("rightsign")) else 1) * (
        right << (right_exp - scale))
    payload_value = 0
    if payload:
        payload_sign = int(get("leftsign")) ^ (payload < 0)
        payload_value = (-1 if payload_sign else 1) * (
            abs(payload) << (left_exp - 8 - scale))
    if left_value + payload_value < 0 <= right_value:
        minuend, subtrahend = -(left_value + payload_value), right_value
    else:
        minuend, subtrahend = -right_value, left_value + payload_value
    magnitude = minuend - subtrahend
    cut = magnitude.bit_length() - 67
    return (~(minuend ^ subtrahend) >> cut) & 1


fix, features = load_tsv("h970_features.tsv")
nix, nhw_rows = load_tsv("h975_nhw.tsv")
nhw = {(row[nix["insn"]], row[nix["op"]]): row for row in nhw_rows}
rows = []
for feature in features:
    get = lambda name: feature[fix[name]]
    nrow = nhw[get("insn"), get("op")]
    nset = {int(value) for value in nrow[nix["nset"]].split(",")}
    pinned = nrow[nix["pinned"]] == "1"
    rows.append({
        "line": "TOP" if int(get("sum8")) >= 128 else "LOW",
        "act": int(get("act")), "half": get("half"),
        "pcut": terminal_pcut(feature, fix), "nset": nset,
        "n": int(nrow[nix["nset"]]) if pinned else None,
        "pinned": pinned,
        "mag": int(get("magsig"), 16),
        "sq": int(get("mulsig"), 16),
        "f4": int(get("f4sig"), 16),
        "left": int(get("leftsig"), 16),
        "right": int(get("rightsig"), 16),
    })


families = (("top0", "TOP", 0, -1),
            ("top1", "TOP", 1, -1),
            ("low1", "LOW", 1, 1))
for family, line, act, target in families:
    direction = 1 if line == "TOP" else 0
    sample = [row for row in rows
              if row["line"] == line and row["act"] == act
              and row["pcut"] == direction
              and ((row["pinned"] and row["n"] == target)
                   or target not in row["nset"])]
    print("\n%s rows=%d positives=%d negatives=%d" %
          (family, len(sample),
           sum(row["pinned"] and row["n"] == target for row in sample),
           sum(target not in row["nset"] for row in sample)))
    for field in ("mag", "sq", "f4", "left", "right"):
        print(" ", field, "high-prefix transfer:")
        for width in range(2, 25):
            cells = defaultdict(Counter)
            for row in sample:
                code = row[field] >> (67 - width)
                label = "pos" if row["pinned"] and row["n"] == target \
                    else "neg"
                cells[code][row["half"], label] += 1
            selected = {code for code, counts in cells.items()
                        if counts["FIT", "pos"] >= 2
                        and counts["FIT", "neg"] == 0}
            fit_pos = sum(cells[code]["FIT", "pos"] for code in selected)
            holdout_pos = sum(cells[code]["HOL", "pos"]
                              for code in selected)
            holdout_neg = sum(cells[code]["HOL", "neg"]
                              for code in selected)
            if selected and (width <= 12 or holdout_pos):
                print("    w%02d bins=%3d FITpos=%3d HOLpos=%3d HOLneg=%3d" %
                      (width, len(selected), fit_pos, holdout_pos,
                       holdout_neg))

