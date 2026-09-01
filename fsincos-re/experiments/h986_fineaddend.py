#!/usr/bin/env python3
# h986: THE FINE-ADDEND RULE.  Hypothesis: hw's terminal window
# adder uses sq's low K bits (not just low3):
#   carry(mag+1)  iff  rA + (sq mod 2^K)/2^(5+K) >= th_hi
#   borrow(mag-1) iff  rA + (sq mod 2^K)/2^(5+K) <  th_lo
# (K=3 with th_hi=1, coarse view = R88's top8+low3>=0x100; the low
# line ~ 8/256 = 2^-5 explains the second ladder).  Exact rational
# comparisons; DISCOVERY = pinned unreduced, VALIDATION = reduced.
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
for ln in open("h975_nhw.tsv"):
    t = ln.rstrip("\n").split("\t")
    if t[0] == "insn":
        jx = {c: i for i, c in enumerate(t)}
        continue
    if t[jx["pinned"]] == "1":
        pin[(t[0], t[1])] = int(t[jx["nset"]])

B2 = -1400
FB = 80                      # fraction bits for exact comparisons

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
    sqsig = int(g("mulsig"), 16)
    ls, rs = int(g("leftsign")), int(g("rightsign"))
    le2, re2 = int(g("lefte2")), int(g("righte2"))
    pay = int(g("pay2")) if g("pay2") not in ("-",) else 0
    A = (-1) ** ls * (int(g("leftsig"), 16) << (le2 - B2)) \
        + (-1) ** rs * (int(g("rightsig"), 16) << (re2 - B2))
    if pay:
        A += (-1) ** (ls ^ (pay < 0)) * (abs(pay) << (le2 - 8 - B2))
    ch = chopw(A, 67)
    eu = abs(A).bit_length() - 67
    rA = (A - ch) if A > 0 else (ch - A)
    rAF = (rA << FB) >> eu          # rA in units of 2^-FB ulp67
    nm = -n if A < 0 else n
    se, sig = k[1].split()
    xexp = (int(se, 16) & 0x7FFF) - 16383 - 63
    red = int((int(sig, 16), xexp)
              != (int(g("magsig"), 16), int(g("mage2"))))
    rows.append((k, nm, red, rAF, sqsig, int(g("act")),
                 int(g("low3"))))

disc = [r for r in rows if r[2] == 0]
valn = [r for r in rows if r[2] == 1]
U = 1 << FB

def W_of(r, K):
    addend = (r[4] & ((1 << K) - 1)) << (FB - 5 - K)
    return r[3] + addend

def score(rowset, K, th_hi, th_lo):
    ok = 0
    for r in rowset:
        W = W_of(r, K)
        npred = 1 if W >= th_hi else (-1 if W < th_lo else 0)
        ok += npred == r[1]
    return ok

print("disc:", len(disc), " val:", len(valn))
res = []
for K in range(3, 22):
    # threshold sweep around 1 and around 2^-5
    for hik in range(-12, 13, 2):
        th_hi = U + (hik << (FB - 10))
        for lok in range(-8, 9, 2):
            th_lo = (1 << (FB - 5)) + (lok << (FB - 10))
            g0 = score(disc, K, th_hi, th_lo)
            res.append((g0, K, hik, lok))
res.sort(reverse=True)
print("\n== top fine-addend rules ==")
shown = set()
for g0, K, hik, lok in res[:400]:
    if K in shown:
        continue
    shown.add(K)
    gv = score(valn, K, (1 << FB) + (hik << (FB - 10)),
               (1 << (FB - 5)) + (lok << (FB - 10)))
    print("K=%-3d hik=%+d lok=%+d  disc %d/%d  VAL %d/%d"
          % (K, hik, lok, g0, len(disc), gv, len(valn)))
    if len(shown) >= 10:
        break

# oracle upper bound: per-K, best achievable with ANY monotone
# threshold pair fit on the COMBINED set (overfit ceiling)
print("\n== W separation quality per K (combined, top line) ==")
for K in (3, 6, 8, 10, 12, 14, 16, 20):
    pts = sorted((W_of(r, K), r[1]) for r in rows
                 if r[3] > (9 << (FB - 4)) // 9)   # rA>~0.56
    # count inversions at the top line: carries below zeros
    best = 0
    tot1 = sum(1 for _, l in pts if l == 1)
    tot0 = sum(1 for _, l in pts if l == 0)
    c1 = 0
    z0 = 0
    bestacc = 0
    for w, l in pts:
        if l == 1:
            c1 += 1
        elif l == 0:
            z0 += 1
        acc = (tot1 - c1) + z0
        bestacc = max(bestacc, acc)
    print("K=%-3d top-line ops %d (carry %d, zero %d): best "
          "single-threshold acc %d" % (K, len(pts), tot1 + tot0,
                                       tot1, bestacc))
