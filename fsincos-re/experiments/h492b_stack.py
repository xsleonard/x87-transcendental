#!/usr/bin/env python3
"""h492b: stack the h492 winners — how deterministic does FCOS get
conditioned on (cell, le2, t4, rdisc, XE)?  Holdout accuracy at
several bin resolutions + remaining-mixing census."""
import random
from collections import defaultdict
from multiprocessing import Pool
from h492_conditional import enrich

def main():
    rows = []
    with open("h491_mapdata.tsv") as fh:
        fh.readline()
        for line in fh:
            f = line.rstrip("\n").split("\t")
            if f[7] in ("CLEAN", "FIRE"):
                rows.append(f)
    with Pool(8) as pool:
        feats = pool.map(enrich, [(f[0],) for f in rows],
                         chunksize=500)
    rnd = random.Random(4922)
    halves = [rnd.random() < 0.5 for _ in rows]
    data = []
    for f, ft, h in zip(rows, feats, halves):
        cell = (f[1], f[2], f[3], f[4])
        t12 = int(f[5], 16)
        d12 = int(f[6], 16)
        data.append((cell, t12, d12, ft, f[7] == "FIRE", h))

    def acc(keyfn):
        rule = defaultdict(lambda: [0, 0])
        for cell, t, d, ft, fire, h in data:
            if not h:
                rule[keyfn(cell, t, d, ft)][fire] += 1
        hit = tot = 0
        mixed_rows = 0
        for cell, t, d, ft, fire, h in data:
            if h:
                k = keyfn(cell, t, d, ft)
                if k in rule:
                    r = rule[k]
                    pred = r[1] > r[0]
                    hit += pred == fire
                    tot += 1
        return hit / tot, tot

    combos = [
        ("pixel(T4,D4)", lambda c, t, d, ft: (c, t >> 8, d >> 8)),
        ("+le2", lambda c, t, d, ft: (c, t >> 8, d >> 8,
                                      ft["le2_off"])),
        ("+le2+XE", lambda c, t, d, ft: (c, t >> 8, d >> 8,
                                         ft["le2_off"], ft["XE_fr4"])),
        ("T5,D5+le2", lambda c, t, d, ft: (c, t >> 7, d >> 7,
                                           ft["le2_off"])),
        ("T6,D6+le2", lambda c, t, d, ft: (c, t >> 6, d >> 6,
                                           ft["le2_off"])),
        ("le2 only+cell", lambda c, t, d, ft: (c, ft["le2_off"])),
        ("XEfr8+le2", lambda c, t, d, ft: (c, ft["le2_off"],
                                           ft["XE_fr4"],
                                           (ft["P_hi4"]))),
    ]
    for name, fn in combos:
        a, t = acc(fn)
        print(f"  {name:16s} holdout acc {a:.4f} (n={t})")

    # per-le2 boundary: theta_D at each le2 within one cell
    print("\n--- cell (8,1,8,1): theta50(D12) by le2_off, "
          "T-band 32-47 ---")
    sub = [(ft["le2_off"], d, fire)
           for cell, t, d, ft, fire, h in data
           if cell == ("8", "1", "8", "1") and 32 <= (t >> 6) < 48]
    byle = defaultdict(list)
    for le, d, fire in sub:
        byle[le].append((d, fire))
    for le in sorted(byle):
        pts = byle[le]
        if len(pts) < 100:
            continue
        bins = defaultdict(lambda: [0, 0])
        for d, fi in pts:
            b = bins[d >> 7]
            b[0] += 1
            b[1] += fi
        th = None
        rates = [(b, bins[b][1] / bins[b][0])
                 for b in sorted(bins) if bins[b][0] >= 5]
        for i in range(len(rates) - 1):
            if rates[i][1] < 0.5 <= rates[i + 1][1]:
                th = (rates[i][0] + rates[i + 1][0]) / 2
                break
        print(f"  le2_off={le:2d} n={len(pts):5d} "
              f"theta50(D5bins)={th}")

if __name__ == "__main__":
    main()
