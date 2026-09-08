#!/usr/bin/env python3
"""h491d: extract the empirical FCOS decision boundary per cell.
For each big cell, in the (t4hi12, rdhi12) plane: per T-band (64
bands of 6 bits... use t4hi12>>6, 64 bands), find the rdisc threshold
where fire rate crosses 0.5 (logistic-free: median of the mixed
zone), plus the boundary WIDTH (rdisc span between 10 percent and 90
percent fire).  Prints theta_D(T) tables and linear fits; narrow
width + smooth curve => 2-variable near-deterministic; wide => more
variables."""
from collections import defaultdict

rows = []
with open("h491_mapdata.tsv") as fh:
    fh.readline()
    for line in fh:
        f = line.rstrip("\n").split("\t")
        rows.append(f)

cells = defaultdict(list)
for f in rows:
    if f[7] in ("CLEAN", "FIRE"):
        cells[(f[1], f[2], f[3], f[4])].append(
            (int(f[5], 16), int(f[6], 16), f[7] == "FIRE"))

for cell in sorted(cells, key=lambda c: -len(cells[c]))[:3]:
    pts = cells[cell]
    print(f"\n=== cell {cell} n={len(pts)} "
          f"fires={sum(p[2] for p in pts)} ===")
    print(f"{'Tband':>6s} {'n':>5s} {'theta50':>8s} {'w10-90':>7s} "
          f"{'lo-rate':>7s} {'hi-rate':>7s}")
    fits = []
    for tb in range(0, 64):
        sub = sorted((d, fi) for t, d, fi in pts
                     if (t >> 6) == tb)
        if len(sub) < 40:
            continue
        # cumulative fire rate by D: find 10/50/90 crossings
        # smooth with binning by 64 D-units
        bins = defaultdict(lambda: [0, 0])
        for d, fi in sub:
            b = bins[d >> 6]
            b[0] += 1
            b[1] += fi
        bs = sorted(bins)
        rates = [(b, bins[b][1] / bins[b][0]) for b in bs
                 if bins[b][0] >= 4]
        if len(rates) < 4:
            continue
        def crossing(level):
            for i in range(len(rates) - 1):
                if rates[i][1] < level <= rates[i + 1][1]:
                    return (rates[i][0] + rates[i + 1][0]) / 2
            return None
        th = crossing(0.5)
        lo = crossing(0.1)
        hi = crossing(0.9)
        lorate = rates[0][1]
        hirate = rates[-1][1]
        w = (hi - lo) if (hi is not None and lo is not None) else None
        print(f"{tb:6d} {len(sub):5d} "
              f"{'%8.1f' % th if th is not None else '     n/a'} "
              f"{'%7.1f' % w if w is not None else '    n/a'} "
              f"{lorate:7.2f} {hirate:7.2f}")
        if th is not None:
            fits.append((tb, th))
    if len(fits) >= 6:
        n = len(fits)
        sx = sum(t for t, _ in fits)
        sy = sum(d for _, d in fits)
        sxx = sum(t * t for t, _ in fits)
        sxy = sum(t * d for t, d in fits)
        slope = (n * sxy - sx * sy) / (n * sxx - sx * sx)
        inter = (sy - slope * sx) / n
        resid = max(abs(d - (slope * t + inter)) for t, d in fits)
        print(f"  linear fit: theta_D = {slope:+.3f}*Tband + "
              f"{inter:.1f} (max resid {resid:.1f} D-bins)")
