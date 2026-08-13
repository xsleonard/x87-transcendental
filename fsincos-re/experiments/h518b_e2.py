#!/usr/bin/env python3
"""h518b: E2 rerun with the correct sincos token — the paired status
line is `OK sin_e sin_sig cos_e cos_sig SW sw`; the cos lane is
token 4 (h518 mistakenly read token 2, the sin lane).

Census the paired cos-lane outcomes on the comb-4 d9-window subset and
test the E2 question: does the PAIRED schedule's gate follow an m-law
(h491 only ruled out (t4, rdisc); m/le2 was never tested)?"""
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h500_plane_m import build
from h510_xd_steps import fit_free


def load_sc():
    rows = []
    seen = set()
    for line in open("ties_comb4.txt"):
        f = line.split()
        if f[0] in seen or f[0] >= "c8":
            continue
        seen.add(f[0])
        rows.append(f)
    inputs = sorted(f[0] for f in rows)
    order = {m: i for i, m in enumerate(inputs)}
    st = {md: open(f"comb4_sc_{md}_status.txt").read().splitlines()
          for md in ROUNDING_MODES}
    out, other, badst = [], 0, 0
    for f in rows:
        R, ce, i = int(f[7], 16), int(f[8]), order[f[0]]
        hw, bad = [], False
        for md in ROUNDING_MODES:
            t = st[md][i].split()
            if t[0] != "OK":
                bad = True
                break
            hw.append(int(t[4], 16))
        if bad:
            badst += 1
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
    print(f"sincos d9-window: {len(out)} labeled, {other} OTHER, "
          f"{badst} bad-status")
    return out


def main():
    rows = load_sc()
    if not rows:
        return
    with Pool(8) as pool:
        data = pool.map(build, rows, chunksize=1000)
    strata = defaultdict(list)
    for cell, XT, XD, mf, fire in data:
        strata[(cell[0], cell[1])].append((XT, XD, mf, fire))
    print(f"{'stratum':10s} {'n':>7s} {'fires':>7s} {'rate':>6s} "
          f"{'line errs':>9s} {'rel':>7s} {'s':>9s} {'c':>9s}")
    for key in sorted(strata):
        pts = strata[key]
        n, n1 = len(pts), sum(p[3] for p in pts)
        if n < 2000 or min(n1, n - n1) < 50:
            print(f"{str(key):10s} {n:7d} {n1:7d} "
                  f"{n1/max(1,n):6.3f}   (sparse/pure)")
            continue
        emin, s, c, blo, bhi = fit_free(pts)
        if s is None:
            print(f"{str(key):10s} {n:7d} {n1:7d} {n1/n:6.3f} "
                  f"  no-line-beats-never-fire ({emin} errs)")
            continue
        print(f"{str(key):10s} {n:7d} {n1:7d} {n1/n:6.3f} "
              f"{emin:9d} {emin/n:7.4f} {s:9.5f} {c:9.5f}")


if __name__ == "__main__":
    main()
