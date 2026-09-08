#!/usr/bin/env python3
"""h501: corridor extraction for all dist=9 strata.

Per stratum, model fire <=> m < c + s*XT + b*XD:
  1. coarse feasibility scan over (s, b): deficit = lo - hi where
     lo = max over fires of (m - s*XT - b*XD), hi = min over cleans;
     feasible iff deficit < 0; refine locally;
  2. rational snapping: test canonical (s, b) rational pairs for
     feasibility directly; report intercept intervals;
  3. curvature: where no plane is feasible, add q*XT^2 and retry;
     classify verdicts EXACT-PLANE / CURVED / TEXTURE with violator
     displacement stats.
Run from /tmp/stageA (needs comb data + captures).
"""
from collections import defaultdict
from multiprocessing import Pool
from h500_plane_m import build, load_comb

S_RATS = [0, 1/16, 1/12, 1/10, 7/64, 1/8, 5/32, 3/16, 7/32, 1/4]
B_RATS = [0, 1/16, -1/16, 1/8, -1/8, 1/4, -1/4, 3/8, 1/2]

def deficit(pts, s, b, q=0.0):
    lo = -1e9
    hi = 1e9
    for x, d, mf, o in pts:
        r = mf - s*x - b*d - q*x*x
        if o:
            if r > lo:
                lo = r
        else:
            if r < hi:
                hi = r
    return lo, hi

def analyze(args):
    cell, pts = args
    n = len(pts)
    n1 = sum(p[3] for p in pts)
    out = [f"{cell} n={n} fires={n1}"]
    if n1 == 0 or n1 == n:
        out.append("  PURE stratum (constant rule)")
        return "\n".join(out)
    # coarse scan
    best = None
    for si in range(0, 36):
        s = si * 0.01
        for bi in range(-20, 41):
            b = bi * 0.01
            lo, hi = deficit(pts, s, b)
            gap = hi - lo
            if best is None or gap > best[0]:
                best = (gap, s, b, lo, hi)
    gap, s, b, lo, hi = best
    if gap > 0:
        out.append(f"  EXACT-PLANE corridor: s~{s:.3f} b~{b:.3f} "
                   f"c in [{lo:.6f},{hi:.6f}] gap={gap:.2e}")
        rats = []
        for sr in S_RATS:
            for br in B_RATS:
                l2, h2 = deficit(pts, sr, br)
                if h2 > l2:
                    rats.append((sr, br, l2, h2))
        if rats:
            rats.sort(key=lambda r: -(r[3] - r[2]))
            for sr, br, l2, h2 in rats[:3]:
                out.append(f"    rational s={sr} b={br}: c in "
                           f"[{l2:.6f},{h2:.6f}]")
        else:
            out.append("    no canonical rational pair feasible")
        return "\n".join(out)
    # infeasible: try quadratic
    bestq = None
    for si in range(0, 36, 2):
        s = si * 0.01
        for bi in range(-10, 21, 2):
            b = bi * 0.01
            for qi in range(-20, 21, 2):
                q = qi * 0.01
                lo2, hi2 = deficit(pts, s, b, q)
                g2 = hi2 - lo2
                if bestq is None or g2 > bestq[0]:
                    bestq = (g2, s, b, q, lo2, hi2)
    g2, s2, b2, q2, lo2, hi2 = bestq
    if g2 > 0:
        out.append(f"  CURVED: plane infeasible (deficit "
                   f"{-gap:.2e}) but quadratic exact: s={s2:.2f} "
                   f"b={b2:.2f} q={q2:.2f} c in [{lo2:.6f},"
                   f"{hi2:.6f}]")
        return "\n".join(out)
    # texture: violation stats at best plane
    # count errors at best plane with optimal c
    rs = sorted((mf - s*x - b*d, o) for x, d, mf, o in pts)
    n1s = sum(o for _, o in rs)
    pre1 = 0
    bb, bc = n1s, None
    for i, (r, o) in enumerate(rs):
        pre1 += o
        e = (i + 1 - pre1) + (n1s - pre1)
        if e < bb:
            bb, bc = e, r
    out.append(f"  TEXTURE: best plane errs={bb} ({bb/n:.4f}) at "
               f"s={s:.2f} b={b:.2f}; quad deficit {-g2:.2e}")
    return "\n".join(out)

def main():
    rows = load_comb()
    with Pool(8) as pool:
        data = pool.map(build, rows, chunksize=1000)
    # need XD too: h500.build returns (cell, XT, XD, mf, fire)
    strata = defaultdict(list)
    for cell, XT, XD, mf, fire in data:
        if cell[0] == 9:
            strata[cell].append((XT, XD, mf, fire))
    jobs = [(c, pts) for c, pts in sorted(strata.items())
            if len(pts) >= 2000]
    with Pool(8) as pool:
        out = pool.map(analyze, jobs, chunksize=1)
    for o in out:
        print(o)

if __name__ == "__main__":
    main()
