#!/usr/bin/env python3
"""h995: exhaustive two-bit interaction hunt on the clean R95 labels.

h928/h970 tested marginal bits.  A carry generate (AND) or parity (XOR) can
have exactly zero marginal signal, so that does not close two-input Boolean
forms.  Build normalized bits from every retained word and every exact product
discard, screen all pairs on FIT, and apply the original stratified z statistic
unchanged to HOL.  The discovery bar is raised for roughly one million tests.
"""

import math
from collections import defaultdict

import numpy as np


def load_tsv(path):
    with open(path) as src:
        head = next(src).rstrip("\n").split("\t")
        ix = {name: i for i, name in enumerate(head)}
        return ix, [line.rstrip("\n").split("\t") for line in src]


ix, feature_rows = load_tsv("h970_features.tsv")
cix, corr_rows = load_tsv("h972_corr.tsv")
corr = {(r[cix["insn"]], r[cix["op"]]): r for r in corr_rows}


def normalized_bits(value, width, count, prefix, output):
    """Expose bits relative to the value's own top, padding at the bottom."""
    shift = max(0, width - count)
    for bit in range(count):
        output[prefix + "_b%02d" % bit] = (value >> (shift + bit)) & 1


def exact_discard(a, b):
    product = a * b
    shift = product.bit_length() - 67
    return product & ((1 << shift) - 1), shift


records = []
all_names = set()
for row in feature_rows:
    label = row[ix["lab"]]
    if label not in ("DOWN", "ZERO", "UP"):
        continue
    get = lambda name: row[ix[name]]
    bits = {}
    for name in ("magsig", "mulsig", "f4sig", "lfsig", "rfsig",
                 "leftsig", "rightsig"):
        value = int(get(name), 16)
        for bit in range(67):
            bits[name + "_b%02d" % bit] = (value >> bit) & 1

    mag = int(get("magsig"), 16)
    sq = int(get("mulsig"), 16)
    fourth = int(get("f4sig"), 16)
    odd = int(get("lfsig"), 16)
    even = int(get("rfsig"), 16)
    for name, a, b in (("sqdisc", mag, mag), ("f4disc", sq, sq),
                       ("ldisc", sq, odd), ("rdisc", fourth, even)):
        value, width = exact_discard(a, b)
        normalized_bits(value, width, 67, name, bits)

    # Full right discard was re-harvested in h972; include its absolute low
    # positions as well as the normalized product-tail view above.
    key = get("insn"), get("op")
    rd = int(corr[key][cix["rdisc"]], 16)
    for bit in range(67):
        bits["rdiscabs_b%02d" % bit] = (rd >> bit) & 1
    d60 = int(get("d60"), 16)
    for bit in range(60):
        bits["d60_b%02d" % bit] = (d60 >> bit) & 1

    stratum = tuple(get(name) for name in ("act", "sum8", "d", "me2", "g"))
    extended = stratum + (get("rsh"), get("rud"))
    records.append((stratum, extended, get("half"), label, bits))
    all_names.update(bits)


names = sorted(all_names)
name_index = {name: i for i, name in enumerate(names)}
X = np.zeros((len(records), len(names)), dtype=np.uint8)
for row_index, (_, _, _, _, bits) in enumerate(records):
    for name, value in bits.items():
        X[row_index, name_index[name]] = value


def exact_z(indexes, labels, first, second, operation):
    numerator = denominator = 0.0
    groups = defaultdict(list)
    for index in indexes:
        groups[records[index][0]].append(index)
    for sample in groups.values():
        a = b = c = d = 0
        for index in sample:
            x1, x2 = int(X[index, first]), int(X[index, second])
            value = (x1 & x2) if operation == "and" else (x1 ^ x2)
            if records[index][3] == labels[0]:
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
    return numerator / math.sqrt(denominator) if denominator else 0.0


def screen(label1, label0):
    fit = [i for i, r in enumerate(records)
           if r[2] == "FIT" and r[3] in (label1, label0)]
    hol = [i for i, r in enumerate(records)
           if r[2] == "HOL" and r[3] in (label1, label0)]
    # Within-stratum residualized outcome.  X.T diag(y) X is the numerator
    # for every AND pair up to a positive stratum-size factor; use it only to
    # select a generous candidate set, then calculate the exact h970 z.
    y = np.zeros(len(fit), dtype=np.float64)
    groups = defaultdict(list)
    for local, index in enumerate(fit):
        groups[records[index][0]].append(local)
    for sample in groups.values():
        case = sum(records[fit[local]][3] == label1 for local in sample)
        rate = case / len(sample)
        for local in sample:
            y[local] = (records[fit[local]][3] == label1) - rate
    xf = X[fit].astype(np.float64)
    score = xf.T @ (xf * y[:, None])
    triangle = np.triu_indices(len(names), 1)
    flat = np.abs(score[triangle])
    keep = min(50000, flat.size)
    selected = np.argpartition(flat, -keep)[-keep:]
    pairs = [(triangle[0][k], triangle[1][k]) for k in selected]

    candidates = []
    for number, (first, second) in enumerate(pairs):
        for operation in ("and", "xor"):
            zfit = exact_z(fit, (label1, label0), first, second, operation)
            if abs(zfit) < 4.8:
                continue
            zhol = exact_z(hol, (label1, label0), first, second, operation)
            candidates.append((abs(zfit), zfit, zhol, operation,
                               names[first], names[second]))
    candidates.sort(reverse=True)
    print("\n%s vs %s: fit=%d hol=%d, features=%d pairs=%d" %
          (label1, label0, len(fit), len(hol), len(names), len(pairs)))
    for _, zfit, zhol, operation, first, second in candidates[:40]:
        tag = " SURVIVE" if abs(zfit) >= 5.5 and abs(zhol) >= 3.5 \
            and zfit * zhol > 0 else ""
        print("  (%-27s %3s %-27s) FIT %+7.2f HOL %+7.2f%s" %
              (first, operation, second, zfit, zhol, tag))
    survivors = [row for row in candidates if row[0] >= 5.5
                 and abs(row[2]) >= 3.5 and row[1] * row[2] > 0]
    print("Bonferroni-grade survivors:", len(survivors))


print("exposed records:", len(records), "bit features:", len(names))
screen("DOWN", "ZERO")
screen("UP", "ZERO")
