#!/usr/bin/env python3
"""h600: CROSS-WINDOW BLIND VALIDATION of the comb-7-fitted J1
selector on the tie combs 3-6 (theta=0, up side; combs 5/6 are
disjoint m-windows).

Fit = h599's (refit here and SAVED to h600_model.json).
Score: for each comb, rows in the fitted strata, EU-anchored
clean labels (blind rows dropped), J1 prediction vs hardware.
Usage: h600_xwindow.py [comb numbers, default 3 4 5 6]
"""
import json
import sys
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h577_three_term import qrow3
from h588_select import split_words
from h598_jframe import jinterval, QGRID, AGRID

MODES = ROUNDING_MODES
STRATA = {(8, 4, -73): "dn", (8, 5, -73): "dn",
          (8, 6, -73): "dn", (8, 7, -73): "dn",
          (9, 2, -72): "up", (9, 3, -72): "up",
          (9, 4, -72): "up", (9, 5, -72): "up",
          (9, 6, -72): "dn", (9, 7, -72): "dn"}


def _ws(args):
    f4v, rfv = args
    S, C = split_words(f4v, rfv)
    return S + C


ZROWS = None


def init_z(z):
    global ZROWS
    ZROWS = z


def fit_zone(zone_id):
    rows = ZROWS[zone_id]
    best = (-1, None)
    for q in QGRID:
        for a in AGRID:
            ev = []
            for (tau, mf, jlo, jhi, st) in rows:
                if jlo > jhi:
                    continue
                x = q * tau + a * mf
                ev.append((jlo - 0.5 - x, 1))
                ev.append((jhi + 0.5 - x, -1))
            if not ev:
                continue
            ev.sort()
            cur = 0
            bestc = -1
            bestb = 0.0
            for pos, d in ev:
                cur += d
                if cur > bestc:
                    bestc = cur
                    bestb = pos + 1e-9
            if bestc > best[0]:
                best = (bestc, (q, a, bestb))
    return zone_id, best[1]


def fit_model():
    raw = []
    for line in open("h596_hard.tsv"):
        f = line.split()
        strat = (int(f[1]), int(f[2]), int(f[3]))
        if strat not in STRATA:
            continue
        raw.append((f[0], strat, f[4], int(f[5]), int(f[6]),
                    int(f[7], 16), int(f[8], 16), int(f[9]),
                    int(f[11]), int(f[12], 16),
                    int(f[13], 16), int(f[15], 16),
                    int(f[16])))
    with Pool(15) as pool:
        wss = pool.map(_ws, [(r[5], r[6]) for r in raw],
                       chunksize=1000)
    zrows = defaultdict(list)
    for r, sc in zip(raw, wss):
        (mhex, strat, side, theta, fire, f4v, rfv, rsh, kf,
         Vlow, rdisc, t4, s4) = r
        req2 = (1 if fire else 0) if side == "up" else \
            (-1 if fire else 0)
        jlo, jhi = jinterval(Vlow, kf, rfv, req2)
        tau = t4 / (1 << s4)
        m = int(mhex, 16)
        mf = (m & ((1 << 63) - 1)) / (1 << 63)
        xd12 = min(11, (rdisc * 12) >> rsh)
        st = (sc >> max(rsh - 59, 0)) & 63
        zrows[(strat, xd12)].append((tau, mf, jlo, jhi, st))
    zlist = sorted(zrows, key=str)
    with Pool(15, initializer=init_z,
              initargs=(dict(zrows),)) as pool:
        fits = dict(pool.map(fit_zone, zlist))
    coff = defaultdict(lambda: defaultdict(int))
    for zid, rows in zrows.items():
        f = fits.get(zid)
        if f is None:
            continue
        q, a, b = f
        for tau, mf, jlo, jhi, st in rows:
            if jlo > jhi:
                continue
            x = q * tau + a * mf + b
            for c in range(-3, 4):
                if jlo <= round(x + c) <= jhi:
                    coff[(zid, st)][c] += 1
    cbest = {k: max(v, key=v.get) for k, v in coff.items()}
    json.dump({"fits": {str(k): v for k, v in fits.items()},
               "cbest": {str(k): v for k, v in
                         cbest.items()}},
              open("h600_model.json", "w"))
    print(f"model: {len(fits)} zones, {len(cbest)} offsets",
          flush=True)
    return fits, cbest


