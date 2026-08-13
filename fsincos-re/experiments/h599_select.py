#!/usr/bin/env python3
"""h599: LOCKED BLIND VALIDATION of the J1 selector (zoned
affine j + per-(zone, state) offsets) on fresh hardware.

Fit on ALL clean comb-7 hard-strata rows (h596_hard.tsv).
Fresh: ties_h585 remainder, minus every captured input, all 10
strata, OBSERVABLE rows only (side refs distinct), up to 160
per stratum (random by hash order).  Locks per-input predicted
fire in h599_locked.json + h599_inputs.txt BEFORE capture.
"""
import json
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
PER_STRATUM = 160


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


def fresh_feat(args):
    mhex, ce, theta = args
    (m, R, A, P, B_full, rsh, rdisc, lsh, ldisc, s4, t4,
     bshift, k, dist, low3) = qrow3(mhex)
    strat = (dist, low3, ce)
    if strat not in STRATA:
        return None
    side = STRATA[strat]
    if (side == "up") != (theta <= 0):
        return None
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
        return None
    Vlow = (APf - B_full) - (EU << kf)
    import h539_D_library as DL
    qr = DL.qrow(mhex)
    sc = _ws((qr[2], qr[3]))
    tau = t4 / (1 << s4)
    mf = (m & ((1 << 63) - 1)) / (1 << 63)
    xd12 = min(11, (rdisc * 12) >> rsh)
    st = (sc >> max(rsh - 59, 0)) & 63
    return (mhex, strat, side, theta, tau, mf, xd12, st,
            Vlow, kf, qr[3])


def main():
    # ---- fit on all clean comb-7 rows
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
    # c offsets per (zone, state)
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
    print(f"fitted zones: {len(fits)}, state offsets: "
          f"{len(cbest)}", flush=True)
    # ---- fresh selection
    captured = set()
    for fn in ("h585_inputs.txt", "h588_inputs.txt",
               "h589_inputs.txt", "h590f_inputs.txt",
               "h590k_inputs.txt", "h597_inputs.txt"):
        for line in open(fn):
            captured.add(line.split()[1])
    fresh = []
    seen = set()
    for line in open("ties_h585.txt"):
        f = line.split()
        if f[0] in seen or f[0] in captured:
            continue
        seen.add(f[0])
        fresh.append((f[0], int(f[8]), int(f[9])))
    print(f"fresh pool: {len(fresh)}", flush=True)
    with Pool(15) as pool:
        feats = pool.map(fresh_feat, fresh, chunksize=200)
    bystrat = defaultdict(list)
    for r in feats:
        if r is None:
            continue
        bystrat[r[1]].append(r)
    sel = []
    for strat in sorted(bystrat, key=str):
        rows = sorted(bystrat[strat],
                      key=lambda r: (int(r[0], 16) *
                                     2654435761) & 0xFFFFFFFF)
        for r in rows[:PER_STRATUM]:
            (mhex, strat2, side, theta, tau, mf, xd12, st,
             Vlow, kf, rfv) = r
            zid = (strat, xd12)
            f = fits.get(zid)
            if f is None:
                continue
            q, a, b = f
            x = q * tau + a * mf + b + \
                cbest.get((zid, st), 0)
            j = round(x)
            req2p = (4 * Vlow - j * rfv) >> (kf + 2)
            firep = 1 if req2p == (1 if side == "up"
                                   else -1) else 0
            sel.append({"m": mhex, "strat": list(strat),
                        "side": side, "theta": theta,
                        "xd12": xd12, "st": st, "j": j,
                        "pred": firep})
    json.dump(sel, open("h599_locked.json", "w"))
    with open("h599_inputs.txt", "w") as fh:
        for rec in sel:
            fh.write(f"3ffc {rec['m']}\n")
    cnt = defaultdict(int)
    for rec in sel:
        cnt[tuple(rec["strat"])] += 1
    print("locked by stratum:", dict(cnt))
    print(f"total inputs: {len(sel)}")


if __name__ == "__main__":
    main()
