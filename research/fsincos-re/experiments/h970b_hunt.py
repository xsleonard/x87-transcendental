#!/usr/bin/env python3
# h970b: THE DISCRIMINANT HUNT ON CLEAN LABELS.  DOWN vs ZERO
# (primary) and UP vs ZERO (secondary), exposed ops only, within-
# stratum contrasts, FIT/HOL hash halves (h968's split), Bonferroni.
# Also: exact duplicate-feature-vector contradiction count (the
# h486 smoking gun at dump power).
#
# PRE-REGISTERED: a feature survives iff FIT stratified |z| >= 4.5
# (Bonferroni ~ 250 bits) AND HOL stratified |z| >= 3.0 with the
# SAME sign.  Anything else is noise.
import math, sys
from collections import Counter, defaultdict

rows = []
hdr = None
for ln in open("h970_features.tsv"):
    t = ln.rstrip("\n").split("\t")
    if t[0] == "insn":
        hdr = t
        continue
    rows.append(t)
ix = {c: i for i, c in enumerate(hdr)}

def bits_of(t):
    f = {}
    d60 = int(t[ix["d60"]], 16)
    for b in range(60):
        f["d60_b%02d" % b] = (d60 >> b) & 1
    low3 = int(t[ix["low3"]])
    for b in range(3):
        f["low3_b%d" % b] = (low3 >> b) & 1
    for col, nb in (("laneb", 8), ("lane2", 8), ("lane3", 8)):
        v = int(t[ix[col]], 16) if t[ix[col]] not in ("-",) else 0
        for b in range(nb):
            f["%s_b%d" % (col, b)] = (v >> b) & 1
    rd = t[ix["rdisc"]]
    rdv = int(rd, 16) if rd != "-" else 0
    for b in range(48, 64):
        f["rdisc_b%02d" % b] = (rdv >> b) & 1
    for col, lo, hi in (("rightsig", 0, 24), ("mulsig", 0, 16),
                        ("leftsig", 0, 16), ("lfsig", 0, 8),
                        ("rfsig", 0, 8), ("f4sig", 0, 8),
                        ("magsig", 0, 8)):
        v = int(t[ix[col]], 16)
        for b in range(lo, hi):
            f["%s_b%02d" % (col, b)] = (v >> b) & 1
    for col in ("ud", "u5d", "rud", "rsh", "payload", "pay2",
                "lanediff"):
        try:
            v = int(t[ix[col]])
        except ValueError:
            v = -99
        f[col + "_sign"] = 1 if v > 0 else 0
        for b in range(5):
            f["%s_b%d" % (col, b)] = (abs(v) >> b) & 1
    f["leftsign"] = int(t[ix["leftsign"]])
    f["rightsign"] = int(t[ix["rightsign"]])
    return f

# collect exposed ops
data = []
for t in rows:
    lab = t[ix["lab"]]
    if lab not in ("DOWN", "ZERO", "UP"):
        continue
    st = tuple(t[ix[c]] for c in ("act", "sum8", "d", "me2", "g"))
    data.append((st, t[ix["half"]], lab, bits_of(t), t))
print("exposed ops:", len(data))
feats = sorted(data[0][3])
print("features:", len(feats))

def hunt(l1, l0, name):
    # stratified two-proportion z per feature, FIT then HOL
    print("\n==== %s vs %s ====" % (l1, l0))
    res = []
    for half in ("FIT", "HOL"):
        zs = {}
        for ft in feats:
            num = den = 0.0
            for st in strata_ix:
                a = b = c = d = 0
                for (h, lab, f) in strata_ix[st]:
                    if h != half:
                        continue
                    v = f[ft]
                    if lab == l1:
                        a += v
                        b += 1 - v
                    elif lab == l0:
                        c += v
                        d += 1 - v
                    else:
                        continue
                n1, n0 = a + b, c + d
                if n1 == 0 or n0 == 0:
                    continue
                p = (a + c) / (n1 + n0)
                if p <= 0 or p >= 1:
                    continue
                num += a - n1 * p
                den += n1 * n0 * p * (1 - p) / (n1 + n0)
            zs[ft] = num / math.sqrt(den) if den > 0 else 0.0
        res.append(zs)
    fit, hol = res
    surv = []
    for ft in feats:
        if abs(fit[ft]) >= 4.5 and abs(hol[ft]) >= 3.0 \
           and fit[ft] * hol[ft] > 0:
            surv.append((ft, fit[ft], hol[ft]))
    top = sorted(feats, key=lambda f: -abs(fit[f]))[:12]
    print("top FIT z:")
    for ft in top:
        print("  %-14s fit %+6.2f  hol %+6.2f" % (ft, fit[ft],
                                                  hol[ft]))
    print("SURVIVORS (fit>=4.5 & hol>=3.0 same sign):", len(surv))
    for s in surv:
        print("  %-14s fit %+6.2f  hol %+6.2f" % s)
    return surv

strata_ix = defaultdict(list)
for st, half, lab, f, t in data:
    strata_ix[st].append((half, lab, f))

s1 = hunt("DOWN", "ZERO", "primary")
s2 = hunt("UP", "ZERO", "secondary")

# exact duplicate-vector contradictions (full dump vector + stratum)
sig = defaultdict(Counter)
for st, half, lab, f, t in data:
    key = (st, tuple(f[ft] for ft in feats))
    sig[key][lab] += 1
coll = [(k, dict(c)) for k, c in sig.items() if len(c) > 1]
print("\nduplicate-vector label contradictions:", len(coll))
n = 0
for (st, _), c in coll[:10]:
    print("  stratum", st, c)
    n += 1
