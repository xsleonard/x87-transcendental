#!/usr/bin/env python3
"""h663b: value-read vs schedule state — the pair-differential test.

h663B: high-field-matched pairs agree 0.825 (L=16) / 0.62 (L=20);
the residual disagreement is either a VALUE READ of specific low
bits or input-smooth SCHEDULE state.  Discriminator: for each pair,
the free-field diff profile (S1^S2, B1^B2 restricted below w+L).
  value read  => P(disagree) steps sharply in WHICH positions
                 differ (band structure), weak in diff magnitude
  smooth state=> P(disagree) ramps with diff magnitude/extent,
                 no band structure
Main analysis restricted to pairs with both members fc=1 (the coin
cells; crit & fc=0 is deterministic — those pairs ride as sanity).
Pool: comb7+comb9 (h663 assembly).
"""
import pickle
from collections import defaultdict


def load_pool():
    rec = list(pickle.load(open("h662z_comb9.pkl", "rb")))
    nrows = pickle.load(open("h662n_rows.pkl", "rb"))
    zmap = pickle.load(open("h662o_rows.pkl", "rb"))
    for o in nrows:
        (mhex, sign, th, fc, fs, z1, pm, w, phw, scale, S, B, F,
         kf, APf, B_full, ce) = o
        Z = zmap[mhex]
        if sign == "up":
            cs = set(1 if z >= 1 else 0 for z in Z)
        else:
            cs = set(1 if z <= -1 else 0 for z in Z)
        if len(cs) != 1:
            continue
        rec.append((sign, th, fc, cs.pop(), pm, w, phw, scale,
                    S, B))
    return rec


def main():
    rec = load_pool()
    print(f"pool {len(rec)}")

    for L in (16, 20):
        groups = defaultdict(list)
        for sign, th, fc, cls, pm, w, phw, scale, S, B in rec:
            crit = (pm + phw) % 8 == 7 and pm in (7, 8)
            groups[(sign, th, pm, phw, w, S >> (w + L),
                    B >> (w + L))].append((cls, fc, crit, S, B, w))
        # pair enumeration
        bypos = defaultdict(lambda: [0, 0])   # tmax rel w -> [agree, dis]
        byband = defaultdict(lambda: [0, 0])
        bycnt = defaultdict(lambda: [0, 0])
        bycnt_inband = defaultdict(lambda: [0, 0])
        sanity = [0, 0]
        npairs = 0
        for g, members in groups.items():
            n = len(members)
            if n < 2:
                continue
            for i in range(n):
                for j in range(i + 1, n):
                    c1, f1, cr1, S1, B1, w = members[i]
                    c2, f2, cr2, S2, B2, _ = members[j]
                    dis = int(c1 != c2)
                    if not (f1 == 1 and f2 == 1):
                        sanity[dis] += 1
                        continue
                    npairs += 1
                    mask = (1 << (w + L)) - 1
                    dS = (S1 ^ S2) & mask
                    dB = (B1 ^ B2) & mask
                    tpS = dS.bit_length() - 1 - w if dS else -99
                    tpB = dB.bit_length() - 1 - w if dB else -99
                    tmax = max(tpS, tpB)
                    cnt = bin(dS).count("1") + bin(dB).count("1")
                    bypos[tmax][dis] += 1
                    band = ("none" if tmax == -99 else
                            "<w" if tmax < 0 else
                            "0-7" if tmax < 8 else
                            "8-11" if tmax < 12 else
                            "12-15" if tmax < 16 else "16-19")
                    byband[band][dis] += 1
                    bycnt[min(cnt // 4, 10)][dis] += 1
                    if band in ("12-15", "16-19"):
                        bycnt_inband[min(cnt // 4, 10)][dis] += 1
        print(f"\n=== L={L}: {npairs} fc=1/fc=1 pairs "
              f"(+{sum(sanity)} mixed-fc sanity, dis rate "
              f"{sanity[1]/max(sum(sanity),1):.3f}) ===")
        print("P(disagree) by TOP differing position rel w:")
        for k in sorted(bypos):
            a, d = bypos[k]
            n = a + d
            if n < 30:
                continue
            print(f"  top={k:+3d}: n={n:5d} dis={d/n:.4f}")
        print("by band:")
        for k in sorted(byband, key=str):
            a, d = byband[k]
            n = a + d
            if n < 20:
                continue
            print(f"  {k:>6s}: n={n:5d} dis={d/n:.4f}")
        print("by total differing-bit count (//4):")
        for k in sorted(bycnt):
            a, d = bycnt[k]
            n = a + d
            if n < 30:
                continue
            print(f"  cnt~{k*4:3d}: n={n:5d} dis={d/n:.4f}")
        print("count curve WITHIN top band 12+ (position fixed):")
        for k in sorted(bycnt_inband):
            a, d = bycnt_inband[k]
            n = a + d
            if n < 30:
                continue
            print(f"  cnt~{k*4:3d}: n={n:5d} dis={d/n:.4f}")


if __name__ == "__main__":
    main()
