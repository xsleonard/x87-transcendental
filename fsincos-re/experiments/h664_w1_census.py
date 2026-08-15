#!/usr/bin/env python3
"""h664: label the W1 corpus (comb11) + comb9 theta=+2, census the
r59/r60 uncovered strata.

Round 60 left the r57 statistical tables alive only for two fringe
strata the mined corpora could not constrain:
  (a) quadrant (s4=66, side=0) at theta != 0 — structurally ABSENT
      from every [0xA8,0xF0)-window corpus (comb7/8/9: 0 rows);
      comb5/comb6 cover the quadrant but are theta=0-only captures.
  (b) dn theta=+2 quadrant (67,1) — present (528,775 rows comb7+8)
      but firing exactly once (the documented h658 anomaly row
      dac0000002eba759).
comb11 (run_scan17.sh) is the W1 window [0x80,0xA8) with the theta
scanner: the first theta-labeled corpus containing (66,0).  This
script labels it (h657m recipe, theta=0 rows INCLUDED), labels
comb9's theta=+2 rows, and answers: do the strata fire at all?
For theta=0 rows it also scores the h646/h656 closed form — W1 may
hold (66,0) dists outside comb5/comb6's support, testing the W(d)
ladder extrapolation baked into Round 60.

Caches: h664_<c>.pkl rows =
  (mhex, theta, dist, s4, side, L, rdisc, sR, label, M, sqlow)
  label: 0 clean, 1 fire_dn (R-1), 2 fire_up (R+1), -1 unmatched.
"""
import os, pickle, sys
from collections import Counter, defaultdict
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h453_chain_variants import (C6_1, C6_2, C6_3, C6_4, C6_5, C6_6,
                                 build_chain, mul_round)

E2M = -66
PIV = 0.70710678118654752
UNIT = 2**66

QUAD = {
    (66, 1): (2, 2, 1,  0, 4, 1, 0, lambda d: -5 * (d - 7)),
    (66, 0): (4, 1, 0,  0, 2, 1, 0, lambda d: -9 - 5 * (d - 9)),
    (67, 0): (4, 2, 1, -2, 4, 2, 1, lambda d: -5 * (d - 7)),
    (67, 1): (2, 2, 3, -3, 8, 2, 1, lambda d: -4 - 2 * (d - 7)),
}


def load3(ties, prefix, thetas=None):
    rows, seen = [], set()
    for lineS in open(ties):
        f = lineS.split()
        if f[0] in seen:
            continue
        seen.add(f[0])
        rows.append(f)
    inputs = sorted(f[0] for f in rows)
    order = {mm: i for i, mm in enumerate(inputs)}
    st = {md: open(f"{prefix}_{md}_status.txt").read().splitlines()
          for md in ROUNDING_MODES}
    out = []
    for f in rows:
        theta = int(f[9])
        if thetas is not None and theta not in thetas:
            continue
        R, ce, i = int(f[7], 16), int(f[8]), order[f[0]]
        hw, bad = [], False
        for md in ROUNDING_MODES:
            t = st[md][i].split()
            if t[0] != "OK":
                bad = True
                break
            hw.append(int(t[2], 16))
        if bad:
            continue
        clean = [final_cosine_result(-R, ce, md) for md in ROUNDING_MODES]
        dn = [final_cosine_result(-(R - 1), ce, md) for md in ROUNDING_MODES]
        up = [final_cosine_result(-(R + 1), ce, md) for md in ROUNDING_MODES]
        if hw == clean:
            out.append((f[0], 0, theta))
        elif hw == dn:
            out.append((f[0], 1, theta))
        elif hw == up:
            out.append((f[0], 2, theta))
        else:
            out.append((f[0], -1, theta))
    return out


def internals(args):
    mhex, label, theta = args
    m = int(mhex, 16)
    mag0 = (0, E2M, m)
    square = mul_round(mag0, mag0, 67, "chop")
    fourth = mul_round(square, square, 67, "chop")
    neg = build_chain(fourth, C6_5, C6_3, C6_1, 67, 64, "rn", False, False, False)
    pos = build_chain(fourth, C6_6, C6_4, C6_2, 67, 64, "rn", False, False, False)
    left = mul_round(square, neg, 67, "chop")
    right = mul_round(fourth, pos, 67, "chop")
    dist = abs(left[1] - right[1])
    sq = square[2]
    f4 = sq * sq
    s4 = f4.bit_length() - 67
    t4 = f4 & ((1 << s4) - 1)
    sqlow = sq - (1 << 66)
    M = (sq & 7) * sqlow - t4
    rprod = fourth[2] * pos[2]
    sR = rprod.bit_length() - 67
    rdisc = rprod & ((1 << sR) - 1)
    side = 0 if m / 2**64 < PIV else 1
    return (mhex, theta, dist, s4, side, sq & 7, rdisc, sR, label, M, sqlow)


