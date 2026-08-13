#!/usr/bin/env python3
"""h487e: per-cell 3D separability in (XT, XD, RF), pure Python.
Perceptron with margin scaling + exact verification of any found
plane.  'PLANE' verdicts are exact; 'none found' is heuristic (large
iteration budget)."""
from collections import defaultdict
from multiprocessing import Pool
from h487d_separability import enrich
from h484_cegis import load_labels
SC = 72

def find_plane(pts, epochs=4000):
    # pts: (x, y, z, o); features scaled to ~[0,1]
    w = [0.0, 0.0, 0.0, 0.0]
    for ep in range(epochs):
        errs = 0
        for x, y, z, o in pts:
            s = w[0]*x + w[1]*y + w[2]*z + w[3]
            pred = 1 if s > 0 else 0
            if pred != o:
                errs += 1
                sgn = 1.0 if o else -1.0
                w[0] += sgn * x
                w[1] += sgn * y
                w[2] += sgn * z
                w[3] += sgn
        if errs == 0:
            ok = all((1 if w[0]*x + w[1]*y + w[2]*z + w[3] > 0
                      else 0) == o for x, y, z, o in pts)
            if ok:
                return w
    return None

def celljob(args):
    cell, rs_ = args
    n1 = sum(o for o, _ in rs_)
    pts = [(q["XT"]/2**SC, q["XD"]/2**SC, q["RF"]/2**64, o)
           for o, q in rs_]
    w = find_plane(pts)
    return cell, len(rs_), n1, w

def main():
    rows = load_labels()
    with Pool(8) as pool:
        data = [r for r in pool.map(enrich, sorted(rows.items()),
                                    chunksize=50) if r]
    cells = defaultdict(list)
    for o, cell, q in data:
        cells[cell].append((o, q))
    jobs = []
    for cell in sorted(cells):
        rs_ = cells[cell]
        if len(rs_) < 8:
            continue
        n1 = sum(o for o, _ in rs_)
        if 0 < n1 < len(rs_):
            jobs.append((cell, rs_))
    with Pool(8) as pool:
        out = pool.map(celljob, jobs, chunksize=1)
    sep = 0
    for cell, n, n1, w in out:
        if w:
            sep += 1
            nz = max(abs(v) for v in w[:3]) or 1
            print(f"  {cell} n={n} f={n1}: PLANE "
                  f"a={w[0]/nz:+.3f} b={w[1]/nz:+.3f} "
                  f"g={w[2]/nz:+.3f} c={w[3]/nz:+.3f}")
        else:
            print(f"  {cell} n={n} f={n1}: no plane found")
    print(f"\n3D separable (exact-verified): {sep}/{len(out)}")

if __name__ == "__main__":
    main()
