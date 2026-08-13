#!/usr/bin/env python3
"""h574d: OPTIMIZER-FREE feasible-band extraction for D(XD).

For the exact sides, per XD-bin (1/96ths), intersect every row's
feasible-D interval (quarters):  band = [max(qlo), min(qhi)].
Print band lo/hi/width per bin — the true D(XD) law is read
directly: staircase (twelfth steps) vs straight line, exact
region-jump positions, and residual slope inside twelfths.
Strata: dist=8 up (all low3 3..7 separately) and (9,1..4)@-72 dn
pooled and separately.
"""
import sys
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h539_D_library import qrow

D9 = {(9, 1, -72), (9, 2, -72), (9, 3, -72), (9, 4, -72)}
D8 = {(8, 3, -73), (8, 4, -73), (8, 5, -73), (8, 6, -73),
      (8, 7, -73)}


def work(rows):
    out = []
    for mhex, theta, lab, ce in rows:
        (m, sqv, f4v, rfv, t4, rdisc, A, P, M, k, R, B_full,
         rsh, bshift, dist, low3) = qrow(mhex)
        strat = (dist, low3, ce)
        side = "up" if theta <= 0 else "dn"
        if not ((strat in D9 and side == "dn") or
                (strat in D8 and side == "up")):
            continue
        F = rsh - bshift
        if F < 0:
            continue
        kf = k + F
        APf = (A + P) << F
        res_hw = R + {"clean": 0, "down": -1, "up": 1}[lab]
        EU = (APf - B_full) >> kf
        req2 = res_hw - EU
        Vlow = (APf - B_full) - (EU << kf)
        uq = 16.0 / rfv
        qlo = (Vlow - ((req2 + 1) << kf)) * uq
        qhi = (Vlow - (req2 << kf)) * uq
        XD = rdisc / 2.0**rsh
        out.append((strat, min(95, int(XD * 96)), qlo, qhi, kf))
    return out


def main():
    seen = set()
    raw = []
    for line in open("ties_comb7.txt"):
        f = line.split()
        if f[0] in seen:
            continue
        seen.add(f[0])
        raw.append(f)
    inputs = sorted(f[0] for f in raw)
    order = {m2: i for i, m2 in enumerate(inputs)}
    st = {md: open(f"comb7_{md}_status.txt").read().splitlines()
          for md in ROUNDING_MODES}
    stride = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    labeled = []
    for j, f in enumerate(raw):
        if j % stride:
            continue
        R, ce, theta = int(f[7], 16), int(f[8]), int(f[9])
        i = order[f[0]]
        hw, bad = [], False
        for md in ROUNDING_MODES:
            t = st[md][i].split()
            if t[0] != "OK":
                bad = True
                break
            hw.append(int(t[2], 16))
        if bad:
            continue
        refs = {name: [final_cosine_result(-(R + d), ce, md)
                       for md in ROUNDING_MODES]
                for name, d in (("clean", 0), ("down", -1),
                                ("up", 1))}
        for name in ("clean", "down", "up"):
            if hw == refs[name]:
                labeled.append((f[0], theta, name, ce))
                break
    print(f"labeled sample: {len(labeled)}", flush=True)
    chunks = [labeled[i::8] for i in range(8)]
    with Pool(8) as pool:
        parts = pool.map(work, chunks)
    bands = defaultdict(lambda: [-1e18, 1e18, 0])
    kfs = defaultdict(lambda: defaultdict(int))
    for part in parts:
        for strat, b96, qlo, qhi, kf in part:
            key = (strat, b96)
            r = bands[key]
            r[0] = max(r[0], qlo)
            r[1] = min(r[1], qhi)
            r[2] += 1
            kfs[strat][kf] += 1
    print("\nkf by stratum (these sides only):")
    for strat in sorted(kfs):
        print(f"  {strat}: {dict(kfs[strat])}")
    strata = sorted(set(k[0] for k in bands))
    for strat in strata:
        print(f"\n=== {strat} ===  (bin: XD*96; lo/hi in "
              "quarters; w=width; n=rows)")
        for b96 in range(96):
            r = bands.get((strat, b96))
            if not r or r[2] < 10:
                continue
            lo, hi, n = r
            mark = " EMPTY" if lo > hi else ""
            if True:
                print(f"  {b96:3d} ({b96/96:.3f}): "
                      f"[{lo:9.3f}, {hi:9.3f}] w={hi-lo:8.3f} "
                      f"n={n:5d}{mark}")


if __name__ == "__main__":
    main()
