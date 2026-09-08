#!/usr/bin/env python3
"""h505: THE LOCKED PREDICTION TEST (h505_locked.json, registered
before the comb-3 capture): at dist=8, payload = low3, so the h504
slope law predicts fire <=> m < c + XT/(4*low3) per (8, low3, rud)
stratum, slope pinned, intercept free.

Scores every dist=8 stratum from the comb-3 data (ties_comb3.txt +
comb3_{rn,rd,ru}_status.txt), h504 discipline: error rate, in-band
fraction of violators, half-intercept agreement, exact corridor.
Also prints dist=9 strata as a cross-comb consistency ride-along.
"""
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h500_plane_m import build


def load_comb3():
    rows = []
    seen = set()
    for line in open("ties_comb3.txt"):
        f = line.split()
        if f[0] in seen:
            continue
        seen.add(f[0])
        rows.append(f)
    inputs = sorted(f[0] for f in rows)
    order = {m: i for i, m in enumerate(inputs)}
    st = {md: open(f"comb3_{md}_status.txt").read().splitlines()
          for md in ROUNDING_MODES}
    out = []
    other = 0
    for f in rows:
        R = int(f[7], 16)
        ce = int(f[8])
        i = order[f[0]]
        hw = []
        bad = False
        for md in ROUNDING_MODES:
            t = st[md][i].split()
            if t[0] != "OK":
                bad = True
                break
            hw.append(int(t[2], 16))
        if bad:
            continue
        clean = [final_cosine_result(-R, ce, md)
                 for md in ROUNDING_MODES]
        fired = [final_cosine_result(-(R-1), ce, md)
                 for md in ROUNDING_MODES]
        if hw == clean:
            out.append((f[0], False))
        elif hw == fired:
            out.append((f[0], True))
        else:
            other += 1
    print(f"loaded {len(out)} labeled rows, {other} OTHER outcomes")
    return out


def best_c(pts, s):
    vals = sorted((mf - s*XT, o) for XT, XD, mf, o in pts)
    ns = sum(o for _, o in vals)
    pre1 = 0
    bb, bc = ns, None
    for i, (r, o) in enumerate(vals):
        pre1 += o
        e = (i + 1 - pre1) + (ns - pre1)
        if e < bb:
            bb, bc = e, r
    return bb, bc


def main():
    from h509_d8_regions import built_comb3
    data = built_comb3()
    strata = defaultdict(list)
    for cell, XT, XD, mf, fire in data:
        strata[cell].append((XT, XD, mf, fire))
    census = defaultdict(int)
    for cell, pts in strata.items():
        census[cell[0]] += len(pts)
    print("dist census:", dict(sorted(census.items())))
    print(f"\n{'stratum':12s} {'payload':>7s} {'slope':>8s} {'n':>6s} "
          f"{'fires':>6s} {'errs':>5s} {'rate':>7s} {'in-band':>7s} "
          f"{'c':>9s} {'c-lo-half':>9s} {'c-hi-half':>9s} "
          f"{'corridor':>22s}")
    for cell in sorted(strata):
        dist, low3, rud = cell
        payload = low3 + 8 - dist
        if payload <= 0:
            continue
        pts = strata[cell]
        if len(pts) < 500:
            continue
        n1 = sum(p[3] for p in pts)
        s = 1.0 / (4 * payload)
        if n1 == 0 or n1 == len(pts):
            print(f"{str(cell):12s} {payload:7d} 1/{4*payload:<6d} "
                  f"{len(pts):6d} {n1:6d}  PURE "
                  f"({'always' if n1 else 'never'}-fire)")
            continue
        errs, c = best_c(pts, s)
        inband = 0
        if c is not None:
            for XT, XD, mf, o in pts:
                r = mf - s*XT
                pred = 1 if r < c else 0
                if pred != o and abs(r - c) < 0.003:
                    inband += 1
        lo_half = [p for p in pts if p[0] < 0.5]
        hi_half = [p for p in pts if p[0] >= 0.5]
        _, cl = best_c(lo_half, s) if len(lo_half) > 500 else (0, None)
        _, ch = best_c(hi_half, s) if len(hi_half) > 500 else (0, None)
        lo, hi = -1e9, 1e9
        for XT, XD, mf, o in pts:
            r = mf - s*XT
            if o:
                lo = max(lo, r)
            else:
                hi = min(hi, r)
        feas = (f"[{lo:.6f},{hi:.6f}]" if hi > lo
                else f"infeas {lo - hi:.1e}")
        print(f"{str(cell):12s} {payload:7d} 1/{4*payload:<6d} "
              f"{len(pts):6d} {n1:6d} {errs:5d} "
              f"{errs/len(pts):7.4f} {inband:7d} "
              f"{c if c is None else round(c, 5)!s:>9s} "
              f"{cl if cl is None else round(cl, 5)!s:>9s} "
              f"{ch if ch is None else round(ch, 5)!s:>9s} "
              f"{feas:>22s}")


if __name__ == "__main__":
    main()
