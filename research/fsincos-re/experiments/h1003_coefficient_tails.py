#!/usr/bin/env python3
"""h1003: execute the previously planned P5C6 ROM-tail solver.

The stored P5C6 words are behaviorally fitted 67-bit reconstructions.  The
handoff's earlier T3 plan proposed testing sub-ULP coefficient tails but was
never implemented.  Extend one coefficient at a time by signed 1/64-ULP
increments, replay the exact chop67/RN64 Horner chain, materialize both
terminal products exactly as the C model does, and score the resulting
integer terminal correction against h975's full admissible sets.
"""

from collections import Counter


CHOP, RN = 0, 1
TAIL_BITS = 6
B2 = -1400

C0 = {
    1: (1, -68, (0x7 << 64) | 0xfffffffffffffffe),
    2: (0, -71, (0x5 << 64) | 0x5555555555554277),
    3: (1, -76, (0x5 << 64) | 0xb05b05b05a18a1ba),
    4: (0, -82, (0x6 << 64) | 0x80680675b559f2cf),
    5: (1, -88, (0x4 << 64) | 0x9f93af61f5349300),
    6: (0, -95, (0x4 << 64) | 0x7a4f2483514c1af8),
}


def load_tsv(path):
    with open(path) as src:
        header = next(src).rstrip("\n").split("\t")
        ix = {name: i for i, name in enumerate(header)}
        return ix, [line.rstrip("\n").split("\t") for line in src]


def rnd(sign, magnitude, scale, bits, mode):
    if magnitude == 0:
        return sign, 0, 0
    shift = magnitude.bit_length() - bits
    if shift <= 0:
        return sign, scale + shift, magnitude << -shift
    kept = magnitude >> shift
    guard = (magnitude >> (shift - 1)) & 1
    sticky = bool(magnitude & ((1 << (shift - 1)) - 1))
    if mode == RN and guard and (sticky or (kept & 1)):
        kept += 1
        if kept == 1 << bits:
            kept >>= 1
            shift += 1
    return sign, scale + shift, kept


def wmul(a, b, bits=67, mode=CHOP):
    return rnd(a[0] ^ b[0], a[2] * b[2], a[1] + b[1], bits, mode)


def wadd(a, b, bits=64, mode=RN):
    scale = min(a[1], b[1])
    value = ((-1) ** a[0] * (a[2] << (a[1] - scale))
             + (-1) ** b[0] * (b[2] << (b[1] - scale)))
    return rnd(int(value < 0), abs(value), scale, bits, mode)


def chop_integer(value, bits=67):
    magnitude = abs(value)
    shift = magnitude.bit_length() - bits
    if shift <= 0:
        return value
    kept = (magnitude >> shift) << shift
    return -kept if value < 0 else kept


def constants(deltas):
    result = {}
    for index, (sign, exponent, significand) in C0.items():
        extended = (significand << TAIL_BITS) + deltas[index]
        if extended <= 0:
            raise ValueError("invalid extended coefficient")
        result[index] = sign, exponent - TAIL_BITS, extended
    return result


def chain(sq, fourth, coefficients):
    odd = wmul(fourth, coefficients[5])
    odd = wadd(coefficients[3], odd)
    odd = wmul(fourth, odd)
    odd = wadd(coefficients[1], odd)
    even = wmul(fourth, coefficients[6])
    even = wadd(coefficients[4], even)
    even = wmul(fourth, even)
    even = wadd(coefficients[2], even)
    return odd, even


fix, feature_rows = load_tsv("h970_features.tsv")
nix, nhw_rows = load_tsv("h975_nhw.tsv")
features = {(r[fix["insn"]], r[fix["op"]]): r for r in feature_rows}

