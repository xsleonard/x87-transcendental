#!/usr/bin/env python3
"""h1002: pre-chop square/fourth-power bypass into terminal products.

h984's only strong unexplained marginal is the discarded fraction of the
``sq*sq`` stage.  h985 changed the stored 67-bit f4 word, while h979 changed
f4 and then recomputed all downstream Horner stages.  Neither tests a common
microarchitectural possibility: extra pre-chop f4 columns bypassing the
stored word into the later terminal multiply while the Horner factor remains
the one computed from chopped f4.

Reconstruct that path exactly.  Sweep how many leading discarded columns are
forwarded into each terminal product and score both the pinned integer truth
and all h975 admissible sets.  FIT/HOL are reported separately; no threshold
is learned from HOL.
"""

from collections import Counter


def load_tsv(path):
    with open(path) as src:
        header = next(src).rstrip("\n").split("\t")
        ix = {name: i for i, name in enumerate(header)}
        return ix, [line.rstrip("\n").split("\t") for line in src]


fix, feature_rows = load_tsv("h970_features.tsv")
nix, nhw_rows = load_tsv("h975_nhw.tsv")
features = {(r[fix["insn"]], r[fix["op"]]): r for r in feature_rows}
B2 = -1400


def chop(value, bits=67):
    magnitude = abs(value)
    shift = magnitude.bit_length() - bits
    if shift <= 0:
        return value
    kept = (magnitude >> shift) << shift
    return -kept if value < 0 else kept


def extend_product(a, ae, b, be, extra):
    """Return (significand, exponent) with `extra` discard bits kept."""
    product = a * b
    shift = product.bit_length() - 67
    keep_extra = min(extra, max(0, shift))
    drop = shift - keep_extra
    return product >> drop, ae + be + drop


rows = []
for nrow in nhw_rows:
    key = nrow[nix["insn"]], nrow[nix["op"]]
    f = features[key]
    get = lambda name: f[fix[name]]
    mag, mage = int(get("magsig"), 16), int(get("mage2"))
    sq, sqe = int(get("mulsig"), 16), int(get("mule2"))
    fourth, f4e = int(get("f4sig"), 16), int(get("f4e2"))
    odd, odde = int(get("lfsig"), 16), int(get("lfe2"))
    even, evene = int(get("rfsig"), 16), int(get("rfe2"))
    left, le = int(get("leftsig"), 16), int(get("lefte2"))
    right, re = int(get("rightsig"), 16), int(get("righte2"))
    ls, rs = int(get("leftsign")), int(get("rightsign"))
    # Use the post-gate terminal payload.  The initial proposal is not part
    # of the materialized accumulator on declined rows.
    payload = int(get("pay2")) if get("pay2") != "-" else 0
    base = ((-1) ** ls * (left << (le - B2))
            + (-1) ** rs * (right << (re - B2)))
    if payload:
        base += (-1) ** (ls ^ (payload < 0)) * (
            abs(payload) << (le - 8 - B2))
    plain = chop(base)
    ulp = 1 << (abs(base).bit_length() - 67)
    rows.append({
        "key": key, "half": get("half"), "nset": {
            int(value) for value in nrow[nix["nset"]].split(",")},
        "pinned": nrow[nix["pinned"]] == "1",
        "n": int(nrow[nix["nset"]])
             if nrow[nix["pinned"]] == "1" else None,
        "line": "TOP" if int(get("sum8")) >= 128 else "LOW",
        "act": int(get("act")), "base": base, "plain": plain,
        "ulp": ulp, "mag": (mag, mage), "sq": (sq, sqe),
        "fourth": (fourth, f4e), "odd": (odd, odde),
        "even": (even, evene), "left": (left, le, ls),
        "right": (right, re, rs), "payload": payload,
    })


def candidate(row, sq_extra, f4_extra, exact_left, exact_right):
    mag, mage = row["mag"]
    sq, sqe = row["sq"]
    odd, odde = row["odd"]
    even, evene = row["even"]
    left, le, ls = row["left"]
    right, re, rs = row["right"]

    if sq_extra >= 0:
        sqx, sqxe = extend_product(mag, mage, mag, mage, sq_extra)
        left_sig, left_e = sqx * odd, sqxe + odde
    elif exact_left:
        left_sig, left_e = sq * odd, sqe + odde
    else:
        left_sig, left_e = left, le

    if f4_extra >= 0:
        f4x, f4xe = extend_product(sq, sqe, sq, sqe, f4_extra)
        right_sig, right_e = f4x * even, f4xe + evene
    elif exact_right:
        fourth, f4e = row["fourth"]
        right_sig, right_e = fourth * even, f4e + evene
    else:
        right_sig, right_e = right, re

    value = ((-1) ** ls * (left_sig << (left_e - B2))
             + (-1) ** rs * (right_sig << (right_e - B2)))
    payload = row["payload"]
    if payload:
        value += (-1) ** (ls ^ (payload < 0)) * (
            abs(payload) << (le - 8 - B2))
    delta = chop(value) - row["plain"]
    return delta // row["ulp"] if delta % row["ulp"] == 0 else 99


def score(parameters):
    counts = Counter()
    family = Counter()
    for row in rows:
        predicted = candidate(row, *parameters)
        ok = predicted in row["nset"]
        counts["all_ok" if ok else "all_bad"] += 1
        if row["pinned"]:
            counts[(row["half"], "ok" if ok else "bad")] += 1
            family[(row["line"], row["act"], row["n"],
                    "ok" if ok else "bad")] += 1
    return counts, family


variants = []
extras = (0, 1, 2, 3, 4, 5, 6, 8, 10, 12, 16, 20, 24, 32, 48, 64,
          999)

# sq_extra/f4_extra == -1 selects the materialized stored product unless its
# exact terminal product flag is set.
for extra in extras:
    variants.append(("f4-bypass-%s" % extra, (-1, extra, False, False)))
    variants.append(("f4-bypass-%s+left-tail" % extra,
                     (-1, extra, True, False)))
    variants.append(("sq-bypass-%s" % extra, (extra, -1, False, False)))
    variants.append(("sq/f4-bypass-%s" % extra,
                     (extra, extra, False, False)))
variants.extend((
    ("plain materialized", (-1, -1, False, False)),
    ("terminal exact L", (-1, -1, True, False)),
    ("terminal exact R", (-1, -1, False, True)),
    ("terminal exact LR", (-1, -1, True, True)),
))


results = []
for name, parameters in variants:
    counts, family = score(parameters)
    fit = counts[("FIT", "ok")]
    hol = counts[("HOL", "ok")]
    results.append((fit + hol, counts["all_ok"], name, parameters,
                    counts, family))

print("rows", len(rows), "pinned", sum(row["pinned"] for row in rows))
print("\nTop bypass variants by pinned score:")
for total, all_ok, name, parameters, counts, _ in sorted(
        results, reverse=True)[:30]:
    print("  %-30s pinned %d/2725 FIT %d/1349 HOL %d/1376; "
          "all %d/8315" %
          (name, total, counts[("FIT", "ok")], counts[("HOL", "ok")],
           all_ok))

best = max(results)
print("\nBest family detail:", best[2], best[3])
for cell, count in sorted(best[5].items()):
    print(" ", cell, count)
