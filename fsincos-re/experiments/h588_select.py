#!/usr/bin/env python3
"""h588 selection: blind disagreement test M3 vs M2.

M2 = h585's split-state model (h584 winner trees, 2-bit read):
     (9,1): ('fr',27,'next','nat','14_23')
     (9,2): ('fr',27,'drop','fb1','12_34')
M3 = h587b winner: nat/14_23 'next' tree + 6-bit resolved-sum
     read st = ((S+C) >> (rsh-54-5)) & 63, per-(stratum, state)
     thresholds.
Both fit on the FULL comb-7 band (h587d_band.tsv).
Sanity: score M2/M3 on the already-captured h585 rows.
Selection: fresh ties from ties_h585.txt (minus already-captured
inputs), rows where M2 != M3, plus agreement controls; lock
h588_locked.json + h588_inputs.txt BEFORE capture.
"""
import json
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h577_three_term import qrow3
from h578_margin_chunks import HARD_T
from h584_constrained_tree import split_state as h584_state
import h539_D_library as DL

WIDTH = 200
MASK = (1 << WIDTH) - 1
W = 27
DIG4 = {0: 0, 1: 1, 2: 1, 3: 2, 4: -2, 5: -1, 6: -1, 7: 0}
TARGETS = [((9, 1, -72), "up"), ((9, 2, -72), "up")]
M2_TREE = {((9, 1, -72), "up"): ("fr", 27, "next", "nat",
                                 "14_23"),
           ((9, 2, -72), "up"): ("fr", 27, "drop", "fb1",
                                 "12_34")}
GROUPING = [[0, 1, 2, 3], [4, 5, 6, 7], [8, 9, 10, 11],
            [12, 13, 14, 15]]
PAIRING = ((0, 3), (1, 2))


def csa(a, b, c):
    return (a ^ b ^ c) & MASK, \
        (((a & b) | (a & c) | (b & c)) << 1) & MASK


def c42(a, b, c, d):
    s1, c1 = csa(a, b, c)
    return csa(s1, c1, d)


def split_words(f4v, rfv):
    S = C = 0
    nb = rfv.bit_length()
    pos = 0
    chunks = []
    while pos < nb:
        y = (rfv >> pos) & ((1 << W) - 1)
        y2 = y << 1
        rows = []
        pend = 0
        for i in range(0, max(y2.bit_length(), 1), 2):
            d = DIG4[(y2 >> i) & 7]
            row = 0
            if d > 0:
                row = (d * f4v << i) & MASK
            elif d < 0:
                row = ((((~((-d) * f4v)) & MASK) << i) & MASK)
            row |= pend
            pend = (1 << i) if d < 0 else 0
            rows.append(row)
        rows = rows[:14]
        while len(rows) < 14:
            rows.append(0)
        chunks.append(rows)
        pos += W
    last = len(chunks) - 1
    for ci, rows in enumerate(chunks):
        it = rows + [S, C]
        gs = [c42(it[g[0]], it[g[1]], it[g[2]], it[g[3]])
              for g in GROUPING]
        (i1, i2), (i3, i4) = PAIRING
        l2a = c42(gs[i1][0], gs[i1][1], gs[i2][0], gs[i2][1])
        l2b = c42(gs[i3][0], gs[i3][1], gs[i4][0], gs[i4][1])
        S, C = c42(l2a[0], l2a[1], l2b[0], l2b[1])
        if ci < last:
            S >>= W
            C >>= W
    return S, C


def m3_state(f4v, rfv, rsh):
    S, C = split_words(f4v, rfv)
    sh = rsh - 54 - 5
    return ((S + C) >> max(sh, 0)) & 63


def states_row(args):
    key, f4v, rfv, rsh = args
    st2 = h584_state(f4v, rfv, rsh, M2_TREE[key])
    st3 = m3_state(f4v, rfv, rsh)
    return st2, st3


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


