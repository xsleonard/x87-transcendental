#!/usr/bin/env python3
# h982: TRUNCATED-COMPARATOR SEARCH on the cleanest population the
# campaign has ever had: pinned unreduced ops (mag == input
# exactly, all stages validated) as DISCOVERY, pinned reduced ops
# as TRANSFER VALIDATION.  Rule families over exact per-op
# fractions (units of ulp67, 60 fractional bits):
#   borrow  <=> cmp_j(FL, rA):   (FL >> j) > (rA >> j)   etc.
#   carry   <=> cmp_j(FR, ulp - rA)
# with variants folding the right tail into rA.  Also dumps the
# unreduced n!=0 microscope table for eyeballing.
import sys
from collections import Counter, defaultdict

feat = {}
for ln in open("h970_features.tsv"):
    t = ln.rstrip("\n").split("\t")
    if t[0] == "insn":
        ix = {c: i for i, c in enumerate(t)}
        continue
    feat[(t[0], t[1])] = t
pin = {}
lab = {}
for ln in open("h975_nhw.tsv"):
    t = ln.rstrip("\n").split("\t")
    if t[0] == "insn":
        jx = {c: i for i, c in enumerate(t)}
        continue
    if t[jx["pinned"]] == "1":
        pin[(t[0], t[1])] = int(t[jx["nset"]])
        lab[(t[0], t[1])] = t[jx["lab"]]

B2 = -1400
F = 60          # fractional bits for ulp67 units

def chopw(x, bits):
    m = -x if x < 0 else x
    w = m.bit_length()
    if w <= bits:
        return x
    return ((m >> (w - bits)) << (w - bits)) * (1 if x >= 0 else -1)

rows = []
for k in sorted(pin):
    t = feat[k]
    g = lambda col: t[ix[col]]
    n = pin[k]
    sqs, sqe = int(g("mulsig"), 16), int(g("mule2"))
    ods, ode = int(g("lfsig"), 16), int(g("lfe2"))
    f4s, f4e = int(g("f4sig"), 16), int(g("f4e2"))
    evs, eve = int(g("rfsig"), 16), int(g("rfe2"))
    ls, rs = int(g("leftsign")), int(g("rightsign"))
    le2, re2 = int(g("lefte2")), int(g("righte2"))
    pay = int(g("pay2")) if g("pay2") not in ("-",) else 0
    A = (-1) ** ls * (int(g("leftsig"), 16) << (le2 - B2)) \
        + (-1) ** rs * (int(g("rightsig"), 16) << (re2 - B2))
    if pay:
        A += (-1) ** (ls ^ (pay < 0)) * (abs(pay) << (le2 - 8 - B2))
    ch = chopw(A, 67)
    eu = abs(A).bit_length() - 67          # ulp67 exponent (rel B2)
    rA = A - ch                            # >= 0 if A > 0
    if A < 0:
        rA = ch - A                        # magnitude-frame residue
    rA60 = (rA << F) >> eu
    PL = sqs * ods
    shL = PL.bit_length() - 67
    dL = PL & ((1 << shL) - 1)
    eLd = sqe + ode - B2                   # weight of dL lsb (rel B2)
    FL60 = (dL << F) >> (eu - eLd) if eu >= eLd else \
        (dL << (F + eLd - eu))
    PR = f4s * evs
    shR = PR.bit_length() - 67
    dR = PR & ((1 << shR) - 1)
    eRd = f4e + eve - B2
    FR60 = (dR << F) >> (eu - eRd) if eu >= eRd else \
        (dR << (F + eRd - eu))
    se, sig = k[1].split()
    xexp = (int(se, 16) & 0x7FFF) - 16383 - 63
    red = int((int(sig, 16), xexp)
              != (int(g("magsig"), 16), int(g("mage2"))))
    # left tail is a borrow iff ls==1 in the A>0 frame; normalize:
    # sL_eff = does the left tail pull the MAGNITUDE down?
    sL_eff = 1 if (ls == 1) == (A > 0) else 0
    sR_eff = 1 if (rs == 1) == (A > 0) else 0
    rows.append((k, n, red, sL_eff, sR_eff, rA60, FL60, FR60,
                 int(g("low3")), int(g("rsh")), int(g("rud")),
                 int(g("ud")), g("act"), g("sum8"), g("d"),
                 g("me2"), g("g")))

disc = [r for r in rows if r[2] == 0]
valn = [r for r in rows if r[2] == 1]
print("discovery (unreduced) pinned:", len(disc),
      " validation (reduced):", len(valn))
print("discovery n distribution:",
      dict(Counter(r[1] for r in disc)))

U = 1 << F

def predict(r, j, useR, cmpop):
    (k, n, red, sLe, sRe, rA60, FL60, FR60, low3, rsh, rud, ud,
     act, s8, d, me2, gg) = r
    down = FL60 if sLe else 0
    up = FL60 if not sLe else 0
    if useR:
        if sRe:
            down += FR60
        else:
            up += FR60
    net = down - up
    m = 1 << j
    borrow = ((net // m) > (rA60 // m)) if cmpop == ">" else \
        ((net // m) >= (rA60 // m) and net > 0)
    carry = (((-net) // m) >= ((U - rA60) // m)) if net < 0 else False
    if borrow:
        return -1
    if carry:
        return 1
    return 0

best = []
for j in range(0, 61, 2):
    for useR in (0, 1):
        for cmpop in (">", ">="):
            gd = sum(1 for r in disc
                     if predict(r, j, useR, cmpop) == r[1])
            best.append((gd, j, useR, cmpop))
best.sort(reverse=True)
print("\n== discovery-set top comparator rules ==")
for gd, j, useR, cmpop in best[:8]:
    gv = sum(1 for r in valn if predict(r, j, useR, cmpop) == r[1])
    print("j=%-3d useR=%d op%s  disc %d/%d  VAL %d/%d"
          % (j, useR, cmpop, gd, len(disc), gv, len(valn)))
base = sum(1 for r in disc if r[1] == 0)
print("baseline always-0: disc %d/%d" % (base, len(disc)))

print("\n== microscope: unreduced n!=0 ops ==")
print("n  sL sR   rA/ulp    FL/ulp    FR/ulp   low3 rsh rud ud"
      "  act sum8 d me2 g")
for r in sorted(disc, key=lambda r: (r[1], -r[5])):
    if r[1] == 0:
        continue
    (k, n, red, sLe, sRe, rA60, FL60, FR60, low3, rsh, rud, ud,
     act, s8, d, me2, gg) = r
    print("%+d  %d  %d  %8.5f  %8.5f  %8.5f   %d  %d  %d  %d"
          "   %s %s %s %s %s"
          % (n, sLe, sRe, rA60 / U, FL60 / U, FR60 / U, low3,
             rsh, rud, ud, act, s8, d, me2, gg))
