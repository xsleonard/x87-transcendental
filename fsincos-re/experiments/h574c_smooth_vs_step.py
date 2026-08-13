#!/usr/bin/env python3
"""h574c: smooth-value vs twelfth-quantized rdisc consumption.

On the EXACT sides ((9,1..4)@-72 dn: q = 11 - XD12 at 1.0000;
dist=8 up: piecewise A_r - 2*XD12), test at full resolution with
NO zones:
  S1  : D = (c0 - floor(12*XD)) * s      quarters, s=1 (d9) 2 (d8)
  S1b : D = (c0 - floor(24*XD)/2) * s    24th-quantized
  S1c : D = (c0 - floor(48*XD)/4) * s    48th-quantized
  S2  : D = c0 - rdisc*2^(C-rsh) * (4/rfv) * s' (smooth value;
        C in {63..67}; expressed in quarters)
  c0 fit on half A (integer for S1*, continuous for S2), scored
  half B; per stratum; breaks at thirds handled for dist=8 by
  fitting c0 per XD-third region (3 constants).
Exactness verdict decides: value-wire vs digit-table.
"""
import sys
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h539_D_library import qrow

D9 = {(9, 1, -72), (9, 2, -72), (9, 3, -72), (9, 4, -72)}
D8 = {(8, 3, -73), (8, 4, -73), (8, 5, -73), (8, 6, -73),
      (8, 7, -73)}


def work(rows):
    out = []
    for mhex, theta, lab, ce in rows:
        (m, sqv, f4v, rfv, t4, rdisc, A, P, M, k, R, B_full,
         rsh, bshift, dist, low3) = qrow(mhex)
        strat = (dist, low3, ce)
        side = "up" if theta <= 0 else "dn"
        if not ((strat in D9 and side == "dn") or
                (strat in D8 and side == "up")):
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
        uq = 16.0 / rfv        # quarters per raw unit
        qlo = (Vlow - ((req2 + 1) << kf)) * uq
        qhi = (Vlow - (req2 << kf)) * uq
        XD = rdisc / 2.0**rsh
        # smooth term candidates in quarters: rdisc*2^(C-rsh)*uq
        sm = {C: rdisc * 2.0**(C - rsh) * uq
              for C in (63, 64, 65, 66, 67)}
        half = (m * 2654435761) & 1
        out.append((strat, half, XD, sm, qlo, qhi))
    return out


def stab_c(ivs):
    ev = []
    for lo, hi in ivs:
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


def stab_i(ivs):
    cands = set()
    for lo, hi in ivs[:600]:
        cands.add(int(lo) + 1)
        cands.add(int(hi))
    best = (-1, None)
    for q in cands:
        c = sum(1 for lo, hi in ivs if lo < q <= hi)
        if c > best[0]:
            best = (c, q)
    return best


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
    groups = defaultdict(lambda: ([], []))
    for part in parts:
        for strat, half, XD, sm, qlo, qhi in part:
            groups[strat][0 if half == 0 else 1].append(
                (XD, sm, qlo, qhi))
    for strat in sorted(groups):
        tr, te = groups[strat]
        print(f"\n{strat}: n_tr={len(tr)} n_te={len(te)}")
        slope = 1 if strat[0] == 9 else 2
        region = (lambda XD: 0) if strat[0] == 9 else \
            (lambda XD: 0 if XD < 1/3 else (1 if XD < 2/3 else 2))
        for name, quant in (("S1_12th", 12), ("S1b_24th", 24),
                            ("S1c_48th", 48)):
            fits = {}
            rints = defaultdict(list)
            for XD, sm, qlo, qhi in tr:
                stepv = int(XD * quant) * 12.0 / quant
                rints[region(XD)].append(
                    (qlo + slope * stepv, qhi + slope * stepv))
            for r, iv in rints.items():
                c, q = stab_i(iv)
                fits[r] = q
            ok = n = 0
            for XD, sm, qlo, qhi in te:
                q = fits.get(region(XD))
                if q is None:
                    continue
                stepv = int(XD * quant) * 12.0 / quant
                n += 1
                if qlo + slope * stepv < q <= qhi + slope * stepv:
                    ok += 1
            print(f"  {name}: {ok}/{n} ({ok/max(n,1):.5f}) "
                  f"c0={fits}")
        for C in (63, 64, 65, 66, 67):
            rints = defaultdict(list)
            for XD, sm, qlo, qhi in tr:
                rints[region(XD)].append((qlo + sm[C],
                                          qhi + sm[C]))
            fits = {}
            for r, iv in rints.items():
                c, b = stab_c(iv)
                fits[r] = b
            ok = n = 0
            for XD, sm, qlo, qhi in te:
                b = fits.get(region(XD))
                if b is None:
                    continue
                n += 1
                if qlo + sm[C] < b <= qhi + sm[C]:
                    ok += 1
            fstr = {r: f"{v:.2f}" for r, v in fits.items()}
            print(f"  S2_C{C}: {ok}/{n} ({ok/max(n,1):.5f}) "
                  f"c0={fstr}")


if __name__ == "__main__":
    main()
