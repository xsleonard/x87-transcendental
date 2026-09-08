#!/usr/bin/env python3
"""h551: TABULATE THE SELECTOR g over (XT, mf) from J-intervals.

pred(j) = floor(((Vlow<<2) - j*rfv) / 2^(kf+2)) is monotone
non-increasing in j, so J(row) = {j : pred(j) = req2} is an
INTERVAL [jlo, jhi] (possibly empty).  If the resolver's selector
is a function g(XT, mf) (physical, stratum-free), then in every
fine (XT, mf) cell the row intervals intersect.

Keys compared:
  G0: (XT/256 bin, mf grid 2^-11)          universal
  G1: G0 + s4 parity
  G2: G0 + stratum (dist, low3, ce)
Outputs: feasibility (rows in non-empty cells), pin fraction
(cells forced to a single j), and the G0 forced-j map dumped to
h551_gmap.tsv for geometry matching.
"""
import sys
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h539_D_library import qrow

JLO, JHI = -8, 8


def work(rows):
    cells = {0: {}, 1: {}, 2: {}}
    nviol = 0
    n = 0
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
        jlo = None
        jhi = None
        for j in range(JLO, JHI + 1):
            T = base - j * rfv
            pred = 1 if T >= top else (-1 if T < 0 else 0)
            if pred == req2:
                if jlo is None:
                    jlo = j
                jhi = j
        n += 1
        if jlo is None:
            nviol += 1
            continue
        f4_full = sqv * sqv
        s4 = f4_full.bit_length() - 67
        xtb = (t4 << 8) >> s4          # XT in 1/256 bins
        mfb = m >> 53                  # mf in 2^-11 bins
        k0 = (xtb, mfb)
        k1 = (xtb, mfb, s4 & 1)
        k2 = (xtb, mfb, dist, low3, ce)
        for lvl, key in ((0, k0), (1, k1), (2, k2)):
            cell = cells[lvl].get(key)
            if cell is None:
                cells[lvl][key] = [jlo, jhi, 1]
            else:
                if jlo > cell[0]:
                    cell[0] = jlo
                if jhi < cell[1]:
                    cell[1] = jhi
                cell[2] += 1
    return cells, nviol, n


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
    stride = int(sys.argv[1]) if len(sys.argv) > 1 else 4
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
    cells = {0: {}, 1: {}, 2: {}}
    nviol = n = 0
    for pc, pv, pn in parts:
        nviol += pv
        n += pn
        for lvl in (0, 1, 2):
            for key, (lo, hi, c) in pc[lvl].items():
                cell = cells[lvl].get(key)
                if cell is None:
                    cells[lvl][key] = [lo, hi, c]
                else:
                    if lo > cell[0]:
                        cell[0] = lo
                    if hi < cell[1]:
                        cell[1] = hi
                    cell[2] += c
    print(f"rows {n}, ladder violations {nviol} ({nviol/n:.5f})")
    for lvl, name in ((0, "G0 (XT, mf)"), (1, "G1 +s4par"),
                      (2, "G2 +stratum")):
        cc = cells[lvl]
        rows_ok = sum(c for lo, hi, c in cc.values() if lo <= hi)
        rows_bad = sum(c for lo, hi, c in cc.values() if lo > hi)
        pinned = sum(1 for lo, hi, c in cc.values() if lo == hi)
        pinrows = sum(c for lo, hi, c in cc.values() if lo == hi)
        print(f"{name}: cells {len(cc)}, rows feasible {rows_ok} "
              f"({rows_ok/(rows_ok+rows_bad):.4f}), pinned cells "
              f"{pinned} ({pinrows} rows)")
    with open("h551_gmap.tsv", "w") as fh:
        fh.write("xtb\tmfb\tjlo\tjhi\tn\n")
        for (xtb, mfb), (lo, hi, c) in sorted(cells[0].items()):
            fh.write(f"{xtb}\t{mfb}\t{lo}\t{hi}\t{c}\n")
    print("G0 map -> h551_gmap.tsv")


if __name__ == "__main__":
    main()
