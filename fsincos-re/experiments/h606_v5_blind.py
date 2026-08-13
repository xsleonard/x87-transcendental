#!/usr/bin/env python3
"""h606: blind validation of the V5 selector (zones =
(xd12, mf16), c in [-3,3]) on the residual pockets.

Phase select: refit V5 on the FULL fit sets (h604_rows for the
W1 pockets, h602_rows comb-8 for the (8,x,-72) up family);
score the h603-captured W1 rows (never in any fit) immediately;
select + lock fresh (8,x,-72)up rows from the uncaptured
ties_h603 [0xC8,0xF0) portion -> h606_locked.json /
h606_inputs.txt.
Phase score (after capture): score the locked rows.
Usage: h606_v5_blind.py select | score
"""
import json
import sys
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h577_three_term import qrow3
from h588_select import split_words
from h598_jframe import QGRID, AGRID, jinterval
import h539_D_library as DL

MODES = ROUNDING_MODES
CAP = 20000
P86 = {(8, 1, -72, "up"), (8, 2, -72, "up"),
       (8, 4, -72, "up"), (8, 5, -72, "up"),
       (8, 6, -72, "up"), (8, 7, -72, "up")}
PW1 = {(9, 1, -73, "up"), (9, 2, -73, "up"),
       (9, 4, -73, "dn"), (9, 5, -73, "dn")}


def zid_of(key, xd12, mf):
    return (key, xd12, min(15, int(mf * 16)))


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


def load_fit_rows():
    rows = defaultdict(list)
    for line in open("h602_rows.tsv"):
        f = line.split()
        key = (int(f[1]), int(f[2]), int(f[3]), f[4])
        if key not in P86:
            continue
        rows[key].append((float(f[6]), float(f[7]),
                          int(f[8]), int(f[9]), int(f[10]),
                          int(f[11])))
    for line in open("h604_rows.tsv"):
        f = line.split()
        key = (int(f[1]), int(f[2]), int(f[3]), f[4])
        if key not in PW1:
            continue
        rows[key].append((float(f[6]), float(f[7]),
                          int(f[8]), int(f[9]), int(f[10]),
                          int(f[11])))
    return rows


def fit_v5(pool):
    rows = load_fit_rows()
    zrows = defaultdict(list)
    for key, rl in rows.items():
        for tau, mf, jlo, jhi, st, xd12 in rl:
            zrows[zid_of(key, xd12, mf)].append(
                (tau, mf, jlo, jhi, st))
    fits = dict(pool.map(fit_zone,
                         sorted(zrows.items(),
                                key=lambda kv: str(kv[0])),
                         chunksize=1))
    coff = defaultdict(lambda: defaultdict(int))
    for zid, rl in zrows.items():
        f = fits.get(zid)
        if f is None:
            continue
        q, a, b = f
        for tau, mf, jlo, jhi, st in rl:
            if jlo > jhi:
                continue
            x = q * tau + a * mf + b
            for c in range(-3, 4):
                if jlo <= round(x + c) <= jhi:
                    coff[(zid, st)][c] += 1
    cbest = {k: max(v, key=v.get) for k, v in coff.items()}
    print(f"V5: {len(fits)} zones, {len(cbest)} offsets",
          flush=True)
    return fits, cbest


def bfeat(args):
    mhex, ce, side = args
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
    return (ra, rb, Vlow, kf, qr[3], t4 / (1 << s4),
            (m & ((1 << 63) - 1)) / (1 << 63),
            min(11, (rdisc * 12) >> rsh),
            ((S + C) >> max(rsh - 59, 0)) & 63,
            (dist, low3, ce))


def predict(fits, cbest, key, xd12, mf, st, tau, Vlow, kf,
            rfv):
    zid = zid_of(key, xd12, mf)
    f = fits.get(zid)
    if f is None:
        return None
    q, a, b = f
    x = q * tau + a * mf + b + cbest.get((zid, st), 0)
    j = round(x)
    req2p = (4 * Vlow - j * rfv) >> (kf + 2)
    side = key[3]
    return 1 if req2p == (1 if side == "up" else -1) else 0


