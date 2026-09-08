#!/usr/bin/env python3
"""h589 selection: constructed straddle pairs beyond the SUM6
read (lead (a) after h588).

Pairs pinned on (stratum, mb, SUM6-state) — identical M3
prediction — restricted to NEAR-THRESHOLD cells
(|mb - t3(state)| <= 4) where the hidden state decides.
Contrast families (one differs, others matched):
  F1 sw6:  S-part of the window (split at fixed sum)
  F2 f2:   deep resolved-sum bits (S+C) & 15  (frame [0,4))
  F3 vbit: (Vlow >> (kf-15)) & 7  (sub-resolution value bits)
  F4 t4g:  (t4 >> (s4-2)) & 3    (h479/h480 causal tail bits)
  CTRL:    all four matched (residual discordance floor)
Output: h589_locked.json (pair structure + M3 predictions,
LOCKED before capture), h589_inputs.txt.
"""
import json
from collections import defaultdict
from multiprocessing import Pool
from h577_three_term import qrow3
from h578_margin_chunks import HARD_T
from h588_select import (split_words, fit_thr, TARGETS)

NEAR = 4
PAIRS_PER_FAM = 150
PAIRS_PER_CELL = 2
CTRL_PAIRS = 80


def feat_fresh(args):
    mhex, ce = args
    if ce != -72:
        return None
    (m, R, A, P, B_full, rsh, rdisc, lsh, ldisc, s4, t4,
     bshift, k, dist, low3) = qrow3(mhex)
    F = rsh - bshift
    if F < 0:
        return None
    kf = k + F
    key = ((dist, low3, ce), "up")
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
    S, C = split_words(*_fr(mhex))
    sh = rsh - 59
    st3 = ((S + C) >> sh) & 63
    sw6 = (S >> sh) & 63
    f2 = (S + C) & 15
    vbit = (Vlow >> (kf - 15)) & 7
    t4g = (t4 >> (s4 - 2)) & 3
    return (mhex, key, mb, st3, sw6, f2, vbit, t4g)


_FR_CACHE = {}


def _fr(mhex):
    import h539_D_library as DL
    qr = DL.qrow(mhex)
    return qr[2], qr[3]


def fit_m3(pool):
    from h588_select import m3_state
    rows = []
    for line in open("h587d_band.tsv"):
        f = line.split()
        key = ((int(f[1]), int(f[2]), int(f[3])), f[4])
        if key not in dict.fromkeys(TARGETS):
            continue
        rows.append((key, int(f[5]), int(f[6]), int(f[7], 16),
                     int(f[8], 16), int(f[9])))
    sts = pool.map(_m3row, [(f4v, rfv, rsh)
                            for key, mb, fire, f4v, rfv, rsh
                            in rows], chunksize=2000)
    by3 = defaultdict(list)
    for (key, mb, fire, f4v, rfv, rsh), st3 in zip(rows, sts):
        by3[(key, st3)].append((mb, fire))
    t3 = defaultdict(dict)
    for (key, st3), pts in by3.items():
        t3[key][st3] = fit_thr(pts)
    return dict(t3)


def _m3row(args):
    from h588_select import m3_state
    return m3_state(*args)


def main():
    with Pool(15) as pool:
        t3 = fit_m3(pool)
        print("M3 thresholds fitted", flush=True)
        captured = set()
        for fn in ("h585_inputs.txt", "h588_inputs.txt"):
            for line in open(fn):
                captured.add(line.split()[1])
        fresh = []
        seen = set()
        for line in open("ties_h585.txt"):
            f = line.split()
            if f[0] in seen or f[0] in captured:
                continue
            seen.add(f[0])
            if int(f[9]) > 0:
                continue
            if int(f[1]) != 9 or int(f[2]) not in (1, 2):
                continue
            fresh.append((f[0], int(f[8])))
        print(f"fresh candidates: {len(fresh)}", flush=True)
        feats = pool.map(feat_fresh, fresh, chunksize=200)
    cells = defaultdict(lambda: defaultdict(list))
    kept = 0
    for r in feats:
        if r is None:
            continue
        mhex, key, mb, st3, sw6, f2, vbit, t4g = r
        thr = t3[key].get(st3)
        if thr is None or abs(mb - thr) > NEAR:
            continue
        kept += 1
        cells[(key, mb, st3)][(sw6, f2, vbit, t4g)].append(mhex)
    print(f"near-threshold rows: {kept}, cells: {len(cells)}",
          flush=True)

    fams = {"F1": 0, "F2": 1, "F3": 2, "F4": 3}
    sel_pairs = defaultdict(list)
    for cell, buckets in sorted(cells.items()):
        bks = sorted(buckets)
        for fam, fi in fams.items():
            if len(sel_pairs[fam]) >= PAIRS_PER_FAM:
                continue
            npc = 0
            used = set()
            for i in range(len(bks)):
                if npc >= PAIRS_PER_CELL:
                    break
                for j in range(i + 1, len(bks)):
                    a, b = bks[i], bks[j]
                    if a[fi] == b[fi]:
                        continue
                    if any(a[x] != b[x] for x in range(4)
                           if x != fi):
                        continue
                    if a in used or b in used:
                        continue
                    used.add(a)
                    used.add(b)
                    sel_pairs[fam].append(
                        (cell, buckets[a][0], buckets[b][0],
                         a, b))
                    npc += 1
                    break
        if len(sel_pairs["CTRL"]) < CTRL_PAIRS:
            for bk in bks:
                if len(buckets[bk]) >= 2:
                    sel_pairs["CTRL"].append(
                        (cell, buckets[bk][0], buckets[bk][1],
                         bk, bk))
                    break

    recs = []
    for fam, pl in sorted(sel_pairs.items()):
        print(f"{fam}: {len(pl)} pairs")
        for pid, (cell, ma, mb2, fa, fb) in enumerate(pl):
            key, mb, st3 = cell
            thr = t3[key][st3]
            p3 = 1 if mb >= thr else 0
            for member, mx, fx in (("a", ma, fa),
                                   ("b", mb2, fb)):
                recs.append({
                    "fam": fam, "pair": pid, "member": member,
                    "m": mx, "key": [list(key[0]), key[1]],
                    "mb": mb, "st3": st3, "feat": list(fx),
                    "M3": p3})
    json.dump(recs, open("h589_locked.json", "w"))
    with open("h589_inputs.txt", "w") as fh:
        for rec in recs:
            fh.write(f"3ffc {rec['m']}\n")
    print(f"total inputs: {len(recs)}")


if __name__ == "__main__":
    main()
