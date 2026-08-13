#!/usr/bin/env python3
"""h601: score the comb-7-fitted J1 selector on comb-8 (fresh
near-tie comb, DISJOINT window [0xC8, 0xF0)) — the dn-side
cross-window validation.  Model from h600_model.json.  Scores
every fitted stratum present, both sides (dn = theta >= 1 rows,
the ones tie combs cannot reach).  EU-anchored clean labels.
"""
import json
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h577_three_term import qrow3
from h588_select import split_words

MODES = ROUNDING_MODES
STRATA = {(8, 4, -73): "dn", (8, 5, -73): "dn",
          (8, 6, -73): "dn", (8, 7, -73): "dn",
          (9, 2, -72): "up", (9, 3, -72): "up",
          (9, 4, -72): "up", (9, 5, -72): "up",
          (9, 6, -72): "dn", (9, 7, -72): "dn"}


def _ws(f4v, rfv):
    S, C = split_words(f4v, rfv)
    return S + C


def row_score(args):
    mhex, ce, theta, hw = args
    (m, R, A, P, B_full, rsh, rdisc, lsh, ldisc, s4, t4,
     bshift, k, dist, low3) = qrow3(mhex)
    strat = (dist, low3, ce)
    fit_side = STRATA.get(strat)
    if fit_side is None:
        return None
    side = "up" if theta <= 0 else "dn"
    if side != fit_side:
        return (strat, side, "offside")
    F = rsh - bshift
    if F < 0:
        return None
    kf = k + F
    APf = (A + P) << F
    EU = (APf - B_full) >> kf
    za, zb = (0, 1) if side == "up" else (-1, 0)
    ra = [final_cosine_result(-(EU + za), ce, md)
          for md in MODES]
    rb = [final_cosine_result(-(EU + zb), ce, md)
          for md in MODES]
    if ra == rb:
        return (strat, side, "blind")
    if side == "up":
        fire = 1 if hw == rb else (0 if hw == ra else -1)
    else:
        fire = 1 if hw == ra else (0 if hw == rb else -1)
    if fire < 0:
        return (strat, side, "other")
    Vlow = (APf - B_full) - (EU << kf)
    import h539_D_library as DL
    qr = DL.qrow(mhex)
    sc = _ws(qr[2], qr[3])
    tau = t4 / (1 << s4)
    mf = (m & ((1 << 63) - 1)) / (1 << 63)
    xd12 = min(11, (rdisc * 12) >> rsh)
    st = (sc >> max(rsh - 59, 0)) & 63
    return (strat, side, "ok", fire, tau, mf, xd12, st, Vlow,
            kf, qr[3], theta)


def main():
    mdl = json.load(open("h600_model.json"))
    fits = {eval(k): tuple(v) for k, v in
            mdl["fits"].items() if v is not None}
    cbest = {eval(k): v for k, v in mdl["cbest"].items()}
    seen = set()
    raw = []
    for line in open("ties_comb8.txt"):
        f = line.split()
        if f[0] in seen:
            continue
        seen.add(f[0])
        raw.append(f)
    inputs = sorted(f[0] for f in raw)
    order = {m2: i for i, m2 in enumerate(inputs)}
    st = {md: open(f"comb8_{md}_status.txt").read()
          .splitlines() for md in MODES}
    jobs = []
    for f in raw:
        strat = (int(f[1]), int(f[2]), int(f[8]))
        if strat not in STRATA:
            continue
        i = order[f[0]]
        hw, bad = [], False
        for md in MODES:
            t = st[md][i].split()
            if t[0] != "OK":
                bad = True
                break
            hw.append(int(t[2], 16))
        if bad:
            continue
        jobs.append((f[0], int(f[8]), int(f[9]), hw))
    print(f"comb-8 rows in fitted strata: {len(jobs)}",
          flush=True)
    with Pool(15) as pool:
        feats = pool.map(row_score, jobs, chunksize=300)
    res = defaultdict(lambda: defaultdict(int))
    theta_res = defaultdict(lambda: [0, 0])
    for r in feats:
        if r is None:
            continue
        strat, side = r[0], r[1]
        key = strat + (side,)
        if r[2] in ("blind", "other", "offside"):
            res[key][r[2]] += 1
            continue
        (_, _, _, fire, tau, mf, xd12, st2, Vlow, kf, rfv,
         theta) = r
        zid = (strat, xd12)
        fz = fits.get(zid)
        if fz is None:
            res[key]["nozone"] += 1
            continue
        q, a, b = fz
        x = q * tau + a * mf + b + cbest.get((zid, st2), 0)
        j = round(x)
        req2p = (4 * Vlow - j * rfv) >> (kf + 2)
        pred = 1 if req2p == (1 if side == "up" else -1) else 0
        res[key]["n"] += 1
        ok = pred == fire
        res[key]["ok"] += ok
        theta_res[(key, theta)][0] += ok
        theta_res[(key, theta)][1] += 1
    print(f"\n{'stratum/side':22s} {'n':>7s} {'acc':>8s} "
          f"{'blind':>6s} {'other':>6s} {'nozone':>7s}")
    tot = defaultdict(int)
    for key in sorted(res):
        r = res[key]
        n = r["n"]
        print(f"{str(key):22s} {n:7d} "
              f"{r['ok'] / max(n, 1):8.4f} {r['blind']:6d} "
              f"{r['other']:6d} {r['nozone']:7d}")
        for kk in ("n", "ok", "blind", "other", "nozone"):
            tot[kk] += r[kk]
    print(f"{'TOTAL':22s} {tot['n']:7d} "
          f"{tot['ok'] / max(tot['n'], 1):8.4f} "
          f"{tot['blind']:6d} {tot['other']:6d} "
          f"{tot['nozone']:7d}")
    print("\ndn strata by theta:")
    for (key, theta), (ok, n) in sorted(theta_res.items(),
                                        key=str):
        if key[3] == "dn":
            print(f"  {key} theta={theta}: {ok}/{n} = "
                  f"{ok / max(n, 1):.4f}")


if __name__ == "__main__":
    main()