def mode_select():
    with Pool(15) as pool:
        fits, cbest = fit_v5(pool)
        json.dump({"fits": {str(k): v for k, v in
                            fits.items()},
                   "cbest": {str(k): v for k, v in
                             cbest.items()}},
                  open("h606_v5_model.json", "w"))
        # --- blind: h603 W1 captures
        sel = json.load(open("h603_locked.json"))
        stf = {md: open(f"h603_{md}_status.txt").read()
               .splitlines() for md in MODES}
        w1 = [(i, rec) for i, rec in enumerate(sel)
              if tuple(rec["key"]) in
              {k[:3] + (k[3],) for k in PW1}]
        bf = pool.map(bfeat, [(rec["m"], rec["key"][2],
                               rec["key"][3])
                              for i, rec in w1],
                      chunksize=20)
        res = defaultdict(lambda: [0, 0])
        for (i, rec), feat in zip(w1, bf):
            (ra, rb, Vlow, kf, rfv, tau, mf, xd12, st,
             strat) = feat
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
                fire = 1 if hw == rb else \
                    (0 if hw == ra else -1)
            else:
                fire = 1 if hw == ra else \
                    (0 if hw == rb else -1)
            if fire < 0:
                continue
            pred = predict(fits, cbest, key, xd12, mf, st,
                           tau, Vlow, kf, rfv)
            if pred is None:
                continue
            res[key][0] += pred == fire
            res[key][1] += 1
        print("\nblind (h603 W1 captures) under V5:")
        tot = [0, 0]
        for kk in sorted(res, key=str):
            ok, n = res[kk]
            print(f"  {kk}: {ok}/{n} = {ok / max(n, 1):.4f}")
            tot[0] += ok
            tot[1] += n
        print(f"  W1 TOTAL: {tot[0]}/{tot[1]} = "
              f"{tot[0] / max(tot[1], 1):.4f}")
        # --- fresh selection for (8,x,-72)up
        captured = set()
        for fn in ("h585_inputs.txt", "h588_inputs.txt",
                   "h589_inputs.txt", "h590f_inputs.txt",
                   "h590k_inputs.txt", "h597_inputs.txt",
                   "h599_inputs.txt", "h603_inputs.txt"):
            for line in open(fn):
                captured.add(line.split()[1])
        fresh = []
        seen = set()
        for line in open("ties_h603.txt"):
            f = line.split()
            if f[0] in seen or f[0] in captured:
                continue
            seen.add(f[0])
            if int(f[1]) != 8 or int(f[8]) != -72 or \
                    int(f[9]) > 0:
                continue
            if int(f[2]) not in (1, 2, 4, 5, 6, 7):
                continue
            fresh.append((f[0], -72, "up"))
        print(f"\nfresh (8,x,-72)up pool: {len(fresh)}",
              flush=True)
        bf = pool.map(bfeat, fresh, chunksize=200)
    global FITS_G, CBEST_G
    FITS_G, CBEST_G = fits, cbest
    locked = []
    cnt = defaultdict(int)
    order = sorted(range(len(fresh)),
                   key=lambda i: (int(fresh[i][0], 16) *
                                  2654435761) & 0xFFFFFFFF)
    for i in order:
        (ra, rb, Vlow, kf, rfv, tau, mf, xd12, st,
         strat) = bf[i]
        key = strat + ("up",)
        if key not in P86 or ra == rb:
            continue
        if cnt[key] >= 150:
            continue
        pred = predict(FITS_G, CBEST_G, key,
                       xd12, mf, st, tau, Vlow, kf, rfv)
        if pred is None:
            continue
        cnt[key] += 1
        locked.append({"m": fresh[i][0], "key": list(key),
                       "pred": pred})
    json.dump(locked, open("h606_locked.json", "w"))
    with open("h606_inputs.txt", "w") as fh:
        for rec in locked:
            fh.write(f"3ffc {rec['m']}\n")
    print(f"locked: {dict(cnt)}  total {len(locked)}")


FITS_G = None
CBEST_G = None


def mode_score():
    sel = json.load(open("h606_locked.json"))
    stf = {md: open(f"h606_{md}_status.txt").read()
           .splitlines() for md in MODES}
    with Pool(15) as pool:
        bf = pool.map(bfeat, [(rec["m"], rec["key"][2],
                               rec["key"][3])
                              for rec in sel], chunksize=50)
    res = defaultdict(lambda: [0, 0])
    other = 0
    for i, (rec, feat) in enumerate(zip(sel, bf)):
        (ra, rb, Vlow, kf, rfv, tau, mf, xd12, st,
         strat) = feat
        key = tuple(rec["key"])
        hw, bad = [], False
        for md in MODES:
            t = stf[md][i].split()
            if t[0] != "OK":
                bad = True
                break
            hw.append(int(t[2], 16))
        if bad or ra == rb:
            continue
        fire = 1 if hw == rb else (0 if hw == ra else -1)
        if fire < 0:
            other += 1
            continue
        res[key][0] += rec["pred"] == fire
        res[key][1] += 1
    print(f"OTHER={other}")
    tot = [0, 0]
    for kk in sorted(res, key=str):
        ok, n = res[kk]
        print(f"  {kk}: {ok}/{n} = {ok / max(n, 1):.4f}")
        tot[0] += ok
        tot[1] += n
    print(f"  TOTAL: {tot[0]}/{tot[1]} = "
          f"{tot[0] / max(tot[1], 1):.4f}")


def main():
    if sys.argv[1] == "select":
        mode_select()
    else:
        mode_score()


if __name__ == "__main__":
    main()
