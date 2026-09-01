#!/usr/bin/env python3
# h981: (a) the FULL-EXACT pipeline crossing decision (every stage
# exact rational from banked mag; only the terminal 67-chop lattice
# compared) scored on pinned n_hw and cross-tabbed against the
# TOOK/IGN borrow split; (b) one-port operand-truncation variants
# of the terminal products (the mechanism the model already proved
# for the sine f4: square64.sig &= ~7).
import sys
from collections import Counter, defaultdict

CHOP, RN = 0, 1
C = {
    1: (1, -68, (0x7 << 64) | 0xfffffffffffffffe),
    2: (0, -71, (0x5 << 64) | 0x5555555555554277),
    3: (1, -76, (0x5 << 64) | 0xb05b05b05a18a1ba),
    4: (0, -82, (0x6 << 64) | 0x80680675b559f2cf),
    5: (1, -88, (0x4 << 64) | 0x9f93af61f5349300),
    6: (0, -95, (0x4 << 64) | 0x7a4f2483514c1af8),
}
B2 = -1400

def val(w):
    return (-1) ** w[0] * (w[2] << (w[1] - B2))

def exmul(a, b):
    return (a[0] ^ b[0], a[1] + b[1], a[2] * b[2])

def exadd(a, b):
    sc = min(a[1], b[1])
    v = (-1) ** a[0] * (a[2] << (a[1] - sc)) \
        + (-1) ** b[0] * (b[2] << (b[1] - sc))
    return (1 if v < 0 else 0, sc, abs(v))

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

def chopw(x, bits):
    m = -x if x < 0 else x
    w = m.bit_length()
    if w <= bits:
        return x
    return ((m >> (w - bits)) << (w - bits)) * (1 if x >= 0 else -1)

cnt = Counter()
cross = Counter()
port = defaultdict(Counter)
for k in sorted(nhw):
    t = feat[k]
    g = lambda col: t[ix[col]]
    n = nhw[k]
    mag = (0, int(g("mage2")), int(g("magsig"), 16))
    sqB = (0, int(g("mule2")), int(g("mulsig"), 16))
    oddB = (1, int(g("lfe2")), int(g("lfsig"), 16))
    f4B = (0, int(g("f4e2")), int(g("f4sig"), 16))
    evenB = (0, int(g("rfe2")), int(g("rfsig"), 16))
    ls, rs = int(g("leftsign")), int(g("rightsign"))
    le2, re2 = int(g("lefte2")), int(g("righte2"))
    pay = int(g("pay2")) if g("pay2") not in ("-",) else 0
    A = (-1) ** ls * (int(g("leftsig"), 16) << (le2 - B2)) \
        + (-1) ** rs * (int(g("rightsig"), 16) << (re2 - B2))
    payterm = 0
    if pay:
        payterm = (-1) ** (ls ^ (pay < 0)) * (abs(pay)
                                              << (le2 - 8 - B2))
        A += payterm
    ch = chopw(A, 67)
    ulp = 1 << (abs(A).bit_length() - 67)
    # exact-tail (terminal only) for the TOOK/IGN frame
    shL = (sqB[2] * oddB[2]).bit_length() - 67
    dL = (sqB[2] * oddB[2]) & ((1 << shL) - 1)
    shR = (f4B[2] * evenB[2]).bit_length() - 67
    dR = (f4B[2] * evenB[2]) & ((1 << shR) - 1)
    TLv = (-1) ** ls * (dL << (sqB[1] + oddB[1] - B2))
    TRv = (-1) ** rs * (dR << (f4B[1] + evenB[1] - B2))
    dex = chopw(A + TLv + TRv, 67) - ch
    nexact = dex // ulp if dex % ulp == 0 else 99
    # full-exact pipeline from banked mag
    sqE = exmul(mag, mag)
    f4E = exmul(sqE, sqE)
    oddE = exadd(C[1], exmul(f4E, exadd(C[3], exmul(f4E, C[5]))))
    evenE = exadd(C[2], exmul(f4E, exadd(C[4], exmul(f4E, C[6]))))
    AE = val(exmul(sqE, oddE)) + val(exmul(f4E, evenE)) + payterm
    dfe = chopw(AE, 67) - ch
    nfull = dfe // ulp if dfe % ulp == 0 else 99
    cnt["full-exact", nfull == n] += 1
    # the borrow-opportunity cross-tab
    cs, ce2, csig = 0, 0, 0
    # ncar from corr not needed: opportunity frame from nexact vs n
    if nexact == -1 and n in (0, -1):
        verdict = "TOOK" if n == -1 else "IGN"
        cross[(verdict, "full%+d" % nfull if nfull != 99
               else "full?")] += 1
    # port variants on terminal products (banked stage outputs)
    for pname, msq, modd, mf4, meven in (
            ("sq~7", ~7, ~0, ~0, ~0), ("odd~7", ~0, ~7, ~0, ~0),
            ("f4~7", ~0, ~0, ~7, ~0), ("even~7", ~0, ~0, ~0, ~7),
            ("sq,f4~7", ~7, ~0, ~7, ~0),
            ("odd,even~7", ~0, ~7, ~0, ~7),
            ("all~7", ~7, ~7, ~7, ~7)):
        KL = (sqB[2] & msq) * (oddB[2] & modd)
        KR = (f4B[2] & mf4) * (evenB[2] & meven)
        AP = ((-1) ** ls * (KL << (sqB[1] + oddB[1] - B2))
              + (-1) ** rs * (KR << (f4B[1] + evenB[1] - B2))
              + payterm)
        dp = chopw(AP, 67) - ch
        npp = dp // ulp if dp % ulp == 0 else 99
        port[pname][npp == n] += 1

print("== full-exact pipeline vs pinned n_hw ==")
print(dict(cnt))
print("\n== borrow-opportunity (nexact=-1) vs full-exact ==")
for kk in sorted(cross):
    print(kk, cross[kk])
print("\n== port variants ==")
for pname in sorted(port):
    d = port[pname]
    print("%-12s good %d wrong %d" % (pname, d[True], d[False]))
