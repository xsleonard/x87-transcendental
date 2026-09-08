#!/usr/bin/env python3
"""h529: dense E1 — the near-tie laws from comb-7.

Rows: theta in {-2..+2} over [0xA8,0xC8) (theta=0 ties ride along as
a cross-scanner consistency check).  Labels test ALL THREE references
(clean / R-1 "down" / R+1 "up") from the full M at raw scale.

Questions:
  Q1 does each theta stratum have its own linear laws in (XT, m)?
  Q2 how do slopes/intercepts move with theta (tie law shifted, or
     new geometry)?
  Q3 fire DIRECTION census per theta (down vs up vs other).
"""
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h500_plane_m import build
from h510_xd_steps import fit_free


def load7():
    rows = []
    seen = set()
    for line in open("ties_comb7.txt"):
        f = line.split()
        if f[0] in seen:
            continue
        seen.add(f[0])
        rows.append(f)
    inputs = sorted(f[0] for f in rows)
    order = {m: i for i, m in enumerate(inputs)}
    st = {md: open(f"comb7_{md}_status.txt").read().splitlines()
          for md in ROUNDING_MODES}
    out = []
    census = defaultdict(int)
    for f in rows:
        R, ce, k, theta = (int(f[7], 16), int(f[8]), int(f[3]),
                           int(f[9]))
        scale = ce - k
        D = theta if theta >= 0 else (1 << k) + theta
        M = (R << k) + D
        i = order[f[0]]
        hw, bad = [], False
        for md in ROUNDING_MODES:
            t = st[md][i].split()
            if t[0] != "OK":
                bad = True
                break
            hw.append(int(t[2], 16))
        if bad:
            census["badstat"] += 1
            continue
        # CHOP convention (h529 first pass proved it): the hardware
        # terminal truncates D before final rounding — references are
        # the integer R neighbors at ce, exactly as for ties.
        refs = {}
        for name, val in (("clean", R), ("down", R - 1),
                          ("up", R + 1)):
            refs[name] = [final_cosine_result(-val, ce, md)
                          for md in ROUNDING_MODES]
        lab = None
        for name in ("clean", "down", "up"):
            if hw == refs[name]:
                lab = name
                break
        if lab is None:
            census[("other", theta)] += 1
            continue
        census[(lab, theta)] += 1
        out.append((f[0], theta, lab))
    print("label census:", dict(sorted(census.items(), key=str)))
    return out


def one_cell(args):
    key, pts = args
    theta, dist, low3 = key
    cells = defaultdict(list)
    for p in pts:
        reg = 0 if p[1] < 1/3 else (1 if p[1] < 2/3 else 2)
        cells[reg].append(p)
    out = [f"\n=== theta={theta:+d} d{dist} low3={low3} "
           f"n={len(pts)} fires={sum(p[3] for p in pts)}"]
    names = {0: "XD<1/3 ", 1: "[1/3,2/3)", 2: "XD>=2/3"}
    for reg in sorted(cells):
        sub = cells[reg]
        n, n1 = len(sub), sum(p[3] for p in sub)
        if n < 500 or min(n1, n - n1) < 30:
            tag = ("always" if n1 == n and n else
                   "never" if n1 == 0 else f"sparse({n1}/{n})")
            out.append(f"  {names[reg]:9s} n={n:6d} {tag}")
            continue
        emin, s, c, blo, bhi = fit_free(sub)
        if s is None:
            out.append(f"  {names[reg]:9s} n={n:6d} fires={n1:5d} "
                       f"rate={n1/n:.3f} no-line ({emin} errs)")
            continue
        out.append(f"  {names[reg]:9s} n={n:6d} fires={n1:5d} "
                   f"errs={emin:5d} ({emin/n:.4f}) s={s:.6f} "
                   f"c={c:.6f} band=[{blo:.5f},{bhi:.5f}]")
    return "\n".join(out)


def main():
    rows = load7()
    with Pool(8) as pool:
        data = pool.map(build, [(mh, 0) for mh, _, _ in rows],
                        chunksize=1000)
    strata = defaultdict(list)
    for (mh, theta, lab), (cell, XT, XD, mf, _) in zip(rows, data):
        fire = 1 if lab in ("down", "up") else 0
        strata[(theta, cell[0], cell[1])].append((XT, XD, mf, fire))
    jobs = [(k, v) for k, v in sorted(strata.items())
            if len(v) >= 1500]
    with Pool(8) as pool:
        for block in pool.imap(one_cell, jobs, chunksize=1):
            print(block, flush=True)


if __name__ == "__main__":
    main()
