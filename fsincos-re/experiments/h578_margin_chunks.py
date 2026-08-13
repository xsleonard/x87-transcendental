#!/usr/bin/env python3
"""h578: hard-side margin census + per-pass CHUNKED-discard terms.

A. MARGIN CENSUS: with the h576/h577 best fixed-column T per
   hard (stratum, side), bin margin = (Vlow - (2^kf - T)) (up) or
   (T - Vlow) (dn) in units of 2^(kf-12); per bin count outcomes.
   Value-determined => clean step at 0; mixed bins far from 0 =>
   non-value state remains (in the NEW frame).
B. CHUNKED TERMS: split rdisc and ldisc at absolute product
   columns 27/54 (iterative retirement chunks); term =
   sum_i si*(chunk_i << ci >> its own width) — grid a restricted
   family: rdisc split at bit rsh-27 (top chunk vs rest), each
   with own column 60..67/sign; ldisc likewise; on the 6 worst
   hard sides.  Report held-out vs the h577 numbers.
"""
import sys
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h577_three_term import qrow3

HARD_T = {
    ((8, 4, -73), "dn"): (1, 63, 0, 0, 0, 0, 0),
    ((8, 5, -73), "dn"): (1, 63, 1, 60, 1, 64, 0),
    ((8, 6, -73), "dn"): (1, 62, 1, 63, 1, 64, 1),
    ((8, 7, -73), "dn"): (1, 64, 1, 62, 1, 65, 1),
    ((9, 1, -72), "up"): (1, 63, 1, 63, 1, 63, 1),
    ((9, 2, -72), "up"): (1, 62, 1, 64, 1, 61, 0),
    ((9, 4, -72), "up"): (1, 61, 1, 63, -1, 62, 1),
    ((9, 5, -72), "up"): (1, 63, 1, 63, -1, 64, 1),
    ((9, 7, -72), "dn"): (1, 62, 0, 0, 0, 0, 0),
}
WORST = [((8, 5, -73), "dn"), ((8, 6, -73), "dn"),
         ((8, 7, -73), "dn"), ((9, 1, -72), "up"),
         ((9, 2, -72), "up"), ((9, 4, -72), "up")]


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
        if (strat, side) not in HARD_T:
            continue
        half = (m * 2654435761) & 1
        out.append((strat, side, half, kf, Vlow, rsh, rdisc,
                    lsh, ldisc, s4, t4, req2, theta))
    return out


def term(cfg, kf, rsh, rdisc, lsh, ldisc, s4, t4):
    sr, cr, sl, cl, st, ct, cq = cfg
    T = cq * (1 << kf) >> 10
    if sr:
        T += sr * (rdisc << cr >> rsh)
    if sl:
        T += sl * (ldisc << cl >> lsh)
    if st:
        T += st * (t4 << ct >> s4)
    return T


GROUP = None


def init_g(g):
    global GROUP
    GROUP = g


def eval_chunks(key):
    strat, side = key
    tr, te = GROUP[key]
    base_cfg = HARD_T[key]
    # chunk family: rdisc top chunk (above rsh-27) and low rest,
    # ldisc likewise; each own (sign, col); coarse then refine.
    sub = tr[:5000]
    best = (-1, None)
    grid1 = [(s, c) for s in (0, 1, -1) for c in
             (range(61, 67) if True else ())] + [(0, 0)]
    grid1 = [(s, c) for s in (1, -1) for c in range(61, 67)]
    grid1.append((0, 0))
    for sa, ca in grid1:
        for sb, cb in grid1:
            for sc, cc in [(s, c) for s in (0, 1, -1)
                           for c in (63, 65, 67)]:
                ok = 0
                for (kf, Vlow, rsh, rdisc, lsh, ldisc, s4, t4,
                     req2, theta) in sub:
                    cut = max(rsh - 27, 0)
                    rhi = rdisc >> cut
                    rlo = rdisc & ((1 << cut) - 1)
                    T = 0
                    if sa:
                        T += sa * (rhi << ca >> (rsh - cut))
                    if sb and cut:
                        T += sb * (rlo << cb >> cut)
                    if sc:
                        T += sc * (ldisc << cc >> lsh)
                    if side == "up":
                        pred = 1 if Vlow >= (1 << kf) - T else 0
                    else:
                        pred = -1 if Vlow < T else 0
                    if pred == req2:
                        ok += 1
                if ok > best[0]:
                    best = (ok, (sa, ca, sb, cb, sc, cc))
        pass
    okf = 0
    (sa, ca, sb, cb, sc, cc) = best[1]
    for (kf, Vlow, rsh, rdisc, lsh, ldisc, s4, t4, req2,
         theta) in te:
        cut = max(rsh - 27, 0)
        rhi = rdisc >> cut
        rlo = rdisc & ((1 << cut) - 1)
        T = 0
        if sa:
            T += sa * (rhi << ca >> (rsh - cut))
        if sb and cut:
            T += sb * (rlo << cb >> cut)
        if sc:
            T += sc * (ldisc << cc >> lsh)
        if side == "up":
            pred = 1 if Vlow >= (1 << kf) - T else 0
        else:
            pred = -1 if Vlow < T else 0
        if pred == req2:
            okf += 1
    return key, best[1], okf, len(te)


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
                ldisc, s4, t4, req2, theta in part:
            pt = (kf, Vlow, rsh, rdisc, lsh, ldisc, s4, t4,
                  req2, theta)
            groups[(strat, side)][0 if half == 0 else 1].append(pt)
    # A: margin census
    print("\nA. margin census (margin units 2^(kf-12); "
          "fire-rate per bin):")
    for key in sorted(HARD_T):
        if key not in groups:
            continue
        cfg = HARD_T[key]
        strat, side = key
        tr, te = groups[key]
        bins = defaultdict(lambda: [0, 0])
        for (kf, Vlow, rsh, rdisc, lsh, ldisc, s4, t4, req2,
             theta) in tr + te:
            T = term(cfg, kf, rsh, rdisc, lsh, ldisc, s4, t4)
            if side == "up":
                marg = Vlow - ((1 << kf) - T)
                fire = req2 == 1
            else:
                marg = T - 1 - Vlow
                fire = req2 == -1
            mb = marg * 4096 >> kf
            mb = max(-40, min(40, mb))
            b = bins[mb]
            b[1] += 1
            if fire:
                b[0] += 1
        cells = []
        for mb in sorted(bins):
            f2, n = bins[mb]
            if n >= 50:
                cells.append(f"{mb}:{f2/n:.2f}")
        print(f"  {key}: " + " ".join(cells))
    # B: chunked grid on worst
    groups2 = {k: groups[k] for k in WORST if k in groups}
    with Pool(6, initializer=init_g,
              initargs=(groups2,)) as pool:
        results = pool.map(eval_chunks, sorted(groups2))
    print("\nB. chunked-rdisc grid (top-27-split), held-out:")
    for key, cfg, ok, n in results:
        print(f"  {key}: {ok}/{n} ({ok/max(n,1):.5f}) cfg={cfg}")


if __name__ == "__main__":
    main()
