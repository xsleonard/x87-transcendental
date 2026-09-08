#!/usr/bin/env python3
"""h631b: fit the uncovered zones on the h631 captures and
merge into model v7 = h604_model_v3 + new (key, xd12) zones
(+ their c-offset tables), leaving all existing zones and the
h606 V5 overrides untouched.

Fit per (key, xd12): const-j fast path, else (q, a) grid + b
stabbing (h602b semantics, same QGRID/AGRID), c-offsets per
(zone, st) in [-3, 3] (model-format compatible).  Split-half
held-out by m-hash; report.  Output: h631_model_v7.json.
"""
import json
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h598_jframe import QGRID, AGRID, jinterval


def load_rows():
    recs = json.load(open("h631_rows.json"))
    st_f = {md: open(f"h631_{md}_status.txt").read()
            .splitlines() for md in ROUNDING_MODES}
    out = []
    for i, rec in enumerate(recs):
        t = [st_f[md][i].split() for md in ROUNDING_MODES]
        if any(x[0] != "OK" for x in t):
            continue
        hw = [int(x[2], 16) for x in t]
        EU = int(rec["EU"])
        Vlow = int(rec["Vlow"])
        kf = rec["kf"]
        rfv = int(rec["rfv"])
        ce = rec["ce"]
        ivs = []
        for z in (-2, -1, 0, 1, 2):
            refs = [final_cosine_result(-(EU + z), ce, md)
                    for md in ROUNDING_MODES]
            if refs == hw:
                lo, hi = jinterval(Vlow, kf, rfv, z)
                if lo <= hi:
                    ivs.append((lo, hi))
        if not ivs:
            continue
        jlo = min(l for l, h in ivs)
        jhi = max(h for l, h in ivs)
        half = (int(rec["m"], 16) * 2654435761 >> 16) & 1
        out.append(((tuple(rec["key"]), rec["xd12"]), half,
                    rec["tau"], rec["mf"], jlo, jhi,
                    rec["st"]))
    return out


def fit_zone(args):
    zid, rows = args
    tr = [(tau, mf, jlo, jhi, st) for h, tau, mf, jlo, jhi,
          st in rows if h == 0]
    if len(tr) > 20000:
        tr = tr[::len(tr) // 20000 + 1]
    for j in range(-16, 17):
        if all(jlo <= j <= jhi for tau, mf, jlo, jhi, st
               in tr):
            return zid, (0.0, 0.0, float(j))
    best = (-1, None)
    for q in QGRID:
        for a in AGRID:
            ev = []
            for (tau, mf, jlo, jhi, st) in tr:
                x = q * tau + a * mf
                ev.append((jlo - 0.5 - x, 1))
                ev.append((jhi + 0.5 - x, -1))
            if not ev:
                continue
            ev.sort()
            cur, bc, bb = 0, -1, 0.0
            for pos, d in ev:
                cur += d
                if cur > bc:
                    bc, bb = cur, pos + 1e-9
            if bc > best[0]:
                best = (bc, (q, a, bb))
    return zid, best[1]


def main():
    rows = load_rows()
    print(f"labeled rows: {len(rows)}", flush=True)
    zones = defaultdict(list)
    for zid, half, tau, mf, jlo, jhi, st in rows:
        zones[zid].append((half, tau, mf, jlo, jhi, st))
    jobs = sorted(zones.items(), key=lambda kv: str(kv[0]))
    with Pool(14) as pool:
        fits = dict(pool.map(fit_zone, jobs, chunksize=1))
    coff = defaultdict(lambda: defaultdict(int))
    for zid, rl in zones.items():
        f = fits.get(zid)
        if f is None:
            continue
        q, a, b = f
        for h, tau, mf, jlo, jhi, st in rl:
            if h != 0:
                continue
            x = q * tau + a * mf + b
            for c in range(-3, 4):
                if jlo <= round(x + c) <= jhi:
                    coff[(zid, st)][c] += 1
    cbest = {k: max(v, key=lambda c: (v[c], -abs(c)))
             for k, v in coff.items()}
    print(f"{'zone':34s} {'n_te':>6s} {'J0':>7s} {'J1':>7s}")
    tot = [0, 0, 0]
    for zid in sorted(zones, key=str):
        f = fits.get(zid)
        ok0 = ok1 = nte = 0
        for h, tau, mf, jlo, jhi, st in zones[zid]:
            if h != 1:
                continue
            nte += 1
            if f is None:
                continue
            q, a, b = f
            x = q * tau + a * mf + b
            if jlo <= round(x) <= jhi:
                ok0 += 1
            if jlo <= round(x + cbest.get((zid, st), 0)) \
                    <= jhi:
                ok1 += 1
        if nte:
            print(f"{str(zid):34s} {nte:6d} {ok0 / nte:7.4f} "
                  f"{ok1 / nte:7.4f}")
            tot[0] += nte
            tot[1] += ok0
            tot[2] += ok1
    print(f"{'TOTAL':34s} {tot[0]:6d} "
          f"{tot[1] / max(tot[0], 1):7.4f} "
          f"{tot[2] / max(tot[0], 1):7.4f}")
    v3 = json.load(open("h604_model_v3.json"))
    added_f = added_c = 0
    for zid, f in fits.items():
        if f is None:
            continue
        key = str(zid)
        if key not in v3["fits"]:
            v3["fits"][key] = list(f)
            added_f += 1
    for (zid, st), c in cbest.items():
        if c == 0:
            continue
        key = str((zid, st))
        if key not in v3["cbest"]:
            v3["cbest"][key] = c
            added_c += 1
    json.dump(v3, open("h631_model_v7.json", "w"))
    print(f"v7: +{added_f} zones, +{added_c} offsets -> "
          f"h631_model_v7.json")


if __name__ == "__main__":
    main()
