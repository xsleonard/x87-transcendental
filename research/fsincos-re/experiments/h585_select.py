#!/usr/bin/env python3
"""h585 selection: blind disagreement-row test of the split-state
model.

1. Fit on comb-7 (full band rows, no split-half): per target
   stratum, M1 = single margin threshold; M2 = per-split-state
   thresholds, split-state from the h584-best constrained tree.
2. On the FRESH uncaptured scan (ties_h585.txt): compute margin +
   state per row; select rows where M1 and M2 predictions
   DIFFER (the models' entire added value), plus agreement
   controls.  Write h585_inputs.txt + h585_locked.json
   (per-input M1/M2 predictions, LOCKED before capture).
Targets and their h584-best tree configs:
  ((9,1,-72),up): ('fr',27,'next','nat','14_23')
  ((9,2,-72),up): ('fr',27,'drop','fb1','12_34')
  ((8,5,-73),dn): ('fr',27,'drop','fb1','12_34')
"""
import json
import sys
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h577_three_term import qrow3
from h578_margin_chunks import HARD_T
from h584_constrained_tree import split_state
import h539_D_library as DL

BEST_TREE = {
    ((9, 1, -72), "up"): ("fr", 27, "next", "nat", "14_23"),
    ((9, 2, -72), "up"): ("fr", 27, "drop", "fb1", "12_34"),
    ((8, 5, -73), "dn"): ("fr", 27, "drop", "fb1", "12_34"),
}


def row_feat(mhex, theta):
    (m, R, A, P, B_full, rsh, rdisc, lsh, ldisc, s4, t4,
     bshift, k, dist, low3) = qrow3(mhex)
    F = rsh - bshift
    if F < 0:
        return None
    kf = k + F
    strat = (dist, low3, ce_g)
    side = "up" if theta <= 0 else "dn"
    key = (strat, side)
    if key not in BEST_TREE or key not in HARD_T:
        return None
    cfg = HARD_T[key]
    sr, cr, sl, cl, st4, ct, cq = cfg
    APf = (A + P) << F
    EU = (APf - B_full) >> kf
    Vlow = (APf - B_full) - (EU << kf)
    T = cq * (1 << kf) >> 10
    if sr:
        T += sr * (rdisc << cr >> rsh)
    if sl:
        T += sl * (ldisc << cl >> lsh)
    if st4:
        T += st4 * (t4 << ct >> s4)
    if side == "up":
        marg = Vlow - ((1 << kf) - T)
    else:
        marg = T - 1 - Vlow
    mb = marg * 4096 >> kf
    if not (-24 <= mb < 24):
        return None
    qr = DL.qrow(mhex)
    f4v, rfv = qr[2], qr[3]
    st = split_state(f4v, rfv, rsh, BEST_TREE[key])
    return key, mb, st, R, EU, kf


def work_fit(rows):
    out = []
    for mhex, theta, lab, ce in rows:
        globals()["ce_g"] = ce
        r = row_feat(mhex, theta)
        if r is None:
            continue
        key, mb, st, R, EU, kf = r
        (m, R2, A, P, B_full, rsh, *_rest) = qrow3(mhex)
        res_hw = R + {"clean": 0, "down": -1, "up": 1}[lab]
        req2 = res_hw - EU
        side = key[1]
        fire = 1 if (req2 == 1 if side == "up" else
                     req2 == -1) else 0
        out.append((key, mb, st, fire))
    return out


def work_sel(rows):
    out = []
    for mhex, theta, ce in rows:
        globals()["ce_g"] = ce
        r = row_feat(mhex, theta)
        if r is None:
            continue
        key, mb, st, R, EU, kf = r
        out.append((mhex, key, mb, st))
    return out


def fit_thr(pts):
    pts.sort()
    cands = sorted(set(mb for mb, _ in pts))
    cands.append(cands[-1] + 1)
    best = (-1, 0)
    for t in cands:
        acc = sum(1 for mb, f in pts
                  if (1 if mb >= t else 0) == f)
        if acc > best[0]:
            best = (acc, t)
    return best[1]


def main():
    # 1. fit on comb-7
    seen = set()
    raw = []
    for line in open("ties_comb7.txt"):
        f = line.split()
        if f[0] in seen:
            continue
        seen.add(f[0])
        raw.append(f)
    inputs = sorted(f[0] for f in raw)
    order = {m2: i for i, m2 in enumerate(inputs)}
    st = {md: open(f"comb7_{md}_status.txt").read().splitlines()
          for md in ROUNDING_MODES}
    labeled = []
    for j, f in enumerate(raw):
        if j % 4:
            continue
        R, ce, theta = int(f[7], 16), int(f[8]), int(f[9])
        i = order[f[0]]
        hw, bad = [], False
        for md in ROUNDING_MODES:
            t = st[md][i].split()
            if t[0] != "OK":
                bad = True
                break
            hw.append(int(t[2], 16))
        if bad:
            continue
        refs = {name: [final_cosine_result(-(R + d), ce, md)
                       for md in ROUNDING_MODES]
                for name, d in (("clean", 0), ("down", -1),
                                ("up", 1))}
        for name in ("clean", "down", "up"):
            if hw == refs[name]:
                labeled.append((f[0], theta, name, ce))
                break
    print(f"comb-7 labeled: {len(labeled)}", flush=True)
    chunks = [labeled[i::8] for i in range(8)]
    with Pool(8) as pool:
        parts = pool.map(work_fit, chunks)
    bykey = defaultdict(list)
    for part in parts:
        for key, mb, st2, fire in part:
            bykey[key].append((mb, st2, fire))
    model = {}
    for key, pts in bykey.items():
        t1 = fit_thr([(mb, f) for mb, _, f in pts])
        by = defaultdict(list)
        for mb, st2, f in pts:
            by[st2].append((mb, f))
        ths = {st2: fit_thr(pl) for st2, pl in by.items()}
        model[key] = (t1, ths)
        print(f"{key}: M1 t={t1}  M2 {dict(ths)}  n={len(pts)}")
    # 2. selection on fresh scan
    seen = set()
    fresh = []
    for line in open("ties_h585.txt"):
        f = line.split()
        if f[0] in seen:
            continue
        seen.add(f[0])
        fresh.append((f[0], int(f[9]), int(f[8])))
    print(f"fresh ties: {len(fresh)}", flush=True)
    chunks = [fresh[i::8] for i in range(8)]
    with Pool(8) as pool:
        parts = pool.map(work_sel, chunks)
    dis = []
    agr = []
    for part in parts:
        for mhex, key, mb, st2 in part:
            t1, ths = model[key]
            p1 = 1 if mb >= t1 else 0
            t2 = ths.get(st2)
            if t2 is None:
                continue
            p2 = 1 if mb >= t2 else 0
            rec = {"m": mhex, "key": [list(key[0]), key[1]],
                   "mb": mb, "state": list(st2), "M1": p1,
                   "M2": p2}
            if p1 != p2:
                dis.append(rec)
            elif len(agr) < 200 and abs(mb) < 6:
                agr.append(rec)
    print(f"disagreement rows: {len(dis)}, controls: {len(agr)}")
    sel = dis[:1200] + agr
    with open("h585_locked.json", "w") as fh:
        json.dump(sel, fh)
    with open("h585_inputs.txt", "w") as fh:
        for rec in sel:
            fh.write(f"3ffc {rec['m']}\n")
    cnt = defaultdict(int)
    for rec in dis:
        cnt[tuple(rec["key"][0]) + (rec["key"][1],)] += 1
    print("disagreements by stratum:", dict(cnt))


if __name__ == "__main__":
    main()
