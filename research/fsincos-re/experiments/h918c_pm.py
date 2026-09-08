#!/usr/bin/env python3
# h918c: pm (borrow-propagate run length from bit k in ~(S^B)) for
# the q67th2 quadrant, POS vs NEG per cell.  5/6 comb POS sit at
# pm=8 — exactly one full 8-bit block (phw=0) — a configuration the
# crit test excludes.  Is pm=8 rare in NEG?
# usage: h918c_pm.py NEG1.txt [...]
import subprocess, re, sys, collections

MODEL = "./model_h917_noled"


def parse_kv(line):
    d = {}
    for m in re.finditer(r"(\w+)=([0-9a-fA-F-]+)", line):
        d[m.group(1)] = m.group(2)
    return d


def pm_of(rec):
    k = int(rec["k"])
    S = int(rec["S"], 16); B = int(rec["B"], 16)
    pmask = ~(S ^ B) & ((1 << 128) - 1)
    pm = 0; j = k
    while pm < 32 and ((pmask >> j) & 1):
        pm += 1; j += 1
    return pm, k, int(rec["ce"]), int(rec["dist"]), int(rec["rsh"]), \
        int(rec["low3"])


ledger_ops = set()
for l in open("probe_keys.tsv"):
    f = l.split()
    if len(f) == 6:
        ledger_ops.add((f[2], f[3]))

hist = collections.defaultdict(collections.Counter)  # cell -> pm hist
hist_l3 = collections.defaultdict(collections.Counter)  # (cell,pm8?) -> low3
n = 0; nled = 0
for fn in sys.argv[1:]:
    for ln in open(fn):
        if "|" not in ln:
            continue
        inpart, rpart = ln.split("|", 1)
        mi = re.match(r"DI_IN ([0-9a-f]{4}) ([0-9a-f]{16})", inpart)
        if mi and (mi.group(1), mi.group(2)) in ledger_ops:
            nled += 1
            continue
        rec = parse_kv(rpart)
        try:
            pm, k, ce, dist, rsh, low3 = pm_of(rec)
        except (KeyError, ValueError):
            continue
        n += 1
        hist[(ce, dist, rsh)][pm] += 1
        hist_l3[(ce, dist, rsh, pm)][low3] += 1

print("NEG rows %d (ledger ops excluded: %d)" % (n, nled))
for cell in sorted(hist):
    h = hist[cell]
    tot = sum(h.values())
    print("\ncell (ce=%d d=%d rsh=%d) n=%d:" % (cell + (tot,)))
    for pm in sorted(h):
        print("  pm=%-2d %8d  (%.5f)" % (pm, h[pm], h[pm] / tot))

# low3 split inside the POS-heavy configs
for cell_pm in sorted(hist_l3):
    ce, dist, rsh, pm = cell_pm
    if pm in (7, 8) and (ce, dist, rsh) in (((-72, 7, 64)), ((-72, 8, 63))):
        print("cell (%d,%d,%d) pm=%d low3:" % cell_pm,
              sorted(hist_l3[cell_pm].items()))
