#!/usr/bin/env python3
# h984: STAGE-DISCARD FRACTIONS AS THE HIDDEN STATE.  The one
# feature class never swept: each upstream stage's own discarded
# field (mag^2 mod cut, sq^2 mod cut, Horner mul discards, RN64
# add guard states).  A hw stage rounding that deviates only at
# its own boundary produces rare sub-ulp67 shifts that surface
# exactly as the boundary-conditional +-1 terminal decisions.
# For every pinned op compute all stage fractions exactly and
# cross them against the magnitude-frame n_hw.
import sys
from collections import Counter, defaultdict

C = {
    1: (1, -68, (0x7 << 64) | 0xfffffffffffffffe),
    2: (0, -71, (0x5 << 64) | 0x5555555555554277),
    3: (1, -76, (0x5 << 64) | 0xb05b05b05a18a1ba),
    4: (0, -82, (0x6 << 64) | 0x80680675b559f2cf),
    5: (1, -88, (0x4 << 64) | 0x9f93af61f5349300),
    6: (0, -95, (0x4 << 64) | 0x7a4f2483514c1af8),
}

def mulfrac(asig, bsig, bits=67):
    p = asig * bsig
    sh = p.bit_length() - bits
    if sh <= 0:
        return (p << -sh, 0.0)
    return (p >> sh, (p & ((1 << sh) - 1)) / (1 << sh))

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
F = 60

def chopw(x, bits):
    m = -x if x < 0 else x
    w = m.bit_length()
    if w <= bits:
        return x
    return ((m >> (w - bits)) << (w - bits)) * (1 if x >= 0 else -1)

def addfrac(a, b, bits=64):
    # exact aligned sum, return (kept sig RN-rounded per model,
    # pre-round fraction of the discarded field, tie flag)
    sc = min(a[1], b[1])
    v = (-1) ** a[0] * (a[2] << (a[1] - sc)) \
        + (-1) ** b[0] * (b[2] << (b[1] - sc))
    s = 1 if v < 0 else 0
    m = abs(v)
    w = m.bit_length()
    sh = w - bits
    if sh <= 0:
        return (s, sc + sh, m << -sh, 0.0)
    top = m >> sh
    fr = (m & ((1 << sh) - 1)) / (1 << sh)
    g = (m >> (sh - 1)) & 1
    below = (m & ((1 << (sh - 1)) - 1)) != 0
    if g and (below or (top & 1)):
        top += 1
        if top == 1 << bits:
            top >>= 1
            sh += 1
    return (s, sc + sh, top, fr)

rows = []
for k in sorted(pin):
    t = feat[k]
    g = lambda col: t[ix[col]]
    n = pin[k]
    mage2, magsig = int(g("mage2")), int(g("magsig"), 16)
    # stage chain with fractions
    sqsig, q_sq = mulfrac(magsig, magsig)
    f4sig, q_f4 = mulfrac(sqsig, sqsig)
    m1, q_m1 = mulfrac(f4sig, C[5][2])
    sqe2 = 2 * mage2 + (magsig * magsig).bit_length() - 67
    f4e2 = 2 * sqe2 + (sqsig * sqsig).bit_length() - 67
    m1e2 = f4e2 + C[5][1] + (f4sig * C[5][2]).bit_length() - 67
    a1 = addfrac(C[3], (1, m1e2, m1))
    q_a1 = a1[3]
    m2, q_m2 = mulfrac(f4sig, a1[2])
    m2e2 = f4e2 + a1[1] + (f4sig * a1[2]).bit_length() - 67
    odd = addfrac(C[1], (a1[0], m2e2, m2))
    q_a2 = odd[3]
    e1, q_e1 = mulfrac(f4sig, C[6][2])
    e1e2 = f4e2 + C[6][1] + (f4sig * C[6][2]).bit_length() - 67
    b1 = addfrac(C[4], (0, e1e2, e1))
    q_b1 = b1[3]
    e2v, q_e2 = mulfrac(f4sig, b1[2])
    e2e2 = f4e2 + b1[1] + (f4sig * b1[2]).bit_length() - 67
    even = addfrac(C[2], (b1[0], e2e2, e2v))
    q_b2 = even[3]
    # terminal residue
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
    rAf = ((rA << F) >> eu) / (1 << F)
    nm = -n if A < 0 else n
    se, sig = k[1].split()
    xexp = (int(se, 16) & 0x7FFF) - 16383 - 63
    red = int((int(sig, 16), xexp) != (magsig, mage2))
    rows.append((k, nm, red, rAf, q_sq, q_f4, q_m1, q_a1, q_m2,
                 q_a2, q_e1, q_b1, q_e2, q_b2, int(g("act")),
                 int(g("low3"))))

# focus: TOP-LINE population (rA > 0.9): carry (nm=1) vs zero
top = [r for r in rows if r[3] > 0.90]
print("top-line population (rA>0.9):", len(top),
      dict(Counter(r[1] for r in top)))
print("\nmean stage fractions, carry vs zero (top-line):")
names = ("q_sq", "q_f4", "q_m1", "q_a1", "q_m2", "q_a2", "q_e1",
         "q_b1", "q_e2", "q_b2")
for i, nmv in enumerate(names):
    c1 = [r[4 + i] for r in top if r[1] == 1]
    c0 = [r[4 + i] for r in top if r[1] == 0]
    if c1 and c0:
        print("  %-5s carry %.4f (n=%d)   zero %.4f (n=%d)"
              % (nmv, sum(c1) / len(c1), len(c1),
                 sum(c0) / len(c0), len(c0)))
# combined predictor: does q_sq (sq's own discard) near 1 mark the
# carries at matched rA?  scatter table rA-band x q_sq-band
print("\ncarry rate by (rA band, q_sq band), top-line:")
tab = defaultdict(lambda: [0, 0])
for r in top:
    key = (round(r[3] * 64) / 64, round(r[4] * 4) / 4)
    tab[key][0] += r[1] == 1
    tab[key][1] += 1
for kk in sorted(tab):
    c, t2 = tab[kk]
    if t2 >= 3:
        print("  rA~%.4f q_sq~%.2f   %d/%d" % (kk[0], kk[1], c, t2))
