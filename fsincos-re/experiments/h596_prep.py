#!/usr/bin/env python3
"""h596 prep: clean-label raw-component cache for the hard-list
strata.  EU-anchored fire (blind rows dropped), all margin-frame
components emitted so any (sr,cr,sl,cl,st4,ct,cq) config can be
evaluated downstream.
  mhex dist low3 ce side theta fire f4v rfv rsh lsh kf Vlow
  rdisc ldisc t4 s4
"""
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h577_three_term import qrow3
import h539_D_library as DL

MODES = ROUNDING_MODES
HARD = {((9, 4, -72), "up"), ((9, 5, -72), "up"),
        ((9, 7, -72), "dn"), ((9, 6, -72), "dn"),
        ((8, 7, -73), "dn"), ((8, 6, -73), "dn"),
        ((8, 5, -73), "dn"), ((9, 3, -72), "up"),
        ((8, 4, -73), "dn"), ((9, 2, -72), "up")}


def work(rows):
    out = []
    for mhex, hw, R, ce, theta in rows:
        (m, R2, A, P, B_full, rsh, rdisc, lsh, ldisc, s4, t4,
         bshift, k, dist, low3) = qrow3(mhex)
        F = rsh - bshift
        if F < 0:
            continue
        kf = k + F
        side = "up" if theta <= 0 else "dn"
        key = ((dist, low3, ce), side)
        if key not in HARD:
            continue
        APf = (A + P) << F
        EU = (APf - B_full) >> kf
        za, zb = (0, 1) if side == "up" else (-1, 0)
        ra = [final_cosine_result(-(EU + za), ce, md)
              for md in MODES]
        rb = [final_cosine_result(-(EU + zb), ce, md)
              for md in MODES]
        if ra == rb:
            continue
        if side == "up":
            fire = 1 if hw == rb else (0 if hw == ra else -1)
        else:
            fire = 1 if hw == ra else (0 if hw == rb else -1)
        if fire < 0:
            continue
        Vlow = (APf - B_full) - (EU << kf)
        qr = DL.qrow(mhex)
        f4v, rfv = qr[2], qr[3]
        out.append((mhex, dist, low3, ce, side, theta, fire,
                    f4v, rfv, rsh, lsh, kf, Vlow, rdisc, ldisc,
                    t4, s4))
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
    cnt = defaultdict(int)
    with Pool(nw) as pool, open("h596_hard.tsv", "w") as out:
        for part in pool.imap_unordered(work, chunks):
            for r in part:
                (mhex, dist, low3, ce, side, theta, fire, f4v,
                 rfv, rsh, lsh, kf, Vlow, rdisc, ldisc, t4,
                 s4) = r
                out.write(
                    f"{mhex} {dist} {low3} {ce} {side} {theta} "
                    f"{fire} {f4v:x} {rfv:x} {rsh} {lsh} {kf} "
                    f"{Vlow:x} {rdisc:x} {ldisc:x} {t4:x} "
                    f"{s4}\n")
                cnt[(dist, low3, ce, side)] += 1
    for k in sorted(cnt):
        print(f"{k}: {cnt[k]}")


if __name__ == "__main__":
    main()
