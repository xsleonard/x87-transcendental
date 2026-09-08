#!/usr/bin/env python3
"""h555: two residual closures for the selector.

(i) rf/8 ladder: J8-intervals from pred8(j8) with D = j8*rf/8;
    selector j8 = round(8*tau) + c8(stratum) — does doubling the
    digit depth absorb the ~7 percent residual?
(ii) rf/4 ladder with an XD term: j = round(4*tau + d*XD + b) per
    stratum (a-term from mf dropped — h554 showed it marginal),
    d grid, b by stabbing.
"""
import sys
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h539_D_library import qrow

DS = [x / 2 for x in range(-16, 17)]


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
    out = defaultdict(list)
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
        base = Vlow << 3
        top = 1 << (kf + 3)
        j8lo = j8hi = None
        for j8 in range(-32, 33):
            T = base - j8 * rfv
            pred = 1 if T >= top else (-1 if T < 0 else 0)
            if pred == req2:
                if j8lo is None:
                    j8lo = j8
                j8hi = j8
        if j8lo is None:
            continue
        f4_full = sqv * sqv
        s4 = f4_full.bit_length() - 67
        tau8 = (t4 * 8) / 2**s4
        XD = rdisc / 2**rsh
        out[(dist, low3, ce)].append((tau8, XD, j8lo, j8hi))
    return dict(out)


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
    stride = int(sys.argv[1]) if len(sys.argv) > 1 else 4
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
    strata = defaultdict(list)
    for part in parts:
        for key, v in part.items():
            strata[key].extend(v)
    print(f"\n{'stratum':16s} {'n':>7s} {'(i) j8+c8':>10s} "
          f"{'(ii) d*':>7s} {'b*':>8s} {'cover':>7s}")
    t1 = t2 = tn = 0
    for key in sorted(strata):
        pts = strata[key]
        n = len(pts)
        # (i) pure offset on the 8-ladder
        iv8 = [(j8lo - 0.5 - t8, j8hi + 0.5 - t8)
               for t8, XD, j8lo, j8hi in pts]
        c8, b8 = stab(iv8)
        # (ii) XD term on the 8-ladder scaled x2 (equiv rf/4 units
        # doubled) — use 8-lattice throughout for comparability
        best = (0, None, None)
        for d in DS:
            iv = [(j8lo - 0.5 - t8 - d * XD,
                   j8hi + 0.5 - t8 - d * XD)
                  for t8, XD, j8lo, j8hi in pts]
            c, b = stab(iv)
            if c > best[0]:
                best = (c, d, b)
        c, d, b = best
        print(f"{str(key):16s} {n:7d} {c8/n:10.4f} "
              f"{d:7.1f} {b:8.2f} {c/n:7.4f}")
        t1 += c8
        t2 += c
        tn += n
    print(f"\nGLOBAL: (i) round(8tau)+c8: {t1/tn:.4f}   "
          f"(ii) +XD term: {t2/tn:.4f}")


if __name__ == "__main__":
    main()
