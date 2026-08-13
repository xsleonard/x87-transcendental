#!/usr/bin/env python3
"""h604b prep: clean J-frame rows for ALL W1 strata from
comb-5 (ties, on-grid positions) + h604 (near-ties, +9*2^52
positions).  Emits h604_rows.tsv:
  src dist low3 ce side pos tau mf jlo jhi st xd12
pos = m >> 54 (position bucket, for position-split held-out).
"""
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h577_three_term import qrow3
from h588_select import split_words
from h598_jframe import jinterval
import h539_D_library as DL

MODES = ROUNDING_MODES
SOURCES = {5: ("ties_comb5.txt", "comb5_%s_status.txt", False),
           64: ("ties_h604.txt", "h604_%s_status.txt", True)}


def work(rows):
    out = []
    for mhex, hw, ce, theta in rows:
        (m, R, A, P, B_full, rsh, rdisc, lsh, ldisc, s4, t4,
         bshift, k, dist, low3) = qrow3(mhex)
        F = rsh - bshift
        if F < 0:
            continue
        side = "up" if theta <= 0 else "dn"
        kf = k + F
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
        req2 = (1 if fire else 0) if side == "up" else \
            (-1 if fire else 0)
        qr = DL.qrow(mhex)
        rfv = qr[3]
        jlo, jhi = jinterval(Vlow, kf, rfv, req2)
        S, C = split_words(qr[2], rfv)
        sc = S + C
        tau = t4 / (1 << s4)
        mf = (m & ((1 << 63) - 1)) / (1 << 63)
        xd12 = min(11, (rdisc * 12) >> rsh)
        st = (sc >> max(rsh - 59, 0)) & 63
        pos = m >> 54
        out.append((dist, low3, ce, side, pos, tau, mf, jlo,
                    jhi, st, xd12))
    return out


def main():
    nw = 14
    with Pool(nw) as pool, open("h604_rows.tsv", "w") as fh:
        for src, (tf, sf, has_theta) in sorted(
                SOURCES.items()):
            seen = set()
            raw = []
            for line in open(tf):
                f = line.split()
                if f[0] in seen:
                    continue
                seen.add(f[0])
                raw.append(f)
            inputs = sorted(f[0] for f in raw)
            order = {m2: i for i, m2 in enumerate(inputs)}
            st = {md: open(sf % md).read().splitlines()
                  for md in MODES}
            jobs = []
            for f in raw:
                ce = int(f[8])
                theta = int(f[9]) if has_theta else 0
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
                jobs.append((f[0], hw, ce, theta))
            print(f"src-{src}: {len(jobs)} rows", flush=True)
            cnt = defaultdict(int)
            chunks = [jobs[i::nw * 4] for i in range(nw * 4)]
            for part in pool.imap_unordered(work, chunks):
                for (dist, low3, ce, side, pos, tau, mf, jlo,
                     jhi, stt, xd12) in part:
                    fh.write(f"{src} {dist} {low3} {ce} "
                             f"{side} {pos} {tau:.10f} "
                             f"{mf:.10f} {jlo} {jhi} {stt} "
                             f"{xd12}\n")
                    cnt[(dist, low3, ce, side)] += 1
            for kk in sorted(cnt):
                print(f"  {kk}: {cnt[kk]}")


if __name__ == "__main__":
    main()
