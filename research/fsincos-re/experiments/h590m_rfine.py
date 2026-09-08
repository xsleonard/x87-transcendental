#!/usr/bin/env python3
"""h590m: does fine R-low structure absorb the M3 residual?
Model ladder on the full band, held-out:
  M3   (key, SUM6)
  +obs (key, SUM6, class-observability bit)
  +R5  (key, SUM6, R & 31)
  +R6  (key, SUM6, R & 63)
  +obsR5 (key, SUM6, obs, R & 31)
Also M3 accuracy split by obs bit."""
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h577_three_term import qrow3
from h588_select import fit_thr, m3_state, TARGETS


def row_feat(args):
    mhex, f4v, rfv, rsh = args
    (m, R, A, P, B_full, rsh2, rd, lsh, ld, s4, t4, bsh, k,
     dist, low3) = qrow3(mhex)
    refs = {d: tuple(final_cosine_result(-(R + d), -72, md)
                     for md in ROUNDING_MODES)
            for d in range(-3, 4)}
    obs = 1
    for d in range(-3, 1):
        for d2 in range(1, 4):
            if refs[d] == refs[d2]:
                obs = 0
    return m3_state(f4v, rfv, rsh), obs, R & 63


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
                       in raw], chunksize=500)
    rows = []
    for (m, key, mb, fire, f4v, rfv, rsh), (st3, obs, r6) in \
            zip(raw, fs):
        half = (int(m, 16) * 2654435761) & 1
        rows.append((half, mb, fire, key, st3, obs, r6))
    for name, keyf in (
            ("M3   key+SUM6", lambda r: (r[3], r[4])),
            ("+obs", lambda r: (r[3], r[4], r[5])),
            ("+R5", lambda r: (r[3], r[4], r[6] & 31)),
            ("+R6", lambda r: (r[3], r[4], r[6])),
            ("+obsR5", lambda r: (r[3], r[4], r[5],
                                  r[6] & 31))):
        acc, n = held_out(rows, keyf)
        print(f"{name:16s}: held-out {acc:.4f}  (n={n})")
    # M3 acc by obs
    tr = defaultdict(list)
    for r in rows:
        if r[0] == 0:
            tr[(r[3], r[4])].append((r[1], r[2]))
    ths = {k: fit_thr(p) for k, p in tr.items()}
    seg = defaultdict(lambda: [0, 0])
    for r in rows:
        if r[0] != 1:
            continue
        t = ths.get((r[3], r[4]))
        if t is None:
            continue
        pred = 1 if r[1] >= t else 0
        seg[r[5]][0] += pred == r[2]
        seg[r[5]][1] += 1
    for ob in sorted(seg):
        ok, n = seg[ob]
        print(f"M3 held-out on obs={ob}: {ok / n:.4f} (n={n})")


if __name__ == "__main__":
    main()
