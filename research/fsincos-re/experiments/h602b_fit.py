#!/usr/bin/env python3
"""h602b: fit J-frame zones for every stratum-side in
h602_rows.tsv; merge with h600_model.json into
h602_model_full.json.  Per (stratum-side, xd12): const-j fast
path (accept if it covers ALL train rows), else (q, a) grid +
b interval stabbing (train subsampled to 20k/zone); c-offsets
per (zone, st).  Scoreboard: held-out J0/J1 per stratum-side.
"""
import json
from collections import defaultdict
from multiprocessing import Pool
from h598_jframe import QGRID, AGRID

CAP = 20000


def fit_zone(args):
    zid, rows = args
    fitr = rows if len(rows) <= CAP else rows[::len(rows)
                                             // CAP + 1]
    # const-j fast path
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


def main():
    data = defaultdict(lambda: defaultdict(list))
    for line in open("h602_rows.tsv"):
        f = line.split()
        key = (int(f[1]), int(f[2]), int(f[3]), f[4])
        data[key][int(f[11])].append(
            (int(f[5]), float(f[6]), float(f[7]), int(f[8]),
             int(f[9]), int(f[10])))
    print(f"stratum-sides: {len(data)}", flush=True)
    jobs = []
    for key, zones in data.items():
        for xd12, rows in zones.items():
            tr = [(tau, mf, jlo, jhi, st)
                  for half, tau, mf, jlo, jhi, st in rows
                  if half == 0]
            if tr:
                jobs.append(((key, xd12), tr))
    with Pool(15) as pool:
        fits = dict(pool.map(fit_zone, jobs, chunksize=1))
    # c offsets
    coff = defaultdict(lambda: defaultdict(int))
    for key, zones in data.items():
        for xd12, rows in zones.items():
            f = fits.get((key, xd12))
            if f is None:
                continue
            q, a, b = f
            for half, tau, mf, jlo, jhi, st in rows:
                if half != 0 or jlo > jhi:
                    continue
                x = q * tau + a * mf + b
                for c in range(-3, 4):
                    if jlo <= round(x + c) <= jhi:
                        coff[((key, xd12), st)][c] += 1
    cbest = {k: max(v, key=v.get) for k, v in coff.items()}
    # scoreboard
    print(f"{'stratum/side':22s} {'n_te':>7s} {'feas':>7s} "
          f"{'J0':>7s} {'J1':>7s}")
    grand = [0, 0, 0]
    board = []
    for key in sorted(data, key=str):
        ok0 = ok1 = nte = infeas = 0
        for xd12, rows in data[key].items():
            f = fits.get((key, xd12))
            for half, tau, mf, jlo, jhi, st in rows:
                if half != 1:
                    continue
                nte += 1
                if jlo > jhi:
                    infeas += 1
                if f is None:
                    continue
                q, a, b = f
                x = q * tau + a * mf + b
                if jlo <= round(x) <= jhi:
                    ok0 += 1
                if jlo <= round(x + cbest.get(
                        ((key, xd12), st), 0)) <= jhi:
                    ok1 += 1
        if nte == 0:
            continue
        board.append((key, nte, 1 - infeas / nte, ok0 / nte,
                      ok1 / nte))
        grand[0] += nte
        grand[1] += ok0
        grand[2] += ok1
        print(f"{str(key):22s} {nte:7d} "
              f"{1 - infeas / nte:7.4f} {ok0 / nte:7.4f} "
              f"{ok1 / nte:7.4f}", flush=True)
    print(f"{'TOTAL':22s} {grand[0]:7d} {'':7s} "
          f"{grand[1] / grand[0]:7.4f} "
          f"{grand[2] / grand[0]:7.4f}")
    # merge with the ten-strata model; keys SIDE-QUALIFIED:
    # str(((dist, low3, ce, side), xd12))
    OLD_SIDE = {(8, 4, -73): "dn", (8, 5, -73): "dn",
                (8, 6, -73): "dn", (8, 7, -73): "dn",
                (9, 2, -72): "up", (9, 3, -72): "up",
                (9, 4, -72): "up", (9, 5, -72): "up",
                (9, 6, -72): "dn", (9, 7, -72): "dn"}
    old = json.load(open("h600_model.json"))
    merged = {"fits": {}, "cbest": {}}
    for k, v in old["fits"].items():
        strat, xd12 = eval(k)
        sk = strat + (OLD_SIDE[strat],)
        merged["fits"][str((sk, xd12))] = v
    for k, v in old["cbest"].items():
        (strat, xd12), st = eval(k)
        sk = strat + (OLD_SIDE[strat],)
        merged["cbest"][str(((sk, xd12), st))] = v
    for (key, xd12), f in fits.items():
        merged["fits"][str((key, xd12))] = f
    for ((key, xd12), st), c in cbest.items():
        merged["cbest"][str(((key, xd12), st))] = c
    json.dump(merged, open("h602_model_full.json", "w"))
    print(f"merged model: {len(merged['fits'])} zones, "
          f"{len(merged['cbest'])} offsets -> "
          f"h602_model_full.json")


if __name__ == "__main__":
    main()
