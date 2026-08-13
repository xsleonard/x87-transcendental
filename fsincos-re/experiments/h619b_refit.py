#!/usr/bin/env python3
"""h619b: refit the miss cells on the densified captures.

Rows: h619_rows.json + h619_*_status.txt (fresh) plus the
in-cell h616 rows (already captured).  Labels: alias-robust
feasible j-interval union over all z in [-2,2] matching the
3-mode hardware vector (h618 protocol).

Fit per (key, xd12, mf32) zone:
  q in {2.0, 2.25, ..., 4.0}, a in AGRID (finer: step 1.25),
  b by interval stabbing; state comparator c(st) = c_lo +
  (c_hi-c_lo)*[st >= t], c in [-8, 8], t free in 0..64.
Split: train = even m-hash, held-out = odd.  Report held-out
vs the CURRENT model on the same rows; emit
h619_patch.json = zones where the refit strictly wins.
"""
import json
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h598_jframe import jinterval
from h609_ref_predictor import load_model, predict, V5_KEYS

QGRID = [2.0 + 0.25 * i for i in range(9)]
AGRID = [1.25 * i for i in range(-24, 25)]
FITS = CBEST = None


def load_labeled():
    rows = []
    recs = json.load(open("h619_rows.json"))
    st_f = {md: open(f"h619_{md}_status.txt").read()
            .splitlines() for md in ROUNDING_MODES}
    for i, rec in enumerate(recs):
        hw = []
        ok = True
        for md in ROUNDING_MODES:
            t = st_f[md][i].split()
            if t[0] != "OK":
                ok = False
                break
            hw.append(int(t[2], 16))
        if ok:
            rows.append((rec, hw))
    # in-cell h616 rows ride along
    locked = json.load(open("h616_locked.json"))
    st6 = {md: open(f"h616_{md}_status.txt").read()
           .splitlines() for md in ROUNDING_MODES}
    cells = {(tuple(r["key"]), r["mf16"])
             for r, hw in rows}
    n616 = 0
    for i, rec in enumerate(locked):
        m = int(rec["m"], 16)
        mf = (m & ((1 << 63) - 1)) / (1 << 63)
        mf16 = min(15, int(mf * 16))
        if (tuple(rec["key"]), mf16) not in cells:
            continue
        hw = [int(st6[md][i].split()[2], 16)
              for md in ROUNDING_MODES]
        rows.append((rec, hw))
        n616 += 1
    print(f"labeled rows: {len(rows)} (incl {n616} from h616)",
          flush=True)
    return rows


def prep(args):
    rec, hw = args
    m = int(rec["m"], 16)
    key = tuple(rec["key"])
    if "tau" not in rec:
        return None  # h616 rec: needs frame recompute
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
        return None
    jlo = min(l for l, h in ivs)
    jhi = max(h for l, h in ivs)
    mf32 = min(31, int(rec["mf"] * 32))
    half = (m * 2654435761 >> 16) & 1
    return (key, rec["xd12"], mf32, half, rec["tau"],
            rec["mf"], rec["st"], jlo, jhi, Vlow, kf, rfv, m)


def fit_zone(args):
    zid, rows = args
    tr = [r for r in rows if r[0] == 0]
    te = [r for r in rows if r[0] == 1]
    if len(tr) < 20 or len(te) < 10:
        return zid, None
    best = (-1, None)
    for q in QGRID:
        for a in AGRID:
            ev = []
            for (h, tau, mf, st, jlo, jhi) in tr:
                x = q * tau + a * mf
                ev.append((jlo - 0.5 - x, 1))
                ev.append((jhi + 0.5 - x, -1))
            ev.sort()
            cur, bc, bb = 0, -1, 0.0
            for pos, d in ev:
                cur += d
                if cur > bc:
                    bc, bb = cur, pos + 1e-9
            if bc > best[0]:
                best = (bc, (q, a, bb))
    q, a, b = best[1]
    coff = defaultdict(lambda: defaultdict(int))
    for (h, tau, mf, st, jlo, jhi) in tr:
        x = q * tau + a * mf + b
        for c in range(-8, 9):
            if jlo <= round(x + c) <= jhi:
                coff[st][c] += 1
    bs = (-1, None)
    cvals = range(-8, 9)
    for t0 in range(0, 65):
        for clo in cvals:
            for chi in cvals:
                n = sum(v.get(clo if s < t0 else chi, 0)
                        for s, v in coff.items())
                if n > bs[0]:
                    bs = (n, (t0, clo, chi))
    t0, clo, chi = bs[1]
    ok = 0
    for (h, tau, mf, st, jlo, jhi) in te:
        c = clo if st < t0 else chi
        x = q * tau + a * mf + b + c
        ok += jlo <= round(x) <= jhi
    return zid, (q, a, b, t0, clo, chi, ok, len(te))


def main():
    global FITS, CBEST
    FITS, CBEST = load_model()
    rows = load_labeled()
    with Pool(14) as pool:
        ps = pool.map(prep, rows, chunksize=500)
    zones = defaultdict(list)
    cur_ok = defaultdict(lambda: [0, 0])
    for p in ps:
        if p is None:
            continue
        (key, xd12, mf32, half, tau, mf, st, jlo, jhi, Vlow,
         kf, rfv, m) = p
        zid = (key, xd12, mf32)
        zones[zid].append((half, tau, mf, st, jlo, jhi))
        if half == 1:
            pr = predict(FITS, CBEST, key, xd12, mf, st, tau,
                         Vlow, kf, rfv)
            c = cur_ok[zid]
            c[1] += 1
            if pr is not None:
                _, req2p, _ = pr
                # current model correct iff its j lands in iv:
                # recompute j from predict internals via req2
                # comparison — use refs equality instead:
                lo2, hi2 = jlo, jhi
                # feasible iff req2p's interval overlaps:
                lo3, hi3 = jinterval(Vlow, kf, rfv, req2p)
                ok = not (hi3 < lo2 or hi2 < lo3)
                c[0] += ok
    print(f"zones: {len(zones)}", flush=True)
    jobs = sorted(zones.items(), key=lambda kv: str(kv[0]))
    with Pool(14) as pool:
        res = pool.map(fit_zone, jobs, chunksize=1)
    patch = {}
    tot = [0, 0, 0]
    print(f"{'zone':44s} {'n_te':>5s} {'cur':>7s} {'new':>7s}")
    for zid, r in res:
        if r is None:
            continue
        q, a, b, t0, clo, chi, ok, nte = r
        co, cn = cur_ok[zid]
        cur = co / max(cn, 1)
        new = ok / max(nte, 1)
        tot[0] += nte
        tot[1] += ok
        tot[2] += co
        flag = ""
        if new > cur + 1e-9:
            patch[str(zid)] = (q, a, b, t0, clo, chi)
            flag = "  PATCH"
        print(f"{str(zid):44s} {nte:5d} {cur:7.4f} "
              f"{new:7.4f}{flag}")
    print(f"TOTAL held-out: current {tot[2] / max(tot[0], 1):.4f}"
          f" refit {tot[1] / max(tot[0], 1):.4f}")
    json.dump(patch, open("h619_patch.json", "w"))
    print(f"patched zones: {len(patch)}")


if __name__ == "__main__":
    main()
