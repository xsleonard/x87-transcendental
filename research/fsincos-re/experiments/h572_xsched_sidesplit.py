#!/usr/bin/env python3
"""h572: the paired (FSINCOS) cos lane in the side-split frame.

comb-7 sincos x3 captured (run_cap571).  Questions:
  A. Label census: d_sc = res_sc - R in [-6..6] window vs theta;
     OTHER fraction (paired-window rows); req2_fc vs req2_sc
     agreement per stratum.
  B. Does the PAIRED lane have an affine-exact side?  Per
     (stratum, XD12, theta-side) fits like h565, held-out.
  C. h567-analog tight-cell contradiction census for sc labels
     per side: does the paired lane's hidden component lateralize,
     and to the SAME side as standalone FCOS?
J-intervals generalized: J = {j in [-32,32] :
(base - j*rfv) // top == req2} (monotone -> interval).
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


def jint(base, top, rfv, req2, lim=32):
    jlo = jhi = None
    for j in range(-lim, lim + 1):
        if (base - j * rfv) // top == req2:
            if jlo is None:
                jlo = j
            jhi = j
    return jlo, jhi


def work(rows):
    out = []
    for mhex, theta, dfc, dscs, ce in rows:
        (m, sqv, f4v, rfv, t4, rdisc, A, P, M, k, R, B_full,
         rsh, bshift, dist, low3) = qrow(mhex)
        F = rsh - bshift
        if F < 0:
            continue
        kf = k + F
        APf = (A + P) << F
        EU = (APf - B_full) >> kf
        Vlow = (APf - B_full) - (EU << kf)
        base = Vlow << 2
        top = 1 << (kf + 2)
        req2_fc = (R + dfc) - EU
        req2_scs = [(R + d) - EU for d in dscs] if dscs else None
        f4_full = sqv * sqv
        s4 = f4_full.bit_length() - 67
        x4 = t4 * 2.0**(65 - s4) / rfv
        XD12 = min(11, (rdisc * 12) >> rsh)
        mf = m / 2**64
        half = (m * 2654435761) & 1
        rec = [(dist, low3, ce), XD12, half, theta, x4, mf,
               req2_fc, None, None, None]
        if req2_scs:
            los, his = [], []
            for r2 in req2_scs:
                lo2, hi2 = jint(base, top, rfv, r2)
                if lo2 is not None:
                    los.append(lo2)
                    his.append(hi2)
            if los:
                rec[8], rec[9] = min(los), max(his)
            rec[7] = min(req2_scs, key=abs)
        cell = ((dist, low3, ce), XD12, int(x4 * 16),
                int(mf * 8192))
        out.append((tuple(rec), cell))
    return out


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
    sc = {md: open(f"comb7_sc_{md}_status.txt").read()
          .splitlines() for md in ROUNDING_MODES}
    stride = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    labeled = []
    n_other = 0
    dsc_census = defaultdict(int)
    for j, f in enumerate(raw):
        if j % stride:
            continue
        R, ce, theta = int(f[7], 16), int(f[8]), int(f[9])
        i = order[f[0]]
        hw, schw, bad = [], [], False
        for md in ROUNDING_MODES:
            t = st[md][i].split()
            t2 = sc[md][i].split()
            if t[0] != "OK" or t2[0] != "OK":
                bad = True
                break
            hw.append(int(t[2], 16))
            schw.append(int(t2[4], 16))
        if bad:
            continue
        refs = {d: [final_cosine_result(-(R + d), ce, md)
                    for md in ROUNDING_MODES]
                for d in range(-6, 7)}
        dfcs = [d for d in range(-6, 7) if hw == refs[d]]
        dscs = [d for d in range(-6, 7) if schw == refs[d]]
        dfc = min((d for d in dfcs if d in (-1, 0, 1)),
                  key=abs, default=None)
        if dfc is None:
            continue
        if not dscs:
            n_other += 1
            dsc_census[(theta, None)] += 1
        else:
            dsc_census[(theta, min(dscs, key=abs))] += 1
        labeled.append((f[0], theta, dfc, dscs, ce))
    print(f"labeled: {len(labeled)}  sc-OTHER: {n_other} "
          f"({n_other/len(labeled):.4f})", flush=True)
    print("\nA. d_sc census by theta (columns d=-6..6, O=other):")
    for th in (-2, -1, 0, 1, 2):
        tot = sum(v for (t, d), v in dsc_census.items()
                  if t == th)
        if not tot:
            continue
        line = [f"th={th:+d} n={tot:7d}: "]
        for d in list(range(-6, 7)) + [None]:
            v = dsc_census.get((th, d), 0)
            if v:
                tag = "O" if d is None else f"{d:+d}"
                line.append(f"{tag}:{v/tot:.3f}")
        print("  " + " ".join(line))
    chunks = [labeled[i::8] for i in range(8)]
    with Pool(8) as pool:
        parts = pool.map(work, chunks)
    recs = []
    for part in parts:
        recs.extend(part)
    # req2 agreement per stratum
    agree = defaultdict(lambda: [0, 0])
    for rec, cell in recs:
        strat, XD12, half, theta, x4, mf, rfc, rsc, jlo, jhi = rec
        if rsc is None:
            continue
        a = agree[strat]
        a[1] += 1
        if rfc == rsc:
            a[0] += 1
    print("\nA2. req2_fc == req2_sc rate per stratum:")
    for strat in sorted(agree):
        ok, n = agree[strat]
        print(f"  {strat}: {ok/n:.4f} ({n})")
    # B: sc affine fits per (stratum, XD12, side)
    tr = defaultdict(list)
    te = defaultdict(list)
    for rec, cell in recs:
        strat, XD12, half, theta, x4, mf, rfc, rsc, jlo, jhi = rec
        if jlo is None:
            continue
        side = "up" if theta <= 0 else "dn"
        key = (strat, XD12, side)
        (tr if half == 0 else te)[key].append((x4, mf, jlo, jhi))
    fitted = {}
    for key, pts in tr.items():
        best = (0, None, None)
        for a in AG:
            iv = [(jlo - 0.5 - x4 - a * mf,
                   jhi + 0.5 - x4 - a * mf)
                  for x4, mf, jlo, jhi in pts]
            c, b = stab(iv)
            if c > best[0]:
                best = (c, a, b)
        fitted[key] = best
    S = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for key, pts in te.items():
        f2 = fitted.get(key)
        if f2 is None or f2[1] is None:
            continue
        _, a, b = f2
        strat, XD12, side = key
        for x4, mf, jlo, jhi in pts:
            s2 = S[strat][side]
            s2[1] += 1
            if jlo <= round(x4 + a * mf + b) <= jhi:
                s2[0] += 1
    print("\nB. sc-lane per-side affine held-out:")
    print(f"{'stratum':14s} {'up':>7s} {'n':>7s} {'dn':>7s} "
          f"{'n':>7s}")
    for strat in sorted(S):
        d = S[strat]
        u, un = d.get("up", [0, 0])
        dn, dnn = d.get("dn", [0, 0])
        print(f"{str(strat):14s} "
              f"{u/un if un else 0:7.4f} {un:7d} "
              f"{dn/dnn if dnn else 0:7.4f} {dnn:7d}")
    # C: tight-cell contradiction census for sc, per side
    cells = defaultdict(list)
    for rec, cell in recs:
        strat, XD12, half, theta, x4, mf, rfc, rsc, jlo, jhi = rec
        if jlo is None:
            continue
        side = "up" if theta <= 0 else "dn"
        cells[(cell, side)].append((jlo, jhi))
    res = defaultdict(lambda: [0, 0])
    for (cell, side), ivs in cells.items():
        lo = max(iv[0] for iv in ivs)
        hi = min(iv[1] for iv in ivs)
        r = res[(cell[0], side)]
        r[0] += len(ivs)
        if lo > hi:
            r[1] += len(ivs)
    print("\nC. sc tight-cell contradiction rows per (stratum,"
          " side):")
    for (strat, side) in sorted(res):
        n, c = res[(strat, side)]
        print(f"  {strat} {side}: {c}/{n} ({c/n:.4f})")


if __name__ == "__main__":
    main()
