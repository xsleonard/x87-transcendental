#!/usr/bin/env python3
"""h590h: is sc-observability associated with fc_fire in the
labeled corpus?  Near-threshold band rows, per stratum:
tabulate fire rate for obs vs non-obs (obs = refs(R-1),
refs(R), refs(R+1) pairwise distinct as 3-mode vectors)."""
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h577_three_term import qrow3
from h588_select import fit_thr, m3_state, TARGETS


def row_obs(args):
    mhex, f4v, rfv, rsh = args
    (m, R, A, P, B_full, rsh2, rd, lsh, ld, s4, t4, bsh, k,
     dist, low3) = qrow3(mhex)
    refs = [tuple(final_cosine_result(-(R + d), -72, md)
                  for md in ROUNDING_MODES)
            for d in (-1, 0, 1)]
    obs = 1 if len(set(refs)) == 3 else 0
    st3 = m3_state(f4v, rfv, rsh)
    return obs, st3, R & 7


def main():
    rows = []
    for line in open("h587d_band.tsv"):
        f = line.split()
        key = ((int(f[1]), int(f[2]), int(f[3])), f[4])
        if key not in dict.fromkeys(TARGETS):
            continue
        rows.append((f[0], key, int(f[5]), int(f[6]),
                     int(f[7], 16), int(f[8], 16), int(f[9])))
    with Pool(15) as pool:
        obs = pool.map(row_obs,
                       [(m, f4v, rfv, rsh)
                        for m, key, mb, fire, f4v, rfv, rsh
                        in rows], chunksize=1000)
    by3 = defaultdict(list)
    for (m, key, mb, fire, f4v, rfv, rsh), (ob, st3, rlow) in \
            zip(rows, obs):
        by3[(key, st3)].append((mb, fire))
    t3 = defaultdict(dict)
    for (key, st3), pts in by3.items():
        t3[key][st3] = fit_thr(pts)
    tab = defaultdict(lambda: [0, 0])
    rtab = defaultdict(lambda: [0, 0])
    for (m, key, mb, fire, f4v, rfv, rsh), (ob, st3, rlow) in \
            zip(rows, obs):
        thr = t3[key].get(st3)
        if thr is None or abs(mb - thr) > 4:
            continue
        tab[(key[0], ob)][fire] += 1
        rtab[(key[0], rlow)][fire] += 1
    print("near-threshold rows: fire rate by sc-observability:")
    for k in sorted(tab):
        c = tab[k]
        n = c[0] + c[1]
        print(f"  {k}: n={n} fire_rate={c[1] / n:.4f}")
    print("\nby R mod 8:")
    for k in sorted(rtab):
        c = rtab[k]
        n = c[0] + c[1]
        print(f"  {k}: n={n} fire_rate={c[1] / n:.4f}")


if __name__ == "__main__":
    main()
