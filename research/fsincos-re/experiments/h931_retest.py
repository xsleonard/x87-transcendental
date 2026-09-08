#!/usr/bin/env python3
# h931 step 3: THE RETEST BATTERY at the grown census.  Split:
# train = everything analysis has ever touched (seeds <= 94639),
# holdout = the h929 chain's never-touched seeds (>= 94640).
# Tests, in pre-registered order:
#   T1  f4.b65 — the h928 sign-consistent runner-up (single test,
#       conditioned on (act, sum, low3, grl), alpha 0.05).
#   T2  full marginal raw-bit sweep, Bonferroni over informative
#       positions, holdout confirmation of the train top-40.
#   T3  fully-conditioned raw-bit sweep (act, sum, low3, grl).
#   T4  h930 borrow/encoding features conditioned on
#       (act, sum, low3, dist, mule2).
# Any survivor => a new vocabulary; none => the park verdict at
# the grown power.
import math, sys
import numpy as np
from collections import defaultdict

HEX = ["mulsig", "lfsig", "rfsig", "f4sig", "leftsig", "rightsig", "d60"]

rows = []
with open("h931_frames.tsv") as f:
    hdr = f.readline().rstrip("\n").split("\t")
    for ln in f:
        t = ln.rstrip("\n").split("\t")
        if len(t) == len(hdr):
            rows.append(dict(zip(hdr, t)))
N = len(rows)
y = np.array([1 if r["lab"] == "C" else 0 for r in rows], dtype=np.int8)
sd = np.array([int(r["seed"]) for r in rows])
tr = sd <= 94639
ho = ~tr
print("rows %d  C %d   train C/N %d/%d   HOLDOUT C/N %d/%d" %
      (N, y.sum(), y[tr].sum(), (y[tr] == 0).sum(),
       y[ho].sum(), (y[ho] == 0).sum()))

def iv(r, k, d=0):
    try:
        return int(r[k])
    except Exception:
        return d

act = np.array([iv(r, "active") for r in rows])
low3 = np.array([iv(r, "low3") for r in rows])
dist = np.array([iv(r, "dist") for r in rows])
mule2 = np.array([iv(r, "mule2") for r in rows])
grl = np.array([iv(r, "grl") for r in rows])
d60v = [int(r["d60"], 16) for r in rows]
summ = np.array([((v >> 52) & 0xFF) for v in d60v]) + low3

B = np.zeros((N, len(HEX) * 128), dtype=np.int8)
for i, r in enumerate(rows):
    for j, h in enumerate(HEX):
        v = int(r[h], 16)
        for b in range(128):
            if (v >> b) & 1:
                B[i, j * 128 + b] = 1
var = B.var(axis=0) > 0
idx = np.where(var)[0]
print("informative bit positions:", len(idx))

CKEY = [(int(act[i]), int(summ[i]), int(low3[i]), int(grl[i]))
        for i in range(N)]

def cond_contrast(vals, mask, ckeys):
    cells = defaultdict(lambda: [[], []])
    for i in np.where(mask)[0]:
        cells[ckeys[i]][y[i]].append(vals[i])
    num = den = 0.0
    for c, (nn, cc) in cells.items():
        if not nn or not cc:
            continue
        d = np.mean(cc) - np.mean(nn)
        allv = nn + cc
        m = np.mean(allv)
        v = (np.var(allv, ddof=1) if len(allv) > 1 else 0) \
            * (1 / len(cc) + 1 / len(nn))
        if v <= 0:
            continue
        w = 1 / v
        num += w * d
        den += w
    return num / math.sqrt(den) if den > 0 else 0.0

def p2(z):
    return math.erfc(abs(z) / math.sqrt(2))

print("\n== T1: f4.b65 (pre-registered single test) ==")
gi = HEX.index("f4sig") * 128 + 65
v = B[:, gi].astype(float)
zt = cond_contrast(v, tr, CKEY)
zh = cond_contrast(v, ho, CKEY)
print("  train z=%+.2f  HOLDOUT z=%+.2f  p_single=%.3g  -> %s"
      % (zt, zh, p2(zh),
         "SURVIVES" if (p2(zh) < 0.05 and zt * zh > 0) else "null"))

