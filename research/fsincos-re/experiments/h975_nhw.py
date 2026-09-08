#!/usr/bin/env python3
# h975: THE INTEGER FRAME.  h974's intervals show hw differs from
# the model by WHOLE ulp67 quanta (point intervals at -2,-1,+1) —
# the object is the terminal carry/borrow DECISION, not sub-ulp
# drift.  Extract per-op the exact set of admissible integers
# n_hw (hw terminal = chop67(A) + n_hw*ulp67), compare with:
#   ncar    = the model's fitted net adjustment (fire71/73/R75/R81)
#   n_exact = (chop67(A+TL+TR) - chop67(A))/ulp67  (true-tail chop)
#   n_exL   = left-tail-only version
# and tabulate agreement by class/coordinates.
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
    legs[(t[0], t[1])] = (m4, h4)

def x87val(s):
    se, sig = s.split(":")
    se, sig = int(se, 16), int(sig, 16)
    return ((se >> 15) & 1, se & 0x7FFF, sig)

def leg_interval(tgt, mode, neg, b2):
    sg, be, sig = x87val(tgt)
    e_out = be - 16383 - 63
    t = sig << (e_out - b2)
    u = 1 << (e_out - b2)
    ul = u >> 1 if sig == 1 << 63 else u
    if mode == "rn":
        even = (sig & 1) == 0
        return (t - (ul >> 1), even, t + (u >> 1), even)
    if (mode == "ru" and not neg) or (mode == "rd" and neg):
        return (t - ul, False, t, True)
    return (t, True, t + u, False)

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

out = open("h975_nhw.tsv", "w")
out.write("insn\top\tlab\tcls\tact\tsum8\td\tme2\tg\tlow3\tls\trs\t"
          "rsh\trud\tncar\tnexact\tnexL\tnset\tpinned\n")
tab = Counter()
tab2 = Counter()
mism = Counter()
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
    b2 = min(le2 - shL, re2 - shR, le2 - 8) - 6
    A = (-1) ** ls * (int(g("leftsig"), 16) << (le2 - b2)) \
        + (-1) ** rs * (int(g("rightsig"), 16) << (re2 - b2))
    if pay:
        A += (-1) ** (ls ^ (pay < 0)) * (abs(pay) << (le2 - 8 - b2))
    TL = (-1) ** ls * (dL << (le2 - shL - b2))
    TR = (-1) ** rs * (dR << (re2 - shR - b2))
    def chop(x):
        m = -x if x < 0 else x
        w = m.bit_length()
        ch = (m >> (w - 67)) << (w - 67)
        return (-ch if x < 0 else ch), 1 << (w - 67)
    chval, ulp67 = chop(A)
    cs, ce2, csig = int(c[5]), int(c[6]), int(c[7], 16)
    corrval = (-1) ** cs * (csig << (ce2 - b2))
    ncar = (corrval - chval) // ulp67
    ex, uex = chop(A + TL + TR)
    nexact = (ex - chval) // ulp67 if uex == ulp67 else \
        round((ex - chval) / ulp67)
    exl, uexl = chop(A + TL)
    nexL = (exl - chval) // ulp67 if uexl == ulp67 else \
        round((exl - chval) / ulp67)
    m4, h4 = legs[k]
    one = 1 << (-b2)
    v = one + corrval
    neg = x87val(m4["rn"])[0]
    iv = None
    for md in MODES:
        li = leg_interval(h4[md], md, neg, b2)
        iv = li if iv is None else isect(iv, li)
    # admissible n_hw integers: v_hw = chval + n*ulp67 + downstream
    # identical => v + (n - ncar)*ulp67 must lie in iv
    nset = [n for n in range(-4, 5)
            if contains(iv, v + (n - ncar) * ulp67)]
    pinned = 1 if len(nset) == 1 else 0
    lab = g("lab")
    cls = g("cls")
    nss = ",".join(map(str, nset))
    out.write("\t".join(map(str, (
        k[0], k[1], lab, cls, g("act"), g("sum8"), g("d"),
        g("me2"), g("g"), g("low3"), ls, rs, g("rsh"), g("rud"),
        ncar, nexact, nexL, nss, pinned))) + "\n")
    if pinned:
        n = nset[0]
        tab[(lab, "ncar%+d" % ncar, "nhw%+d" % n)] += 1
        tab2[("nhw==nexact" if n == nexact else "nhw!=nexact",
              "nhw==nexL" if n == nexL else "nhw!=nexL",
              "nhw==ncar" if n == ncar else "nhw!=ncar")] += 1
        if n != nexact:
            mism[(lab, "ncar%+d" % ncar, "nhw%+d" % n,
                  "nex%+d" % nexact)] += 1
out.close()

print("== pinned ops: (label, ncar, nhw) ==")
for kk, n in sorted(tab.items()):
    print(kk, n)
print("\n== pinned: nhw vs candidates ==")
for kk, n in sorted(tab2.items(), key=lambda x: -x[1]):
    print(kk, n)
print("\n== nhw != nexact detail ==")
for kk, n in sorted(mism.items(), key=lambda x: -x[1])[:20]:
    print(kk, n)
