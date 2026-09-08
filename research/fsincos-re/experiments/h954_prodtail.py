#!/usr/bin/env python3
# h954: the exact PRODUCT-TAIL features.  left = round67(mul x lf)
# in the model; the discarded product bits below the chop are the
# physical quantity the payload approximates -- never featurized.
# Compute the exact 256-bit products (left = mul x lf, right-side =
# f4 x rf), locate the chop point against the dumped left/right
# words, and contrast tail features with the honest xval.
import pickle, sys
from collections import Counter, defaultdict

table = pickle.load(open("h949_features.pkl", "rb"))
SPLIT = 96411

def prodtail(ws, wf, wchop):
    """product ws x wf vs the chopped word wchop.
    Returns (ok, tailbits_int, ntail) where tail = product bits
    below wchop's LSB weight, or ok=False if wchop != chop(product)."""
    s1, e1, m1 = ws; s2, e2, m2 = wf; sc, ec, mc = wchop
    P = m1 * m2                       # weight 2^(e1+e2) per unit
    pe = e1 + e2
    # wchop unit weight 2^ec; tail = P mod 2^(ec-pe)
    sh = ec - pe
    if sh < 0: return (False, 0, 0)
    keep = P >> sh
    if keep != mc: return (False, 0, 0)
    return (True, P & ((1 << sh) - 1), sh)

recs = []
nbad = 0
for r in table:
    ok, tail, ntl = prodtail(r["tc_mul"], r["tc_lf"], r["tc_left"])
    okr, rtail, nrt = prodtail(r["tc_f4"], r["tc_rf"], r["tc_right"])
    if not ok: nbad += 1
    recs.append((r, ok, tail, ntl, okr, rtail, nrt))
print("ops:", len(recs), " left-chop mismatch:", nbad,
      " right-chop mismatch:", sum(1 for x in recs if not x[4]))

def features(r, ok, tail, ntl, okr, rtail, nrt):
    d = r["tc_dist"]
    ls, le2, lsig = r["tc_left"]; rs, re2, rsig = r["tc_right"]
    mask = (1 << d) - 1
    rlow = rsig & mask
    grl = (rlow if rlow else (1 << d)) if ls != rs else ((1 << d) - rlow)
    g = 64 if grl > 64 else int(grl)
    f = {"_cell": (d, r["tc_mul"][1]), "_g": g, "_pay": r["tc_payload"]}
    t8 = (tail >> (ntl - 8)) & 0xFF if ok and ntl >= 8 else -1
    t16 = (tail >> (ntl - 16)) & 0xFF if ok and ntl >= 16 else -1
    rt8 = (rtail >> (nrt - 8)) & 0xFF if okr and nrt >= 8 else -1
    f["ltail8"] = t8
    f["ltail_hi2"] = t8 >> 6 if t8 >= 0 else -1
    f["ltail_hi4"] = t8 >> 4 if t8 >= 0 else -1
    f["ltail16b"] = t16
    f["rtail8"] = rt8
    f["rtail_hi2"] = rt8 >> 6 if rt8 >= 0 else -1
    f["ltz"] = 0 if not ok else (tail == 0 and 99 or
                                 (tail & -tail).bit_length() - 1 if tail else 99)
    pay = r["tc_payload"]
    f["t8_vs_pay"] = (t8 - pay) & 0xFF if t8 >= 0 else -1
    f["t8_minus_pay_sgn"] = (0 if t8 == pay else (1 if ((t8 - pay) & 0xFF) < 128
                             else 2)) if t8 >= 0 else -1
    f["t8_carrybit"] = 1 if t8 >= 128 else 0
    f["sumtail"] = ((t8 + rt8) >> 7) if (t8 >= 0 and rt8 >= 0) else -1
    return f

train = [(features(*t), t[0]["hwlab"], t[0]["seed"])
         for t in recs if t[0]["seed"] < SPLIT]
print("train:", len(train))

tup = lambda f: (f["_cell"], f["_g"], f["_pay"])
def xval(featfn):
    maj = defaultdict(Counter); tmaj = defaultdict(Counter); oc = []
    for f, y, s in train:
        if s % 2 == 0:
            maj[(tup(f), featfn(f))][y] += 1
            tmaj[tup(f)][y] += 1
        else: oc.append((f, y))
    err = 0
    for f, y in oc:
        k = (tup(f), featfn(f))
        if k in maj: pred = maj[k].most_common(1)[0][0]
        elif tup(f) in tmaj: pred = tmaj[tup(f)].most_common(1)[0][0]
        else: pred = "FIRE"
        if pred != y: err += 1
    return err
print("tuple baseline xval:", xval(lambda f: 0))
rows = []
for feat in sorted(train[0][0]):
    if feat.startswith("_"): continue
    raw = defaultdict(Counter)
    for f, y, s in train: raw[(tup(f), f[feat])][y] += 1
    err = sum(sum(c.values()) - max(c.values()) for c in raw.values())
    rows.append((xval(lambda f, ft=feat: f[ft]), err, feat))
rows.sort()
print("%-16s %7s %7s" % ("feature", "xval", "raw"))
for xv, err, feat in rows: print("%-16s %7d %7d" % (feat, xv, err))

# direct look: biggest mixed tuple, ltail8 distribution by label
bytup = defaultdict(list)
for f, y, s in train: bytup[tup(f)].append((f["ltail8"], y))
mixed = sorted(((len(v), k) for k, v in bytup.items()
                if len(set(y for _, y in v)) > 1), reverse=True)
for n, k in mixed[:2]:
    print("=== tuple", k, "n=", n)
    fs = sorted(t for t, y in bytup[k] if y == "FIRE")
    ds = sorted(t for t, y in bytup[k] if y == "DECL")
    print("  FIRE ltail8:", fs[:40])
    print("  DECL ltail8:", ds[:40])
