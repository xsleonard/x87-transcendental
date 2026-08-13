#!/usr/bin/env python3
"""h506: Phase B on the dist=9 comb data (ties_comb + comb_* captures).

B1  (9,5,*) fine-slope corridor: slope grid ~1/4096 over [0.058,0.078],
    optional XD term; error-minimizing intercept per slope; require
    half-intercept agreement; snap to simplest feasible rational.
B2  rud=0 second branch ((9,4,0),(9,6,0), check (9,2,0)):
    fire = [m < c1 + s*XT] OR [XD >= x0 and m < c2 + s2*XT];
    grid x0, fit both intercepts; is the step EXACTLY 1/3?
B3  payload=1 census ((9,2,*)): where do the sparse fires live —
    band-edge onset of the same law, or separate structure?
"""
from collections import defaultdict
from fractions import Fraction
from multiprocessing import Pool
from h500_plane_m import build, load_comb


def best_c(pts, s, b=0.0):
    """Error-minimizing intercept for fire <=> m - s*XT - b*XD < c.
    Returns (errs, c).  Never-fire = threshold below all rows."""
    vals = sorted((mf - s*XT - b*XD, o) for XT, XD, mf, o in pts)
    ns = sum(o for _, o in vals)
    pre1 = 0
    bb, bc = ns, None          # never-fire baseline
    for i, (r, o) in enumerate(vals):
        pre1 += o
        e = (i + 1 - pre1) + (ns - pre1)
        if e < bb:
            bb, bc = e, r
    return bb, bc


def corridor(pts, s, b=0.0):
    """Exact-feasibility interval: (lo, hi); feasible iff hi > lo."""
    lo, hi = -1e9, 1e9
    for XT, XD, mf, o in pts:
        r = mf - s*XT - b*XD
        if o:
            lo = max(lo, r)
        else:
            hi = min(hi, r)
    return lo, hi


def b1_fine_slope(strata):
    print("=" * 70)
    print("B1: (9,5,*) fine-slope corridor")
    for cell in [(9, 5, 0), (9, 5, 1)]:
        pts = strata[cell]
        n = len(pts)
        print(f"\n{cell} n={n} fires={sum(p[3] for p in pts)}")
        results = []
        for si in range(int(0.058 * 4096), int(0.078 * 4096) + 1):
            s = si / 4096
            e, c = best_c(pts, s)
            results.append((e, s, c))
        results.sort()
        emin = results[0][0]
        good = sorted(s for e, s, c in results if e <= emin + 2)
        print(f"  best errs={emin} at s={results[0][1]:.6f} "
              f"c={results[0][2]:.6f}")
        print(f"  near-optimal slope band (errs<=min+2): "
              f"[{good[0]:.6f}, {good[-1]:.6f}]")
        # half-intercept agreement at the best few slopes
        lo_half = [p for p in pts if p[0] < 0.5]
        hi_half = [p for p in pts if p[0] >= 0.5]
        for e, s, c in results[:5]:
            _, cl = best_c(lo_half, s)
            _, ch = best_c(hi_half, s)
            d = None if (cl is None or ch is None) else ch - cl
            print(f"    s={s:.6f} errs={e:5d} c={c:.6f} "
                  f"c_lo={cl if cl is None else round(cl, 6)} "
                  f"c_hi={ch if ch is None else round(ch, 6)} "
                  f"diff={d if d is None else round(d, 6)}")
        # rational snap: q <= 512, in the near-optimal band
        rats = []
        for q in range(2, 513):
            p_lo = int(good[0] * q)
            for p in (p_lo, p_lo + 1):
                s = p / q
                if good[0] - 1e-9 <= s <= good[-1] + 1e-9:
                    fr = Fraction(p, q)
                    if (fr.numerator, fr.denominator) not in \
                            [(r[0], r[1]) for r in rats]:
                        e, c = best_c(pts, s)
                        rats.append((fr.numerator, fr.denominator,
                                     s, e, c))
        rats.sort(key=lambda r: (r[1], r[3]))
        print("  simplest rationals in band (num/den, errs, c):")
        for num, den, s, e, c in rats[:8]:
            lo, hi = corridor(pts, s)
            feas = f"corridor [{lo:.6f},{hi:.6f}]" if hi > lo \
                else f"infeasible (deficit {lo - hi:.2e})"
            print(f"    {num}/{den} = {s:.6f}  errs={e}  "
                  f"c={c:.6f}  {feas}")
        # XD term at the best slope
        e0, s0, _ = results[0]
        for b in (-1/16, -1/32, -1/64, 1/64, 1/32, 1/16):
            e, c = best_c(pts, s0, b)
            if e < e0:
                print(f"  XD term helps: b={b} errs={e} (vs {e0})")


def two_branch_err(pts, x0, s1, s2):
    """fire <=> [m - s1*XT < c1]  OR  [XD >= x0 and m - s2*XT < c2].
    OR-model exact scoring needs joint (c1, c2); since branch A
    applies to ALL rows and branch B only to XD>=x0 rows, fit c1 on
    XD<x0 rows (only branch A there), then c2 on XD>=x0 rows among
    those NOT already fired by branch A; iterate once."""
    A = [p for p in pts if p[1] < x0]
    B = [p for p in pts if p[1] >= x0]
    eA, c1 = best_c(A, s1)
    if c1 is None:
        c1 = -1e9
    # rows in B not fired by branch A get decided by branch B
    B_rest, eB_pre = [], 0
    for XT, XD, mf, o in B:
        if mf - s1*XT < c1:
            eB_pre += 0 if o else 1     # branch A fires here
        else:
            B_rest.append((XT, XD, mf, o))
    eB, c2 = best_c(B_rest, s2)
    return eA + eB_pre + eB, c1, c2


