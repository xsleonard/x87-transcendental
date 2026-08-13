#!/usr/bin/env python3
"""h573b: per-(stratum, side) TERM INVENTORY for exact-D.

For each stratum and side, fit and score (split-half):
  V0: D = c(zone)                       zone = XD12
  V1: D = t4*2^(c4-s4)*u + c(zone)      c4 scanned 58..68, sign +-
  V2: V1 + a*mf                          a scanned -80..8 step 4
  V3: V1 + rdisc-term (cd scanned, sign) instead of mf
Exact (unrounded) D scored against the h538 brackets.  Output: the
minimal term set per (stratum, side) and its held-out rate — the
draft wiring table a circuit must reproduce.
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
        u = 4.0 / rfv
        dlo = (Vlow - ((req2 + 1) << kf)) * u
        dhi = (Vlow - (req2 << kf)) * u
        f4_full = sqv * sqv
        s4 = f4_full.bit_length() - 67
        t4f = t4 * u / 2.0**s4
        rdf = rdisc * u / 2.0**rsh
        XD12 = min(11, (rdisc * 12) >> rsh)
        mf = m / 2**64
        half = (m * 2654435761) & 1
        side = "up" if theta <= 0 else "dn"
        out.append(((dist, low3, ce), side, XD12, half,
                    t4f, rdf, mf, dlo, dhi))
    return out


C4S = [(s, c) for s in (1, -1) for c in range(58, 69)]
AS = list(range(-80, 9, 4))
CDS = [(s, c) for s in (1, -1) for c in range(58, 69)]

GROUP = None


def init_g(g):
    global GROUP
    GROUP = g


def fit_score(pts_tr, pts_te, basef):
    zones_tr = defaultdict(list)
    for p in pts_tr:
        zones_tr[p[0]].append(p)
    fitted = {}
    for z, pl in zones_tr.items():
        iv = [(p[5] - basef(p), p[6] - basef(p)) for p in pl]
        c, b = stab(iv)
        fitted[z] = b
    ok = n = 0
    for p in pts_te:
        b = fitted.get(p[0])
        if b is None:
            continue
        D = basef(p) + b
        n += 1
        if p[5] < D <= p[6]:
            ok += 1
    return ok, n


def eval_group(key):
    pts_tr, pts_te = GROUP[key]
    res = {}
    res["V0"] = (fit_score(pts_tr, pts_te, lambda p: 0.0), None)
    best = ((0, 1), None)
    for s, c in C4S:
        f = s * 2.0**c
        r = fit_score(pts_tr, pts_te,
                      lambda p, f=f: f * p[1])
        if r[0] * best[0][1] > best[0][0] * max(r[1], 1):
            best = (r, (s, c))
    res["V1"] = best
    s1, c1 = best[1] if best[1] else (1, 63)
    f1 = s1 * 2.0**c1
    best2 = ((0, 1), None)
    for a in AS:
        r = fit_score(pts_tr, pts_te,
                      lambda p, f1=f1, a=a: f1 * p[1] + a * p[3])
        if r[0] * best2[0][1] > best2[0][0] * max(r[1], 1):
            best2 = (r, (s1, c1, a))
    res["V2"] = best2
    best3 = ((0, 1), None)
    for s, c in CDS:
        f2 = s * 2.0**c
        r = fit_score(pts_tr, pts_te,
                      lambda p, f1=f1, f2=f2: f1 * p[1] + f2 * p[2])
        if r[0] * best3[0][1] > best3[0][0] * max(r[1], 1):
            best3 = (r, (s1, c1, s, c))
    res["V3"] = best3
    return key, res


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
    groups = defaultdict(lambda: ([], []))
    for part in parts:
        for strat, side, XD12, half, t4f, rdf, mf, dlo, dhi \
                in part:
            pt = (XD12, t4f, rdf, mf, None, dlo, dhi)
            groups[(strat, side)][0 if half == 0 else 1].append(pt)
    groups = dict(groups)
    keys = sorted(groups)
    with Pool(8, initializer=init_g,
              initargs=(groups,)) as pool:
        results = pool.map(eval_group, keys)
    print(f"\n{'stratum':14s} {'side':4s} {'V0':>7s} {'V1':>7s}"
          f" {'V1par':>9s} {'V2':>7s} {'V2a':>5s} {'V3':>7s}"
          f" {'V3par':>10s}")
    for key, res in results:
        strat, side = key
        (o0, n0), _ = res["V0"]
        (o1, n1), p1 = res["V1"]
        (o2, n2), p2 = res["V2"]
        (o3, n3), p3 = res["V3"]
        print(f"{str(strat):14s} {side:4s} "
              f"{o0/max(n0,1):7.4f} {o1/max(n1,1):7.4f} "
              f"{str(p1):>9s} {o2/max(n2,1):7.4f} "
              f"{p2[2] if p2 else 0:5d} {o3/max(n3,1):7.4f} "
              f"{str(p3[2:] if p3 else None):>10s}")


if __name__ == "__main__":
    main()
