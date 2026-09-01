#!/usr/bin/env python3
# h979: THE UPSTREAM-GUARD SEARCH.  Reconstruct the cosine
# polynomial chain (sq=chop67(mag^2), f4=chop67(sq^2), Horner
# odd/even: products chop67 + adds RN64, constants P5C6_1..6)
# in exact python from the banked mag, VALIDATE the shipped
# parameterization against the banked sq/f4/odd/even of all
# 8,315 census ops, then sweep per-stage guard hypotheses
# (widths/modes) scored on the pinned n_hw decisions — the first
# width-style search ever run against boundary-pinned integer
# ground truth instead of 1e-8 final-output rates.
import sys
from collections import Counter, defaultdict

CHOP, RN, ODD = 0, 1, 2

C = {
    1: (1, -68, (0x7 << 64) | 0xfffffffffffffffe),
    2: (0, -71, (0x5 << 64) | 0x5555555555554277),
    3: (1, -76, (0x5 << 64) | 0xb05b05b05a18a1ba),
    4: (0, -82, (0x6 << 64) | 0x80680675b559f2cf),
    5: (1, -88, (0x4 << 64) | 0x9f93af61f5349300),
    6: (0, -95, (0x4 << 64) | 0x7a4f2483514c1af8),
}

def rnd(sign, mag, scale, bits, mode):
    # value = (-1)^sign * mag * 2^scale, normalize to `bits` bits
    if mag == 0:
        return (sign, 0, 0)
    if bits >= 900:
        return (sign, scale, mag)          # exact carrier
    w = mag.bit_length()
    sh = w - bits
    if sh <= 0:
        return (sign, scale + sh, mag << -sh)
    top = mag >> sh
    guard = (mag >> (sh - 1)) & 1
    below = (mag & ((1 << (sh - 1)) - 1)) != 0
    if mode == ODD:
        if guard or below:
            top |= 1
    elif mode == RN and guard and (below or (top & 1)):
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

def chain(mag, P):
    (wsq, msq), (wf4, mf4), (wpm, mpm), (wad, mad) = P
    sq = wmul(mag, mag, wsq, msq)
    f4 = wmul(sq, sq, wf4, mf4)
    odd = wmul(f4, C[5], wpm, mpm)
    odd = wadd(C[3], odd, wad, mad)
    odd = wmul(f4, odd, wpm, mpm)
    odd = wadd(C[1], odd, wad, mad)
    even = wmul(f4, C[6], wpm, mpm)
    even = wadd(C[4], even, wad, mad)
    even = wmul(f4, even, wpm, mpm)
    even = wadd(C[2], even, wad, mad)
    return sq, f4, odd, even

SHIPPED = ((67, CHOP), (67, CHOP), (67, CHOP), (64, RN))

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

# ---- validation of the shipped parameterization ----
bad = Counter()
OPS = []
for k in sorted(feat):
    t = feat[k]
    g = lambda col: t[ix[col]]
    mag = (0, int(g("mage2")), int(g("magsig"), 16))
    sq, f4, odd, even = chain(mag, SHIPPED)
    ok = (sq == (0, int(g("mule2")), int(g("mulsig"), 16))
          and f4 == (0, int(g("f4e2")), int(g("f4sig"), 16))
          and odd[1:] == (int(g("lfe2")), int(g("lfsig"), 16))
          and even[1:] == (int(g("rfe2")), int(g("rfsig"), 16)))
    if not ok:
        bad[(sq[1:] == (int(g("mule2")), int(g("mulsig"), 16)),
             f4[1:] == (int(g("f4e2")), int(g("f4sig"), 16)),
             odd[1:] == (int(g("lfe2")), int(g("lfsig"), 16)),
             even[1:] == (int(g("rfe2")), int(g("rfsig"), 16)))] += 1
        continue
    # reduced-arg flag: mag value vs |input| value
    se, sig = g("op").split() if False else (None, None)
    ins_se, ins_sig = k[1].split()
    xexp = (int(ins_se, 16) & 0x7FFF) - 16383 - 63
    reduced = int((int(ins_sig, 16), xexp)
                  != (int(g("magsig"), 16), int(g("mage2"))))
    pay = int(g("pay2")) if g("pay2") not in ("-",) else 0
    ls, rs = int(g("leftsign")), int(g("rightsign"))
    le2, re2 = int(g("lefte2")), int(g("righte2"))
    b2 = min(le2, re2, le2 - 8) - 140
    A = (-1) ** ls * (int(g("leftsig"), 16) << (le2 - b2)) \
        + (-1) ** rs * (int(g("rightsig"), 16) << (re2 - b2))
    payterm = 0
    if pay:
        payterm = (-1) ** (ls ^ (pay < 0)) * (abs(pay)
                                              << (le2 - 8 - b2))
        A += payterm
    OPS.append((k, mag, reduced, A, payterm, b2))
