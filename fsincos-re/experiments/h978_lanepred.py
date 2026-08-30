#!/usr/bin/env python3
# h978: lane-byte addend family vs the pinned n_hw truth.  h956
# proved the lane byte physically real (621 legs beat exact tail);
# test whether hw's terminal injects lane-derived bytes where the
# model injects its fitted payload (or nothing when declined):
#   t = A - pay*2^(le2-8) [optionally remove model byte]
#         + s*laneK*2^(le2-8K)      K in {1,2,3}, s in {+ls,-ls}
# plus difference forms (laneb - pay).  Scored on all pinned ops.
import sys
from collections import Counter, defaultdict

feat = {}
for ln in open("h970_features.tsv"):
    t = ln.rstrip("\n").split("\t")
    if t[0] == "insn":
        ix = {c: i for i, c in enumerate(t)}
        continue
    feat[(t[0], t[1])] = t
nhw = {}
lab = {}
for ln in open("h975_nhw.tsv"):
    t = ln.rstrip("\n").split("\t")
    if t[0] == "insn":
        jx = {c: i for i, c in enumerate(t)}
        continue
    if t[jx["pinned"]] == "1":
        nhw[(t[0], t[1])] = int(t[jx["nset"]])
        lab[(t[0], t[1])] = t[jx["lab"]]
corr = {}
for ln in open("h972_corr.tsv"):
    t = ln.rstrip("\n").split("\t")
    if t[0] != "insn":
        corr[(t[0], t[1])] = t

OPS = []
for k, n in sorted(nhw.items()):
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
    lane = {}
    for col, kk in (("laneb", 1), ("lane2", 2), ("lane3", 3)):
        v = g(col)
        lane[kk] = int(v, 16) if v not in ("-",) else 0
    b2 = min(le2 - shL, re2 - shR, le2 - 8 * 3) - 6
    A = (-1) ** ls * (int(g("leftsig"), 16) << (le2 - b2)) \
        + (-1) ** rs * (int(g("rightsig"), 16) << (re2 - b2))
    payterm = 0
    if pay:
        payterm = (-1) ** (ls ^ (pay < 0)) * (abs(pay)
                                              << (le2 - 8 - b2))
        A += payterm
    cs, ce2, csig = int(c[5]), int(c[6]), int(c[7], 16)
    corrval = (-1) ** cs * (csig << (ce2 - b2))
    TLv = (-1) ** ls * (dL << (le2 - shL - b2))
    TRv = (-1) ** rs * (dR << (re2 - shR - b2))
    OPS.append((k, n, A, payterm, lane, ls, le2, b2, corrval,
                TLv, TRv))

def chopw(x, bits):
    m = -x if x < 0 else x
    w = m.bit_length()
    if w <= bits:
        return x
    ch = (m >> (w - bits)) << (w - bits)
    return -ch if x < 0 else ch

def run(name, fn):
    good = 0
    fam = defaultdict(Counter)
    for (k, n, A, payterm, lane, ls, le2, b2, corrval, TLv,
         TRv) in OPS:
        chval = chopw(A, 67)
        ulp67 = 1 << (abs(A).bit_length() - 67)
        t = fn(A, payterm, lane, ls, le2, b2, TLv, TRv)
        npred = (chopw(t, 67) - chval) // ulp67
        ok = npred == n
        good += ok
        ncar = (corrval - chval) // ulp67
        fam[("%+d" % ncar, lab[k])]["ok" if ok else "BAD"] += 1
    return good, fam

def laneterm(lane, kk, s, le2, b2):
    return s * (lane[kk] << (le2 - 8 * kk - b2))

VARIANTS = []
for kk in (1, 2, 3):
    for sname, sfn in (("+ls", lambda ls: (-1) ** ls),
                       ("-ls", lambda ls: -((-1) ** ls))):
        VARIANTS.append((
            "lane%d%s" % (kk, sname),
            (lambda kk=kk, sfn=sfn:
             lambda A, payterm, lane, ls, le2, b2, TLv, TRv:
             A + laneterm(lane, kk, sfn(ls), le2, b2))()))
        VARIANTS.append((
            "lane%d%s-nopay" % (kk, sname),
            (lambda kk=kk, sfn=sfn:
             lambda A, payterm, lane, ls, le2, b2, TLv, TRv:
             A - payterm + laneterm(lane, kk, sfn(ls), le2, b2))()))
        VARIANTS.append((
            "lane%d%s+TL" % (kk, sname),
            (lambda kk=kk, sfn=sfn:
             lambda A, payterm, lane, ls, le2, b2, TLv, TRv:
             A + TLv + laneterm(lane, kk, sfn(ls), le2, b2))()))
VARIANTS.append(("chop-only",
                 lambda A, payterm, lane, ls, le2, b2, TLv, TRv: A))
VARIANTS.append(("nopay",
                 lambda A, payterm, lane, ls, le2, b2, TLv, TRv:
                 A - payterm))

res = []
for nm, fn in VARIANTS:
    good, fam = run(nm, fn)
    res.append((good, nm, fam))
res.sort(reverse=True, key=lambda x: x[0])
print("pinned ops:", len(OPS))
for good, nm, fam in res:
    print("%-18s %d" % (nm, good))
print("\n== best non-baseline breakdown ==")
for good, nm, fam in res:
    if nm not in ("chop-only", "nopay"):
        print(nm, good)
        for kk in sorted(fam):
            print("  ", kk, dict(fam[kk]))
        break
