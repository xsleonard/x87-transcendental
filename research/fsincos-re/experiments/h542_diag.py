#!/usr/bin/env python3
"""h542: diagnose the h541 best config (e=1, chop, w=64, inj=0) —
per (theta, req2, pred, dist) census + error-row anatomy."""
import math
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h539_D_library import qrow


def work(rows):
    stats = defaultdict(int)
    samples = []
    for mhex, theta, lab, ce in rows:
        (m, sqv, f4v, rfv, t4, rdisc, A, P, M, k, R, B_full,
         rsh, bshift, dist, low3) = qrow(mhex)
        F = rsh - bshift
        if F < 0:
            continue
        kf = k + F
        APf = (A + P) << F
        res_hw = R + {"clean": 0, "down": -1, "up": 1}[lab]
        EU = (APf - B_full) >> kf
        req2 = res_hw - EU
        Vlow = (APf - B_full) - (EU << kf)
        f4_full = sqv * sqv
        s4 = f4_full.bit_length() - 67
        e = 1
        fe = f4_full >> (s4 - e)
        Bp0 = fe * rfv
        chunk = Bp0 & ((1 << 64) - 1)
        Bp = Bp0 - chunk
        V = (APf << e) - Bp
        pred = (V >> (kf + e)) - EU
        eps = fe - (f4v << e)
        Dn = chunk - eps * rfv
        gu = ((1 << kf) - Vlow) << e
        gd = (Vlow + 1) << e
        stats[(theta, req2, pred, dist)] += 1
        if pred != req2 and len(samples) < 60:
            if req2 == 1:
                miss = math.log2(gu - Dn) if gu > Dn else -1
                need = f"need_up miss {miss:.1f}b gu {math.log2(gu):.1f}"
            elif req2 == -1:
                miss = math.log2(Dn + gd) if Dn + gd > 0 else -1
                need = f"need_dn miss {miss:.1f}b gd {math.log2(gd):.1f}"
            elif pred == 1:
                need = (f"overshoot_up by "
                        f"{math.log2(Dn - gu + 1):.1f}b gu "
                        f"{math.log2(gu):.1f}")
            else:
                need = (f"overshoot_dn by "
                        f"{math.log2(-(Dn + gd) + 1):.1f}b gd "
                        f"{math.log2(gd):.1f}")
            samples.append((theta, req2, int(pred), dist, low3, ce,
                            int(eps),
                            round(chunk / 2**64, 4),
                            round(t4 / 2**s4, 4),
                            round(rdisc / 2**rsh, 4), need))
    return stats, samples


def main():
    rows = []
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
    labeled = []
    for j, f in enumerate(raw):
        if j % 16:
            continue
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
        refs = {name: [final_cosine_result(-(R + d), ce, md)
                       for md in ROUNDING_MODES]
                for name, d in (("clean", 0), ("down", -1),
                                ("up", 1))}
        for name in ("clean", "down", "up"):
            if hw == refs[name]:
                labeled.append((f[0], theta, name, ce))
                break
    chunks = [labeled[i::8] for i in range(8)]
    with Pool(8) as pool:
        parts = pool.map(work, chunks)
    stats = defaultdict(int)
    samples = []
    for s, sm in parts:
        for kk, v in s.items():
            stats[kk] += v
        samples.extend(sm[:8])
    print("theta req2 pred dist : n")
    for kk in sorted(stats):
        print(f"  {kk[0]:+d} {kk[1]:+d} {kk[2]:+d} d{kk[3]}: "
              f"{stats[kk]}")
    print("\nsample errors (theta req2 pred dist low3 ce eps "
          "chunk/2^64 XT XD need):")
    for s in samples[:40]:
        print("  ", s)


if __name__ == "__main__":
    main()
