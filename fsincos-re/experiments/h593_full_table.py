#!/usr/bin/env python3
"""h593: determinism ladder on CLEAN labels (h592_band).
Nonparametric majority tables, split-half held-out:
  T0 (key, mb, st3)
  T1 + sw6
  T2 + f2
  T3 + vbit
  T4 + t4g   (the full h589 pin)
Unseen-key fallback: per-(key, st3) threshold prediction."""
from collections import defaultdict
from multiprocessing import Pool
from h577_three_term import qrow3
from h588_select import fit_thr, split_words, m3_state, TARGETS


def row_feat(args):
    mhex, f4v, rfv, rsh, kf, Vlow = args
    (m, R, A, P, B_full, rsh2, rd, lsh, ld, s4, t4, bsh, k,
     dist, low3) = qrow3(mhex)
    S, C = split_words(f4v, rfv)
    sh = rsh - 59
    st3 = ((S + C) >> sh) & 63
    sw6 = (S >> sh) & 63
    f2 = (S + C) & 15
    vbit = (Vlow >> (kf - 15)) & 7
    t4g = (t4 >> (s4 - 2)) & 3
    return st3, sw6, f2, vbit, t4g


def main():
    raw = []
    for line in open("h592_band.tsv"):
        f = line.split()
        key = ((int(f[1]), int(f[2]), int(f[3])), f[4])
        if key not in dict.fromkeys(TARGETS):
            continue
        raw.append((f[0], key, int(f[5]), int(f[6]),
                    int(f[7], 16), int(f[8], 16), int(f[9]),
                    int(f[10]), int(f[11], 16)))
    print(f"clean band rows: {len(raw)}", flush=True)
    with Pool(15) as pool:
        fs = pool.map(row_feat,
                      [(m, f4v, rfv, rsh, kf, Vlow)
                       for m, key, mb, fire, f4v, rfv, rsh,
                       kf, Vlow in raw], chunksize=500)
    rows = []
    for (m, key, mb, fire, f4v, rfv, rsh, kf, Vlow), \
            (st3, sw6, f2, vbit, t4g) in zip(raw, fs):
        half = (int(m, 16) * 2654435761) & 1
        rows.append((half, mb, fire, key, st3, sw6, f2, vbit,
                     t4g))
    # threshold fallback
    tr3 = defaultdict(list)
    for r in rows:
        if r[0] == 0:
            tr3[(r[3], r[4])].append((r[1], r[2]))
    ths = {k: fit_thr(p) for k, p in tr3.items()}

    def fallback(r):
        t = ths.get((r[3], r[4]))
        return 0 if t is None else (1 if r[1] >= t else 0)

    LADDER = [
        ("T0 key+mb+st3", lambda r: (r[3], r[1], r[4])),
        ("T1 +sw6", lambda r: (r[3], r[1], r[4], r[5])),
        ("T2 +f2", lambda r: (r[3], r[1], r[4], r[5], r[6])),
        ("T3 +vbit", lambda r: (r[3], r[1], r[4], r[5], r[6],
                                r[7])),
        ("T4 +t4g", lambda r: (r[3], r[1], r[4], r[5], r[6],
                               r[7], r[8]))]
    for name, keyf in LADDER:
        tab = defaultdict(lambda: [0, 0])
        for r in rows:
            if r[0] == 0:
                tab[keyf(r)][r[2]] += 1
        ok = n = unseen = 0
        for r in rows:
            if r[0] != 1:
                continue
            c = tab.get(keyf(r))
            if c is None:
                pred = fallback(r)
                unseen += 1
            else:
                pred = 0 if c[0] >= c[1] else 1
            ok += pred == r[2]
            n += 1
        print(f"{name:14s}: held-out {ok / n:.4f} "
              f"(n={n}, unseen={unseen}, groups={len(tab)})",
              flush=True)


if __name__ == "__main__":
    main()
