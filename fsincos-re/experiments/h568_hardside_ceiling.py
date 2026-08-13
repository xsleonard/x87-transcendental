#!/usr/bin/env python3
"""h568: hard-side ceiling vs achieved.

For each stratum and side, compute the CEILING at h567 cell
resolution: sum over cells of the max rows a single j satisfies
(stab within cell), evaluated properly held-out (fit majority-j
on half A, score half B; singleton-train cells fall back to the
cell's train j; cells absent from train are scored by the h565
affine line as a proxy).  Compare with the h565/h566 affine
achieved numbers.  Also emit contradiction PAIRS (closest-m row
pairs inside contradictory hard-side cells) to
h568_contra_pairs.tsv for later hardware straddle construction.
"""
import sys
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h539_D_library import qrow


def stab_int(ivs):
    # feasible set: all integer j maximizing rows satisfied
    counts = {j: sum(1 for lo, hi in ivs if lo <= j <= hi)
              for j in range(-16, 17)}
    mx = max(counts.values())
    return mx, {j for j, c in counts.items() if c == mx}


def work(rows):
    out = []
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
        base = Vlow << 2
        top = 1 << (kf + 2)
        jlo = jhi = None
        for j in range(-16, 17):
            T = base - j * rfv
            pred = 1 if T >= top else (-1 if T < 0 else 0)
            if pred == req2:
                if jlo is None:
                    jlo = j
                jhi = j
        if jlo is None:
            continue
        f4_full = sqv * sqv
        s4 = f4_full.bit_length() - 67
        x4 = t4 * 2.0**(65 - s4) / rfv
        XD12 = min(11, (rdisc * 12) >> rsh)
        mf = m / 2**64
        side = "up" if theta <= 0 else "dn"
        cell = ((dist, low3, ce), XD12, int(x4 * 16),
                int(mf * 8192))
        half = (m * 2654435761) & 1
        out.append((cell, side, half, m, jlo, jhi))
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
    stride = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    labeled = []
    for j, f in enumerate(raw):
        if j % stride:
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
    print(f"labeled sample: {len(labeled)}", flush=True)
    chunks = [labeled[i::8] for i in range(8)]
    with Pool(8) as pool:
        parts = pool.map(work, chunks)
    cells = defaultdict(lambda: {"tr": [], "te": []})
    for part in parts:
        for cell, side, half, m, jlo, jhi in part:
            cells[(cell, side)]["tr" if half == 0 else
                                "te"].append((m, jlo, jhi))
    agg = defaultdict(lambda: [0, 0, 0])  # n, ok, nocov
    pairs = open("h568_contra_pairs.tsv", "w")
    print("strat\tside\tXD12\tx4bin\tmfbin\tm1\tm2\tj1lo\tj1hi"
          "\tj2lo\tj2hi", file=pairs)
    npairs = 0
    for (cell, side), d in cells.items():
        strat = cell[0]
        tr, te = d["tr"], d["te"]
        if tr:
            _, jset = stab_int([(lo, hi) for _, lo, hi in tr])
        else:
            jset = None
        a = agg[(strat, side)]
        for m, lo, hi in te:
            a[0] += 1
            if jset is None:
                a[2] += 1
            elif any(lo <= j <= hi for j in jset):
                a[1] += 1
        # contradiction pairs from ALL rows in the cell
        allr = tr + te
        glo = max(lo for _, lo, hi in allr)
        ghi = min(hi for _, lo, hi in allr)
        if glo > ghi and npairs < 20000:
            allr.sort()
            for (m1, l1, h1), (m2, l2, h2) in zip(allr,
                                                  allr[1:]):
                if l1 > h2 or l2 > h1:
                    print(f"{strat}\t{side}\t{cell[1]}\t{cell[2]}"
                          f"\t{cell[3]}\t{m1:016x}\t{m2:016x}"
                          f"\t{l1}\t{h1}\t{l2}\t{h2}",
                          file=pairs)
                    npairs += 1
                    break
    pairs.close()
    print(f"contradiction pairs written: {npairs}")
    print(f"\n{'stratum':14s} {'side':4s} {'n_te':>7s} "
          f"{'ceiling':>8s} {'nocov':>6s}")
    for (strat, side) in sorted(agg):
        n, ok, nocov = agg[(strat, side)]
        if n == 0:
            continue
        cov = n - nocov
        print(f"{str(strat):14s} {side:4s} {n:7d} "
              f"{ok/max(cov,1):8.4f} {nocov:6d}")


if __name__ == "__main__":
    main()
