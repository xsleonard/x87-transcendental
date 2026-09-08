#!/usr/bin/env python3
"""h543: REQUIRED-EPSILON MINING (inversion stage 3).

Family: hardware B' = (f4v*2^e + eps)*rf with its low-w columns
dropped; Dn(eps) = chunk(eps) - eps*rf where
chunk(eps) = ((f4v*2^e + eps)*rf) mod 2^w.
Exact requirement per row (T-floor, no convention freedom):
  req2 = floor((Vlow*2^e + Dn) / 2^(kf+e))
E(row) = set of eps in [0, 2^e) whose Dn satisfies the label.

If the class is right, some map eps = g(f4-tail bits, ...) has
g(row) in E(row) for every row.  Census: tail4 x E-bitmask, the
membership rate of the natural eps = tail (top-e tail bits), per
theta and per stratum.  e = 4, w in {64, 68}.
"""
import sys
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h539_D_library import qrow

E = 4
WS = [64, 68]


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
        tail = (f4_full >> (s4 - E)) - (f4v << E)
        base = Vlow << E
        top = 1 << (kf + E)
        for w in WS:
            wm = (1 << w) - 1
            eset = 0
            for eps in range(1 << E):
                Bp = (f4v * (1 << E) + eps) * rfv
                Dn = (Bp & wm) - eps * rfv
                T = base + Dn
                r = 1 if T >= top else (-1 if T < 0 else 0)
                if r == req2:
                    eset |= 1 << eps
            cen[("mask", w, theta, tail, eset)] += 1
            cen[("member", w, theta,
                 1 if (eset >> tail) & 1 else 0)] += 1
            cen[("strat", w, dist, low3, ce,
                 1 if (eset >> tail) & 1 else 0)] += 1
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
    for w in WS:
        print(f"\n=== w={w}: eps=tail membership by theta ===")
        for theta in (-2, -1, 0, 1, 2):
            good = cen.get(("member", w, theta, 1), 0)
            badn = cen.get(("member", w, theta, 0), 0)
            if good + badn:
                print(f"  theta={theta:+d}: {good}/{good+badn} "
                      f"({good/(good+badn):.4f})")
        print(f"  strata with worst membership (w={w}):")
        srows = []
        for kk, v in cen.items():
            if kk[0] == "strat" and kk[1] == w and kk[5] == 0:
                tot = v + cen.get(("strat", w, kk[2], kk[3],
                                   kk[4], 1), 0)
                srows.append((v / tot, v, tot,
                              (kk[2], kk[3], kk[4])))
        srows.sort(reverse=True)
        for r, v, tot, s2 in srows[:12]:
            print(f"    {s2}: {v}/{tot} bad ({r:.3f})")
    # the E-mask structure at theta=0, w=64: what do the sets look
    # like vs tail?
    print("\n=== theta=0, w=64: top (tail, mask) rows ===")
    mrows = [(v, kk[3], kk[4]) for kk, v in cen.items()
             if kk[0] == "mask" and kk[1] == 64 and kk[2] == 0]
    mrows.sort(reverse=True)
    for v, tail, mask in mrows[:24]:
        print(f"  tail={tail:2d} mask={mask:016b} n={v}")


if __name__ == "__main__":
    main()