def main():
    # 1. fit both models on the comb-7 band cache
    rows = []
    for line in open("h587d_band.tsv"):
        f = line.split()
        key = ((int(f[1]), int(f[2]), int(f[3])), f[4])
        if key not in dict.fromkeys(TARGETS):
            continue
        rows.append((key, int(f[5]), int(f[6]), int(f[7], 16),
                     int(f[8], 16), int(f[9])))
    print(f"fit rows: {len(rows)}", flush=True)
    with Pool(15) as pool:
        sts = pool.map(states_row,
                       [(key, f4v, rfv, rsh)
                        for key, mb, fire, f4v, rfv, rsh
                        in rows],
                       chunksize=2000)
    by1 = defaultdict(list)
    by2 = defaultdict(list)
    by3 = defaultdict(list)
    for (key, mb, fire, f4v, rfv, rsh), (st2, st3) in \
            zip(rows, sts):
        by1[key].append((mb, fire))
        by2[(key, st2)].append((mb, fire))
        by3[(key, st3)].append((mb, fire))
    model = {}
    for key in dict.fromkeys(TARGETS):
        t1 = fit_thr(by1[key])
        t2 = {st: fit_thr(p) for (k, st), p in by2.items()
              if k == key}
        t3 = {st: fit_thr(p) for (k, st), p in by3.items()
              if k == key}
        model[key] = (t1, t2, t3)
        print(f"{key}: M1 t={t1}  M2 states={len(t2)}  "
              f"M3 states={len(t3)}", flush=True)

    # in-sample acc report
    for key in dict.fromkeys(TARGETS):
        t1, t2, t3 = model[key]
        n = ok1 = ok2 = ok3 = 0
        for (k, mb, fire, f4v, rfv, rsh), (st2, st3) in \
                zip(rows, sts):
            if k != key:
                continue
            n += 1
            ok1 += (1 if mb >= t1 else 0) == fire
            ok2 += (1 if mb >= t2[st2] else 0) == fire
            ok3 += (1 if mb >= t3[st3] else 0) == fire
        print(f"{key}: in-sample M1 {ok1 / n:.4f} "
              f"M2 {ok2 / n:.4f} M3 {ok3 / n:.4f}", flush=True)

    # 2. sanity score on already-captured h585 rows
    sel585 = json.load(open("h585_locked.json"))
    st585 = {md: open(f"h585_{md}_status.txt").read()
             .splitlines() for md in ROUNDING_MODES}
    sc = defaultdict(lambda: defaultdict(int))
    feats = []
    for i, rec in enumerate(sel585):
        mhex = rec["m"]
        strat = tuple(rec["key"][0])
        side = rec["key"][1]
        key = (strat, side)
        if key not in model:
            feats.append(None)
            continue
        hw, bad = [], False
        for md in ROUNDING_MODES:
            t = st585[md][i].split()
            if t[0] != "OK":
                bad = True
                break
            hw.append(int(t[2], 16))
        if bad:
            feats.append(None)
            continue
        feats.append((mhex, key, hw))
    with Pool(15) as pool:
        qres = pool.map(_qfeat, [f for f in feats if f],
                        chunksize=50)
    for (mhex, key, hw), q in zip([f for f in feats if f],
                                  qres):
        if q is None:
            continue
        mb, st2, st3, R, EU, ce = q
        lab = None
        for name, d in (("clean", 0), ("down", -1), ("up", 1)):
            refs = [final_cosine_result(-(R + d), ce, md)
                    for md in ROUNDING_MODES]
            if hw == refs:
                lab = name
                break
        if lab is None:
            sc[key]["OTHER"] += 1
            continue
        res_hw = R + {"clean": 0, "down": -1, "up": 1}[lab]
        req2 = res_hw - EU
        fire = 1 if req2 == 1 else 0
        t1, t2, t3 = model[key]
        p1 = 1 if mb >= t1 else 0
        p2 = 1 if mb >= t2.get(st2, t1) else 0
        p3 = 1 if mb >= t3.get(st3, t1) else 0
        sc[key]["n"] += 1
        sc[key]["M1"] += p1 == fire
        sc[key]["M2"] += p2 == fire
        sc[key]["M3"] += p3 == fire
        sc[key]["d23"] += p2 != p3
        if p2 != p3:
            sc[key]["d23_M3"] += p3 == fire
    print("\nsanity on h585 captures (NOT blind for M3):")
    for key in sorted(sc):
        r = sc[key]
        print(f"{key}: n={r['n']} M1={r['M1']} M2={r['M2']} "
              f"M3={r['M3']} | M2!=M3 on {r['d23']} "
              f"(M3 right {r['d23_M3']}) OTHER={r['OTHER']}",
              flush=True)

    # 3. fresh selection
    captured = set()
    for line in open("h585_inputs.txt"):
        captured.add(line.split()[1])
    fresh = []
    seen = set()
    for line in open("ties_h585.txt"):
        f = line.split()
        if f[0] in seen or f[0] in captured:
            continue
        seen.add(f[0])
        theta = int(f[9])
        if theta > 0:
            continue
        if int(f[1]) != 9 or int(f[2]) not in (1, 2):
            continue
        fresh.append((f[0], int(f[8])))
    print(f"\nfresh candidates: {len(fresh)}", flush=True)
    with Pool(15) as pool:
        qres = pool.map(_qsel, fresh, chunksize=200)
    dis, agr = [], []
    for r in qres:
        if r is None:
            continue
        mhex, key, mb, st2, st3 = r
        t1, t2, t3 = model[key]
        p1 = 1 if mb >= t1 else 0
        p2 = 1 if mb >= t2.get(st2, t1) else 0
        p3 = 1 if mb >= t3.get(st3, t1) else 0
        rec = {"m": mhex, "key": [list(key[0]), key[1]],
               "mb": mb, "st2": list(st2), "st3": st3,
               "M1": p1, "M2": p2, "M3": p3}
        if p2 != p3:
            dis.append(rec)
        elif len(agr) < 200 and abs(mb) < 6:
            agr.append(rec)
    print(f"disagreement rows: {len(dis)}, controls: "
          f"{len(agr)}")
    sel = dis[:1400] + agr
    json.dump(sel, open("h588_locked.json", "w"))
    with open("h588_inputs.txt", "w") as fh:
        for rec in sel:
            fh.write(f"3ffc {rec['m']}\n")
    cnt = defaultdict(int)
    for rec in dis[:1400]:
        cnt[tuple(rec["key"][0])] += 1
    print("selected disagreements by stratum:", dict(cnt))
    print(f"total inputs: {len(sel)}")


