#!/usr/bin/env python3
"""h432: comparison-predicate gate synthesis.

Augments the zone rows with arithmetic comparator predicates between the
natural multi-bit datapath quantities (magnitude compares, wrap/borrow
conditions, post-insertion byte collisions) that bit-threshold trees
cannot express, then reruns feasibility-tree synthesis.
"""
import sys, time
from collections import Counter
from multiprocessing import Pool

exec(open("h431_enriched.py").read().split("if __name__")[0])

def predicates(s):
    p, lane, sum8 = s["p"], s["lane"], s["sum8"]
    ls8, rs8 = s["ls8"], s["rs8"]
    dl, dr = s["dl16"], s["dr16"]
    post = (sum8 + p) & 0xFF
    postc = 1 if sum8 + p >= 256 else 0
    v = {
        "p_lt_lane": 1 if p < lane else 0,
        "p_eq_lane": 1 if p == lane else 0,
        "sum8_lt_p": 1 if sum8 < p else 0,
        "sum8_eq_p": 1 if sum8 == p else 0,
        "sum8_lt_lane": 1 if sum8 < lane else 0,
        "sum8_eq_lane": 1 if sum8 == lane else 0,
        "ls8_lt_rs8": 1 if ls8 < rs8 else 0,
        "dl_lt_dr": 1 if dl < dr else 0,
        "dl_hi_lt_dr_hi": 1 if (dl >> 8) < (dr >> 8) else 0,
        "post_carry": postc,
        "post_lt_lane": 1 if post < lane else 0,
        "post_eq_lane": 1 if post == lane else 0,
        "post_eq_lanem1": 1 if post == ((lane - 1) & 0xFF) else 0,
        "post_eq_lanep1": 1 if post == ((lane + 1) & 0xFF) else 0,
        "sub_borrow": 1 if sum8 - p < 0 else 0,
        "planewrap": 1 if p + lane >= 256 else 0,
        "dldr_wrap": 1 if dl + dr >= (1 << 16) else 0,
        "dl_top": (dl >> 15) & 1, "dr_top": (dr >> 15) & 1,
        "dl_top2": (dl >> 14) & 3, "dr_top2": (dr >> 14) & 3,
        "post_top": (post >> 7) & 1,
        "lane_minus_sum8": ((lane - sum8) & 0xFF) if lane >= sum8 else 256 - ((sum8 - lane) & 0xFF),
    }
    keep = ("diff", "dist", "low3", "lf3", "rf3", "mul3", "f43",
            "shl", "shr", "borrow", "lane9", "lane10", "dl_nz", "dr_nz",
            "lsign", "rsign", "p", "lane", "sum8")
    for k in keep:
        v[k] = s[k]
    return v

if __name__ == "__main__":
    with Pool(8) as pool:
        rows = pool.map(build, load(), chunksize=2000)
    zone = [(predicates(s), m) for s, m in rows if -3 <= s["diff"] <= 3]
    print(f"zone rows: {len(zone)}", flush=True)
    FEATS = sorted(zone[0][0].keys())
    def vecp(s):
        return tuple(s[f] for f in FEATS)
    gm, gc = {}, Counter()
    for s, m in zone:
        t = vecp(s)
        gc[t] += 1
        gm[t] = gm.get(t, (1 << 20) - 1) & m
    ROWS = [(t, gm[t], gc[t]) for t in gm]
    print(f"unique vectors: {len(ROWS)}  feats: {len(FEATS)}", flush=True)
    FULL = (1 << len(MECHS)) - 1
    def feas(rr):
        a = FULL
        for t, m, c in rr:
            a &= m
            if not a:
                return 0
        return a
    best_fail = [None]
    def search(rr, depth, path):
        a = feas(rr)
        if a:
            return [(path, a, sum(c for *_, c in rr))]
        if depth == 0:
            n = sum(c for *_, c in rr)
            if best_fail[0] is None or n < best_fail[0][0]:
                best_fail[0] = (n, path)
            return None
        scored = []
        for fi in range(len(FEATS)):
            vals = sorted({t[fi] for t, m, c in rr})
            for v in vals[1:]:
                lo = [r for r in rr if r[0][fi] < v]
                hi = [r for r in rr if r[0][fi] >= v]
                bad = (0 if feas(lo) else 1) + (0 if feas(hi) else 1)
                scored.append((bad, -min(len(lo), len(hi)), fi, v, lo, hi))
        scored.sort(key=lambda s: (s[0], s[1]))
        for bad, _, fi, v, lo, hi in scored[:4]:
            rl = search(lo, depth - 1, path + [f"{FEATS[fi]}<{v}"])
            if rl is None:
                continue
            rh = search(hi, depth - 1, path + [f"{FEATS[fi]}>={v}"])
            if rh is not None:
                return rl + rh
        return None
    for depth in (5, 7, 9, 11):
        t0 = time.time()
        best_fail[0] = None
        res = search(ROWS, depth, [])
        if res:
            print(f"DEPTH {depth}: SOLVED, {len(res)} leaves ({time.time()-t0:.0f}s)", flush=True)
            for path, a, n in res:
                ms = [MECHS[i] for i in range(len(MECHS)) if a & (1 << i)]
                print(f"  n={n} mechs={ms} :: {' & '.join(path) or '(root)'}")
            sys.exit(0)
        print(f"DEPTH {depth}: no gate ({time.time()-t0:.0f}s); "
              f"hardest={best_fail[0][0]} at {' & '.join(best_fail[0][1])}", flush=True)
    print("NO GATE up to depth 11 with comparator predicates", flush=True)
