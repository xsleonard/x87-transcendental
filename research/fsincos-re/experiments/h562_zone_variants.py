#!/usr/bin/env python3
"""h562: zone-structure variants for the open strata.

Shared rows (comb-7, all theta, J-intervals).  Variants, all
split-half held-out:
  V1: zones (strat, XD48),           j = round(4tau + a*mf + b)
  V2: zones (strat, XD12, tau-qtr),  j = round(4tau + a*mf + b)
  V4: zones (strat, XD12),  j = round(4tau + a*mf + d*XD + b)
Baseline for comparison: h558 = zones (strat, XD12), 0.958.
Reports per-variant global + per-stratum held-out and the theta
split of V-best misses.
"""
import sys
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h539_D_library import qrow


def stab(intervals):
    ev = []
    for lo, hi in intervals:
        ev.append((lo, 1))
        ev.append((hi, -1))
    ev.sort()
    best = (0, None)
    cur = 0
    for x, d in ev:
        cur += d
        if cur > best[0]:
            best = (cur, x)
    return best


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
        tau4 = (t4 * 4) / 2**s4
        XD = rdisc / 2**rsh
        mf = m / 2**64
        half = (m * 2654435761) & 1
        out.append(((dist, low3, ce), half, tau4, XD, mf,
                    jlo, jhi, theta))
    return out


def fit_eval(rows, keyf, argf, param_grid):
    """rows: list of tuples; keyf(row)->zone key; argf(row, p)
    -> base argument (without b); returns held-out stats."""
    tr = defaultdict(list)
    te = defaultdict(list)
    for r in rows:
        (tr if r[1] == 0 else te)[keyf(r)].append(r)
    fitted = {}
    for key, pts in tr.items():
        best = (0, None, None)
        for p in param_grid:
            iv = []
            for r in pts:
                x = argf(r, p)
                iv.append((r[5] - 0.5 - x, r[6] + 0.5 - x))
            c, b = stab(iv)
            if c > best[0]:
                best = (c, p, b)
        fitted[key] = best
    ok = n = 0
    per_strat = defaultdict(lambda: [0, 0])
    th_miss = defaultdict(int)
    for key, pts in te.items():
        f2 = fitted.get(key)
        if f2 is None or f2[1] is None:
            continue
        _, p, b = f2
        for r in pts:
            jp = round(argf(r, p) + b)
            good = r[5] <= jp <= r[6]
            n += 1
            ps = per_strat[r[0]]
            ps[1] += 1
            if good:
                ok += 1
                ps[0] += 1
            else:
                th_miss[r[7]] += 1
    return ok, n, per_strat, th_miss


def main():
    rows_l = []
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
    rows = [r for part in parts for r in part]
    AS = list(range(-60, 9, 2))
    variants = {
        "V1_xd48": (
            lambda r: (r[0], min(47, int(r[3] * 48))),
            lambda r, p: r[2] + p * r[4],
            AS),
        "V2_tauq": (
            lambda r: (r[0], min(11, int(r[3] * 12)),
                       min(3, int(r[2]))),
            lambda r, p: r[2] + p * r[4],
            AS),
        "V4_xdterm": (
            lambda r: (r[0], min(11, int(r[3] * 12))),
            lambda r, p: r[2] + p[0] * r[4] + p[1] * r[3],
            [(a, d) for a in range(-60, 9, 4)
             for d in range(-8, 9, 2)]),
    }
    results = {}
    for name, (keyf, argf, grid) in variants.items():
        ok, n, per_strat, th_miss = fit_eval(rows, keyf, argf,
                                             grid)
        results[name] = (ok, n, per_strat, th_miss)
        print(f"\n{name}: HELD-OUT {ok}/{n} ({ok/n:.4f})",
              flush=True)
        for s2 in sorted(per_strat):
            o2, n2 = per_strat[s2]
            print(f"  {s2}: {o2/n2:.4f} ({n2})")
        print("  misses by theta:",
              dict(sorted(th_miss.items())))


if __name__ == "__main__":
    main()
