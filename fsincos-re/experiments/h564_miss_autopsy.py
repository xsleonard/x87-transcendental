#!/usr/bin/env python3
"""h564: autopsy of the h559-form selector's held-out misses in the
open dist=8 strata ((8,4)/(8,5)/(8,6)@-73).

Fit j = round(x4 + a*mf + b) per (stratum, XD12) zone on half A,
collect every half-B miss, and characterize misses vs hits:
  - by how far the predicted j falls outside [jlo, jhi] (1 step or
    many);
  - tau-fraction position (frac(4*tau)) — near .5 = rounding-edge?
  - J-interval width (narrow intervals = informative rows);
  - XD fine position within the twelfth (echo-stripe adjacency);
  - mf position within the zone's fitted line (banding);
  - theta slice.
Output: per-stratum summary + a TSV of miss rows for eyeballing.
"""
import sys
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h539_D_library import qrow

AG = list(range(-80, 9, 2))
TARGET = {(8, 4, -73), (8, 5, -73), (8, 6, -73)}


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
        if (dist, low3, ce) not in TARGET:
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
        out.append((mhex, (dist, low3, ce), half, x4, XDf, mf,
                    jlo, jhi, theta))
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
    tr = defaultdict(list)
    te = defaultdict(list)
    for part in parts:
        for r in part:
            key = (r[1], min(11, int(r[4] * 12)))
            (tr if r[2] == 0 else te)[key].append(r)
    fitted = {}
    for key, pts in tr.items():
        best = (0, None, None)
        for a in AG:
            iv = [(r[6] - 0.5 - r[3] - a * r[5],
                   r[7] + 0.5 - r[3] - a * r[5]) for r in pts]
            c, b = stab(iv)
            if c > best[0]:
                best = (c, a, b)
        fitted[key] = best
    outf = open("h564_misses.tsv", "w")
    print("mhex\tstrat\tXD12\ttau4frac\tXDfine\tmf\tjlo\tjhi\tjpred"
          "\ttheta\twidth\tover", file=outf)
    stats = defaultdict(lambda: defaultdict(int))
    for key, pts in te.items():
        f2 = fitted.get(key)
        if f2 is None or f2[1] is None:
            continue
        _, a, b = f2
        for r in pts:
            mhex, strat, _, x4, XDf, mf, jlo, jhi, theta = r
            xarg = x4 + a * mf + b
            jp = round(xarg)
            S = stats[strat]
            S["n"] += 1
            width = jhi - jlo
            tfrac = xarg - int(xarg)
            edge = min(abs(tfrac - 0.5), abs(tfrac + 0.5))
            if jlo <= jp <= jhi:
                S["ok"] += 1
                if width == 0:
                    S["ok_w0"] += 1
                if edge < 0.1:
                    S["ok_edge"] += 1
            else:
                over = jlo - jp if jp < jlo else jp - jhi
                S["miss"] += 1
                S[f"miss_over_{min(over,3)}"] += 1
                S[f"miss_th_{theta}"] += 1
                if width == 0:
                    S["miss_w0"] += 1
                if edge < 0.1:
                    S["miss_edge"] += 1
                xd12 = key[1]
                xdfine = XDf * 12 - xd12
                print(f"{mhex}\t{strat}\t{xd12}\t{x4 - int(x4):.4f}"
                      f"\t{xdfine:.4f}\t{mf:.6f}\t{jlo}\t{jhi}"
                      f"\t{jp}\t{theta}\t{width}\t{over}",
                      file=outf)
    outf.close()
    for strat in sorted(stats):
        S = stats[strat]
        n, ok, miss = S["n"], S["ok"], S["miss"]
        print(f"\n{strat}: n={n} ok={ok/n:.4f} miss={miss}")
        print(f"  overshoot dist: 1:{S['miss_over_1']} "
              f"2:{S['miss_over_2']} 3+:{S['miss_over_3']}")
        print(f"  misses by theta: "
              + " ".join(f"{t}:{S[f'miss_th_{t}']}"
                         for t in (-2, -1, 0, 1, 2)))
        print(f"  rounding-edge (|frac-.5|<.1): miss {S['miss_edge']}"
              f"/{miss} vs ok {S['ok_edge']}/{ok}")
        print(f"  width0 rows: miss {S['miss_w0']} ok {S['ok_w0']}")


if __name__ == "__main__":
    main()