def u_of(quad, dist, L, b1, b2):
    a, G1, G2, p, Q, K, par, W = QUAD[quad]
    lp = L % 2
    return K * ((a * L + G1 * b1 + G2 * b2 + p * lp + W(dist)) // Q) + par * lp


def census(name, rows):
    print(f"\n================ {name}: {len(rows)} labeled rows ================")
    unm = sum(1 for r in rows if r[8] == -1)
    if unm:
        print(f"  UNMATCHED (hw not in R-1/R/R+1): {unm}")
    tot = Counter()
    fir = Counter()
    for r in rows:
        mhex, th, dist, s4, side, L, rdisc, sR, label, M, sqlow = r
        if label < 0:
            continue
        tot[(s4, side, th)] += 1
        if label:
            fir[(s4, side, th)] += 1
    print("  (s4,side) x theta: rows / fires")
    for k in sorted(tot):
        print(f"    (s4={k[0]}, side={k[1]}) th={k[2]:+d}: "
              f"{tot[k]:>9,} / {fir[k]:>8,}")

    # stratum (a): quadrant (66,0) theta != 0, fires by cell
    cells = defaultdict(lambda: [0, 0])
    for r in rows:
        mhex, th, dist, s4, side, L, rdisc, sR, label, M, sqlow = r
        if (s4, side) != (66, 0) or th == 0 or label < 0:
            continue
        sign = "dn" if th > 0 else "up"
        fire = int(label == (1 if th > 0 else 2))
        c = cells[(sign, abs(th), dist, L)]
        c[0] += 1
        c[1] += fire
    if cells:
        print("  (66,0) theta!=0 by (sign,|th|,dist,L): rows/fires")
        for k in sorted(cells):
            n, nf = cells[k]
            print(f"    {k}: {n:>7,} / {nf:>6,}")

    # stratum (b): dn theta=+2 (67,1)
    n = nf = 0
    for r in rows:
        mhex, th, dist, s4, side, L, rdisc, sR, label, M, sqlow = r
        if th == 2 and (s4, side) == (67, 1) and label >= 0:
            n += 1
            if label == 1:
                nf += 1
                print(f"  dn th=+2 (67,1) FIRE: {r[0]} dist={dist} L={L}")
    print(f"  dn th=+2 (67,1): rows={n:,} dn-fires={nf}")

    # theta=0: score the h646/h656 closed form per quadrant
    sc = defaultdict(lambda: [0, 0, 0, 0])   # n, fires, fneg, mneg
    for r in rows:
        mhex, th, dist, s4, side, L, rdisc, sR, label, M, sqlow = r
        if th != 0 or label < 0:
            continue
        b1 = 1 if 3 * rdisc >= (1 << sR) else 0
        b2 = 1 if 3 * rdisc >= (1 << (sR + 1)) else 0
        pred = int(M < u_of((s4, side), dist, L, b1, b2) * UNIT)
        obs = int(label == 1)
        s = sc[(s4, side, dist)]
        s[0] += 1
        s[1] += obs
        if pred and not obs:
            s[2] += 1
        if obs and not pred:
            s[3] += 1
    if sc:
        print("  theta=0 h646/h656 law: (s4,side,dist): "
              "rows fires false+ miss")
        for k in sorted(sc):
            n, nf, fp, ms = sc[k]
            flag = "  <-- MISMATCH" if fp or ms else ""
            print(f"    {k}: {n:>8,} {nf:>7,} {fp:>5} {ms:>5}{flag}")


def main():
    for name in sys.argv[1:]:
        cache = f"h664_{name}.pkl"
        if os.path.exists(cache):
            out = pickle.load(open(cache, "rb"))
            print(f"{name}: {len(out)} rows from cache", flush=True)
        else:
            thetas = None
            if name == "comb9":
                thetas = {2}       # dn th=+2 concurrence only
            lab = load3(f"ties_{name}.txt", name, thetas)
            print(f"{name}: {len(lab)} labeled; internals ...", flush=True)
            with Pool(os.cpu_count()) as pool:
                out = pool.map(internals, lab, chunksize=2000)
            pickle.dump(out, open(cache, "wb"))
        census(name, out)


if __name__ == "__main__":
    main()
