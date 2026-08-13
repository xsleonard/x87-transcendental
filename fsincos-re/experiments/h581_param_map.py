#!/usr/bin/env python3
"""h581: THE PARAMETER MAP — measure exact (CR, wl, CL, K) sets
per stratum across all windows and correlate with alignment.

Law family:  T = (rdisc << CR >> rsh) - wl*(ldisc << CL >> lsh)
             - K,   K in {0, 2^(kf-8), 2^(kf-7), 2^(kf-6)}
  up rows (theta<=0/ties): req2=+1 <=> Vlow >= 2^kf - T
  dn rows (theta>=1):      req2=-1 <=> Vlow <  T
Data: comb5 ties (W1, dist 9/10 @-73), comb6 ties (W2, dist
7/9/10), comb7 near-ties (dist 8/9, both sides).  Per
(stratum, side) print: n, alignment profile (kf, payload, F,
bshift, rsh, lsh modes), the EXACT-config set (acc >= 0.9995)
or the top-3 configs by accuracy if none exact.
"""
import sys
from collections import Counter, defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h577_three_term import qrow3

CFGS = []
for CR in range(60, 68):
    for wl, CLs in ((0, (0,)), (1, (66, 67, 68))):
        for CL in CLs:
            for Ke in (None, 8, 7, 6):
                CFGS.append((CR, wl, CL, Ke))


def work(rows):
    out = []
    for mhex, theta, lab, ce in rows:
        (m, R, A, P, B_full, rsh, rdisc, lsh, ldisc, s4, t4,
         bshift, k, dist, low3) = qrow3(mhex)
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
        out.append((strat, side, kf, Vlow, rsh, rdisc, lsh,
                    ldisc, req2, F, bshift, low3 + 8 - dist))
    return out


GROUP = None


def init_g(g):
    global GROUP
    GROUP = g


def eval_group(key):
    rows2 = GROUP[key]
    side = key[1]
    res = []
    for CR, wl, CL, Ke in CFGS:
        ok = 0
        for kf, Vlow, rsh, rdisc, lsh, ldisc, req2 in rows2:
            T = rdisc << CR >> rsh
            if wl:
                T -= ldisc << CL >> lsh
            if Ke is not None:
                T -= 1 << max(kf - Ke, 0)
            if side == "up":
                pred = 1 if Vlow >= (1 << kf) - T else 0
            else:
                pred = -1 if Vlow < T else 0
            if pred == req2:
                ok += 1
        res.append((ok, (CR, wl, CL, Ke)))
    res.sort(key=lambda x: -x[0])
    return key, len(rows2), res


def load_comb7(stride):
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
    return labeled


def load_comb(name, statpre, stride):
    seen = set()
    raw = []
    for line in open(name):
        f = line.split()
        if f[0] in seen:
            continue
        seen.add(f[0])
        raw.append(f)
    inputs = sorted(f[0] for f in raw)
    order = {m2: i for i, m2 in enumerate(inputs)}
    st = {md: open(f"{statpre}_{md}_status.txt").read()
          .splitlines() for md in ROUNDING_MODES}
    out = []
    for j, f in enumerate(raw):
        if j % stride:
            continue
        R, ce = int(f[7], 16), int(f[8])
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
        refs = {nm: [final_cosine_result(-(R + d), ce, md)
                     for md in ROUNDING_MODES]
                for nm, d in (("clean", 0), ("down", -1),
                              ("up", 1))}
        for nm in ("clean", "down", "up"):
            if hw == refs[nm]:
                out.append((f[0], 0, nm, ce))
                break
    return out


def main():
    labeled = []
    labeled += load_comb("ties_comb5.txt", "comb5", 2)
    labeled += load_comb("ties_comb6.txt", "comb6", 4)
    labeled += load_comb7(4)
    print(f"labeled total: {len(labeled)}", flush=True)
    chunks = [labeled[i::8] for i in range(8)]
    with Pool(8) as pool:
        parts = pool.map(work, chunks)
    groups = defaultdict(list)
    prof = defaultdict(lambda: defaultdict(Counter))
    for part in parts:
        for (strat, side, kf, Vlow, rsh, rdisc, lsh, ldisc,
             req2, F, bshift, payload) in part:
            key = (strat, side)
            groups[key].append((kf, Vlow, rsh, rdisc, lsh,
                                ldisc, req2))
            p = prof[key]
            p["kf"][kf] += 1
            p["F"][F] += 1
            p["rsh"][rsh] += 1
            p["lsh"][lsh] += 1
            p["pay"][payload] += 1
    groups = {k: v for k, v in groups.items() if len(v) >= 2000}
    keys = sorted(groups)
    with Pool(8, initializer=init_g,
              initargs=(groups,)) as pool:
        results = pool.map(eval_group, keys)
    for key, n, res in results:
        p = prof[key]
        kfm = p["kf"].most_common(1)[0][0]
        Fm = p["F"].most_common(1)[0][0]
        rshm = p["rsh"].most_common(2)
        lshm = p["lsh"].most_common(2)
        pay = p["pay"].most_common(1)[0][0]
        exact = [cfg for ok, cfg in res if ok / n >= 0.9995]
        print(f"\n{key} n={n} kf={kfm} F={Fm} pay={pay} "
              f"rsh={rshm} lsh={lshm}")
        if exact:
            print(f"  EXACT set ({len(exact)}): "
                  f"{exact[:12]}{'...' if len(exact)>12 else ''}")
        else:
            for ok, cfg in res[:3]:
                print(f"  top {cfg}: {ok/n:.5f}")


if __name__ == "__main__":
    main()