print("validation: %d/%d ops match banked sq/f4/odd/even"
      % (len(OPS), len(feat)))
for kk, n in bad.most_common(5):
    print("   mismatch(sq,f4,odd,even ok-flags):", kk, n)
print("reduced:", sum(o[2] for o in OPS), "unreduced:",
      len(OPS) - sum(o[2] for o in OPS))
pinned = [(o, nhw[o[0]]) for o in OPS if o[0] in nhw]
print("pinned in validated set:", len(pinned))

def chopw(x, bits):
    m = -x if x < 0 else x
    w = m.bit_length()
    if w <= bits:
        return x
    return ((m >> (w - bits)) << (w - bits)) * (1 if x >= 0 else -1)

def score(P, detail=False):
    good = wrong = skip = 0
    fam = Counter()
    for (k, mag, reduced, A, payterm, b2), n in pinned:
        sq, f4, odd, even = chain(mag, P)
        # terminal-exact sum of the stage carriers (+ payload)
        AP = ((-1) ** (sq[0] ^ odd[0]) * (sq[2] * odd[2]
              << (sq[1] + odd[1] - b2))
              + (-1) ** (f4[0] ^ even[0]) * (f4[2] * even[2]
              << (f4[1] + even[1] - b2))
              + payterm)
        ch = chopw(A, 67)
        ulp = 1 << (abs(A).bit_length() - 67)
        d = chopw(AP, 67) - ch
        if d % ulp:
            skip += 1
            continue
        npred = d // ulp
        if npred == n:
            good += 1
        else:
            wrong += 1
            if detail:
                fam[(lab[k], "red%d" % reduced, "n%+d" % n,
                     "p%+d" % npred)] += 1
    return good, wrong, skip, fam

g0, w0, s0, _ = score(SHIPPED)
print("\nshipped params (terminal-exact tails):", g0, "wrong:",
      w0, "skip:", s0)

# ceteris-paribus sweeps
def show(name, P):
    g, w, s, _ = score(P)
    print("%-34s good %d  wrong %d  skip %d" % (name, g, w, s))

print("\n== sq/f4 width sweep ==")
for wb in (66, 68, 69, 70, 72, 999):
    show("wsq=%d" % wb, ((wb, CHOP), (67, CHOP), (67, CHOP),
                         (64, RN)))
    show("wf4=%d" % wb, ((67, CHOP), (wb, CHOP), (67, CHOP),
                         (64, RN)))
print("== horner mul width ==")
for wb in (66, 68, 69, 70, 72, 999):
    show("wpm=%d" % wb, ((67, CHOP), (67, CHOP), (wb, CHOP),
                         (64, RN)))
print("== horner add width/mode ==")
for wb, md, nm in ((63, RN, "63rn"), (65, RN, "65rn"),
                   (66, RN, "66rn"), (67, RN, "67rn"),
                   (64, CHOP, "64c"), (67, CHOP, "67c"),
                   (68, RN, "68rn"), (999, RN, "exact"),
                   (64, ODD, "64odd"), (67, ODD, "67odd")):
    show("wad=%s" % nm, ((67, CHOP), (67, CHOP), (67, CHOP),
                         (wb, md)))
print("== everything exact ==")
show("all-exact", ((999, 0), (999, 0), (999, 0), (999, 0)))
