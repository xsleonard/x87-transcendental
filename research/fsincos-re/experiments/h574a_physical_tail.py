#!/usr/bin/env python3
"""h574a: WHICH physical tail term?  Per (stratum, side) compare:
  V1 : D = tau * 2^c            (fixed-column slot; c 58..68)
  P1 : D = tail9 * rfv * 2^-9 / 2^(s4-9)
       = (t4 >> (s4-9)) * rfv * 2^(9-s4)   (76-bit f4 operand:
       9 extra tail bits, rf-scaled, 9-bit resolution)
  P1w: same with w extra bits, w in {5..13}
  P3 : D = t4 * rfv * 2^-s4     (fully unchopped f4, rf-scaled)
  All + per-(XD12) zone offset, split-half, exact-D scoring
  against the h538 brackets (code units u = 4/rfv).
Also h574b: for the offset-only strata ((9,1..4)@-72 dn), print
the fitted per-zone offsets in ladder units to look for rational
structure.
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
        tau = t4 / 2.0**s4
        # P1w family in code units: (t4 >> (s4-w)) * rfv *
        # 2^(w-s4) * u = (t4 >> (s4-w)) * 2^(w-s4+2)
        p1 = {}
        for w in range(5, 14):
            if s4 > w:
                p1[w] = (t4 >> (s4 - w)) * 2.0**(w - s4 + 2)
            else:
                p1[w] = t4 * 2.0**(2 - 0)  # s4<=w: full tail
        p3 = tau * 4.0  # t4*rfv*2^-s4 * u = tau*4
        XD12 = min(11, (rdisc * 12) >> rsh)
        half = (m * 2654435761) & 1
        side = "up" if theta <= 0 else "dn"
        out.append(((dist, low3, ce), side, XD12, half,
                    tau, p1, p3, dlo, dhi))
    return out


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
        iv = [(p[4] - basef(p), p[5] - basef(p)) for p in pl]
        c, b = stab(iv)
        fitted[z] = b
    ok = n = 0
    for p in pts_te:
        b = fitted.get(p[0])
        if b is None:
            continue
        n += 1
        D = basef(p) + b
        if p[4] < D <= p[5]:
            ok += 1
    return (ok, n), fitted


def eval_group(key):
    pts_tr, pts_te = GROUP[key]
    res = {}
    best = ((0, 1), None, None)
    for s in (1, -1):
        for c in range(58, 69):
            f = s * 2.0**c
            (o, n), fits = fit_score(pts_tr, pts_te,
                                     lambda p, f=f: f * p[1])
            if o * best[0][1] > best[0][0] * max(n, 1):
                best = ((o, n), (s, c), fits)
    res["V1"] = best[:2]
    v0, fits0 = fit_score(pts_tr, pts_te, lambda p: 0.0)
    res["V0"] = (v0, None)
    res["V0fits"] = fits0
    bp1 = ((0, 1), None)
    for s in (1, -1):
        for w in range(5, 14):
            (o, n), _ = fit_score(pts_tr, pts_te,
                                  lambda p, s=s, w=w: s * p[2][w])
            if o * bp1[0][1] > bp1[0][0] * max(n, 1):
                bp1 = ((o, n), (s, w))
    res["P1"] = bp1
    bp3 = ((0, 1), None)
    for s in (1, -1):
        (o, n), _ = fit_score(pts_tr, pts_te,
                              lambda p, s=s: s * p[3])
        if o * bp3[0][1] > bp3[0][0] * max(n, 1):
            bp3 = ((o, n), s)
    res["P3"] = bp3
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
        for strat, side, XD12, half, tau, p1, p3, dlo, dhi \
                in part:
            pt = (XD12, tau, p1, p3, dlo, dhi)
            groups[(strat, side)][0 if half == 0 else 1].append(pt)
    groups = dict(groups)
    keys = sorted(groups)
    with Pool(8, initializer=init_g,
              initargs=(groups,)) as pool:
        results = pool.map(eval_group, keys)
    print(f"\n{'stratum':14s} {'side':4s} {'V0':>7s} {'V1':>7s}"
          f" {'V1par':>9s} {'P1':>7s} {'P1par':>8s} {'P3':>7s}"
          f" {'P3s':>4s}")
    OFFSET_ONLY = {((9, 1, -72), "dn"), ((9, 2, -72), "dn"),
                   ((9, 3, -72), "dn"), ((9, 4, -72), "dn")}
    for key, res in results:
        strat, side = key
        (o0, n0), _ = res["V0"]
        (o1, n1), p1p = res["V1"]
        (op, np_), pp = res["P1"]
        (o3, n3), p3s = res["P3"]
        print(f"{str(strat):14s} {side:4s} "
              f"{o0/max(n0,1):7.4f} {o1/max(n1,1):7.4f} "
              f"{str(p1p):>9s} {op/max(np_,1):7.4f} "
              f"{str(pp):>8s} {o3/max(n3,1):7.4f} "
              f"{str(p3s):>4s}")
        if key in OFFSET_ONLY:
            fits = res["V0fits"]
            offs = " ".join(f"{z}:{fits[z]:+.3f}"
                            for z in sorted(fits))
            print(f"    offsets(ladder units): {offs}")


if __name__ == "__main__":
    main()
