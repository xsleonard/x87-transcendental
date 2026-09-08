#!/usr/bin/env python3
"""h590i: M4 = threshold per (key, SUM6, R mod 8) — held-out on
the full band.  Also (key, R mod 8) alone, and R mod 8 x
near/far interaction census."""
from collections import defaultdict
from multiprocessing import Pool
from h577_three_term import qrow3
from h588_select import fit_thr, m3_state, TARGETS


def row_feat(args):
    mhex, f4v, rfv, rsh = args
    (m, R, A, P, B_full, rsh2, rd, lsh, ld, s4, t4, bsh, k,
     dist, low3) = qrow3(mhex)
    return m3_state(f4v, rfv, rsh), R & 7


def held_out(rows, keyf):
    tr = defaultdict(list)
    gl = defaultdict(int)
    for r in rows:
        if r[0] == 0:
            tr[keyf(r)].append((r[1], r[2]))
            gl[r[2]] += 1
    ths = {k: fit_thr(p) for k, p in tr.items()}
    gmaj = 1 if gl[1] >= gl[0] else 0
    ok = n = 0
    for r in rows:
        if r[0] != 1:
            continue
        t = ths.get(keyf(r))
        pred = gmaj if t is None else (1 if r[1] >= t else 0)
        ok += pred == r[2]
        n += 1
    return ok / max(n, 1), n


def main():
    raw = []
    for line in open("h587d_band.tsv"):
        f = line.split()
        key = ((int(f[1]), int(f[2]), int(f[3])), f[4])
        if key not in dict.fromkeys(TARGETS):
            continue
        raw.append((f[0], key, int(f[5]), int(f[6]),
                    int(f[7], 16), int(f[8], 16), int(f[9])))
    with Pool(15) as pool:
        fs = pool.map(row_feat,
                      [(m, f4v, rfv, rsh)
                       for m, key, mb, fire, f4v, rfv, rsh
                       in raw], chunksize=1000)
    rows = []
    rcen = defaultdict(lambda: [0, 0])
    for (m, key, mb, fire, f4v, rfv, rsh), (st3, r8) in \
            zip(raw, fs):
        half = (int(m, 16) * 2654435761) & 1
        rows.append((half, mb, fire, key, st3, r8))
        rcen[(key[0], r8)][fire] += 1
    print("full-band fire rate by (stratum, R mod 8):")
    for k in sorted(rcen):
        c = rcen[k]
        n = c[0] + c[1]
        print(f"  {k}: n={n} rate={c[1] / n:.4f}")
    for name, keyf in (
            ("M1  key", lambda r: r[3]),
            ("M3  key+SUM6", lambda r: (r[3], r[4])),
            ("key+R8", lambda r: (r[3], r[5])),
            ("M4  key+SUM6+R8", lambda r: (r[3], r[4], r[5]))):
        acc, n = held_out(rows, keyf)
        print(f"{name:18s}: held-out {acc:.4f}  (n={n})")


if __name__ == "__main__":
    main()
