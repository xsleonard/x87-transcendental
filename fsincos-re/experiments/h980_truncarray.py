#!/usr/bin/env python3
# h980: THE TRUNCATED-MULTIPLIER-ARRAY HYPOTHESIS.  If hw computes
# the terminal products (left = sq x odd, right = f4 x even) with a
# truncated partial-product array — only columns >= c_abs summed,
# c_abs FIXED relative to the operand alignment (not the product
# msb; product width 130-vs-131 = rsh63/64 then shifts the cut
# against the kept-67 line by one bit, explaining the rsh
# correlation) — then the array result is
#     K = a*b - S,   S = sum of dropped pp bits = sum_{i+j<c} a_i b_j 2^(i+j)
# i.e. chop-exact MINUS the dropped columns' would-be carry, an
# operand-dependent integer deficit.  Optional compensation adds a
# constant at the cut column.  n_pred scored on pinned n_hw.
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

OPS = []
for k in sorted(nhw):
    t = feat[k]
    g = lambda col: t[ix[col]]
    sq = (int(g("mule2")), int(g("mulsig"), 16))
    odd = (int(g("lfe2")), int(g("lfsig"), 16))
    f4 = (int(g("f4e2")), int(g("f4sig"), 16))
    even = (int(g("rfe2")), int(g("rfsig"), 16))
    ls, rs = int(g("leftsign")), int(g("rightsign"))
    le2, re2 = int(g("lefte2")), int(g("righte2"))
    pay = int(g("pay2")) if g("pay2") not in ("-",) else 0
    b2 = min(le2, re2, le2 - 8) - 140
    A = (-1) ** ls * (int(g("leftsig"), 16) << (le2 - b2)) \
        + (-1) ** rs * (int(g("rightsig"), 16) << (re2 - b2))
    payterm = 0
    if pay:
        payterm = (-1) ** (ls ^ (pay < 0)) * (abs(pay)
                                              << (le2 - 8 - b2))
        A += payterm
    OPS.append((k, nhw[k], sq, odd, f4, even, ls, rs, payterm,
                b2, A))
print("pinned ops:", len(OPS))

def dropped_sum(a, b, c):
    # S = sum over i+j < c of a_i b_j 2^(i+j)
    #   = sum_i a_i * (b mod 2^(c-i)) * 2^i   for i < c
    S = 0
    aa = a
    i = 0
    while aa and i < c:
        if aa & 1:
            m = c - i
            S += (b & ((1 << m) - 1)) << i
        aa >>= 1
        i += 1
    return S

def chopw(x, bits):
    m = -x if x < 0 else x
    w = m.bit_length()
    if w <= bits:
        return x
    return ((m >> (w - bits)) << (w - bits)) * (1 if x >= 0 else -1)

def score(cL, cR, comp, detail=False):
    good = wrong = 0
    fam = Counter()
    for (k, n, sq, odd, f4, even, ls, rs, payterm, b2, A) in OPS:
        PL = sq[1] * odd[1]
        SL = dropped_sum(sq[1], odd[1], cL)
        KL = PL - SL + (comp << (cL - 1) if cL > 0 and comp else 0)
        PR = f4[1] * even[1]
        SR = dropped_sum(f4[1], even[1], cR)
        KR = PR - SR + (comp << (cR - 1) if cR > 0 and comp else 0)
        AP = ((-1) ** ls * (KL << (sq[0] + odd[0] - b2))
              + (-1) ** rs * (KR << (f4[0] + even[0] - b2))
              + payterm)
        ch = chopw(A, 67)
        ulp = 1 << (abs(A).bit_length() - 67)
        d = chopw(AP, 67) - ch
        npred = d // ulp if d % ulp == 0 else 99
        if npred == n:
            good += 1
        else:
            wrong += 1
            if detail:
                fam[(lab[k], "n%+d" % n,
                     "p%s" % ("?" if npred == 99 else
                              "%+d" % npred))] += 1
    return good, wrong, fam

print("\n== equal-cut sweep (cL == cR == c), comp in {0, half} ==")
best = (0, None)
for c in range(52, 70):
    for comp in (0, 1):
        g, w, _ = score(c, c, comp)
        tag = ""
        if g > best[0]:
            best = (g, (c, c, comp))
            tag = "  <-- best"
        print("c=%d comp=%d  good %d  wrong %d%s" % (c, comp, g, w,
                                                     tag))
print("\n== independent cuts around the best ==")
c0 = best[1][0]
for cL in range(c0 - 3, c0 + 4):
    for cR in range(c0 - 3, c0 + 4):
        for comp in (0, 1):
            g, w, _ = score(cL, cR, comp)
            if g > best[0]:
                best = (g, (cL, cR, comp))
                print("cL=%d cR=%d comp=%d  good %d  <-- best" %
                      (cL, cR, comp, g))
print("\nBEST:", best)
g, w, fam = score(*best[1], detail=True)
print("breakdown of wrong:")
for kk, n in fam.most_common(15):
    print("  ", kk, n)
