#!/usr/bin/env python3
"""h603 selection: lock J1 predictions (h602_model_full.json)
for fresh observable rows in the NEWLY-fitted stratum-sides.

Pools: ties_h603.txt (fresh off-grid scan: W1 + [0xC8,0xF0) +
W2) and the ties_h585 remainder (comb-7 window strata), minus
every previously captured input.  Up to 120 rows per
stratum-side (hash order).  The ten h599/h601-validated
stratum-sides are EXCLUDED (already validated).  Locks
h603_locked.json + h603_inputs.txt BEFORE capture.
"""
import json
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h577_three_term import qrow3
from h588_select import split_words
import h539_D_library as DL

MODES = ROUNDING_MODES
OLD = {(8, 4, -73, "dn"), (8, 5, -73, "dn"),
       (8, 6, -73, "dn"), (8, 7, -73, "dn"),
       (9, 2, -72, "up"), (9, 3, -72, "up"),
       (9, 4, -72, "up"), (9, 5, -72, "up"),
       (9, 6, -72, "dn"), (9, 7, -72, "dn")}
PER = 120


def row_pred(args):
    mhex, ce, theta = args
    (m, R, A, P, B_full, rsh, rdisc, lsh, ldisc, s4, t4,
     bshift, k, dist, low3) = qrow3(mhex)
    side = "up" if theta <= 0 else "dn"
    key = (dist, low3, ce, side)
    if key in OLD:
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
    qr = DL.qrow(mhex)
    rfv = qr[3]
    S, C = split_words(qr[2], rfv)
    sc = S + C
    tau = t4 / (1 << s4)
    mf = (m & ((1 << 63) - 1)) / (1 << 63)
    xd12 = min(11, (rdisc * 12) >> rsh)
    st = (sc >> max(rsh - 59, 0)) & 63
    return (mhex, key, xd12, st, tau, mf, Vlow, kf, rfv,
            theta)


def main():
    mdl = json.load(open("h602_model_full.json"))
    fits = {eval(k): tuple(v) for k, v in
            mdl["fits"].items() if v is not None}
    cbest = {eval(k): v for k, v in mdl["cbest"].items()}
    captured = set()
    for fn in ("h585_inputs.txt", "h588_inputs.txt",
               "h589_inputs.txt", "h590f_inputs.txt",
               "h590k_inputs.txt", "h597_inputs.txt",
               "h599_inputs.txt"):
        for line in open(fn):
            captured.add(line.split()[1])
    pool_rows = []
    seen = set()
    for fn in ("ties_h603.txt", "ties_h585.txt"):
        for line in open(fn):
            f = line.split()
            if f[0] in seen or f[0] in captured:
                continue
            seen.add(f[0])
            pool_rows.append((f[0], int(f[8]), int(f[9])))
    print(f"fresh pool: {len(pool_rows)}", flush=True)
    with Pool(15) as pool:
        feats = pool.map(row_pred, pool_rows, chunksize=400)
    bykey = defaultdict(list)
    for r in feats:
        if r is not None:
            bykey[r[1]].append(r)
    sel = []
    for key in sorted(bykey, key=str):
        rows = sorted(bykey[key],
                      key=lambda r: (int(r[0], 16) *
                                     2654435761) & 0xFFFFFFFF)
        taken = 0
        for r in rows:
            if taken >= PER:
                break
            (mhex, key2, xd12, st, tau, mf, Vlow, kf, rfv,
             theta) = r
            f = fits.get((key, xd12))
            if f is None:
                continue
            q, a, b = f
            x = q * tau + a * mf + b + \
                cbest.get(((key, xd12), st), 0)
            j = round(x)
            req2p = (4 * Vlow - j * rfv) >> (kf + 2)
            side = key[3]
            pred = 1 if req2p == (1 if side == "up"
                                  else -1) else 0
            sel.append({"m": mhex, "key": list(key),
                        "theta": theta, "xd12": xd12,
                        "st": st, "j": j, "pred": pred})
            taken += 1
    json.dump(sel, open("h603_locked.json", "w"))
    with open("h603_inputs.txt", "w") as fh:
        for rec in sel:
            fh.write(f"3ffc {rec['m']}\n")
    cnt = defaultdict(int)
    for rec in sel:
        cnt[tuple(rec["key"])] += 1
    print(f"locked stratum-sides: {len(cnt)}, total inputs: "
          f"{len(sel)}")
    for k in sorted(cnt, key=str):
        print(f"  {k}: {cnt[k]}")


if __name__ == "__main__":
    main()