def comb_feat(args):
    mhex, R, ce, hw = args
    (m, R2, A, P, B_full, rsh, rdisc, lsh, ldisc, s4, t4,
     bshift, k, dist, low3) = qrow3(mhex)
    strat = (dist, low3, ce)
    side = STRATA.get(strat)
    if side != "up":  # ties are theta=0 = up side only
        return None
    F = rsh - bshift
    if F < 0:
        return None
    kf = k + F
    APf = (A + P) << F
    EU = (APf - B_full) >> kf
    r0 = [final_cosine_result(-EU, ce, md) for md in MODES]
    r1 = [final_cosine_result(-(EU + 1), ce, md)
          for md in MODES]
    if r0 == r1:
        return (strat, "blind")
    if hw == r1:
        fire = 1
    elif hw == r0:
        fire = 0
    else:
        return (strat, "other")
    Vlow = (APf - B_full) - (EU << kf)
    import h539_D_library as DL
    qr = DL.qrow(mhex)
    sc = _ws((qr[2], qr[3]))
    tau = t4 / (1 << s4)
    mf = (m & ((1 << 63) - 1)) / (1 << 63)
    xd12 = min(11, (rdisc * 12) >> rsh)
    st = (sc >> max(rsh - 59, 0)) & 63
    return (strat, "ok", fire, tau, mf, xd12, st, Vlow, kf,
            qr[3])


def score_comb(cn, fits, cbest, pool):
    seen = set()
    raw = []
    for line in open(f"ties_comb{cn}.txt"):
        f = line.split()
        if f[0] in seen:
            continue
        seen.add(f[0])
        strat = (int(f[1]), int(f[2]), int(f[8]))
        if strat not in STRATA or STRATA[strat] != "up":
            continue
        raw.append(f)
    if not raw:
        print(f"comb-{cn}: no rows in fitted up-strata")
        return {}
    # status join needs the FULL sorted input list of the comb
    seen2 = set()
    allin = []
    for line in open(f"ties_comb{cn}.txt"):
        mh = line.split()[0]
        if mh not in seen2:
            seen2.add(mh)
            allin.append(mh)
    order = {m2: i for i, m2 in enumerate(sorted(allin))}
    st = {md: open(f"comb{cn}_{md}_status.txt").read()
          .splitlines() for md in MODES}
    jobs = []
    for f in raw:
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
        jobs.append((f[0], int(f[7], 16), int(f[8]), hw))
    feats = pool.map(comb_feat, jobs, chunksize=300)
    res = defaultdict(lambda: defaultdict(int))
    for r in feats:
        if r is None:
            continue
        strat = r[0]
        if r[1] in ("blind", "other"):
            res[strat][r[1]] += 1
            continue
        _, _, fire, tau, mf, xd12, st2, Vlow, kf, rfv = r
        zid = (strat, xd12)
        f = fits.get(zid)
        if f is None:
            res[strat]["nozone"] += 1
            continue
        q, a, b = f
        x = q * tau + a * mf + b + cbest.get((zid, st2), 0)
        j = round(x)
        req2p = (4 * Vlow - j * rfv) >> (kf + 2)
        pred = 1 if req2p == 1 else 0
        res[strat]["n"] += 1
        res[strat]["ok"] += pred == fire
    return res


def main():
    combs = [int(a) for a in sys.argv[1:]] or [3, 4, 5, 6]
    fits, cbest = fit_model()
    with Pool(15) as pool:
        for cn in combs:
            res = score_comb(cn, fits, cbest, pool)
            tot = defaultdict(int)
            for strat in sorted(res):
                r = res[strat]
                n = r["n"]
                acc = r["ok"] / max(n, 1)
                print(f"comb-{cn} {strat}: n={n} "
                      f"acc={acc:.4f} blind={r['blind']} "
                      f"other={r['other']} "
                      f"nozone={r['nozone']}", flush=True)
                for kk in ("n", "ok", "blind", "other",
                           "nozone"):
                    tot[kk] += r[kk]
            if tot["n"]:
                print(f"comb-{cn} TOTAL: n={tot['n']} "
                      f"acc={tot['ok'] / tot['n']:.4f} "
                      f"blind={tot['blind']} "
                      f"other={tot['other']} "
                      f"nozone={tot['nozone']}", flush=True)


if __name__ == "__main__":
    main()
