#!/usr/bin/env python3
"""h569: paired deep-bit mining over the h568 contradiction pairs.

Each pair: two m in the same tight cell (stratum, XD12, x4/16,
mf/2^-13) with DISJOINT J-intervals — the hidden variable in its
purest measured form.  Define hi = the member requiring larger j.
For each feature f, concordance = mean sign(f_hi - f_lo) over
pairs where f differs (binomial z against 0.5).  Features:
  - sub-bin positions: frac16(x4), frac(XD*12), frac8192(mf)
  - deep tails as values: t2f (square tail frac), t4f_low (x4
    sub-bin), rdf_low (XD sub-twelfth), m_low (below 2^-13)
  - selected raw bits: t4 tail bits 0..7, rdisc bits 0..7,
    m bits 0..15, sq low bits 0..7 (bit = that bit of the value)
Stratified by (stratum, side) family: dist=8 dn, dist=9 up,
dist=9 dn — plus pooled.
"""
import math
import sys
from collections import defaultdict
from multiprocessing import Pool
from h539_D_library import qrow


def features(mhex):
    (m, sqv, f4v, rfv, t4, rdisc, A, P, M, k, R, B_full,
     rsh, bshift, dist, low3) = qrow(mhex)
    f4_full = sqv * sqv
    s4 = f4_full.bit_length() - 67
    x4 = t4 * 2.0**(65 - s4) / rfv
    sq_full = m * m
    s2 = sq_full.bit_length() - 67
    t2 = sq_full & ((1 << s2) - 1)
    t2f = t2 / 2.0**s2
    XDf = rdisc / 2.0**rsh
    mf = m / 2.0**64
    out = {
        "x4_subbin": (x4 * 16) % 1.0,
        "XD_subtw": (XDf * 12) % 1.0,
        "mf_low": (mf * 8192) % 1.0,
        "t2f": t2f,
        "sq_lowbyte": (sqv & 255) / 255.0,
        "f4_lowbyte": (f4v & 255) / 255.0,
    }
    for b in range(8):
        out[f"t4_b{b}"] = (t4 >> b) & 1
        out[f"rd_b{b}"] = (rdisc >> b) & 1
        out[f"sq_b{b}"] = (sqv >> b) & 1
    for b in range(16):
        out[f"m_b{b}"] = (m >> b) & 1
    return out


def work(pairs):
    acc = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for fam, mlo, mhi in pairs:
        flo = features(mlo)
        fhi = features(mhi)
        for name in flo:
            d = fhi[name] - flo[name]
            if d == 0:
                continue
            a = acc[fam][name]
            a[1] += 1
            if d > 0:
                a[0] += 1
    return {fam: {name: list(v) for name, v in d.items()}
            for fam, d in acc.items()}


def main():
    pairs = []
    with open("h568_contra_pairs.tsv") as fh:
        header = fh.readline()
        for line in fh:
            t = line.rstrip("\n").split("\t")
            strat, side = t[0], t[1]
            m1, m2 = t[5], t[6]
            l1, h1 = int(t[7]), int(t[8])
            l2, h2 = int(t[9]), int(t[10])
            if h1 < l2:
                mlo, mhi = m1, m2
            elif h2 < l1:
                mlo, mhi = m2, m1
            else:
                continue
            dist = int(strat.strip("()").split(",")[0])
            fam = f"d{dist}_{side}"
            pairs.append((fam, mlo, mhi))
    print(f"pairs: {len(pairs)}")
    chunks = [pairs[i::8] for i in range(8)]
    with Pool(8) as pool:
        parts = pool.map(work, chunks)
    acc = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for part in parts:
        for fam, d in part.items():
            for name, (p, n) in d.items():
                acc[fam][name][0] += p
                acc[fam][name][1] += n
    pooled = defaultdict(lambda: [0, 0])
    for fam, d in acc.items():
        for name, (p, n) in d.items():
            pooled[name][0] += p
            pooled[name][1] += n
    for fam in sorted(acc) + ["POOLED"]:
        d = acc.get(fam, pooled)
        print(f"\n=== {fam} ===")
        rows = []
        for name, (p, n) in d.items():
            if n < 30:
                continue
            z = (p - n / 2) / math.sqrt(n / 4)
            rows.append((abs(z), z, name, p, n))
        rows.sort(reverse=True)
        for _, z, name, p, n in rows[:14]:
            print(f"  {name:12s} conc={p/n:.3f} n={n:6d} z={z:+.1f}")


if __name__ == "__main__":
    main()
