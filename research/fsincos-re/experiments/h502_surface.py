#!/usr/bin/env python3
"""h502: empirical boundary surface m*(XT, XD) for the mixed dist=9
strata.  Per (XT, XD) bin (12x12), the 50-percent m-crossing from
the comb's dense m coverage.  Prints the surface as a grid (values =
crossing m as percent of binade; '..' = no crossing in range) for
shape reading: plane -> parallel contours; XD steps -> banded rows;
XT curvature -> bowed columns."""
from collections import defaultdict
from multiprocessing import Pool
from h500_plane_m import build, load_comb

TARGETS = [(9, 4, 1), (9, 5, 0), (9, 6, 0), (9, 7, 0)]

def main():
    rows = load_comb()
    with Pool(8) as pool:
        data = pool.map(build, rows, chunksize=1000)
    strata = defaultdict(list)
    for cell, XT, XD, mf, fire in data:
        if cell in TARGETS:
            strata[cell].append((XT, XD, mf, fire))
    for cell in TARGETS:
        pts = strata[cell]
        print(f"\n=== {cell} n={len(pts)}: m*(XT rows, XD cols) "
              f"in percent of binade ===")
        grid = defaultdict(list)
        for x, d, mf, o in pts:
            grid[(int(x * 12), int(d * 12))].append((mf, o))
        hdr = "      " + " ".join(f"D{d:02d} " for d in range(12))
        print(hdr)
        for t in range(12):
            line = []
            for d in range(12):
                sub = sorted(grid.get((t, d), []))
                if len(sub) < 40:
                    line.append(" .. ")
                    continue
                # m-crossing: rate above/below median-ish
                B = max(4, len(sub) // 30)
                prof = []
                for bi in range(B):
                    seg = sub[bi*len(sub)//B:(bi+1)*len(sub)//B]
                    if seg:
                        prof.append((seg[len(seg)//2][0],
                                     sum(o for _, o in seg)/len(seg)))
                cr = None
                for i in range(len(prof)-1):
                    a, b2 = prof[i], prof[i+1]
                    if (a[1]-0.5)*(b2[1]-0.5) <= 0 and a[1] != b2[1]:
                        t2 = (a[1]-0.5)/(a[1]-b2[1])
                        cr = a[0] + t2*(b2[0]-a[0])
                        break
                if cr is None:
                    r = sum(o for _, o in sub)/len(sub)
                    line.append("FIRE" if r > 0.5 else "  0 ")
                else:
                    line.append(f"{100*cr:4.1f}")
            print(f"T{t:02d} " + " ".join(line))

if __name__ == "__main__":
    main()
