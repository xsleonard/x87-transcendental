#!/usr/bin/env python3
"""h607: THE VALUE-FORM COLLAPSE TEST — can the zoned selector
be DERIVED from a single terminal equation?

Hypothesis: D = st4*(t4 << c4 >> s4) + sr*(rdisc << cr >> rsh)
            + sl*(ldisc << cl >> lsh) + K0
(one constant per stratum-side; columns/signs = physical
placement of the operand tail fields in the terminal), with the
selector's whole zone table = round(4*D/rf(m)) expanded in
(tau, mf, xd12).  Per-row constraint (from the EU frame):
  up:  fire <=> D <= Vlow - 2^kf   (else clean)
  dn:  fire <=> D >  Vlow          (else clean)
Fit: grid over (st4, c4, sr, cr, sl, cl); K0 by exact 1-D
threshold sweep on the train half; held-out accuracy.
Variant +state: c(st) * rf/4 offsets on top of the winner.
Data: h596_hard.tsv (the ten hard strata).  Bar: the V5
held-out numbers.
"""
import sys
from collections import defaultdict
from multiprocessing import Pool
from h588_select import split_words
import h539_D_library as DL

C4S = (61, 62, 63, 64, 65)
CRS = (61, 62, 63, 64, 65, 66)
CLS = (64, 65, 66, 67, 68)


def _ws(args):
    f4v, rfv = args
    S, C = split_words(f4v, rfv)
    return S + C


ROWS = None


def init_rows(r):
    global ROWS
    ROWS = r


def eval_cfg(cfg):
    st4, c4, sr, cr, sl, cl = cfg
    # rows: (train, thr, isfire, t4, s4, rdisc, rsh, ldisc,
    #        lsh, rfv, st, isdn)
    # up: fire <=> D <= thr;  dn: fire <=> D > thr.
    # Normalize to "low-side satisfied iff K0 <= x": for dn
    # rows treat CLEAN as the low-side event.
    ev = []
    for r in ROWS:
        if not r[0]:
            continue
        T = 0
        if st4:
            T += st4 * (r[3] << c4 >> r[4])
        if sr:
            T += sr * (r[5] << cr >> r[6])
        if sl:
            T += sl * (r[7] << cl >> r[8])
        x = r[1] - T
        low_event = r[2] if not r[11] else (not r[2])
        ev.append((x, low_event))
    if not ev:
        return cfg, 0.0, 0
    # sweep K0 with ATOMIC tie groups (exact-boundary masses are
    # real: x = Vlow + rdisc == 2^64 for whole tie populations)
    ev.sort()
    nlow = sum(1 for x, le in ev if le)
    best = nlow
    bestk = ev[0][0] - 1
    cur = nlow
    i = 0
    n = len(ev)
    while i < n:
        j = i
        d = 0
        while j < n and ev[j][0] == ev[i][0]:
            d += -1 if ev[j][1] else 1
            j += 1
        cur += d
        if cur > best:
            best = cur
            bestk = ev[i][0] + 1
        i = j
    return cfg, best / len(ev), bestk


def main():
    raw = []
    for line in open("h596_hard.tsv"):
        f = line.split()
        raw.append(f)
    bykey = defaultdict(list)
    with Pool(15) as pool:
        wss = pool.map(_ws, [(int(f[7], 16), int(f[8], 16))
                             for f in raw], chunksize=1000)
    for f, sc in zip(raw, wss):
        key = (int(f[1]), int(f[2]), int(f[3]), f[4])
        side = f[4]
        fire = int(f[6]) == 1
        kf = int(f[11])
        Vlow = int(f[12], 16)
        thr = (Vlow - (1 << kf)) if side == "up" else Vlow
        m = int(f[0], 16)
        train = ((m * 2654435761) >> 16 & 1) == 0
        rsh = int(f[9])
        st = (sc >> max(rsh - 59, 0)) & 63
        bykey[key].append(
            (train, thr, fire, int(f[15], 16), int(f[16]),
             int(f[13], 16), rsh, int(f[14], 16), int(f[10]),
             int(f[8], 16), st, side == "dn"))
    cfgs = []
    for st4 in (0, 1, -1):
        for c4 in (C4S if st4 else (0,)):
            for sr in (0, 1, -1):
                for cr in (CRS if sr else (0,)):
                    for sl in (0, 1, -1):
                        for cl in (CLS if sl else (0,)):
                            cfgs.append((st4, c4, sr, cr, sl,
                                         cl))
    print(f"configs: {len(cfgs)}", flush=True)
    for key in sorted(bykey, key=str):
        rows = bykey[key]
        with Pool(15, initializer=init_rows,
                  initargs=(rows,)) as pool:
            res = pool.map(eval_cfg, cfgs,
                           chunksize=max(1,
                                         len(cfgs) // 60))
        res.sort(key=lambda r: -r[1])
        cfg, acctr, K0 = res[0]
        st4, c4, sr, cr, sl, cl = cfg
        side = key[3]
        # held-out for the winner (+ state offsets in rf/4)
        coff = defaultdict(lambda: defaultdict(int))
        for r in rows:
            if not r[0]:
                continue
            T = K0
            if st4:
                T += st4 * (r[3] << c4 >> r[4])
            if sr:
                T += sr * (r[5] << cr >> r[6])
            if sl:
                T += sl * (r[7] << cl >> r[8])
            q4 = r[9] / 4.0
            for c in range(-3, 4):
                D = T + c * q4
                if side == "up":
                    ok = (D <= r[1]) == r[2]
                else:
                    ok = (D > r[1]) == r[2]
                if ok:
                    coff[r[10]][c] += 1
        cbest = {k: max(v, key=v.get) for k, v in
                 coff.items()}
        ok0 = ok1 = nte = 0
        for r in rows:
            if r[0]:
                continue
            nte += 1
            T = K0
            if st4:
                T += st4 * (r[3] << c4 >> r[4])
            if sr:
                T += sr * (r[5] << cr >> r[6])
            if sl:
                T += sl * (r[7] << cl >> r[8])
            if side == "up":
                ok0 += (T <= r[1]) == r[2]
                D = T + cbest.get(r[10], 0) * r[9] / 4.0
                ok1 += (D <= r[1]) == r[2]
            else:
                ok0 += (T > r[1]) == r[2]
                D = T + cbest.get(r[10], 0) * r[9] / 4.0
                ok1 += (D > r[1]) == r[2]
        print(f"{str(key):20s} cfg={cfg} K0={K0:.3e} "
              f"tr={acctr:.4f} heldout={ok0 / nte:.4f} "
              f"+state={ok1 / nte:.4f}", flush=True)


if __name__ == "__main__":
    main()
