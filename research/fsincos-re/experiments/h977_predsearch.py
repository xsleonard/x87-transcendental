#!/usr/bin/env python3
# h977: predictor enumeration over the pinned n_hw ground truth.
# Candidate law: hw's terminal = chop67( chop_{67+woff}(A)
#     + trunc_top(TL, jL) + trunc_top(TR, jR) )
# i.e., a working value truncated at 67+woff bits plus width-
# limited tail addends, chopped architecturally.  n_pred compared
# against the pinned n_hw on all 2,725 pinned ops (the 1,721
# ncar=0 ZERO ops constrain false fires; the fitted-rule sides
# constrain rule-replacement; the +0->-1 mixture is the target).
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
print("pinned ops:", len(nhw))

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
    b2 = min(le2 - shL, re2 - shR, le2 - 8) - 6
    A = (-1) ** ls * (int(g("leftsig"), 16) << (le2 - b2)) \
        + (-1) ** rs * (int(g("rightsig"), 16) << (re2 - b2))
    if pay:
        A += (-1) ** (ls ^ (pay < 0)) * (abs(pay) << (le2 - 8 - b2))
    cs, ce2, csig = int(c[5]), int(c[6]), int(c[7], 16)
    corrval = (-1) ** cs * (csig << (ce2 - b2))
    OPS.append((k, n, A, dL, shL, ls, le2, dR, shR, rs, re2, b2,
                corrval))

def chopw(x, bits):
    m = -x if x < 0 else x
    w = m.bit_length()
    if w <= bits:
        return x
    ch = (m >> (w - bits)) << (w - bits)
    return -ch if x < 0 else ch

def trunc_top(d, sh, j):
    if j >= sh:
        return d
    if j <= 0:
        return 0
    return (d >> (sh - j)) << (sh - j)

def run(woff, jL, jR):
    good = 0
    fam = defaultdict(Counter)
    for (k, n, A, dL, shL, ls, le2, dR, shR, rs, re2, b2,
         corrval) in OPS:
        chval = chopw(A, 67)
        ulp67_w = (abs(A).bit_length() - 67)
        ulp67 = 1 << ulp67_w
        Aw = chopw(A, 67 + woff) if woff < 200 else A
        TLv = (-1) ** ls * (trunc_top(dL, shL, jL) << (le2 - shL - b2))
        TRv = (-1) ** rs * (trunc_top(dR, shR, jR) << (re2 - shR - b2))
        t = Aw + TLv + TRv
        npred = (chopw(t, 67) - chval) // ulp67
        ok = npred == n
        good += ok
        ncar = (corrval - chval) // ulp67
        fam[("%+d" % ncar, lab[k])]["ok" if ok else "BAD"] += 1
    return good, fam

results = []
for woff in (0, 1, 2, 3, 4, 6, 8, 12, 999):
    for jL in (0, 1, 2, 3, 4, 6, 8, 12, 999):
        for jR in (0, 1, 2, 999):
            good, fam = run(woff, jL, jR)
            results.append((good, woff, jL, jR))
results.sort(reverse=True)
print("== top 20 predictors (good/%d) ==" % len(OPS))
for good, woff, jL, jR in results[:20]:
    print("woff=%-3s jL=%-3s jR=%-3s  %d" % (woff, jL, jR, good))
print("== baselines ==")
for nm, args in (("model(ncar)", None), ("exact", (999, 999, 999)),
                 ("chop-only", (999, 0, 0))):
    if args is None:
        good = sum(1 for (k, n, A, dL, shL, ls, le2, dR, shR, rs,
                          re2, b2, corrval) in OPS
                   if (corrval - chopw(A, 67))
                   // (1 << (abs(A).bit_length() - 67)) == n)
        print(nm, good)
    else:
        print(nm, run(*args)[0])

# detail the best
good, woff, jL, jR = results[0][0], results[0][1], results[0][2], \
    results[0][3]
_, fam = run(woff, jL, jR)
print("\n== best predictor family breakdown (ncar, label) ==")
for kk in sorted(fam):
    print(kk, dict(fam[kk]))
