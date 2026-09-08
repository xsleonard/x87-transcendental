#!/usr/bin/env python3
"""h595: FULL EU-ANCHORED LABEL AUDIT of comb-7 (all strata,
all theta, both sides).

Per row:
  EU from the replica; hw matched against refs(EU+z),
  z in {-1, 0, 1} (extended to +-2 if unmatched).
  side = up (theta <= 0, res in {EU, EU+1}) or dn (theta >= 1,
  res in {EU-1, EU}).
  blind: the side's two relevant refs alias (fire unreadable).
  off-frame: hw matches neither relevant ref (frame-theorem
  re-test on clean coordinates; z=+-2 matches counted here).
  fire_clean: hw == refs(EU+1) [up] / refs(EU-1) [dn].
  old label: the h536-era first-match over refs(R+d),
  d in (0, -1, +1); fire_old = (req2_old == +1 [up] / -1 [dn]).
Output: h595_audit.tsv, one line per (dist, low3, ce, theta):
  n blind off frame_ok fire_clean_rate fire_old_rate
  n_obs disagree(old vs clean on observable)
Console: per-(stratum, side) aggregation + worst distortions.
"""
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h577_three_term import qrow3

MODES = ROUNDING_MODES


def work(rows):
    out = []
    for mhex, hw, R, ce, theta in rows:
        (m, R2, A, P, B_full, rsh, rdisc, lsh, ldisc, s4, t4,
         bshift, k, dist, low3) = qrow3(mhex)
        F = rsh - bshift
        if F < 0:
            continue
        kf = k + F
        APf = (A + P) << F
        EU = (APf - B_full) >> kf
        refs = {z: [final_cosine_result(-(EU + z), ce, md)
                    for md in MODES] for z in (-1, 0, 1)}
        side = "up" if theta <= 0 else "dn"
        zrel = (0, 1) if side == "up" else (-1, 0)
        blind = 1 if refs[zrel[0]] == refs[zrel[1]] else 0
        off = 0
        fire_clean = -1
        if not blind:
            if hw == refs[zrel[1 if side == "up" else 0]]:
                fire_clean = 1
            elif hw == refs[zrel[0 if side == "up" else 1]]:
                fire_clean = 0
            else:
                off = 1
        # old first-match label
        fire_old = 0
        for name, d in (("clean", 0), ("down", -1), ("up", 1)):
            r = [final_cosine_result(-(R + d), ce, md)
                 for md in MODES]
            if hw == r:
                req2_old = R + d - EU
                fire_old = 1 if (req2_old == (1 if side == "up"
                                              else -1)) else 0
                break
        out.append((dist, low3, ce, theta, blind, off,
                    fire_clean, fire_old))
    return out


def main():
    seen = set()
    raw = []
    for line in open("ties_comb7.txt"):
        f = line.split()
        if f[0] in seen:
            continue
        seen.add(f[0])
        raw.append(f)
    inputs = sorted(f[0] for f in raw)
    order = {m2: i for i, m2 in enumerate(inputs)}
    st = {md: open(f"comb7_{md}_status.txt").read().splitlines()
          for md in MODES}
    jobs = []
    for f in raw:
        R, ce, theta = int(f[7], 16), int(f[8]), int(f[9])
        i = order[f[0]]
        hw, bad = [], False
        for md in MODES:
            t = st[md][i].split()
            if t[0] != "OK":
                bad = True
                break
            hw.append(int(t[2], 16))
        if bad:
            continue
        jobs.append((f[0], hw, R, ce, theta))
    print(f"rows: {len(jobs)}", flush=True)
    nw = 14
    chunks = [jobs[i::nw * 4] for i in range(nw * 4)]
    agg = defaultdict(lambda: [0] * 8)
    # [n, blind, off, fire_clean_1, obs_n, fire_old_1,
    #  disagree_obs, old_fire_on_blind]
    with Pool(nw) as pool:
        for part in pool.imap_unordered(work, chunks):
            for (dist, low3, ce, theta, blind, off, fc,
                 fo) in part:
                a = agg[(dist, low3, ce, theta)]
                a[0] += 1
                a[1] += blind
                a[2] += off
                a[5] += fo
                if blind:
                    a[7] += fo
                elif fc >= 0:
                    a[3] += fc
                    a[4] += 1
                    if fc != fo:
                        a[6] += 1
    with open("h595_audit.tsv", "w") as fh:
        fh.write("dist low3 ce theta n blind off fire_clean "
                 "n_obs fire_old disagree_obs "
                 "old_fire_on_blind\n")
        for k in sorted(agg):
            a = agg[k]
            fh.write(f"{k[0]} {k[1]} {k[2]} {k[3]} {a[0]} "
                     f"{a[1]} {a[2]} {a[3]} {a[4]} {a[5]} "
                     f"{a[6]} {a[7]}\n")
    # console: per (stratum, side)
    sagg = defaultdict(lambda: [0] * 8)
    for (dist, low3, ce, theta), a in agg.items():
        side = "up" if theta <= 0 else "dn"
        s = sagg[(dist, low3, ce, side)]
        for i in range(8):
            s[i] += a[i]
    print(f"\n{'stratum/side':22s} {'n':>7s} {'blind%':>7s} "
          f"{'off':>4s} {'fclean%':>8s} {'fold%':>7s} "
          f"{'dis_obs%':>9s} {'foldblind':>9s}")
    rows_out = []
    for k in sorted(sagg):
        a = sagg[k]
        n, bl, off, fc1, nobs, fo1, dis, fob = a
        rows_out.append((k, n, bl / n, off,
                         fc1 / max(nobs, 1), fo1 / n,
                         dis / max(nobs, 1), fob))
        print(f"{str(k):22s} {n:7d} {100 * bl / n:6.1f}% "
              f"{off:4d} {100 * fc1 / max(nobs, 1):7.2f}% "
              f"{100 * fo1 / n:6.2f}% "
              f"{100 * dis / max(nobs, 1):8.3f}% {fob:9d}")
    print("\nWORST label distortions (disagree_obs% + blind%):")
    rows_out.sort(key=lambda r: -(r[6] + r[2]))
    for k, n, blr, off, fcr, forr, disr, fob in rows_out[:10]:
        print(f"  {k}: blind {100 * blr:.1f}%  "
              f"obs-disagree {100 * disr:.2f}%  n={n}")
    tot = [0] * 8
    for a in sagg.values():
        for i in range(8):
            tot[i] += a[i]
    print(f"\nTOTAL: n={tot[0]} blind={tot[1]} "
          f"({100 * tot[1] / tot[0]:.1f}%) off-frame={tot[2]} "
          f"obs-disagree={tot[6]} "
          f"({100 * tot[6] / max(tot[4], 1):.3f}% of observable)"
          f" old-fire-on-blind={tot[7]}")


if __name__ == "__main__":
    main()
