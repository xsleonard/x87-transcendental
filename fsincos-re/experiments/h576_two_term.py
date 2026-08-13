#!/usr/bin/env python3
"""h576: THE TWO-TERM CLOSED FORM — full grid, held-out.

Threshold model per (stratum, side):
  up:  req2=+1 <=> Vlow >= 2^kf - Tr - Tl - c*2^(kf-10)
  dn:  req2=-1 <=> Vlow <  Tr + Tl + c*2^(kf-10)
  Tr = sr * (rdisc << cr >> rsh),  sr in {0,+1,-1}, cr 61..66
  Tl = sl * (ldisc << cl >> lsh),  sl in {0,+1,-1}, cl 58..67
  c  in {-8..8} (units of 2^-10 of the bracket)
Split-half: fit (sr,cr,sl,cl,c) on half A (max accuracy), score
half B.  Report per (stratum, side): best config, held-out rate,
misses by |theta| for the winner (theta passed through).
The prior exact findings pin some entries; the grid must
reproduce them and extend to the hard sides.
"""
import sys
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h575_predicate import qrow2

CFGS = []
for sr, crs in ((1, range(61, 67)), (0, (0,))):
    for cr in crs:
        for sl, cls in ((0, (0,)), (1, range(58, 68)),
                        (-1, range(58, 68))):
            for cl in cls:
                CFGS.append((sr, cr, sl, cl))


def work(rows):
    out = []
    for mhex, theta, lab, ce in rows:
        (m, R, A, P, B_full, rsh, rdisc, lsh, ldisc, bshift,
         k, dist, low3) = qrow2(mhex)
        F = rsh - bshift
        if F < 0:
            continue
        kf = k + F
        APf = (A + P) << F
        res_hw = R + {"clean": 0, "down": -1, "up": 1}[lab]
        EU = (APf - B_full) >> kf
        req2 = res_hw - EU
        Vlow = (APf - B_full) - (EU << kf)
        strat = (dist, low3, ce)
        side = "up" if theta <= 0 else "dn"
        half = (m * 2654435761) & 1
        out.append((strat, side, half, kf, Vlow, rsh, rdisc,
                    lsh, ldisc, req2, theta))
    return out


GROUP = None


def init_g(g):
    global GROUP
    GROUP = g


def score(rows2, side, cfg, cq):
    sr, cr, sl, cl = cfg
    ok = 0
    for kf, Vlow, rsh, rdisc, lsh, ldisc, req2, theta in rows2:
        T = 0
        if sr:
            T += sr * (rdisc << cr >> rsh)
        if sl:
            T += sl * (ldisc << cl >> lsh)
        T += cq * (1 << kf) >> 10
        if side == "up":
            pred = 1 if Vlow >= (1 << kf) - T else 0
        else:
            pred = -1 if Vlow < T else 0
        if pred == req2:
            ok += 1
    return ok


def eval_group(key):
    strat, side = key
    tr, te = GROUP[key]
    sub = tr[:6000]
    coarse = []
    for cfg in CFGS:
        ok = score(sub, side, cfg, 0)
        coarse.append((ok, cfg))
    coarse.sort(reverse=True)
    best = (-1, None, None)
    for _, cfg in coarse[:8]:
        for cq in (-8, -4, -2, -1, 0, 1, 2, 4, 8):
            ok = score(tr, side, cfg, cq)
            if ok > best[0]:
                best = (ok, cfg, cq)
    _, cfg, cq = best
    ok = score(te, side, cfg, cq)
    # miss census by theta
    sr, cr, sl, cl = cfg
    th_miss = defaultdict(int)
    for kf, Vlow, rsh, rdisc, lsh, ldisc, req2, theta in te:
        T = 0
        if sr:
            T += sr * (rdisc << cr >> rsh)
        if sl:
            T += sl * (ldisc << cl >> lsh)
        T += cq * (1 << kf) >> 10
        if side == "up":
            pred = 1 if Vlow >= (1 << kf) - T else 0
        else:
            pred = -1 if Vlow < T else 0
        if pred != req2:
            th_miss[theta] += 1
    return key, best[0], len(tr), ok, len(te), cfg, cq, \
        dict(th_miss)


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
    groups = defaultdict(lambda: ([], []))
    for part in parts:
        for strat, side, half, kf, Vlow, rsh, rdisc, lsh, \
                ldisc, req2, theta in part:
            pt = (kf, Vlow, rsh, rdisc, lsh, ldisc, req2, theta)
            groups[(strat, side)][0 if half == 0 else 1].append(pt)
    groups = {k: v for k, v in groups.items()
              if len(v[0]) >= 1000}
    keys = sorted(groups)
    with Pool(8, initializer=init_g,
              initargs=(groups,)) as pool:
        results = pool.map(eval_group, keys)
    print(f"\n{'stratum':14s} {'side':4s} {'train':>7s} "
          f"{'HELDOUT':>8s} {'config':>22s} {'c':>3s}  misses_by_theta")
    for key, otr, ntr, ote, nte, cfg, cq, thm in results:
        strat, side = key
        print(f"{str(strat):14s} {side:4s} {otr/ntr:7.5f} "
              f"{ote/max(nte,1):8.5f} {str(cfg):>22s} {cq:3d}  "
              f"{dict(sorted(thm.items()))}")


if __name__ == "__main__":
    main()
