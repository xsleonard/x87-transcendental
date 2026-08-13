#!/usr/bin/env python3
"""h545: per-stratum cut-column solve (inversion, stage 4).

Family per row: B' = fe*rf (fe = f4 with e extra chop bits), low-w
columns of B' dropped; pred req2 = floor((Vlow*2^e + Dn)/2^(kf+e)),
Dn = (B' mod 2^w) - eps*rf.  For EACH stratum (dist, low3, ce) and
config (w, e) count errors over all theta.  If strata admit
zero-error (w, e), the residual unknown reduces to the alignment map
w(stratum).  Reports per-stratum best and the error matrix around
it, plus theta-split at the best.
"""
import sys
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h539_D_library import qrow

WS = list(range(56, 73))
ES = [0, 1, 2]
CONFIGS = [(w, e) for w in WS for e in ES]


def work(rows):
    res = defaultdict(int)
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
        strat = (dist, low3, ce)
        for w, e in CONFIGS:
            fe = f4_full >> (s4 - e)
            eps = fe - (f4v << e)
            Bp = fe * rfv
            Dn = (Bp & ((1 << w) - 1)) - eps * rfv
            T = (Vlow << e) + Dn
            top = 1 << (kf + e)
            pred = 1 if T >= top else (-1 if T < 0 else 0)
            ok = pred == req2
            res[(strat, w, e, "n")] += 1
            if not ok:
                res[(strat, w, e, "err")] += 1
                res[(strat, w, e, "err_th", theta)] += 1
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
    agg = defaultdict(int)
    for part in parts:
        for kk, v in part.items():
            agg[kk] += v
    strata = sorted(set(kk[0] for kk in agg))
    print(f"\n{'stratum':16s} {'n':>7s}  best(w,e) err  runner-ups")
    for strat in strata:
        best = []
        for w, e in CONFIGS:
            n = agg.get((strat, w, e, "n"), 0)
            if not n:
                continue
            err = agg.get((strat, w, e, "err"), 0)
            best.append((err, w, e, n))
        best.sort()
        if not best:
            continue
        err, w, e, n = best[0]
        ths = {th: agg.get((strat, w, e, "err_th", th), 0)
               for th in (-2, -1, 0, 1, 2)}
        ru = " ".join(f"({b[1]},{b[2]}):{b[0]}" for b in best[1:4])
        print(f"{str(strat):16s} {n:7d}  w={w} e={e} "
              f"err={err} ({err/n:.4f}) th={ths}  | {ru}")


if __name__ == "__main__":
    main()
