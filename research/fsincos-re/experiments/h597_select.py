#!/usr/bin/env python3
"""h597 selection: blind hardware disagreement test of the
dist-8 DN word-state read (clean-label discovery, h596b).

M1 = margin-only threshold; M3 = per-(theta, state) thresholds
with the h596b-selected margin config + read per stratum.
Fit on clean comb-7 dn rows (h596_hard.tsv).  Fresh selection
from ties_h585 remainder, dn side (theta >= 1), dist=8 ce=-73,
OBSERVABLE only (refs(EU-1) != refs(EU)); rows where M1 != M3
plus near-boundary agreement controls.  Locks
h597_locked.json + h597_inputs.txt BEFORE capture.
"""
import json
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h577_three_term import qrow3
from h588_select import split_words

MODES = ROUNDING_MODES
CFG = {
    (8, 4): ((1, 64, 1, 60, 1, 63, 0), (7, -5)),
    (8, 5): ((1, 62, 0, 0, 1, 63, 0), (5, -6)),
    (8, 6): ((1, 61, -1, 60, 1, 63, 0), (7, -4)),
    (8, 7): ((1, 63, 1, 63, 1, 65, 0), (7, -3)),
}


def margin_state(dist, low3, rsh, lsh, kf, Vlow, rdisc, ldisc,
                 t4, s4, scword):
    cfg, (w, off) = CFG[(dist, low3)]
    sr, cr, sl, cl, st4, ct, cq = cfg
    T = cq * (1 << kf) >> 10
    if sr:
        T += sr * (rdisc << cr >> rsh)
    if sl:
        T += sl * (ldisc << cl >> lsh)
    if st4:
        T += st4 * (t4 << ct >> s4)
    marg = T - 1 - Vlow
    mb = marg * 4096 >> kf
    mb = max(-4096, min(4095, mb))
    sh = rsh - 59 + (off + 5)
    st = (scword >> max(sh, 0)) & ((1 << w) - 1)
    return mb, st


def fit_thr(pts):
    hist = defaultdict(lambda: [0, 0])
    for mb, f in pts:
        hist[mb][f] += 1
    cands = sorted(hist)
    cands.append(cands[-1] + 1)
    best = (-1, 0)
    for t in cands:
        acc = sum((n1 if mb >= t else n0)
                  for mb, (n0, n1) in hist.items())
        if acc > best[0]:
            best = (acc, t)
    return best[1]


def _ws(args):
    f4v, rfv = args
    S, C = split_words(f4v, rfv)
    return S + C


def fresh_feat(args):
    mhex, ce = args
    if ce != -73:
        return None
    (m, R, A, P, B_full, rsh, rdisc, lsh, ldisc, s4, t4,
     bshift, k, dist, low3) = qrow3(mhex)
    if dist != 8 or (dist, low3) not in CFG:
        return None
    F = rsh - bshift
    if F < 0:
        return None
    kf = k + F
    APf = (A + P) << F
    EU = (APf - B_full) >> kf
    ra = [final_cosine_result(-(EU - 1), ce, md)
          for md in MODES]
    r0 = [final_cosine_result(-EU, ce, md) for md in MODES]
    if ra == r0:
        return None  # blind
    Vlow = (APf - B_full) - (EU << kf)
    import h539_D_library as DL
    qr = DL.qrow(mhex)
    scword = _ws((qr[2], qr[3]))
    mb, st = margin_state(dist, low3, rsh, lsh, kf, Vlow,
                          rdisc, ldisc, t4, s4, scword)
    return (mhex, dist, low3, mb, st)


def main():
    # fit on clean comb-7 dn rows
    fitrows = defaultdict(list)
    with Pool(15) as pool:
        raw = []
        for line in open("h596_hard.tsv"):
            f = line.split()
            dist, low3, ce, side = int(f[1]), int(f[2]), \
                int(f[3]), f[4]
            if side != "dn" or dist != 8 or ce != -73:
                continue
            raw.append((int(f[5]), int(f[6]), int(f[7], 16),
                        int(f[8], 16), int(f[9]), int(f[10]),
                        int(f[11]), int(f[12], 16),
                        int(f[13], 16), int(f[14], 16),
                        int(f[15], 16), int(f[16]), dist,
                        low3))
        wss = pool.map(_ws, [(r[2], r[3]) for r in raw],
                       chunksize=1000)
        for r, sc in zip(raw, wss):
            (theta, fire, f4v, rfv, rsh, lsh, kf, Vlow, rdisc,
             ldisc, t4, s4, dist, low3) = r
            mb, st = margin_state(dist, low3, rsh, lsh, kf,
                                  Vlow, rdisc, ldisc, t4, s4,
                                  sc)
            fitrows[(dist, low3)].append((theta, mb, st, fire))
        model = {}
        for key, pts in fitrows.items():
            t1 = fit_thr([(mb, f) for th, mb, st, f in pts])
            by = defaultdict(list)
            for th, mb, st, f in pts:
                by[(th, st)].append((mb, f))
            t3 = {k: fit_thr(p) for k, p in by.items()}
            model[key] = (t1, t3)
            print(f"{key}: n={len(pts)} t1={t1} "
                  f"states={len(t3)}", flush=True)
        # fresh pool
        captured = set()
        for fn in ("h585_inputs.txt", "h588_inputs.txt",
                   "h589_inputs.txt", "h590f_inputs.txt",
                   "h590k_inputs.txt"):
            for line in open(fn):
                captured.add(line.split()[1])
        fresh = []
        seen = set()
        for line in open("ties_h585.txt"):
            f = line.split()
            if f[0] in seen or f[0] in captured:
                continue
            seen.add(f[0])
            if int(f[9]) < 1:
                continue
            if int(f[1]) != 8 or int(f[2]) not in (4, 5, 6, 7):
                continue
            fresh.append((f[0], int(f[8])))
        print(f"fresh dn candidates: {len(fresh)}", flush=True)
        feats = pool.map(fresh_feat, fresh, chunksize=200)
    dis, agr = [], []
    for r in feats:
        if r is None:
            continue
        mhex, dist, low3, mb, st = r
        # theta unknown pre-capture? theta comes from the scan
        # file — refetch: we stored only (mhex, ce); rebuild
        # theta lookup below.
        dis.append((mhex, dist, low3, mb, st))
    # theta lookup
    thetamap = {}
    for line in open("ties_h585.txt"):
        f = line.split()
        thetamap[f[0]] = int(f[9])
    sel_dis, sel_agr = [], []
    for mhex, dist, low3, mb, st in dis:
        th = thetamap[mhex]
        t1, t3 = model[(dist, low3)]
        p1 = 1 if mb >= t1 else 0
        p3 = 1 if mb >= t3.get((th, st), t1) else 0
        rec = {"m": mhex, "key": [dist, low3], "theta": th,
               "mb": mb, "st": st, "M1": p1, "M3": p3}
        if p1 != p3:
            sel_dis.append(rec)
        elif len(sel_agr) < 200 and abs(mb) < 6:
            sel_agr.append(rec)
    print(f"disagreements: {len(sel_dis)}, controls: "
          f"{len(sel_agr)}")
    sel = sel_dis[:1400] + sel_agr
    json.dump(sel, open("h597_locked.json", "w"))
    with open("h597_inputs.txt", "w") as fh:
        for rec in sel:
            fh.write(f"3ffc {rec['m']}\n")
    cnt = defaultdict(int)
    for rec in sel_dis[:1400]:
        cnt[tuple(rec["key"])] += 1
    print("selected by stratum:", dict(cnt))
    print(f"total inputs: {len(sel)}")


if __name__ == "__main__":
    main()
