#!/usr/bin/env python3
"""h549: test closed-form j-maps against the required-j sets.

j(row) candidates (tau = t4/2^s4, f4's fractional tail):
  A: floor(4*tau)              B: round(4*tau)
  C: floor(4*tau) - 4*[tau>=1/2]   (signed chop)
  D: round(4*tau) - 4          E: round(4*tau)-4 if tau>=1/2 else
                                  round(4*tau)   (signed round)
  P/Q: A/C with tau from the parity-shifted anchor (s4-1).
Membership of j_map in J(row) per map, overall / per theta / per
stratum-worst.  A ~100% map = the resolver found.
"""
import sys
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h539_D_library import qrow

JS = list(range(-8, 9))


def maps(f4_full, s4):
    t4 = f4_full & ((1 << s4) - 1)
    q = (t4 << 2) >> s4              # floor(4 tau) 0..3
    qr = ((t4 << 2) + (1 << (s4 - 1))) >> s4   # round(4 tau) 0..4
    half = 1 if (t4 >> (s4 - 1)) & 1 else 0
    t4b = f4_full & ((1 << (s4 - 1)) - 1)      # parity-shifted tail
    qb = (t4b << 2) >> (s4 - 1)
    halfb = 1 if (t4b >> (s4 - 2)) & 1 else 0
    return {
        "A": q,
        "B": qr,
        "C": q - 4 * half,
        "D": qr - 4,
        "E": qr - 4 if half else qr,
        "P": qb,
        "Q": qb - 4 * halfb,
    }


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
        f4_full = sqv * sqv
        s4 = f4_full.bit_length() - 67
        base = Vlow << 2
        top = 1 << (kf + 2)
        okj = set()
        for j in JS:
            T = base - j * rfv
            pred = 1 if T >= top else (-1 if T < 0 else 0)
            if pred == req2:
                okj.add(j)
        mp = maps(f4_full, s4)
        for name, j in mp.items():
            good = 1 if j in okj else 0
            cen[("m", name, good)] += 1
            cen[("t", name, theta, good)] += 1
            cen[("s", name, (dist, low3, ce), good)] += 1
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
    stride = int(sys.argv[1]) if len(sys.argv) > 1 else 8
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
    for name in "ABCDEPQ":
        good = cen.get(("m", name, 1), 0)
        bad = cen.get(("m", name, 0), 0)
        if good + bad == 0:
            continue
        ths = " ".join(
            f"{th:+d}:{cen.get(('t', name, th, 0), 0)}"
            for th in (-2, -1, 0, 1, 2))
        print(f"map {name}: member {good}/{good+bad} "
              f"({good/(good+bad):.4f})  miss by theta: {ths}")
    # worst strata for the best map
    best = max("ABCDEPQ",
               key=lambda nm: cen.get(("m", nm, 1), 0))
    srows = []
    for kk, v in cen.items():
        if kk[0] == "s" and kk[1] == best and kk[3] == 0:
            tot = v + cen.get(("s", best, kk[2], 1), 0)
            srows.append((v / tot, v, tot, kk[2]))
    srows.sort(reverse=True)
    print(f"\nworst strata for map {best}:")
    for r, v, tot, s2 in srows[:10]:
        print(f"  {s2}: {v}/{tot} ({r:.4f})")


if __name__ == "__main__":
    main()