def b2_second_branch(strata):
    print("=" * 70)
    print("B2: rud=0 second branch — fire = lineA OR "
          "[XD >= x0 and lineB]")
    for cell, payload in [((9, 4, 0), 3), ((9, 6, 0), 5),
                          ((9, 2, 0), 1)]:
        pts = strata[cell]
        n = len(pts)
        n1 = sum(p[3] for p in pts)
        s = 1.0 / (4 * payload)
        print(f"\n{cell} n={n} fires={n1} pinned slope 1/{4*payload}")
        e_single, c_single = best_c(pts, s)
        print(f"  single line: errs={e_single}")
        # grid x0; both branch slopes pinned to the law first
        results = []
        for xi in range(int(0.25 * 1024), int(0.45 * 1024) + 1):
            x0 = xi / 1024
            e, c1, c2 = two_branch_err(pts, x0, s, s)
            results.append((e, x0, c1, c2))
        results.sort()
        emin, x0b, c1b, c2b = results[0]
        band = sorted(x0 for e, x0, _, _ in results if e <= emin + 2)
        print(f"  two-branch (both slopes 1/{4*payload}): "
              f"errs={emin} at x0={x0b:.6f} "
              f"c1={c1b if c1b is None else round(c1b, 6)} "
              f"c2={c2b if c2b is None else round(c2b, 6)}")
        print(f"  x0 near-optimal band: [{band[0]:.6f}, "
              f"{band[-1]:.6f}]  "
          f"({'1/3 INSIDE' if band[0] - 1e-9 <= 1/3 <= band[-1] + 1e-9 else '1/3 OUTSIDE'})")
        e3, c13, c23 = two_branch_err(pts, 1/3, s, s)
        print(f"  at exactly x0=1/3: errs={e3} "
              f"c1={c13 if c13 is None else round(c13, 6)} "
              f"c2={c23 if c23 is None else round(c23, 6)}")
        # let branch-B slope float coarsely
        best_free = None
        for s2i in range(0, 32):
            s2 = s2i / 128
            e, c1, c2 = two_branch_err(pts, x0b, s, s2)
            if best_free is None or e < best_free[0]:
                best_free = (e, s2, c1, c2)
        e, s2, c1, c2 = best_free
        print(f"  branch-B slope float: best errs={e} at s2={s2:.5f}")


def b3_payload1(strata):
    print("=" * 70)
    print("B3: payload=1 census ((9,2,*)) — sparse-fire location")
    for cell in [(9, 2, 0), (9, 2, 1)]:
        pts = strata[cell]
        fires = [p for p in pts if p[3]]
        cleans = [p for p in pts if not p[3]]
        s = 0.25
        rs_f = sorted(mf - s*XT for XT, XD, mf, o in fires)
        rs_c = sorted(mf - s*XT for XT, XD, mf, o in cleans)
        print(f"\n{cell} n={len(pts)} fires={len(fires)}")
        if not fires:
            continue
        print(f"  r = m - XT/4:  fires  min={rs_f[0]:.6f} "
              f"med={rs_f[len(rs_f)//2]:.6f} max={rs_f[-1]:.6f}")
        print(f"                 cleans min={rs_c[0]:.6f} "
              f"max={rs_c[-1]:.6f}")
        below = sum(1 for r in rs_c if r < rs_f[-1])
        print(f"  cleans below the top fire: {below} "
              f"(0 => same-law onset: fires are the extreme-low-r "
              f"rows)")
        print(f"  fire coords (XT, XD, m):")
        for XT, XD, mf, _ in sorted(fires,
                                    key=lambda p: p[2] - s*p[0])[:12]:
            print(f"    XT={XT:.4f} XD={XD:.4f} m={mf:.6f} "
                  f"r={mf - s*XT:.6f}")
        if len(fires) > 12:
            print(f"    ... {len(fires) - 12} more")
        # m distribution: band-edge onset predicts fires at low m
        mmin = min(p[2] for p in pts)
        mmax = max(p[2] for p in pts)
        print(f"  stratum m range [{mmin:.4f},{mmax:.4f}]; "
              f"fire m range "
              f"[{min(p[2] for p in fires):.4f},"
              f"{max(p[2] for p in fires):.4f}]")
        # XD dependence
        hi_xd = sum(1 for p in fires if p[1] >= 1/3)
        print(f"  fires with XD >= 1/3: {hi_xd}/{len(fires)} "
              f"(stratum rate "
              f"{sum(1 for p in pts if p[1] >= 1/3)/len(pts):.3f})")


def main():
    rows = load_comb()
    with Pool(8) as pool:
        data = pool.map(build, rows, chunksize=1000)
    strata = defaultdict(list)
    for cell, XT, XD, mf, fire in data:
        if cell[0] == 9:
            strata[cell].append((XT, XD, mf, fire))
    b1_fine_slope(strata)
    b2_second_branch(strata)
    b3_payload1(strata)


if __name__ == "__main__":
    main()
