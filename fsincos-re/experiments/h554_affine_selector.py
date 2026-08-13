#!/usr/bin/env python3
"""h554: affine selector j = round(4*tau + a*mf + b) per stratum.

Per row the exact requirement is j in [jlo, jhi], i.e.
4*tau + a*mf + b in [jlo - 1/2, jhi + 1/2): for fixed a this is an
interval constraint on b — solved by interval stabbing per
(stratum, a).  Reports per stratum: best (a, b), coverage, and
whether a tracks -16*payload (the h504 slope law reexpressed).
"""
import sys
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h539_D_library import qrow

AS = list(range(-72, 1, 2))


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
        mf = m / 2**64
        out[(dist, low3, ce)].append((tau4, mf, jlo, jhi))
    return dict(out)


def stab(intervals):
    """max-coverage point over [lo, hi) intervals -> (count, b)."""
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
    print(f"\n{'stratum':16s} {'n':>7s} {'a*':>4s} {'b*':>9s} "
          f"{'cover':>7s}  {'-16*payload':>11s}")
    tot = totn = 0
    for key in sorted(strata):
        pts = strata[key]
        n = len(pts)
        best = (0, None, None)
        for a in AS:
            iv = [(jlo - 0.5 - t4a - a * mf,
                   jhi + 0.5 - t4a - a * mf)
                  for t4a, mf, jlo, jhi in pts]
            c, b = stab(iv)
            if c > best[0]:
                best = (c, a, b)
        c, a, b = best
        dist, low3, ce = key
        payload = low3 + 8 - dist
        print(f"{str(key):16s} {n:7d} {a:4d} {b:9.3f} "
              f"{c/n:7.4f}  {-16*payload:11d}")
        tot += c
        totn += n
    print(f"\nGLOBAL affine per-stratum: {tot}/{totn} "
          f"({tot/totn:.4f})")


if __name__ == "__main__":
    main()
