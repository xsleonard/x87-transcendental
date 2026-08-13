#!/usr/bin/env python3
"""h522: fit the W1 window ([0x80,0xA8), mf [0.5,0.656)) laws from
comb-5.  Census by (dist, low3), then per-(dist, low3) XD-twelfth
free-slope fits (h510 pattern).  Everything here gets locked into
h520's concrete amendment BEFORE comb-6's shifted-W1 rows are read."""
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h500_plane_m import build
from h510_xd_steps import fit_free


def load_comb5():
    rows = []
    seen = set()
    for line in open("ties_comb5.txt"):
        f = line.split()
        if f[0] in seen:
            continue
        seen.add(f[0])
        rows.append(f)
    inputs = sorted(f[0] for f in rows)
    order = {m: i for i, m in enumerate(inputs)}
    st = {md: open(f"comb5_{md}_status.txt").read().splitlines()
          for md in ROUNDING_MODES}
    out, other = [], 0
    for f in rows:
        R, ce, i = int(f[7], 16), int(f[8]), order[f[0]]
        hw, bad = [], False
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
        fired = [final_cosine_result(-(R - 1), ce, md)
                 for md in ROUNDING_MODES]
        if hw == clean:
            out.append((f[0], False))
        elif hw == fired:
            out.append((f[0], True))
        else:
            other += 1
    print(f"comb-5: {len(out)} labeled, {other} OTHER")
    return out


def one_stratum(args):
    (dist, low3), pts = args
    cells = defaultdict(list)
    for p in pts:
        cells[min(11, int(p[1] * 12))].append(p)
    out = [f"\n=== d{dist} low3={low3}  n={len(pts)} "
           f"fires={sum(p[3] for p in pts)}"]
    for k in sorted(cells):
        sub = cells[k]
        n, n1 = len(sub), sum(p[3] for p in sub)
        lo, hi = k / 12, (k + 1) / 12
        if n < 400 or min(n1, n - n1) < 25:
            tag = ("always" if n1 == n and n else
                   "never" if n1 == 0 else f"sparse({n1}/{n})")
            out.append(f"  XD[{lo:.3f},{hi:.3f}) n={n:6d} {tag}")
            continue
        emin, s, c, blo, bhi = fit_free(sub)
        if s is None:
            out.append(f"  XD[{lo:.3f},{hi:.3f}) n={n:6d} "
                       f"fires={n1:5d} never-fire-opt errs={emin}")
            continue
        out.append(f"  XD[{lo:.3f},{hi:.3f}) n={n:6d} fires={n1:5d} "
                   f"errs={emin:5d} ({emin/n:.4f}) s={s:.6f} "
                   f"1/s={1/s:7.3f} c={c:.6f} "
                   f"band=[{blo:.5f},{bhi:.5f}]")
    return "\n".join(out)


def main():
    rows = load_comb5()
    with Pool(8) as pool:
        data = pool.map(build, rows, chunksize=1000)
    census = defaultdict(int)
    strata = defaultdict(list)
    for cell, XT, XD, mf, fire in data:
        census[(cell[0], cell[1])] += 1
        strata[(cell[0], cell[1])].append((XT, XD, mf, fire))
    print("census:", {k: v for k, v in sorted(census.items())})
    jobs = [(k, v) for k, v in sorted(strata.items())
            if sum(p[3] for p in v) > 0 or len(v) > 2000]
    with Pool(8) as pool:
        for block in pool.imap(one_stratum, jobs, chunksize=1):
            print(block, flush=True)


if __name__ == "__main__":
    main()