def _qfeat(args):
    mhex, key, hw = args
    return _feat_common(mhex, key, want_R=True)


def _qsel(args):
    mhex, ce = args
    if ce != -72:
        return None
    return _feat_common(mhex, None, want_R=False)


def _feat_common(mhex, key0, want_R):
    (m, R, A, P, B_full, rsh, rdisc, lsh, ldisc, s4, t4,
     bshift, k, dist, low3) = qrow3(mhex)
    F = rsh - bshift
    if F < 0:
        return None
    kf = k + F
    ce = key0[0][2] if key0 is not None else -72
    strat = (dist, low3, ce)
    key = (strat, "up")
    if key not in dict.fromkeys(TARGETS) or key not in HARD_T:
        return None
    cfg = HARD_T[key]
    sr, cr, sl, cl, st4c, ct, cq = cfg
    APf = (A + P) << F
    EU = (APf - B_full) >> kf
    Vlow = (APf - B_full) - (EU << kf)
    T = cq * (1 << kf) >> 10
    if sr:
        T += sr * (rdisc << cr >> rsh)
    if sl:
        T += sl * (ldisc << cl >> lsh)
    if st4c:
        T += st4c * (t4 << ct >> s4)
    marg = Vlow - ((1 << kf) - T)
    mb = marg * 4096 >> kf
    if not (-24 <= mb < 24):
        return None
    qr = DL.qrow(mhex)
    f4v, rfv = qr[2], qr[3]
    st2 = h584_state(f4v, rfv, rsh, M2_TREE[key])
    st3 = m3_state(f4v, rfv, rsh)
    if want_R:
        return mb, st2, st3, R, EU, ce
    return mhex, key, mb, st2, st3


if __name__ == "__main__":
    main()
