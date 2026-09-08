#!/usr/bin/env python3
"""h586a: prep/cache the band rows for the tree-refinement
campaign.  Labels ALL comb-7 rows (stride 1), computes the h576/
h578 margin frame, and writes the (9,1)/(9,2)@-72 up-side band
rows (|mb| < 24) to h586_band.tsv:
  mhex dist low3 ce side mb fire f4v_hex rfv_hex rsh
Everything downstream (h586 search, h587 finals, h588 selection)
reads this cache instead of redoing replica work.
"""
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h577_three_term import qrow3
from h578_margin_chunks import HARD_T
import h539_D_library as DL

TARGETS = [((9, 1, -72), "up"), ((9, 2, -72), "up")]


def work(rows):
    out = []
    for mhex, hw, R, ce, theta in rows:
        lab = None
        for name, d in (("clean", 0), ("down", -1), ("up", 1)):
            refs = [final_cosine_result(-(R + d), ce, md)
                    for md in ROUNDING_MODES]
            if hw == refs:
                lab = name
                break
        if lab is None:
            continue
        (m, R2, A, P, B_full, rsh, rdisc, lsh, ldisc, s4, t4,
         bshift, k, dist, low3) = qrow3(mhex)
        F = rsh - bshift
        if F < 0:
            continue
        kf = k + F
        strat = (dist, low3, ce)
        side = "up" if theta <= 0 else "dn"
        key = (strat, side)
        if key not in dict.fromkeys(TARGETS) or key not in HARD_T:
            continue
        cfg = HARD_T[key]
        sr, cr, sl, cl, st4, ct, cq = cfg
        APf = (A + P) << F
        res_hw = R + {"clean": 0, "down": -1, "up": 1}[lab]
        EU = (APf - B_full) >> kf
        req2 = res_hw - EU
        Vlow = (APf - B_full) - (EU << kf)
        T = cq * (1 << kf) >> 10
        if sr:
            T += sr * (rdisc << cr >> rsh)
        if sl:
            T += sl * (ldisc << cl >> lsh)
        if st4:
            T += st4 * (t4 << ct >> s4)
        if side == "up":
            marg = Vlow - ((1 << kf) - T)
            fire = 1 if req2 == 1 else 0
        else:
            marg = T - 1 - Vlow
            fire = 1 if req2 == -1 else 0
        mb = marg * 4096 >> kf
        if not (-24 <= mb < 24):
            continue
        qr = DL.qrow(mhex)
        f4v, rfv = qr[2], qr[3]
        out.append((mhex, dist, low3, ce, side, mb, fire,
                    f4v, rfv, rsh))
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
          for md in ROUNDING_MODES}
    jobs = []
    for f in raw:
        R, ce, theta = int(f[7], 16), int(f[8]), int(f[9])
        i = order[f[0]]
        hw, bad = [], False
        for md in ROUNDING_MODES:
            t = st[md][i].split()
            if t[0] != "OK":
                bad = True
                break
            hw.append(int(t[2], 16))
        if bad:
            continue
        jobs.append((f[0], hw, R, ce, theta))
    print(f"labeled candidates: {len(jobs)}", flush=True)
    nw = 14
    chunks = [jobs[i::nw * 4] for i in range(nw * 4)]
    nband = defaultdict(int)
    with Pool(nw) as pool, open("h586_band.tsv", "w") as out:
        for rows in pool.imap_unordered(work, chunks):
            for (mhex, dist, low3, ce, side, mb, fire, f4v, rfv,
                 rsh) in rows:
                out.write(f"{mhex} {dist} {low3} {ce} {side} "
                          f"{mb} {fire} {f4v:x} {rfv:x} {rsh}\n")
                nband[(dist, low3, ce, side)] += 1
    for k in sorted(nband):
        print(f"{k}: band rows {nband[k]}")


if __name__ == "__main__":
    main()
