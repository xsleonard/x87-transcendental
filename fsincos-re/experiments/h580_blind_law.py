#!/usr/bin/env python3
"""h580: BLIND VALIDATION of the universal threshold law on
combs 5+6 (disjoint m-windows; ties only, theta=0 -> up-side).

LOCKED LAW (from comb-7, h575/h576 — no refitting here):
  up-side prediction at ties: req2=+1 (res = EU+1) iff
     Vlow >= 2^kf - [(rdisc << CR >> rsh) - (ldisc << 67 >> lsh)
                     - 2^(kf-7)]
  with CR = 65 for dist=8 strata (the h576 up-easy config),
  and the h575 zero-param variant (CR=63, no ldisc, no const)
  reported alongside.
Score every labeled tie in combs 5/6; report per stratum:
n, accuracy for LAW-A (65,-l,-c) and LAW-B (63 bare).
dist=9 ties are up-side rows too (hard side there — report but
expect degraded).  Window W1=[0x80,0xA8) comb5, W2=[0xF0,0x100)
comb6.
"""
import sys
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h577_three_term import qrow3


def work(rows):
    cen = defaultdict(int)
    for mhex, lab, ce in rows:
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
        # LAW-A
        TA = (rdisc << 65 >> rsh) - (ldisc << 67 >> lsh) \
            - (1 << max(kf - 7, 0))
        predA = 1 if Vlow >= (1 << kf) - TA else 0
        # LAW-B
        TB = rdisc << 63 >> rsh
        predB = 1 if Vlow >= (1 << kf) - TB else 0
        cen[(strat, "n")] += 1
        if predA == req2:
            cen[(strat, "A")] += 1
        if predB == req2:
            cen[(strat, "B")] += 1
    return dict(cen)


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
                out.append((f[0], nm, ce))
                break
    return out


def main():
    for cname, spre, stride in (("ties_comb5.txt", "comb5", 2),
                                ("ties_comb6.txt", "comb6", 4)):
        rows = load_comb(cname, spre, stride)
        print(f"\n===== {cname}: labeled {len(rows)} =====",
              flush=True)
        chunks = [rows[i::8] for i in range(8)]
        with Pool(8) as pool:
            parts = pool.map(work, chunks)
        cen = defaultdict(int)
        for part in parts:
            for kk, v in part.items():
                cen[kk] += v
        strata = sorted(set(kk[0] for kk in cen))
        totA = totB = totn = 0
        for strat in strata:
            n = cen.get((strat, "n"), 0)
            if n < 200:
                continue
            a = cen.get((strat, "A"), 0)
            b = cen.get((strat, "B"), 0)
            totA += a
            totB += b
            totn += n
            print(f"  {strat}: n={n:6d}  LAW-A {a/n:.5f}  "
                  f"LAW-B {b/n:.5f}")
        print(f"  TOTAL: LAW-A {totA/max(totn,1):.5f}  "
              f"LAW-B {totB/max(totn,1):.5f}")


if __name__ == "__main__":
    main()
