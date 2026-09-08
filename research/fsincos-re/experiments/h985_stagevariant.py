#!/usr/bin/env python3
# h985: stage-rounding variants chasing the q_f4 signal (h984:
# f4's own discard fraction separates carry/zero 0.390-vs-0.537,
# the strongest value-level single feature ever).  Recompute the
# whole chain under variant roundings for sq/f4/adds, score n_pred
# on all pinned ops under BOTH terminal treatments (chop-only,
# which is the 2,320 baseline to beat, and exact-tails).
import sys
from collections import Counter, defaultdict

CHOP, RN, ODDR, AWAY = 0, 1, 2, 3
C = {
    1: (1, -68, (0x7 << 64) | 0xfffffffffffffffe),
    2: (0, -71, (0x5 << 64) | 0x5555555555554277),
    3: (1, -76, (0x5 << 64) | 0xb05b05b05a18a1ba),
    4: (0, -82, (0x6 << 64) | 0x80680675b559f2cf),
    5: (1, -88, (0x4 << 64) | 0x9f93af61f5349300),
    6: (0, -95, (0x4 << 64) | 0x7a4f2483514c1af8),
}

def rnd(sign, mag, scale, bits, mode):
    if mag == 0:
        return (sign, 0, 0)
    w = mag.bit_length()
    sh = w - bits
    if sh <= 0:
        return (sign, scale + sh, mag << -sh)
    top = mag >> sh
    guard = (mag >> (sh - 1)) & 1
    below = (mag & ((1 << (sh - 1)) - 1)) != 0
    inc = 0
    if mode == RN:
        inc = guard and (below or (top & 1))
    elif mode == ODDR:
        if guard or below:
            top |= 1
    elif mode == AWAY:
        inc = guard or below
    if inc:
        top += 1
        if top == (1 << bits):
            top >>= 1
            sh += 1
    return (sign, scale + sh, top)

def wmul(a, b, bits, mode):
    return rnd(a[0] ^ b[0], a[2] * b[2], a[1] + b[1], bits, mode)

def wadd(a, b, bits, mode):
    sc = min(a[1], b[1])
    v = (-1) ** a[0] * (a[2] << (a[1] - sc)) \
        + (-1) ** b[0] * (b[2] << (b[1] - sc))
    s = 1 if v < 0 else 0
    return rnd(s, abs(v), sc, bits, mode)

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

def chopw(x, bits):
    m = -x if x < 0 else x
    w = m.bit_length()
    if w <= bits:
        return x
    return ((m >> (w - bits)) << (w - bits)) * (1 if x >= 0 else -1)

OPS = []
for k in sorted(pin):
    t = feat[k]
    g = lambda col: t[ix[col]]
    mag = (0, int(g("mage2")), int(g("magsig"), 16))
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
    OPS.append((k, pin[k], mag, payterm, A))

def run(sqm, f4m, adm, adb, term):
    good = 0
    for (k, n, mag, payterm, A) in OPS:
        sq = wmul(mag, mag, 67, sqm)
        f4 = wmul(sq, sq, 67, f4m)
        odd = wmul(f4, C[5], 67, CHOP)
        odd = wadd(C[3], odd, adb, adm)
        odd = wmul(f4, odd, 67, CHOP)
        odd = wadd(C[1], odd, adb, adm)
        even = wmul(f4, C[6], 67, CHOP)
        even = wadd(C[4], even, adb, adm)
        even = wmul(f4, even, 67, CHOP)
        even = wadd(C[2], even, adb, adm)
        if term == 0:      # chop-only: chop67 the two products
            L = wmul(sq, odd, 67, CHOP)
            R = wmul(f4, even, 67, CHOP)
            AP = ((-1) ** L[0] * (L[2] << (L[1] - B2))
                  + (-1) ** R[0] * (R[2] << (R[1] - B2)) + payterm)
        else:              # exact tails
            AP = ((-1) ** (sq[0] ^ odd[0]) * (sq[2] * odd[2]
                  << (sq[1] + odd[1] - B2))
                  + (-1) ** (f4[0] ^ even[0]) * (f4[2] * even[2]
                  << (f4[1] + even[1] - B2)) + payterm)
        ch = chopw(A, 67)
        ulp = 1 << (abs(A).bit_length() - 67)
        d = chopw(AP, 67) - ch
        npred = d // ulp if d % ulp == 0 else 99
        good += npred == n
    return good

MODES = {"c": CHOP, "r": RN, "o": ODDR, "a": AWAY}
print("pinned:", len(OPS))
res = []
for sqn, sqm in (("c", CHOP), ("r", RN)):
    for f4n, f4m in (("c", CHOP), ("r", RN), ("o", ODDR),
                     ("a", AWAY)):
        for adn, adm, adb in (("r64", RN, 64), ("r65", RN, 65),
                              ("c64", CHOP, 64), ("o64", ODDR, 64)):
            for term in (0, 1):
                g0 = run(sqm, f4m, adm, adb, term)
                res.append((g0, sqn, f4n, adn, term))
res.sort(reverse=True)
for g0, sqn, f4n, adn, term in res:
    tag = " <-- SHIPPED" if (sqn, f4n, adn) == ("c", "c", "r64") \
        else ""
    print("sq=%s f4=%s add=%s term=%s  %d%s"
          % (sqn, f4n, adn, "chop" if term == 0 else "exact", g0,
             tag))
