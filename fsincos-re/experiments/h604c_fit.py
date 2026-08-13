#!/usr/bin/env python3
"""h604c: position-diverse refit of the W1 strata.

Fit rows: h604_rows.tsv (comb-5 on-grid + h604 +9*2^52
positions).  Held-out: POSITION-SPLIT (odd vs even position
buckets) — the honest test for range-shift structure.
Blind: the h603 locked+captured W1 rows (offset +5*2^52,
positions never seen by this fit; captured before it existed).
Merge updated W1 fits into h604_model_v3.json (all other
strata carried from h602_model_full.json).
"""
import json
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h577_three_term import qrow3
from h588_select import split_words
from h598_jframe import QGRID, AGRID
import h539_D_library as DL

MODES = ROUNDING_MODES
CAP = 20000


def fit_zone(args):
    zid, rows = args
    fitr = rows if len(rows) <= CAP else rows[::len(rows)
                                             // CAP + 1]
    for j in range(-16, 17):
        if all(jlo <= j <= jhi for tau, mf, jlo, jhi, st
               in fitr if jlo <= jhi):
            return zid, (0.0, 0.0, float(j))
    best = (-1, None)
    for q in QGRID:
        for a in AGRID:
            ev = []
            for (tau, mf, jlo, jhi, st) in fitr:
                if jlo > jhi:
                    continue
                x = q * tau + a * mf
                ev.append((jlo - 0.5 - x, 1))
                ev.append((jhi + 0.5 - x, -1))
            if not ev:
                continue
            ev.sort()
            cur = 0
            bc = -1
            bb = 0.0
            for pos, d in ev:
                cur += d
                if cur > bc:
                    bc = cur
                    bb = pos + 1e-9
            if bc > best[0]:
                best = (bc, (q, a, bb))
    return zid, best[1]


def bfeat(args):
    i, mhex, ce, side = args
    (m, R, A, P, B_full, rsh, rdisc, lsh, ldisc, s4, t4,
     bshift, k, dist, low3) = qrow3(mhex)
    F = rsh - bshift
    kf = k + F
    APf = (A + P) << F
    EU = (APf - B_full) >> kf
    za, zb = (0, 1) if side == "up" else (-1, 0)
    ra = [final_cosine_result(-(EU + za), ce, md)
          for md in MODES]
    rb = [final_cosine_result(-(EU + zb), ce, md)
          for md in MODES]
    Vlow = (APf - B_full) - (EU << kf)
    qr = DL.qrow(mhex)
    S, C = split_words(qr[2], qr[3])
    sc = S + C
    return (i, ra, rb, Vlow, kf, qr[3],
            t4 / (1 << s4),
            (m & ((1 << 63) - 1)) / (1 << 63),
            min(11, (rdisc * 12) >> rsh),
            (sc >> max(rsh - 59, 0)) & 63)


def main():
    data = defaultdict(lambda: defaultdict(list))
    for line in open("h604_rows.tsv"):
        f = line.split()
        key = (int(f[1]), int(f[2]), int(f[3]), f[4])
        data[key][int(f[11])].append(
            (int(f[5]), float(f[6]), float(f[7]), int(f[8]),
             int(f[9]), int(f[10])))
    print(f"W1 stratum-sides: {len(data)}", flush=True)
    jobs = []
    for key, zones in data.items():
        for xd12, rows in zones.items():
            tr = [(tau, mf, jlo, jhi, st)
                  for pos, tau, mf, jlo, jhi, st in rows
                  if pos % 2 == 0]
            if tr:
                jobs.append(((key, xd12), tr))
    with Pool(15) as pool:
        fits = dict(pool.map(fit_zone, jobs, chunksize=1))
    coff = defaultdict(lambda: defaultdict(int))
    for key, zones in data.items():
        for xd12, rows in zones.items():
            f = fits.get((key, xd12))
            if f is None:
                continue
            q, a, b = f
            for pos, tau, mf, jlo, jhi, st in rows:
                if pos % 2 != 0 or jlo > jhi:
                    continue
                x = q * tau + a * mf + b
                for c in range(-3, 4):
                    if jlo <= round(x + c) <= jhi:
                        coff[((key, xd12), st)][c] += 1
    cbest = {k: max(v, key=v.get) for k, v in coff.items()}
    print(f"{'stratum/side':22s} {'n_te':>7s} {'J1(pos-ho)':>10s}")
    for key in sorted(data, key=str):
        ok1 = nte = 0
        for xd12, rows in data[key].items():
            f = fits.get((key, xd12))
            for pos, tau, mf, jlo, jhi, st in rows:
                if pos % 2 == 0:
                    continue
                nte += 1
                if f is None:
                    continue
                q, a, b = f
                if jlo <= round(q * tau + a * mf + b +
                                cbest.get(((key, xd12), st),
                                          0)) <= jhi:
                    ok1 += 1
        if nte:
            print(f"{str(key):22s} {nte:7d} "
                  f"{ok1 / nte:10.4f}", flush=True)
    # blind: h603 captured W1 rows
    sel = json.load(open("h603_locked.json"))
    stf = {md: open(f"h603_{md}_status.txt").read()
           .splitlines() for md in MODES}
    w1 = [(i, rec) for i, rec in enumerate(sel)
          if tuple(rec["key"])[:4][0] in (9, 10)
          and rec["key"][2] == -73]
    print(f"\nblind h603 W1 rows: {len(w1)}", flush=True)

    with Pool(15) as pool:
        bf = pool.map(bfeat,
                      [(i, rec["m"], rec["key"][2],
                        rec["key"][3]) for i, rec in w1],
                      chunksize=20)
    res = defaultdict(lambda: [0, 0])
    for (i, rec), (i2, ra, rb, Vlow, kf, rfv, tau, mf, xd12,
                   st) in zip(w1, bf):
        key = tuple(rec["key"])
        side = key[3]
        hw, bad = [], False
        for md in MODES:
            t = stf[md][i].split()
            if t[0] != "OK":
                bad = True
                break
            hw.append(int(t[2], 16))
        if bad or ra == rb:
            continue
        if side == "up":
            fire = 1 if hw == rb else (0 if hw == ra else -1)
        else:
            fire = 1 if hw == ra else (0 if hw == rb else -1)
        if fire < 0:
            continue
        kk = (key[0], key[1], key[2], key[3])
        f = fits.get((kk, xd12))
        if f is None:
            continue
        q, a, b = f
        x = q * tau + a * mf + b + cbest.get(((kk, xd12), st),
                                             0)
        j = round(x)
        req2p = (4 * Vlow - j * rfv) >> (kf + 2)
        pred = 1 if req2p == (1 if side == "up" else -1) else 0
        res[kk][0] += pred == fire
        res[kk][1] += 1
    tot = [0, 0]
    for kk in sorted(res, key=str):
        ok, n = res[kk]
        print(f"  blind {kk}: {ok}/{n} = {ok / max(n, 1):.4f}")
        tot[0] += ok
        tot[1] += n
    print(f"  blind TOTAL: {tot[0]}/{tot[1]} = "
          f"{tot[0] / max(tot[1], 1):.4f}")
    # merge v3
    old = json.load(open("h602_model_full.json"))
    merged = {"fits": dict(old["fits"]),
              "cbest": dict(old["cbest"])}
    for (key, xd12), f in fits.items():
        merged["fits"][str((key, xd12))] = f
    for ((key, xd12), st), c in cbest.items():
        merged["cbest"][str(((key, xd12), st))] = c
    json.dump(merged, open("h604_model_v3.json", "w"))
    print(f"v3: {len(merged['fits'])} zones, "
          f"{len(merged['cbest'])} offsets")


if __name__ == "__main__":
    main()
