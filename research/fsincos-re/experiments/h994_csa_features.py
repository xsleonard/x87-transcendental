#!/usr/bin/env python3
"""h994: carry-save/LZA feature census for all four multiply stages.

Intel's multiplier LZA patent predicts from the carry-save pair rather than
the resolved product.  The h970 raw-bit sweep cannot see that encoding.  Build
tree-independent exact unsigned partial-product CSAs (three canonical
reductions, either operand supplying the rows) and test their LZA, generate,
and propagate fields with the same within-stratum FIT/HOL criterion as h970b.
"""

import math
from collections import defaultdict

from h621_carry_predict import reduce_rows


WIDTH = 224
MASK = (1 << WIDTH) - 1


def load_tsv(path):
    with open(path) as src:
        head = next(src).rstrip("\n").split("\t")
        ix = {name: i for i, name in enumerate(head)}
        return ix, [line.rstrip("\n").split("\t") for line in src]


ix, rows = load_tsv("h970_features.tsv")


def unsigned_rows(a, b):
    return [(a << bit) & MASK for bit in range(b.bit_length())
            if (b >> bit) & 1]


def pair_features(a, b, name):
    product = a * b
    top = product.bit_length() - 1
    cut = product.bit_length() - 67
    out = {}
    for role, x, y in (("ab", a, b), ("ba", b, a)):
        pp = unsigned_rows(x, y)
        for arrangement in ("seq", "eo", "tree"):
            s, c = reduce_rows(pp, arrangement)
            if s + c != product:
                raise AssertionError((name, role, arrangement))
            tag = "%s_%s_%s" % (name, role, arrangement)
            sorc = s | c
            out[tag + "_lzaerr"] = top - (sorc.bit_length() - 1)
            for rel in range(-12, 13):
                bit = top + rel
                if bit >= 0:
                    out[tag + "_orT%+d" % rel] = (sorc >> bit) & 1
            generate = s & c
            propagate = s ^ c
            for rel in range(-16, 17):
                bit = cut + rel
                if bit >= 0:
                    out[tag + "_gC%+d" % rel] = (generate >> bit) & 1
                    out[tag + "_pC%+d" % rel] = (propagate >> bit) & 1
            for direction, word in (("p", propagate), ("g", generate)):
                run = 0
                bit = cut - 1
                while bit >= 0 and run < 32 and ((word >> bit) & 1):
                    run += 1
                    bit -= 1
                for threshold in (1, 2, 4, 8, 12, 16, 24):
                    out[tag + "_%srun%d" % (direction, threshold)] = \
                        int(run >= threshold)
    return out


data = []
for index, row in enumerate(rows):
    label = row[ix["lab"]]
    if label not in ("DOWN", "ZERO", "UP"):
        continue
    mag = int(row[ix["magsig"]], 16)
    sq = int(row[ix["mulsig"]], 16)
    fourth = int(row[ix["f4sig"]], 16)
    odd = int(row[ix["lfsig"]], 16)
    even = int(row[ix["rfsig"]], 16)
    feats = {}
    feats.update(pair_features(mag, mag, "sq"))
    feats.update(pair_features(sq, sq, "f4"))
    feats.update(pair_features(sq, odd, "left"))
    feats.update(pair_features(fourth, even, "right"))
    stratum = tuple(row[ix[name]] for name in
                    ("act", "sum8", "d", "me2", "g"))
    extended = stratum + (row[ix["rsh"]], row[ix["rud"]])
    data.append((stratum, extended, row[ix["half"]], label, feats))
    if index and index % 1000 == 0:
        print("built", index, flush=True)


names = sorted(data[0][4])
def hunt(label1, label0, use_extended=False):
    strata = defaultdict(list)
    for basic, extended, half, label, feats in data:
        strata[extended if use_extended else basic].append(
            (half, label, feats))
    result = []
    for half in ("FIT", "HOL"):
        zs = {}
        for name in names:
            numerator = denominator = 0.0
            for sample in strata.values():
                a = b = c = d = 0
                for h, label, feats in sample:
                    if h != half or label not in (label1, label0):
                        continue
                    value = feats[name]
                    if label == label1:
                        a += value
                        b += 1 - value
                    else:
                        c += value
                        d += 1 - value
                n1, n0 = a + b, c + d
                if not n1 or not n0:
                    continue
                p = (a + c) / (n1 + n0)
                if p <= 0 or p >= 1:
                    continue
                numerator += a - n1 * p
                denominator += n1 * n0 * p * (1 - p) / (n1 + n0)
            zs[name] = numerator / math.sqrt(denominator) \
                if denominator else 0.0
        result.append(zs)
    fit, hol = result
    top = sorted(names, key=lambda name: abs(fit[name]), reverse=True)[:20]
    print("\n%s vs %s%s; top FIT features:" %
          (label1, label0, " conditioned on rsh/rud" if use_extended else ""))
    for name in top:
        print("  %-34s FIT %+7.2f HOL %+7.2f" %
              (name, fit[name], hol[name]))
    survivors = [name for name in names if abs(fit[name]) >= 4.8
                 and abs(hol[name]) >= 3.2 and fit[name] * hol[name] > 0]
    print("survivors:", len(survivors))
    for name in survivors[:80]:
        print("  %-34s FIT %+7.2f HOL %+7.2f" %
              (name, fit[name], hol[name]))


print("exposed ops:", len(data), "CSA features:", len(names))
hunt("DOWN", "ZERO")
hunt("UP", "ZERO")
hunt("DOWN", "ZERO", True)
hunt("UP", "ZERO", True)
