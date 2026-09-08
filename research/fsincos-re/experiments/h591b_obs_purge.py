#!/usr/bin/env python3
"""h591b: label-observability purge, CORRECT blind bit:
res_hw is always EU or EU+1 (frame theorem, up side), so a row
is blind iff refs(EU) == refs(EU+1) as 3-mode vectors.

Blind row (up side): refs(R+1) == refs(R) or refs(R+1) ==
refs(R-1) as 3-mode vectors — a true fire would be mislabeled
clean/down.  On OBSERVABLE rows only:
  1. model ladder held-out (M1, M3) fit on observable train;
  2. h587c borrow-census ceiling + held-out at w = 10, 14, 18
     (winner tree);
  3. blind-row census: predicted-fire rate among blind rows
     under the observable-fit M3 (how much fire mass was
     hidden).
"""
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h577_three_term import qrow3
from h588_select import fit_thr, m3_state, split_words, TARGETS


def row_feat(args):
    mhex, f4v, rfv, rsh = args
    (m, R, A, P, B_full, rsh2, rd, lsh, ld, s4, t4, bsh, k,
     dist, low3) = qrow3(mhex)
    F = rsh2 - bsh
    kf = k + F
    APf = (A + P) << F
    EU = (APf - B_full) >> kf
    r0 = tuple(final_cosine_result(-EU, -72, md)
               for md in ROUNDING_MODES)
    r1 = tuple(final_cosine_result(-(EU + 1), -72, md)
               for md in ROUNDING_MODES)
    blind = r0 == r1
    B_low = B_full & ((1 << kf) - 1)
    APf_low = (0 + B_low + ((APf - B_full) - (EU << kf))) \
        & ((1 << kf) - 1)
    b = 1 if APf_low < B_low else 0
    S, C = split_words(f4v, rfv)
    st3 = m3_state(f4v, rfv, rsh)
    fb = kf - 54
    wins = tuple(((S >> (fb - w)) & ((1 << w) - 1),
                  (C >> (fb - w)) & ((1 << w) - 1))
                 for w in (10, 14, 18))
    return (0 if blind else 1), st3, b, wins


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
    preds = []
    for r in rows:
        if r[0] != 1:
            continue
        t = ths.get(keyf(r))
        pred = gmaj if t is None else (1 if r[1] >= t else 0)
        ok += pred == r[2]
        n += 1
    return ok / max(n, 1), n, ths, gmaj


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
    obs_rows = []
    blind_rows = []
    for (m, key, mb, fire, f4v, rfv, rsh), \
            (obs, st3, b, wins) in zip(raw, fs):
        half = (int(m, 16) * 2654435761) & 1
        rec = (half, mb, fire, key, st3, b, wins)
        (obs_rows if obs else blind_rows).append(rec)
    print(f"observable: {len(obs_rows)}, blind: "
          f"{len(blind_rows)}")
    print(f"observable fire rate: "
          f"{sum(r[2] for r in obs_rows) / len(obs_rows):.4f}"
          f"; blind 'fire' rate: "
          f"{sum(r[2] for r in blind_rows) / len(blind_rows):.4f}")
    print("\n1. model ladder on OBSERVABLE rows only:")
    for name, keyf in (
            ("M1 key", lambda r: r[3]),
            ("M3 key+SUM6", lambda r: (r[3], r[4]))):
        acc, n, ths, gmaj = held_out(obs_rows, keyf)
        print(f"  {name:14s}: held-out {acc:.4f} (n={n})")
    print("\n2. borrow census on OBSERVABLE rows "
          "(winner tree):")
    print(f"{'w':>4s} {'groups':>7s} {'ceil':>7s} "
          f"{'heldout':>8s} {'unseen':>7s}")
    for wi, w in enumerate((10, 14, 18)):
        gtr = defaultdict(lambda: [0, 0])
        te = []
        for half, mb, fire, key, st3, b, wins in obs_rows:
            if fire and b == 0:
                continue
            bp = 0 if fire else b
            gk = (key,) + wins[wi]
            if half == 0:
                gtr[gk][bp] += 1
            else:
                te.append((gk, bp, b))
        ceil_ok = sum(max(c) for c in gtr.values())
        ceil_n = sum(sum(c) for c in gtr.values())
        ho = unseen = 0
        for gk, bp, b in te:
            c = gtr.get(gk)
            if c is None:
                pred = b
                unseen += 1
            else:
                pred = 0 if c[0] >= c[1] else 1
            ho += pred == bp
        print(f"{w:4d} {len(gtr):7d} "
              f"{ceil_ok / max(ceil_n, 1):7.4f} "
              f"{ho / max(len(te), 1):8.4f} {unseen:7d}",
              flush=True)
    print("\n3. observable-fit M3 predictions on BLIND rows:")
    acc, n, ths, gmaj = held_out(obs_rows,
                                 lambda r: (r[3], r[4]))
    pf = tot = agree = 0
    for half, mb, fire, key, st3, b, wins in blind_rows:
        t = ths.get((key, st3))
        pred = gmaj if t is None else (1 if mb >= t else 0)
        pf += pred
        agree += pred == fire
        tot += 1
    print(f"  predicted-fire rate on blind rows: "
          f"{pf / tot:.4f}; label 'agreement': "
          f"{agree / tot:.4f} (labels there are corrupt)")


if __name__ == "__main__":
    main()
