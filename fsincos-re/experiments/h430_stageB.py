#!/usr/bin/env python3
"""h430 Stage B: boolean-gate synthesis over the Stage-A constraint DB.

Find a decision tree over datapath signals whose every leaf has a common
allowed mechanism (AND of row masks != 0).  Splits: thresholds on ordered
signals, bit tests on byte signals.  Greedy with lookahead beam, iterative
deepening; falls back to reporting irreducible conflict cells.
"""
import pickle, sys, time
from collections import Counter

DB = pickle.load(open("h429_rows.pkl", "rb"))
MECHS, RAW = DB["mechs"], DB["rows"]
FEATS = sorted(RAW[0][0].keys())
BYTE_FEATS = {"ls_low8", "rs_low8", "sum_byte", "sq_low8", "p", "lane"}

# expand byte feats into bit signals; keep ordered feats as-is
def vec(sig):
    v = []
    for f in FEATS:
        x = sig[f]
        if f in BYTE_FEATS:
            v.extend((x >> b) & 1 for b in range(8))
        else:
            v.append(x)
    return tuple(v)

NAMES = []
for f in FEATS:
    if f in BYTE_FEATS:
        NAMES.extend(f"{f}.b{b}" for b in range(8))
    else:
        NAMES.append(f)

groups = Counter()
gmask = {}
for sig, mask in RAW:
    t = vec(sig)
    groups[t] += 1
    gmask[t] = gmask.get(t, (1 << 20) - 1) & mask
ROWS = [(t, gmask[t], groups[t]) for t in groups]
print(f"unique signal vectors: {len(ROWS)} (from {len(RAW)})", flush=True)

FULL = (1 << len(MECHS)) - 1

def feasible(rows):
    a = FULL
    for t, m, c in rows:
        a &= m
        if not a:
            return 0
    return a

def split_candidates(rows):
    cands = []
    nf = len(ROWS[0][0])
    for fi in range(nf):
        vals = sorted({t[fi] for t, m, c in rows})
        if len(vals) < 2:
            continue
        for v in vals[1:]:
            cands.append((fi, v))
    return cands

best_fail = [None]

def search(rows, depth, path):
    a = feasible(rows)
    if a:
        return [("LEAF", path, a, sum(c for *_, c in rows))]
    if depth == 0:
        n = sum(c for *_, c in rows)
        if best_fail[0] is None or n < best_fail[0][0]:
            best_fail[0] = (n, path)
        return None
    scored = []
    for fi, v in split_candidates(rows):
        lo = [r for r in rows if r[0][fi] < v]
        hi = [r for r in rows if r[0][fi] >= v]
        if not lo or not hi:
            continue
        nf = (0 if feasible(lo) else 1) + (0 if feasible(hi) else 1)
        scored.append((nf, -min(len(lo), len(hi)), fi, v, lo, hi))
    scored.sort(key=lambda s: (s[0], s[1]))
    for nf, _, fi, v, lo, hi in scored[:3]:
        rl = search(lo, depth - 1, path + [f"{NAMES[fi]}<{v}"])
        if rl is None:
            continue
        rh = search(hi, depth - 1, path + [f"{NAMES[fi]}>={v}"])
        if rh is None:
            continue
        return rl + rh
    return None

for depth in (3, 4, 5, 6, 7, 8):
    t0 = time.time()
    best_fail[0] = None
    res = search(ROWS, depth, [])
    dt = time.time() - t0
    if res:
        print(f"DEPTH {depth}: SOLVED with {len(res)} leaves ({dt:.0f}s)", flush=True)
        for kind, path, a, n in res:
            ms = [MECHS[i] for i in range(len(MECHS)) if a & (1 << i)]
            print(f"  n={n} mechs={ms} :: {' & '.join(path) or '(root)'}")
        sys.exit(0)
    print(f"DEPTH {depth}: no gate ({dt:.0f}s); hardest cell rows={best_fail[0][0]}"
          f" at {' & '.join(best_fail[0][1])}", flush=True)
print("NO CONSISTENT GATE up to depth 8 over current signal set")