rows = []
for nrow in nhw_rows:
    key = nrow[nix["insn"]], nrow[nix["op"]]
    f = features[key]
    get = lambda name: f[fix[name]]
    sq = (0, int(get("mule2")), int(get("mulsig"), 16))
    fourth = (0, int(get("f4e2")), int(get("f4sig"), 16))
    left = (int(get("leftsign")), int(get("lefte2")),
            int(get("leftsig"), 16))
    right = (int(get("rightsign")), int(get("righte2")),
             int(get("rightsig"), 16))
    # The terminal composes the post-gate payload (`pay2`), not the initial
    # proposal recorded by DI_TC.  Using the proposal corrupts the declined
    # rows that dominate the unresolved top-line population.
    payload = int(get("pay2")) if get("pay2") != "-" else 0
    base = ((-1) ** left[0] * (left[2] << (left[1] - B2))
            + (-1) ** right[0] * (right[2] << (right[1] - B2)))
    if payload:
        base += (-1) ** (left[0] ^ (payload < 0)) * (
            abs(payload) << (left[1] - 8 - B2))
    plain = chop_integer(base)
    ulp = 1 << (abs(base).bit_length() - 67)
    rows.append({
        "sq": sq, "fourth": fourth, "left": left, "right": right,
        "payload": payload, "plain": plain, "ulp": ulp,
        "nset": {int(value) for value in nrow[nix["nset"]].split(",")},
        "pinned": nrow[nix["pinned"]] == "1",
        "half": get("half"),
        "line": "TOP" if int(get("sum8")) >= 128 else "LOW",
        "act": int(get("act")),
        "n": int(nrow[nix["nset"]])
             if nrow[nix["pinned"]] == "1" else None,
        "banked_odd": (int(get("lfe2")), int(get("lfsig"), 16)),
        "banked_even": (int(get("rfe2")), int(get("rfsig"), 16)),
    })


def predict(row, coefficient_words):
    odd, even = chain(row["sq"], row["fourth"], coefficient_words)
    left = wmul(row["sq"], odd)
    right = wmul(row["fourth"], even)
    value = ((-1) ** left[0] * (left[2] << (left[1] - B2))
             + (-1) ** right[0] * (right[2] << (right[1] - B2)))
    payload = row["payload"]
    if payload:
        value += (-1) ** (left[0] ^ (payload < 0)) * (
            abs(payload) << (left[1] - 8 - B2))
    delta = chop_integer(value) - row["plain"]
    predicted = delta // row["ulp"] if delta % row["ulp"] == 0 else 99
    return predicted, odd, even


def score(deltas, validate=False):
    coefficient_words = constants(deltas)
    counts = Counter()
    for row in rows:
        predicted, odd, even = predict(row, coefficient_words)
        ok = predicted in row["nset"]
        counts["all_ok" if ok else "all_bad"] += 1
        if row["pinned"]:
            counts[(row["half"], "ok" if ok else "bad")] += 1
            counts[(row["line"], row["act"], row["n"],
                    "ok" if ok else "bad")] += 1
        if validate:
            counts["odd_same" if odd[1:] == row["banked_odd"]
                   else "odd_changed"] += 1
            counts["even_same" if even[1:] == row["banked_even"]
                   else "even_changed"] += 1
    return counts


zero = {index: 0 for index in C0}
baseline = score(zero, validate=True)
print("rows", len(rows), "pinned", sum(row["pinned"] for row in rows))
print("baseline", dict(baseline))

grid = tuple(range(-128, 129, 2))
results = []
for coefficient in C0:
    for delta in grid:
        trial = dict(zero)
        trial[coefficient] = delta
        counts = score(trial)
        results.append((counts[("FIT", "ok")] + counts[("HOL", "ok")],
                        counts["all_ok"], coefficient, delta, counts))

print("\nBest one-coefficient tails by pinned score:")
for pinned, all_ok, coefficient, delta, counts in sorted(
        results, reverse=True)[:40]:
    print("  C%d delta=%+d/64: pinned %d/2725 FIT %d HOL %d; "
          "all %d/8315" %
          (coefficient, delta, pinned, counts[("FIT", "ok")],
           counts[("HOL", "ok")], all_ok))

best = max(results)
print("\nBest family detail: C%d delta=%+d/64" % (best[2], best[3]))
for key, count in sorted(best[4].items(), key=lambda item: str(item[0])):
    print(" ", key, count)
