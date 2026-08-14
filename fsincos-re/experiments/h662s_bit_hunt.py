#!/usr/bin/env python3
"""h662s: assumption-free bit hunt over the redundant (S, C) words.

h662r's alignment reasoning failed (S+C = B_full<<43 + D with D
row-varying over 166 bits — the h588 (S,C) model is only meaningful
through window reads).  So hunt the way h662g found the cos coin:
single-bit cross-tabs of the sc class against EVERY column of the
redundant words Sw, Cw, X=S^C, G=S&C, R=S+C, indexed relative to
the retention column rsh, per sign.  Any real state read lights up
as a rate split; the h662g signature was 0.005/1.000 on one bit.
Column counting via bit-sliced carry-save accumulators.
"""
import pickle
from collections import defaultdict

CACHE = "h662r_red.pkl"
MASK = (1 << 200) - 1
LO, HI = -80, 80
NREL = HI - LO + 1
WMASK = (1 << NREL) - 1


class BitCount:
    def __init__(self):
        self.planes = []

    def add(self, v):
        for i, p in enumerate(self.planes):
            carry = p & v
            self.planes[i] = p ^ v
            v = carry
            if not v:
                return
        if v:
            self.planes.append(v)

    def col(self, j):
        return sum(((p >> j) & 1) << k
                   for k, p in enumerate(self.planes))


def main():
    rows = pickle.load(open(CACHE, "rb"))
    print(f"{len(rows)} rows", flush=True)

    words = ("S", "C", "X", "G", "R")
    acc = {}
    tot = defaultdict(int)
    totf = defaultdict(int)
    base = defaultdict(lambda: [0, 0])
    for r in rows:
        (mhex, sign, th, fc, cls, rsh, Sw, Cw, B_full, scale,
         re, w, phw, pm, al) = r
        base[sign][cls] += 1
        j0 = rsh + 43 + LO
        X = Sw ^ Cw
        G = Sw & Cw
        R = (Sw + Cw) & MASK
        for wn, wv in zip(words, (Sw, Cw, X, G, R)):
            win = (wv >> j0) & WMASK if j0 >= 0 else \
                (wv << -j0) & WMASK
            k = (sign, wn)
            if k not in acc:
                acc[k] = (BitCount(), BitCount())
            acc[k][0].add(win)
            if cls:
                acc[k][1].add(win)
            tot[k] += 1
            totf[k] += cls

    br = {s: c[1] / (c[0] + c[1]) for s, c in base.items()}
    print(f"base rates: { {k: round(v, 4) for k, v in br.items()} }")

    hits = []
    for (sign, wn), (a_all, a_f) in acc.items():
        n_tot = tot[(sign, wn)]
        f_tot = totf[(sign, wn)]
        for rel in range(NREL):
            n1 = a_all.col(rel)
            f1 = a_f.col(rel)
            for bit, n, f in ((1, n1, f1),
                              (0, n_tot - n1, f_tot - f1)):
                if n < 2000:
                    continue
                rate = f / n
                dev = abs(rate - br[sign])
                if dev > 0.02:
                    hits.append((dev, rel + LO, sign, wn, bit, n,
                                 rate))
    hits.sort(reverse=True)
    print(f"\ntop deviations (|rate - base| > 0.02, n >= 2000): "
          f"{len(hits)}")
    for dev, rel, sign, wn, bit, n, rate in hits[:40]:
        print(f"  rel={rel:+4d} {sign} {wn} bit={bit}: n={n:6d} "
              f"rate={rate:.4f} (base {br[sign]:.4f}, "
              f"dev {dev:.4f})")
    if not hits:
        print("  NONE — the redundant words carry no marginal "
              "sc-class signal at any column in [-80, +80]")


if __name__ == "__main__":
    main()
