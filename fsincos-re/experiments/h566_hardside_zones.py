#!/usr/bin/env python3
"""h566: zone battery on the HARD SIDE only.

h565: each stratum has one affine-exact side and one hard side
(dist=8: down/theta>=1 hard; dist=9 low low3: up/theta<=0 hard).
Sweep zonings for the hard side alone, own affine line per zone,
split-half held-out:
  Z1: (strat, XD12)      [h565 D2 baseline]
  Z2: (strat, XD24)
  Z3: (strat, XD48)
  Z4: (strat, XD12, tau-quarter)
  Z5: (strat, XD12, mf-eighth)   -- m-region zoning
Hard side def: dist==8 -> theta>=1 rows; dist==9 -> theta<=0 rows.
(Also runs dist=9 high-low3 @-72 down rows as hard for 5..7.)
"""
import sys
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h539_D_library import qrow

AG = list(range(-80, 9, 2))


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


def hard(dist, low3, theta):
    if dist == 8:
        return theta >= 1
    if dist == 9 and low3 <= 4:
        return theta <= 0
    if dist == 9:
        return theta >= 1
    return False


def work(rows):
    out = []
    for mhex, theta, lab, ce in rows:
        (m, sqv, f4v, rfv, t4, rdisc, A, P, M, k, R, B_full,
         rsh, bshift, dist, low3) = qrow(mhex)
        if not hard(dist, low3, theta):
            continue
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
        XDf = rdisc / 2**rsh
        mf = m / 2**64
        half = (m * 2654435761) & 1
        out.append(((dist, low3, ce), half, x4, XDf, mf,
                    jlo, jhi))
    return out


def run_zoning(rowsl, keyf, tag):
    tr = defaultdict(list)
    te = defaultdict(list)
    for r in rowsl:
        key = keyf(r)
        (tr if r[1] == 0 else te)[key].append(r)
    fitted = {}
    for key, pts in tr.items():
        best = (0, None, None)
        for a in AG:
            iv = [(p[5] - 0.5 - p[2] - a * p[4],
                   p[6] + 0.5 - p[2] - a * p[4]) for p in pts]
            c, b = stab(iv)
            if c > best[0]:
                best = (c, a, b)
        fitted[key] = best
    ok = n = 0
    per_strat = defaultdict(lambda: [0, 0])
    for key, pts in te.items():
        f2 = fitted.get(key)
        if f2 is None or f2[1] is None:
            continue
        _, a, b = f2
        for p in pts:
            jp = round(p[2] + a * p[4] + b)
            good = p[5] <= jp <= p[6]
            n += 1
            ps = per_strat[p[0]]
            ps[1] += 1
            if good:
                ok += 1
                ps[0] += 1
    print(f"\n{tag}: HARD-SIDE HELD-OUT {ok}/{n} ({ok/n:.4f})",
          flush=True)
    for s2 in sorted(per_strat):
        o2, n2 = per_strat[s2]
        print(f"  {s2}: {o2/n2:.4f} ({n2})")


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
    rowsl = [r for part in parts for r in part]
    print(f"hard-side rows: {len(rowsl)}")
    run_zoning(rowsl, lambda r: (r[0], min(11, int(r[3] * 12))),
               "Z1_xd12")
    run_zoning(rowsl, lambda r: (r[0], min(23, int(r[3] * 24))),
               "Z2_xd24")
    run_zoning(rowsl, lambda r: (r[0], min(47, int(r[3] * 48))),
               "Z3_xd48")
    run_zoning(rowsl,
               lambda r: (r[0], min(11, int(r[3] * 12)),
                          min(3, int(r[2]))),
               "Z4_xd12_tauq")
    run_zoning(rowsl,
               lambda r: (r[0], min(11, int(r[3] * 12)),
                          int(r[4] * 128)),
               "Z5_xd12_mf128")


if __name__ == "__main__":
    main()