print("\n== T2: marginal sweep ==")
ytr = y[tr].astype(float)
Btr = B[tr][:, idx].astype(float)
pC = Btr[ytr == 1].mean(axis=0)
pN = Btr[ytr == 0].mean(axis=0)
p0 = Btr.mean(axis=0)
nC = int(ytr.sum()); nNn = int((1 - ytr).sum())
se = np.sqrt(p0 * (1 - p0) * (1 / nC + 1 / nNn)) + 1e-12
z = (pC - pN) / se
order = np.argsort(-np.abs(z))
yh = y[ho].astype(float)
Bh = B[ho][:, idx].astype(float)
nCh = int(yh.sum()); nNh = int((1 - yh).sum())
surv = 0
for r_ in order[:40]:
    gi2 = idx[r_]
    qC = Bh[yh == 1, r_].mean(); qN = Bh[yh == 0, r_].mean()
    q0 = Bh[:, r_].mean()
    seh = math.sqrt(max(q0 * (1 - q0), 1e-12) * (1 / nCh + 1 / nNh))
    zh2 = (qC - qN) / seh
    pb = p2(zh2) * len(idx)
    if zh2 * z[r_] > 0 and pb < 0.05:
        surv += 1
        nm = HEX[gi2 // 128] + ".b%d" % (gi2 % 128)
        print("  MARGINAL SURVIVOR %-14s train z=%+.2f hold z=%+.2f p_bonf=%.2g"
              % (nm, z[r_], zh2, pb))
print("  marginal survivors (of top-40):", surv)

print("\n== T3: fully-conditioned sweep (act,sum,low3,grl) ==")
zs = []
for k, gi2 in enumerate(idx):
    zt3 = cond_contrast(B[:, gi2].astype(float), tr, CKEY)
    zs.append((abs(zt3), zt3, gi2))
zs.sort(reverse=True)
surv3 = 0
for _, zt3, gi2 in zs[:25]:
    zh3 = cond_contrast(B[:, gi2].astype(float), ho, CKEY)
    pb = p2(zh3) * len(idx)
    nm = HEX[gi2 // 128] + ".b%d" % (gi2 % 128)
    tag = ""
    if zh3 * zt3 > 0 and pb < 0.05:
        surv3 += 1
        tag = "  <== SURVIVOR"
    print("  %-14s train z=%+.2f  hold z=%+.2f  p_bonf=%.2g%s"
          % (nm, zt3, zh3, pb, tag))
print("  conditioned survivors (of top-25):", surv3)

print("\n== T4: borrow/encoding features ==")
CONDF = [(int(act[i]), int(summ[i]), int(low3[i]), int(dist[i]),
          int(mule2[i])) for i in range(N)]
feats = {}
pm_a = np.zeros(N); phw_a = np.zeros(N); gw0 = np.zeros(N)
gfu = np.zeros(N); pru = np.zeros(N); wfr = np.zeros(N); s3b = np.zeros(N)
for i, r in enumerate(rows):
    le2 = iv(r, "lefte2"); re2 = iv(r, "righte2")
    L = int(r["leftsig"], 16); R = int(r["rightsig"], 16)
    pay = iv(r, "payload")
    scale = min(le2, re2)
    if pay and le2 - 8 < scale:
        scale = le2 - 8
    X = (L << (le2 - scale)) + \
        ((abs(pay) << max(0, le2 - 8 - scale)) * (1 if pay >= 0 else -1))
    AR = R << (re2 - scale)
    M = X - AR
    if M <= 0:
        continue
    kk = M.bit_length() - 67
    if kk < 0:
        continue
    pmask = ~(X ^ AR); gmask = (~X) & AR
    p = 0
    while p < 24 and ((pmask >> (kk + p)) & 1):
        p += 1
    pm_a[i] = p
    phw_a[i] = ((scale + kk) % 8 + 8) % 8
    gw0[i] = 1 if ((gmask >> kk) & 0xFF) == 0 else 0
    d = 0
    while d < 24 and not ((gmask >> (kk + d)) & 1):
        d += 1
    gfu[i] = d
    pru[i] = p
    W = M & ((1 << kk) - 1) if kk > 0 else 0
    wfr[i] = W / (1 << kk) if kk > 0 else 0
    s3b[i] = ((X ^ (~AR)) >> max(0, kk - 8)) & 0xFF
for nm, v in (("pm", pm_a), ("phw", phw_a), ("gwin0", gw0),
              ("gfree_up", gfu), ("wfrac", wfr), ("s3b", s3b)):
    zt4 = cond_contrast(v, tr, CONDF)
    zh4 = cond_contrast(v, ho, CONDF)
    tag = "  <== SURVIVOR" if (zt4 * zh4 > 0 and abs(zt4) > 3
                               and p2(zh4) * 6 < 0.05) else ""
    print("  %-10s train z=%+.2f  hold z=%+.2f%s" % (nm, zt4, zh4, tag))

print("\n== VERDICT ==")
print("Report generated at the grown census; survivors above (if any)")
print("are the new vocabulary; none => the park verdict holds at this")
print("power.  Next: if survivors, build the law + wall + blind (R93")
print("protocol); if none, the census chain may be extended or the")
print("program rests at the measured optimum.")
