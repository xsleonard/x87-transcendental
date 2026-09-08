#!/usr/bin/env python3
# h983: EXACT WINDOW-ADDER FIT.  The h982 microscope (magnitude
# frame: A<0 always) shows hw's terminal deviations are a carry at
# the top line (residue rA just below 1 ulp67, sums 0x100+ — on
# act1 where the model has NO adder at all) and a borrow at the low
# line (rA just above 0, sums ~0x8), with low3 as an addend and NO
# deep-tail sensitivity.  Hypothesis: hw's terminal applies
#   mag+1  iff  rA60 + low3*2^(52+j) + extras >= (1 + t/2^12)*2^60
#   mag-1  iff  rA60 + low3*2^(52+j) + extras <  (b/2^12)*2^60
# a fine-grained window adder (the model's R88 = its coarse act0
# shadow).  Enumerate j, addend sets, thresholds; DISCOVERY =
# pinned unreduced ops, VALIDATION = pinned reduced ops.
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
F = 60

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
    rA60 = (rA << F) >> eu
    # magnitude-frame n: for A<0, value-frame -1 == magnitude +1
    nm = -n if A < 0 else n
    se, sig = k[1].split()
    xexp = (int(se, 16) & 0x7FFF) - 16383 - 63
    red = int((int(sig, 16), xexp)
              != (int(g("magsig"), 16), int(g("mage2"))))
    rows.append((k, nm, red, rA60, int(g("low3")), int(g("ud")),
                 int(g("u5d")), int(g("rud")), int(g("rsh")),
                 int(g("act")), int(g("d")), int(g("me2")),
                 int(g("g")), int(g("sum8"))))

disc = [r for r in rows if r[2] == 0]
valn = [r for r in rows if r[2] == 1]
print("disc:", len(disc), dict(Counter(r[1] for r in disc)),
      " val:", len(valn), dict(Counter(r[1] for r in valn)))

U = 1 << F

def fit(rowset, j, ju, use_ud, tshift):
    # returns (ok, wrong) for carry iff W >= 2^60 + thi, borrow iff
    # W < blo, thresholds FIT per (act) on the rowset itself is
    # cheating — instead thresholds are parameters: enumerate a few
    pass

def W_of(r, j, use_ud, ju):
    (k, nm, red, rA60, low3, ud, u5d, rud, rsh, act, d, me2, gg,
     s8) = r
    W = rA60 + (low3 << (52 + j))
    if use_ud:
        W += ud << (52 + ju)
    return W

def score(rowset, j, use_ud, ju, thi, blo):
    ok = 0
    for r in rowset:
        W = W_of(r, j, use_ud, ju)
        npred = 1 if W >= U + thi else (-1 if W < blo else 0)
        ok += npred == r[1]
    return ok

results = []
for j in (0, 1, 2, 3):
    for use_ud, ju in ((0, 0), (1, 0), (1, 1), (1, 2)):
        for thi_k in (-16, -8, -4, -2, -1, 0, 1, 2, 4, 8, 16):
            thi = thi_k << 48
            for blo_k in (0, 1, 2, 4, 8, 16, 32):
                blo = blo_k << 48
                g0 = score(disc, j, use_ud, ju, thi, blo)
                results.append((g0, j, use_ud, ju, thi_k, blo_k))
results.sort(reverse=True)
print("\n== top window rules (discovery) ==")
seen = 0
for g0, j, use_ud, ju, thi_k, blo_k in results[:12]:
    gv = score(valn, j, use_ud, ju, thi_k << 48, blo_k << 48)
    print("j=%d ud=%d ju=%d thi=%d blo=%d   disc %d/%d  VAL %d/%d"
          % (j, use_ud, ju, thi_k, blo_k, g0, len(disc), gv,
             len(valn)))

# per-act split of the best rule's errors
g0, j, use_ud, ju, thi_k, blo_k = results[0]
thi, blo = thi_k << 48, blo_k << 48
err = Counter()
for r in disc + valn:
    W = W_of(r, j, use_ud, ju)
    npred = 1 if W >= U + thi else (-1 if W < blo else 0)
    if npred != r[1]:
        err[("act%d" % r[9], "n%+d" % r[1], "p%+d" % npred,
             "red%d" % r[2])] += 1
print("\nbest-rule errors (all pinned):")
for kk, n in err.most_common(14):
    print("  ", kk, n)
# W distribution near the top line for carry-vs-not (all pinned)
print("\n== W histogram near the top line (all pinned, "
      "carry-labeled vs not) ==")
hi = Counter()
for r in disc + valn:
    W = W_of(r, results[0][1], results[0][2], results[0][3])
    dW = (W - U) / (1 << 52)
    if -8 <= dW <= 8:
        hi[("carry" if r[1] == 1 else ("mag-1" if r[1] == -1
            else "zero"), round(dW * 4) / 4)] += 1
for kk in sorted(hi):
    print("  ", kk, hi[kk])
