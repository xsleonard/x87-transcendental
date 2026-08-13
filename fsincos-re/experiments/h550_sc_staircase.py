#!/usr/bin/env python3
"""h550: N4 — the rf/4-ladder staircase test on the PAIRED-FSINCOS
cos lane (comb-4 ties, theta=0), vs standalone FCOS on the same
rows.  If the paired lane shows steps at rho = j/4 too, the
schedule-dependence is a second j-selector on the SAME ladder.

comb4_sc status tokens: 1,2 = sin exp/mant, 3,4 = cos exp/mant.
"""
import math
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h539_D_library import qrow

LOG2RF = math.log2(2 / 3) + 64


def work(rows):
    hist = defaultdict(lambda: [0, 0])
    census = defaultdict(int)
    for mhex, labs, labc in rows:
        (m, sqv, f4v, rfv, t4, rdisc, A, P, M, k, R, B_full,
         rsh, bshift, dist, low3) = qrow(mhex)
        F = rsh - bshift
        if F < 0:
            continue
        kf = k + F
        APf = (A + P) << F
        EU = (APf - B_full) >> kf
        Vlow = (APf - B_full) - (EU << kf)
        gap_up = (1 << kf) - Vlow
        rho = 2 ** (math.log2(gap_up) - LOG2RF)
        if rho > 1.7:
            continue
        b = int(rho * 60)
        for tag, lab in (("sc", labs), ("cos", labc)):
            if lab is None:
                continue
            req2 = (R + {"clean": 0, "down": -1, "up": 1}[lab]) - EU
            census[(tag, req2)] += 1
            hist[(tag, b)][1] += 1
            if req2:
                hist[(tag, b)][0] += 1
    return {k2: list(v) for k2, v in hist.items()}, dict(census)


def main():
    order = {}
    for i, ln in enumerate(open("comb4_sincos_inputs.txt")):
        order[ln.split()[1]] = i
    orderc = {}
    raw = []
    seen = set()
    for ln in open("ties_comb4.txt"):
        f = ln.split()
        if f[0] in seen:
            continue
        seen.add(f[0])
        raw.append(f)
    for i, mh in enumerate(sorted(f[0] for f in raw)):
        orderc[mh] = i
    sc = {md: open(f"comb4_sc_{md}_status.txt").read().splitlines()
          for md in ROUNDING_MODES}
    cs = {md: open(f"comb4_{md}_status.txt").read().splitlines()
          for md in ROUNDING_MODES}
    rows = []
    for j, f in enumerate(raw):
        if j % 4:
            continue
        R, ce = int(f[7], 16), int(f[8])
        refs = {name: [final_cosine_result(-(R + d), ce, md)
                       for md in ROUNDING_MODES]
                for name, d in (("clean", 0), ("down", -1),
                                ("up", 1))}
        labs = labc = None
        i = order.get(f[0])
        if i is not None:
            hw, bad = [], False
            for md in ROUNDING_MODES:
                t = sc[md][i].split()
                if t[0] != "OK":
                    bad = True
                    break
                hw.append(int(t[4], 16))
            if not bad:
                for name in ("clean", "down", "up"):
                    if hw == refs[name]:
                        labs = name
                        break
        ic = orderc.get(f[0])
        if ic is not None:
            hw, bad = [], False
            for md in ROUNDING_MODES:
                t = cs[md][ic].split()
                if t[0] != "OK":
                    bad = True
                    break
                hw.append(int(t[2], 16))
            if not bad:
                for name in ("clean", "down", "up"):
                    if hw == refs[name]:
                        labc = name
                        break
        if labs or labc:
            rows.append((f[0], labs, labc))
    print(f"rows with labels: {len(rows)}", flush=True)
    chunks = [rows[i::8] for i in range(8)]
    with Pool(8) as pool:
        parts = pool.map(work, chunks)
    hist = defaultdict(lambda: [0, 0])
    census = defaultdict(int)
    for h, c in parts:
        for kk, v in h.items():
            hist[kk][0] += v[0]
            hist[kk][1] += v[1]
        for kk, v in c.items():
            census[kk] += v
    print("req2 census:", dict(sorted(census.items())))
    for tag in ("cos", "sc"):
        print(f"\n=== {tag} lane staircase (theta=0 ties) ===")
        for b in range(0, 102):
            nf, n = hist.get((tag, b), (0, 0))
            if n < 300:
                continue
            bar = "#" * int(50 * nf / n)
            print(f"  {b/60:5.3f} {n:7d} {nf/n:6.3f} {bar}")


if __name__ == "__main__":
    main()
