#!/usr/bin/env python3
"""h1015: R60-style nonlinear arithmetic in the 66-bit residue ring."""

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
    payload = int(get("payload"))
    pay2 = int(get("pay2")) if get("pay2") != "-" else 0
    records.append({
        "line": "TOP" if int(nrow[nix["sum8"]]) >= 128 else "LOW",
        "act": int(nrow[nix["act"]]),
        "nset": {int(value) for value in nrow[nix["nset"]].split(",")},
        "pinned": nrow[nix["pinned"]] == "1",
        "half": get("half"),
        "q": {
            "post": terminal_q(feature, "pay2", fix),
            "pre": terminal_q(feature, "payload", fix),
            "sq": qdiscard(mag, mag),
            "f4": qdiscard(sq, sq),
            "left": qdiscard(sq, odd),
            "right": qdiscard(fourth, even),
        },
        "s": {
            "low3": int(get("low3")),
            "dist": int(get("dist")),
            "payload": payload,
            "pay2": pay2,
            "ud": int(get("ud")),
            "u5d": int(get("u5d")),
            "rud": int(get("rud")),
        },
    })


def words(sample):
    bases = tuple(sorted(sample[0]["q"]))
    for base in bases:
        yield base, [row["q"][base] for row in sample]
    multipliers = [(str(value), [value] * len(sample))
                   for value in (2, 3, 4, 5, 6, 7, 8, 16, 32, 64)]
    multipliers += [(name, [row["s"][name] for row in sample])
                    for name in sorted(sample[0]["s"])]
    for aname in bases:
        for bname in bases:
            av = [row["q"][aname] for row in sample]
            bv = [row["q"][bname] for row in sample]
            for mname, mv in multipliers:
                yield (mname + "*" + aname + "+" + bname), [
                    (m * a + b) & MASK
                    for m, a, b in zip(mv, av, bv)]
                yield (mname + "*" + aname + "-" + bname), [
                    (m * a - b) & MASK
                    for m, a, b in zip(mv, av, bv)]


families = (("TOP", 0, -1), ("TOP", 1, -1), ("LOW", 1, 1))
for line, act, target in families:
    sample = [row for row in records
              if row["line"] == line and row["act"] == act]
    bad_indexes = [index for index, row in enumerate(sample)
                   if target not in row["nset"]]
    fit_indexes = [index for index, row in enumerate(sample)
                   if row["pinned"] and row["nset"] == {target}
                   and row["half"] == "FIT"]
    hol_indexes = [index for index, row in enumerate(sample)
                   if row["pinned"] and row["nset"] == {target}
                   and row["half"] == "HOL"]
    results = []
    threshold_results = []
    count_words = 0
    for name, values in words(sample):
        count_words += 1
        bad_or = 0
        bad_and = MASK
        for index in bad_indexes:
            bad_or |= values[index]
            bad_and &= values[index]
        for bit in range(SCALE):
            for wanted in (0, 1):
                safe = not ((bad_or >> bit) & 1) if wanted else (
                    (bad_and >> bit) & 1)
                if not safe:
                    continue
                fit = sum(((values[index] >> bit) & 1) == wanted
                          for index in fit_indexes)
                hol = sum(((values[index] >> bit) & 1) == wanted
                          for index in hol_indexes)
                if not fit or not hol:
                    continue
                fires = sum(((value >> bit) & 1) == wanted
                            for value in values)
                results.append((fit + hol, min(fit, hol), fires,
                                name, bit, wanted, fit, hol))
        bad_values = [values[index] for index in bad_indexes]
        for sense, boundary in (("gt", max(bad_values)),
                                ("lt", min(bad_values))):
            predicate = ((lambda value, b=boundary: value > b)
                         if sense == "gt" else
                         (lambda value, b=boundary: value < b))
            fit = sum(predicate(values[index]) for index in fit_indexes)
            hol = sum(predicate(values[index]) for index in hol_indexes)
            if fit and hol:
                fires = sum(map(predicate, values))
                threshold_results.append((
                    fit + hol, min(fit, hol), fires, name, sense,
                    boundary, fit, hol))
    print("\n%s act%d target=%+d words=%d" %
          (line, act, target, count_words))
    print("  zero-contradiction word bits:")
    for result in sorted(results, reverse=True)[:60]:
        total, minimum, fires, name, bit, wanted, fit, hol = result
        print("    bit%d(%s)=%d pinned=%d FIT/HOL=%d/%d fires=%d" %
              (bit, name, wanted, total, fit, hol, fires))
    print("  conservative word tails:")
    for result in sorted(threshold_results, reverse=True)[:40]:
        total, minimum, fires, name, sense, boundary, fit, hol = result
        print("    %s %s %d pinned=%d FIT/HOL=%d/%d fires=%d" %
              (name, sense, boundary, total, fit, hol, fires))
