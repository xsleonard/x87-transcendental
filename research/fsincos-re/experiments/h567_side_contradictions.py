#!/usr/bin/env python3
"""h567: side-resolved contradiction census.

Claim under test: the hidden (arrangement) variable acts ONLY on
each stratum's hard side.  Method: bin rows into tight value cells
(stratum, XD12, x4 to 1/16 ladder-unit, mf to 2^-13) SEPARATELY
per side (up = theta<=0, dn = theta>=1).  A cell is CONTRADICTORY
if the intersection of its rows' J-intervals is empty (no single j
explains all rows).  Report, per stratum and side: cells, rows,
contradictory cells, rows in them.  Also the joint-side version
(both sides pooled) for reference.
Prediction: contradiction mass on the exact side ~0; on the hard
side substantial.
"""
import sys
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h539_D_library import qrow


def work(rows):
    out = []
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
        x4 = t4 * 2.0**(65 - s4) / rfv
        XD12 = min(11, (rdisc * 12) >> rsh)
        mf = m / 2**64
        side = "up" if theta <= 0 else "dn"
        cell = ((dist, low3, ce), XD12, int(x4 * 16),
                int(mf * 8192))
        out.append((cell, side, jlo, jhi))
    return out


def census(cells):
    res = defaultdict(lambda: [0, 0, 0, 0])  # cells rows ccells crows
    for (strat, *_), ivs in cells.items():
        lo = max(iv[0] for iv in ivs)
        hi = min(iv[1] for iv in ivs)
        r = res[strat]
        r[0] += 1
        r[1] += len(ivs)
        if lo > hi:
            r[2] += 1
            r[3] += len(ivs)
    return res


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
    stride = int(sys.argv[1]) if len(sys.argv) > 1 else 1
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
    per_side = {"up": defaultdict(list), "dn": defaultdict(list)}
    joint = defaultdict(list)
    for part in parts:
        for cell, side, jlo, jhi in part:
            per_side[side][cell].append((jlo, jhi))
            joint[cell].append((jlo, jhi))
    cen = {s: census(c) for s, c in per_side.items()}
    cj = census(joint)
    print(f"\n{'stratum':14s} {'side':4s} {'cells':>8s} {'rows':>8s}"
          f" {'contra_cells':>12s} {'contra_rows':>11s} {'frac':>7s}")
    strata = sorted(set(list(cen['up']) + list(cen['dn'])))
    for strat in strata:
        for side in ("up", "dn"):
            r = cen[side].get(strat)
            if not r:
                continue
            print(f"{str(strat):14s} {side:4s} {r[0]:8d} {r[1]:8d}"
                  f" {r[2]:12d} {r[3]:11d} {r[3]/r[1]:7.4f}")
        r = cj.get(strat)
        print(f"{str(strat):14s} {'both':4s} {r[0]:8d} {r[1]:8d}"
              f" {r[2]:12d} {r[3]:11d} {r[3]/r[1]:7.4f}")


if __name__ == "__main__":
    main()
