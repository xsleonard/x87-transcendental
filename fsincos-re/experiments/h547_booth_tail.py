#!/usr/bin/env python3
"""h547: BOOTH-TAIL-ROW GATE (exact, the convergent candidate).

The staircase (h546) pins the resolver delta to the ladder
j*rf/4, j in [-6, 6] — exactly the value range of the Booth-encode
difference of the f4 multiplier at its 67-bit chop boundary:
  c0 = f4_g row-0 overlap change   (value +-rf)
  dA = extra tail digit at bits (f4_g, b2, b3), standard radix-4
       table (value in [-2, 2] * rf/4)
Hardware B' = B + D, D = (s0*c0*4 + s1*dA) * rf/4, conventions
s0, s1 in {-1, 0, +1}.  pred req2 = floor(((Vlow<<2) - Dq)/2^(kf+2)),
Dq = 4D.  Exact score vs labels, all theta, per stratum.
"""
import sys
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h539_D_library import qrow

M4 = {0: 0, 1: 1, 2: 1, 3: 2, 4: -2, 5: -1, 6: -1, 7: 0}
CONFIGS = [(s0, s1) for s0 in (-1, 0, 1) for s1 in (-1, 0, 1)]


def work(rows):
    res = {cfg: defaultdict(int) for cfg in CONFIGS}
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
        b1 = (f4_full >> (s4 - 1)) & 1
        b2 = (f4_full >> (s4 - 2)) & 1
        b3 = (f4_full >> (s4 - 3)) & 1
        dA = M4[(b1 << 2) | (b2 << 1) | b3]
        strat = (dist, low3, ce)
        base = Vlow << 2
        top = 1 << (kf + 2)
        for cfg in CONFIGS:
            s0, s1 = cfg
            Dq = (s0 * b1 * 4 + s1 * dA) * rfv
            T = base - Dq
            pred = 1 if T >= top else (-1 if T < 0 else 0)
            ok = pred == req2
            res[cfg][("t", theta, ok)] += 1
            res[cfg][("s", strat, ok)] += 1
    return res


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
    agg = {cfg: defaultdict(int) for cfg in CONFIGS}
    for part in parts:
        for cfg, d in part.items():
            for kk, v in d.items():
                agg[cfg][kk] += v
    print(f"\n{'cfg':>9s} {'errs':>8s}  per-theta errs")
    ranked = []
    for cfg, d in agg.items():
        errs = sum(v for kk, v in d.items()
                   if kk[0] == "t" and not kk[2])
        n = sum(v for kk, v in d.items() if kk[0] == "t")
        ranked.append((errs, n, cfg))
    ranked.sort(key=lambda x: x[0])
    for errs, n, cfg in ranked:
        d = agg[cfg]
        ths = " ".join(
            f"{th:+d}:{d.get(('t', th, False), 0)}"
            for th in (-2, -1, 0, 1, 2))
        print(f"{str(cfg):>9s} {errs:8d}  {ths}")
    best = ranked[0][2]
    print(f"\nper-stratum errors for best {best}:")
    d = agg[best]
    strata = sorted(set(kk[1] for kk in d if kk[0] == "s"))
    for strat in strata:
        bad = d.get(("s", strat, False), 0)
        n = bad + d.get(("s", strat, True), 0)
        print(f"  {strat}: {bad}/{n} ({bad/n:.4f})")


if __name__ == "__main__":
    main()
