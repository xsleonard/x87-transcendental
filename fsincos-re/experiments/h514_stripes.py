#!/usr/bin/env python3
"""h514: stripe finder for the multi-boundary dist=8 regions.

The comb samples 160 discrete m teeth (2^54 spacing from 0xC8).  Per
(stratum, XD zone, tooth): sort rows by XT, majority-smooth labels,
extract C->F / F->C transition points.  Hough over slope grid: each
transition votes c = m - s*XT; sharp peaks = stripe boundary lines.

Zones chosen from h510/h512: the mixed regions + controls.
"""
from collections import defaultdict
from multiprocessing import Pool
from h509_d8_regions import built_comb3

ZONES = [
    (1, 0.0, 1/3, "(8,1) XD<1/3"),
    (1, 1/3, 2/3, "(8,1) XD[1/3,2/3)"),
    (1, 2/3, 1.0, "(8,1) XD>=2/3"),
    (2, 1/3, 2/3, "(8,2) XD[1/3,2/3)"),
    (2, 2/3, 1.0, "(8,2) XD>=2/3"),
    (5, 0.0, 1/3, "(8,5) XD<1/3"),
    (5, 1/3, 2/3, "(8,5) XD[1/3,2/3)"),
    (5, 2/3, 1.0, "(8,5) XD>=2/3"),
    (7, 0.0, 2/3, "CTRL (8,7) XD<2/3"),
    (6, 1/3, 1.0, "CTRL (8,6) XD>=1/3"),
]
M0 = 0.78125
SP = 2.0 ** -10          # tooth spacing 2^54/2^64


def transitions(pts):
    """pts: rows of one (zone, tooth).  Returns list of (XT, dir)
    where dir=+1 for C->F (fire starts, going up in XT), -1 F->C."""
    srt = sorted(pts)
    labs = [o for _, o in srt]
    n = len(labs)
    if n < 12:
        return []
    # majority smooth, window 5
    sm = []
    for i in range(n):
        w = labs[max(0, i - 2):i + 3]
        sm.append(1 if sum(w) * 2 > len(w) else 0)
    out = []
    for i in range(1, n):
        if sm[i] != sm[i - 1]:
            xt = (srt[i][0] + srt[i - 1][0]) / 2
            out.append((xt, 1 if sm[i] else -1))
    return out


def one_zone(args):
    low3, xlo, xhi, label, rows = args
    teeth = defaultdict(list)
    for XT, XD, mf, o in rows:
        t = round((mf - M0) / SP)
        teeth[t].append((XT, o))
    trans = []          # (m_tooth, XT, dir)
    nte = 0
    for t, pts in teeth.items():
        if len(pts) < 12:
            continue
        nte += 1
        m = M0 + t * SP
        for xt, d in transitions(pts):
            trans.append((m, xt, d))
    out = [f"\n=== {label}  rows={len(rows)} teeth={nte} "
           f"transitions={len(trans)} "
           f"({sum(1 for t in trans if t[2] > 0)} up / "
           f"{sum(1 for t in trans if t[2] < 0)} down)"]
    for d, dname in ((-1, "F->C (upper edge: m=c+s*XT)"),
                     (1, "C->F (lower edge)")):
        pts = [(m, xt) for m, xt, dd in trans if dd == d]
        if not pts:
            continue
        peaks = []
        for si in range(0, 226):
            s = si * 0.002
            hist = defaultdict(int)
            for m, xt in pts:
                hist[round((m - s * xt) / 0.002)] += 1
            for cb, cnt in hist.items():
                if cnt >= max(8, 0.15 * nte):
                    peaks.append((cnt, s, cb * 0.002))
        peaks.sort(reverse=True)
        # deduplicate: keep peaks not within (0.01, 0.004) of a better
        kept = []
        for cnt, s, c in peaks:
            if all(abs(s - s2) > 0.012 or abs(c - c2) > 0.006
                   for _, s2, c2 in kept):
                kept.append((cnt, s, c))
            if len(kept) >= 6:
                break
        out.append(f"  {dname}: {len(pts)} pts")
        for cnt, s, c in kept:
            out.append(f"    line s={s:.3f} c={c:.4f}  votes={cnt} "
                       f"({cnt/max(1,nte):.2f}/tooth)")
    return "\n".join(out)


def main():
    data = built_comb3()
    rows8 = defaultdict(list)
    for cell, XT, XD, mf, fire in data:
        if cell[0] == 8:
            rows8[cell[1]].append((XT, XD, mf, fire))
    jobs = []
    for low3, xlo, xhi, label in ZONES:
        rows = [(XT, XD, mf, o) for XT, XD, mf, o in rows8[low3]
                if xlo <= XD < xhi]
        jobs.append((low3, xlo, xhi, label, rows))
    with Pool(8) as pool:
        for block in pool.imap(one_zone, jobs, chunksize=1):
            print(block, flush=True)


if __name__ == "__main__":
    main()
