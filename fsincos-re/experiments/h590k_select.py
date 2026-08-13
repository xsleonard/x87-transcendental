#!/usr/bin/env python3
"""h590k: sc-observable cross-schedule pairs.

Selection = h589's CTRL recipe (pairs matched on stratum, mb,
SUM6, sw6, f2, vbit, t4g; near-fc-threshold cells) with an
added constraint: SC-OBSERVABLE — the 3-mode reference vectors
for d in {-1, 0, +1} are pairwise distinct, so the paired cos
lane labels unambiguously.  Capture under BOTH schedules; the
2x2 (fc_disc x sc_disc) table answers shared-vs-schedule-
generated arrangement state.  Locks h590k_locked.json +
h590k_inputs.txt.
"""
import json
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h577_three_term import qrow3
from h578_margin_chunks import HARD_T
from h588_select import split_words, fit_thr, TARGETS
import h539_D_library as DL

NEAR = 4
MAX_PAIRS = 300


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
    # class-observability: no alias crossing the d>=1
    # boundary; restrict to the fc-mixed population R = 7 mod 8
    if R & 7 != 7:
        return None
    refs = {d: tuple(final_cosine_result(-(R + d), ce, md)
                     for md in ROUNDING_MODES)
            for d in range(-3, 4)}
    for d in range(-3, 1):
        for d2 in range(1, 4):
            if refs[d] == refs[d2]:
                return None
    qr = DL.qrow(mhex)
    f4v, rfv = qr[2], qr[3]
    S, C = split_words(f4v, rfv)
    sh = rsh - 59
    st3 = ((S + C) >> sh) & 63
    sw6 = (S >> sh) & 63
    f2 = (S + C) & 15
    vbit = (Vlow >> (kf - 15)) & 7
    t4g = (t4 >> (s4 - 2)) & 3
    return (mhex, key, mb, st3, sw6, f2, vbit, t4g)


def _m3row(args):
    from h588_select import m3_state
    return m3_state(*args)


def main():
    with Pool(15) as pool:
        rows = []
        for line in open("h587d_band.tsv"):
            f = line.split()
            key = ((int(f[1]), int(f[2]), int(f[3])), f[4])
            if key not in dict.fromkeys(TARGETS):
                continue
            rows.append((key, int(f[5]), int(f[6]),
                         int(f[7], 16), int(f[8], 16),
                         int(f[9])))
        sts = pool.map(_m3row, [(f4v, rfv, rsh)
                                for key, mb, fire, f4v, rfv,
                                rsh in rows], chunksize=2000)
        by3 = defaultdict(list)
        for (key, mb, fire, f4v, rfv, rsh), st3 in \
                zip(rows, sts):
            by3[(key, st3)].append((mb, fire))
        t3 = defaultdict(dict)
        for (key, st3), pts in by3.items():
            t3[key][st3] = fit_thr(pts)
        print("M3 fitted", flush=True)
        captured = set()
        for fn in ("h585_inputs.txt", "h588_inputs.txt",
                   "h589_inputs.txt"):
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
    print(f"near-threshold sc-observable rows: {kept}, "
          f"cells: {len(cells)}", flush=True)
    # h589 proved (sw6, f2, vbit, t4g) carry no state — pair
    # within (key, mb, st3) cells regardless of bucket.
    pairs = []
    for cell, buckets in sorted(cells.items()):
        if len(pairs) >= MAX_PAIRS:
            break
        ms = sorted(m for bk in buckets for m in buckets[bk])
        for i in range(0, min(len(ms) - 1, 8), 2):
            if len(pairs) >= MAX_PAIRS:
                break
            pairs.append((cell, ms[i], ms[i + 1], (0, 0, 0, 0)))
    print(f"pairs: {len(pairs)}")
    recs = []
    for pid, (cell, ma, mb2, bk) in enumerate(pairs):
        key, mb, st3 = cell
        thr = t3[key][st3]
        p3 = 1 if mb >= thr else 0
        for member, mx in (("a", ma), ("b", mb2)):
            recs.append({"pair": pid, "member": member,
                         "m": mx,
                         "key": [list(key[0]), key[1]],
                         "mb": mb, "st3": st3,
                         "feat": list(bk), "M3": p3})
    json.dump(recs, open("h590k_locked.json", "w"))
    with open("h590k_inputs.txt", "w") as fh:
        for rec in recs:
            fh.write(f"3ffc {rec['m']}\n")
    print(f"total inputs: {len(recs)}")


if __name__ == "__main__":
    main()
