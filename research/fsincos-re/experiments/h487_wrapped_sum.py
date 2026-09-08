#!/usr/bin/env python3
"""h487: fit fire = [alpha*T + beta*D + c(cell) crosses boundary] --
the wrapped-sum/carry form the maps revealed.

h486 maps: per-cell fire is a step in t4 (up), a step in rdisc (up or
DOWN), or an interval/co-interval -- the exact signature of the carry
bit of X + c(cell) as the cell offset moves.  Prior searches all
capped the constant at |c|<=2, so this family was never tested.

Per cell, per composite X in {a*Tj + b*Dj, a*Pj + b*Dj, Tj - Dj,
Dj - Tj, singles}: sweep the threshold freely (exact iff labels are a
step in X).  Report per-cell exact fits, then the fitted thresholds
vs cell geometry (dist, low3, k, rud, payload).
"""
from collections import defaultdict
from multiprocessing import Pool
from h484_cegis import load_labels, quantities

def build_row(item):
    mhex, o = item
    if o == 2:
        return None
    cell, payload, q = quantities(mhex)
    return (o, cell, payload, q)

def step_fit(vals):
    """vals: (x, o) list.  Exact iff, after sorting by x, labels form
    0*1* (up) or 1*0* (down); ties in x must be label-consistent.
    Returns (dir, theta) or None."""
    byx = defaultdict(set)
    for x, o in vals:
        byx[x].add(o)
    if any(len(s) > 1 for s in byx.values()):
        return None
    xs = sorted(byx)
    seq = [next(iter(byx[x])) for x in xs]
    if all(seq[i] <= seq[i+1] for i in range(len(seq)-1)):
        th = next((xs[i] for i, s in enumerate(seq) if s == 1), None)
        return ("up", th)
    if all(seq[i] >= seq[i+1] for i in range(len(seq)-1)):
        th = next((xs[i] for i, s in enumerate(seq) if s == 0), None)
        return ("down", th)
    return None

def main():
    rows = load_labels()
    with Pool(8) as pool:
        data = [r for r in pool.map(build_row, sorted(rows.items()),
                                    chunksize=50) if r]
    cells = defaultdict(list)
    payload_of = {}
    for o, cell, payload, q in data:
        cells[cell].append((o, q))
        payload_of[cell] = payload

    T_names = ["T4", "T6", "T8", "T10", "T12"]
    P_names = ["P4", "P6", "P8", "P10", "P12"]
    D_names = ["D4", "D6", "D8", "D10", "D12"]
    composites = []
    for tn in T_names + P_names:
        for dn in D_names:
            for a, b in ((1, 1), (2, 1), (1, 2), (3, 1), (1, 3)):
                composites.append((f"{a}*{tn}+{b}*{dn}",
                                   lambda q, tn=tn, dn=dn, a=a, b=b:
                                   a * q[tn] + b * q[dn]))
            composites.append((f"{tn}-{dn}",
                               lambda q, tn=tn, dn=dn: q[tn] - q[dn]))
    for nm in T_names + P_names + D_names:
        composites.append((nm, lambda q, nm=nm: q[nm]))
    print(f"composites: {len(composites)}")

    fits = {}
    for cell in sorted(cells):
        rs_ = cells[cell]
        if len(rs_) < 8:
            continue
        n1 = sum(o for o, _ in rs_)
        if n1 == 0 or n1 == len(rs_):
            continue
        best = []
        for name, fn in composites:
            r = step_fit([(fn(q), o) for o, q in rs_])
            if r:
                best.append((name, r[0], r[1]))
        if best:
            fits[cell] = best
            show = "; ".join(f"{n}:{d}@{t}" for n, d, t in best[:3])
            print(f"  {cell} n={len(rs_)} f={n1}: {show}"
                  f"  [{len(best)} exact fits]")
        else:
            print(f"  {cell} n={len(rs_)} f={n1}: none")

    print(f"\ncells with exact composite step: {len(fits)} / "
          f"{sum(1 for c in cells.values() if len(c) >= 8 and 0 < sum(o for o,_ in c) < len(c))}")

    # which composite family solves the most cells?
    fam_count = defaultdict(list)
    for cell, best in fits.items():
        for n, d, t in best:
            fam_count[n].append((cell, d, t))
    ranked = sorted(fam_count.items(), key=lambda kv: -len(kv[1]))
    print("\n=== composites by cells solved ===")
    for name, lst in ranked[:10]:
        print(f"  {name}: {len(lst)} cells")
        for cell, d, t in lst:
            print(f"      {cell} payload={payload_of[cell]} "
                  f"{d}@{t}")

if __name__ == "__main__":
    main()
