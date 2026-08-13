#!/usr/bin/env python3
"""h553: j = q(4*tau) + c(stratum) — fit integer offsets per
stratum, membership in the exact J-intervals, theta-stability.

q variants: round(4tau), floor(4tau), round(8tau)/2-ish is left
out (integer ladder only).  c in [-14, 14].  Reports per stratum:
best c, membership, membership by theta at best c, and the global
membership with per-stratum c.
"""
import sys
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h539_D_library import qrow

CS = range(-14, 15)


def work(rows):
    cen = defaultdict(int)
    for mhex, theta, lab, ce in rows:
        (m, sqv, f4v, rfv, t4, rdisc, A, P, M, k, R, B_full,
         rsh, bshift, dist, low3) = qrow(mhex)
        F = rsh - bshift
        if F < 0:
            continue
        kf = k + F
        APf = (A + P) << F
        res_hw = R + {"clean": 0, "down": -1, "up": 1}[lab]
        EU = (APf - B_full) >> kf
        req2 = res_hw - EU
        Vlow = (APf - B_full) - (EU << kf)
        base = Vlow << 2
        top = 1 << (kf + 2)
        jlo = jhi = None
        for j in range(-16, 17):
            T = base - j * rfv
            pred = 1 if T >= top else (-1 if T < 0 else 0)
            if pred == req2:
                if jlo is None:
                    jlo = j
                jhi = j
        if jlo is None:
            continue
        f4_full = sqv * sqv
        s4 = f4_full.bit_length() - 67
        qr = ((t4 << 2) + (1 << (s4 - 1))) >> s4
        qf = (t4 << 2) >> s4
        strat = (dist, low3, ce)
        for c in CS:
            if jlo <= qr + c <= jhi:
                cen[("r", strat, c)] += 1
                cen[("rt", strat, c, theta)] += 1
            if jlo <= qf + c <= jhi:
                cen[("f", strat, c)] += 1
        cen[("n", strat)] += 1
        cen[("nt", strat, theta)] += 1
    return cen


def main():
    rows = []
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
    stride = int(sys.argv[1]) if len(sys.argv) > 1 else 4
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
    cen = defaultdict(int)
    for part in parts:
        for kk, v in part.items():
            cen[kk] += v
    strata = sorted(set(kk[1] for kk in cen if kk[0] == "n"))
    tot_best = tot_n = 0
    print(f"\n{'stratum':16s} {'n':>7s} {'best_c':>6s} "
          f"{'rate':>7s} {'floor_c/rate':>13s}   per-theta at best")
    for strat in strata:
        n = cen[("n", strat)]
        br = max(CS, key=lambda c: cen.get(("r", strat, c), 0))
        bf = max(CS, key=lambda c: cen.get(("f", strat, c), 0))
        rr = cen.get(("r", strat, br), 0) / n
        rf2 = cen.get(("f", strat, bf), 0) / n
        ths = []
        for th in (-2, -1, 0, 1, 2):
            nt = cen.get(("nt", strat, th), 0)
            if nt:
                g = cen.get(("rt", strat, br, th), 0)
                ths.append(f"{th:+d}:{g/nt:.2f}")
        tot_best += cen.get(("r", strat, br), 0)
        tot_n += n
        print(f"{str(strat):16s} {n:7d} {br:6d} {rr:7.4f} "
              f"{bf:6d}/{rf2:.4f}   {' '.join(ths)}")
    print(f"\nGLOBAL with per-stratum c (round variant): "
          f"{tot_best}/{tot_n} ({tot_best/tot_n:.4f})")


if __name__ == "__main__":
    main()
