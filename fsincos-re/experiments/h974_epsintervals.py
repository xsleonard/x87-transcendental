#!/usr/bin/env python3
# h974: EXACT REQUIRED-EPSILON INTERVALS.  For every census op,
# invert the four hw legs through the (proven) rounding replica to
# get the exact interval of epsilon = v_hw - v_model each op
# REQUIRES, then test membership of candidate corrections:
#   e0 = 0                      (hw = model)
#   eC = -ncar*ulp67            (hw = plain chop67(A), fitted
#                                carry/borrow dropped)
#   eL = TL                     (hw = model + full left tail)
#   eLC = TL - ncar*ulp67       (chop67(A)+left tail, no carry)
#   eLR = TL + TR               (both tails)
#   eLRC = TL + TR - ncar*ulp67 (exact chop, no carry)
# Membership bitmask per op, tabulated by h968 class -> which
# correction hw actually applied, op by op, with exact arithmetic.
import sys
from collections import Counter, defaultdict

MODES = ("rn", "rd", "ru", "rz")

feat = {}
for ln in open("h970_features.tsv"):
    t = ln.rstrip("\n").split("\t")
    if t[0] == "insn":
        ix = {c: i for i, c in enumerate(t)}
        continue
    feat[(t[0], t[1])] = t
corr = {}
for ln in open("h972_corr.tsv"):
    t = ln.rstrip("\n").split("\t")
    if t[0] != "insn":
        corr[(t[0], t[1])] = t
legs = {}
for ln in open("h968_ops.tsv"):
    t = ln.rstrip("\n").split("\t")
    if t[0] == "insn":
        continue
    m4 = {md: t[12 + 2 * j].lower() for j, md in enumerate(MODES)}
    h4 = {md: t[13 + 2 * j].lower() for j, md in enumerate(MODES)}
    legs[(t[0], t[1])] = (t[8], t[9], m4, h4)

def x87val(s):
    se, sig = s.split(":")
    se, sig = int(se, 16), int(sig, 16)
    return ((se >> 15) & 1, se & 0x7FFF, sig)

# All arithmetic at scale b-2 (quarter-ulp resolution built in).
def leg_interval(tgt, mode, neg, b2):
    # magnitude preimage [lo,hi] with closed flags for round(m)=tgt
    sg, be, sig = x87val(tgt)
    e_out = be - 16383 - 63
    t = sig << (e_out - b2)              # target value at scale b2
    u = 1 << (e_out - b2)                # ulp at t
    ul = u >> 1 if sig == 1 << 63 else u  # ulp just below t
    kind = "trunc"
    if mode == "rn":
        kind = "rn"
    elif (mode == "ru" and not neg) or (mode == "rd" and neg):
        kind = "ceil"
    if kind == "trunc":
        return (t, True, t + u, False)
    if kind == "ceil":
        return (t - ul, False, t, True)
    even = (sig & 1) == 0
    return (t - (ul >> 1), even, t + (u >> 1), even)

def isect(a, b):
    lo, lc, hi, hc = a
    lo2, lc2, hi2, hc2 = b
    if lo2 > lo or (lo2 == lo and not lc2):
        lo, lc = lo2, lc2
    if hi2 < hi or (hi2 == hi and not hc2):
        hi, hc = hi2, hc2
    return (lo, lc, hi, hc)

def contains(iv, x):
    lo, lc, hi, hc = iv
    if x < lo or (x == lo and not lc):
        return False
    if x > hi or (x == hi and not hc):
        return False
    return True

pat = Counter()
patlab = defaultdict(Counter)
resid = []
skipped = 0
for k in sorted(feat):
    t = feat[k]
    c = corr[k]
    g = lambda col: t[ix[col]]
    mulsig, lfsig = int(g("mulsig"), 16), int(g("lfsig"), 16)
    rfsig, f4sig = int(g("rfsig"), 16), int(g("f4sig"), 16)
    ls, rs = int(g("leftsign")), int(g("rightsign"))
    le2, re2 = int(g("lefte2")), int(g("righte2"))
    PL, PR = mulsig * lfsig, f4sig * rfsig
    shL, shR = PL.bit_length() - 67, PR.bit_length() - 67
    dL, dR = PL & ((1 << shL) - 1), PR & ((1 << shR) - 1)
    pay = int(g("pay2")) if g("pay2") not in ("-",) else 0
    b = min(le2 - shL, re2 - shR, le2 - 8) - 4
    b2 = b - 2
    A = (-1) ** ls * (int(g("leftsig"), 16) << (le2 - b2)) \
        + (-1) ** rs * (int(g("rightsig"), 16) << (re2 - b2))
    if pay:
        A += (-1) ** (ls ^ (pay < 0)) * (abs(pay) << (le2 - 8 - b2))
    mag = -A if A < 0 else A
    w = mag.bit_length()
    ch = (mag >> (w - 67)) << (w - 67)
    chval = -ch if A < 0 else ch
    ulp67 = 1 << (w - 67)
    cs, ce2, csig = int(c[5]), int(c[6]), int(c[7], 16)
    corrval = (-1) ** cs * (csig << (ce2 - b2))
    ncar = (corrval - chval) // ulp67
    TL = (-1) ** ls * (dL << (le2 - shL - b2))
    TR = (-1) ** rs * (dR << (re2 - shR - b2))
    cls, lab, m4, h4 = legs[k]
    one = 1 << (-b2)
    v = one + corrval
    neg = x87val(m4["rn"])[0]
    iv = None
    ok = True
    for md in MODES:
        if h4[md].startswith("weird"):
            ok = False
            break
        li = leg_interval(h4[md], md, neg, b2)
        iv = li if iv is None else isect(iv, li)
    if not ok:
        skipped += 1
        continue
    eiv = (iv[0] - v, iv[1], iv[2] - v, iv[3])
    cands = (("0", 0), ("C", -ncar * ulp67), ("L", TL),
             ("LC", TL - ncar * ulp67), ("LR", TL + TR),
             ("LRC", TL + TR - ncar * ulp67))
    mask = tuple(nm for nm, val in cands if contains(eiv, val))
    pat[mask] += 1
    patlab[lab][mask] += 1
    if not mask and len(resid) < 2000:
        # required eps in ulp67 units (float ok for report)
        lo = (eiv[0]) / ulp67
        hi = (eiv[2]) / ulp67
        resid.append((k, cls, lab, ncar, round(lo, 4), round(hi, 4),
                      round(TL / ulp67, 4), round(TR / ulp67, 6)))

print("ops with WEIRD leg skipped:", skipped)
print("\n== membership pattern -> count (top 30) ==")
for m, n in pat.most_common(30):
    print("%-28s %d" % ("+".join(m) if m else "NONE", n))
print("\n== per label ==")
for lab in ("DOWN", "ZERO", "UP", "UNEXPOSED"):
    print(lab, ":")
    for m, n in patlab[lab].most_common(12):
        print("   %-26s %d" % ("+".join(m) if m else "NONE", n))
print("\nresidual (NONE) ops:", len(resid))
for r in resid[:25]:
    print(r)
