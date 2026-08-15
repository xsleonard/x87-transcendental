#!/usr/bin/env python3
"""h663c: the steering discriminator — field-matched distant pairs.

h663b bounded the residual coin's support to bits ~w+13..w+19 with
graded response, leaving (a) arithmetic value function of that
field vs (b) schedule state smooth in m.  Discriminator, mined
from the pooled corpus (the corpus IS the construction set at this
multiplicity):

  Groups: (sign, th, pm, phw, w, Sfield, Bfield) with
          Xfield = (X >> (w+13)) & 0x7F  — the ENTIRE support
          field of both operands pinned, plus context.
  Pairs stratified by top OTHER differing position:
    NEAR   (top < w+13):        both models predict ~0.89 agree
    DISTANT(top >= w+20):       (a) ~0.89   (b) ~0.5
  Dose-response: within context+high-matched groups (L=20),
  disagreement vs ARITHMETIC field distance |dSf| + |dBf|
  ((a)-quasi-threshold: decays with numeric distance).

fc=1/fc=1 pairs only (the coin cells).  Pool: comb7 + comb9.
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
    return [r for r in rec if r[2] == 1]


def main():
    rec = load_pool()
    print(f"pool (fc=1) {len(rec)}")

    # A. field-matched groups, pairs stratified by other-diff top
    groups = defaultdict(list)
    for sign, th, fc, cls, pm, w, phw, scale, S, B in rec:
        Sf = (S >> (w + 13)) & 0x7F
        Bf = (B >> (w + 13)) & 0x7F
        groups[(sign, th, pm, phw, w, Sf, Bf)].append((cls, S, B, w))
    strata = defaultdict(lambda: [0, 0])
    for g, members in groups.items():
        n = len(members)
        if n < 2 or n > 200:
            continue
        for i in range(n):
            for j in range(i + 1, n):
                c1, S1, B1, w = members[i]
                c2, S2, B2, _ = members[j]
                dS = S1 ^ S2
                dB = B1 ^ B2
                # mask OUT the pinned field bits
                fm = 0x7F << (w + 13)
                dS &= ~fm
                dB &= ~fm
                top = max(dS.bit_length(), dB.bit_length()) - 1 - w
                if dS == 0 and dB == 0:
                    band = "identical"
                elif top < 13:
                    band = "NEAR (<w+13)"
                elif top < 20:
                    band = "mid (13-19 gap bits)"
                else:
                    band = "DISTANT (>=w+20)"
                strata[band][int(c1 != c2)] += 1
    print("\nA. field-matched pairs by other-diff band:")
    for k in sorted(strata, key=str):
        a, d = strata[k]
        n = a + d
        if n < 20:
            continue
        print(f"  {k:>22s}: n={n:6d} disagree={d/n:.4f}")

    # B. dose-response: context+high-matched (L=20), arithmetic
    # field distance
    groups = defaultdict(list)
    for sign, th, fc, cls, pm, w, phw, scale, S, B in rec:
        groups[(sign, th, pm, phw, w, S >> (w + 20),
                B >> (w + 20))].append((cls, S, B, w))
    dose = defaultdict(lambda: [0, 0])
    for g, members in groups.items():
        n = len(members)
        if n < 2 or n > 200:
            continue
        for i in range(n):
            for j in range(i + 1, n):
                c1, S1, B1, w = members[i]
                c2, S2, B2, _ = members[j]
                Sf1 = (S1 >> (w + 13)) & 0x7F
                Sf2 = (S2 >> (w + 13)) & 0x7F
                Bf1 = (B1 >> (w + 13)) & 0x7F
                Bf2 = (B2 >> (w + 13)) & 0x7F
                dist = abs(Sf1 - Sf2) + abs(Bf1 - Bf2)
                b = (0 if dist == 0 else
                     1 if dist <= 2 else
                     2 if dist <= 4 else
                     3 if dist <= 8 else
                     4 if dist <= 16 else
                     5 if dist <= 32 else
                     6 if dist <= 64 else 7)
                dose[b][int(c1 != c2)] += 1
    lbl = {0: "0", 1: "1-2", 2: "3-4", 3: "5-8", 4: "9-16",
           5: "17-32", 6: "33-64", 7: "65+"}
    print("\nB. high-matched pairs: disagreement vs arithmetic "
          "field distance |dSf|+|dBf|:")
    for k in sorted(dose):
        a, d = dose[k]
        n = a + d
        if n < 30:
            continue
        print(f"  dist {lbl[k]:>6s}: n={n:6d} disagree={d/n:.4f}")


if __name__ == "__main__":
    main()
