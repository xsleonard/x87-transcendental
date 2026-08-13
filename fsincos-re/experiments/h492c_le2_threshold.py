#!/usr/bin/env python3
"""h492c: per-(cell, le2) full-precision threshold fit on XE.
The h492/h492b screens say the gate ~ threshold on the extended
discard fraction with the threshold set by (cell, le2).  Per stratum:
exact step fit (h487b machinery) on XE, XT, XD at full precision;
census of exact/near strata and the fitted theta table."""
from collections import defaultdict
from multiprocessing import Pool
from h453_chain_variants import (C6_1, C6_2, C6_3, C6_4, C6_5, C6_6,
                                 build_chain, mul_round)
E2M = -66
SC = 72

def build(args):
    mhex, fire = args
    m = int(mhex, 16)
    mag = (0, E2M, m)
    square = mul_round(mag, mag, 67, "chop")
    fourth = mul_round(square, square, 67, "chop")
    negative = build_chain(fourth, C6_5, C6_3, C6_1, 67, 64, "rn",
                           False, False, False)
    positive = build_chain(fourth, C6_6, C6_4, C6_2, 67, 64, "rn",
                           False, False, False)
    left = mul_round(square, negative, 67, "chop")
    right = mul_round(fourth, positive, 67, "chop")
    f4_full = square[2] * square[2]
    s4 = f4_full.bit_length() - 67
    t4 = f4_full & ((1 << s4) - 1)
    rprod = fourth[2] * positive[2]
    sR = rprod.bit_length() - 67
    rdisc = rprod & ((1 << sR) - 1)
    low3 = square[2] & 7
    dist = left[1] - right[1]
    if dist < 0:
        dist = -dist
    XT = (t4 << SC) >> s4
    XD = (rdisc << SC) >> sR
    XE = (((rdisc << s4) + t4 * positive[2]) << SC) >> (sR + s4)
    rud = rdisc >> (sR - 1)
    cell = (dist, low3, left[1], rud)
    return (cell, XT, XD, XE, fire)

def step_errs(vals):
    """min errors of a monotone step, either direction."""
    vals.sort()
    labs = [o for _, o in vals]
    n1 = sum(labs)
    n = len(labs)
    best_up = n1
    best_dn = n - n1
    pre1 = 0
    for i, o in enumerate(labs):
        pre1 += o
        pre0 = (i + 1) - pre1
        e_up = pre1 + (n - i - 1) - (n1 - pre1)
        e_dn = pre0 + (n1 - pre1)
        if e_up < best_up:
            best_up = e_up
        if e_dn < best_dn:
            best_dn = e_dn
    return min(best_up, min(best_dn, n1)), n

def main():
    rows = []
    with open("h491_mapdata.tsv") as fh:
        fh.readline()
        for line in fh:
            f = line.rstrip("\n").split("\t")
            if f[7] in ("CLEAN", "FIRE"):
                rows.append((f[0], f[7] == "FIRE"))
    with Pool(8) as pool:
        data = pool.map(build, rows, chunksize=500)
    strata = defaultdict(list)
    for cell, XT, XD, XE, fire in data:
        strata[cell].append((XT, XD, XE, fire))
    print(f"strata (dist, low3, le2, rud): {len(strata)}")
    tot_rows = tot_err_xe = tot_err_xt = tot_err_xd = 0
    exact = near = 0
    table = []
    for cell in sorted(strata):
        pts = strata[cell]
        if len(pts) < 30:
            continue
        n1 = sum(p[3] for p in pts)
        if n1 == 0 or n1 == len(pts):
            continue
        e_xe, n = step_errs([(p[2], p[3]) for p in pts])
        e_xt, _ = step_errs([(p[0], p[3]) for p in pts])
        e_xd, _ = step_errs([(p[1], p[3]) for p in pts])
        tot_rows += n
        tot_err_xe += e_xe
        tot_err_xt += e_xt
        tot_err_xd += e_xd
        if e_xe == 0:
            exact += 1
        elif e_xe <= max(2, n // 100):
            near += 1
        table.append((cell, n, n1, e_xe, e_xt, e_xd))
    print(f"mixed strata >=30 rows: {len(table)}; XE-step exact: "
          f"{exact}, near (<=1%): {near}")
    print(f"total rows {tot_rows}; step-errors XE {tot_err_xe} "
          f"({1-tot_err_xe/tot_rows:.4f}), XT {tot_err_xt} "
          f"({1-tot_err_xt/tot_rows:.4f}), XD {tot_err_xd} "
          f"({1-tot_err_xd/tot_rows:.4f})")
    print("\nworst 12 strata by XE errors:")
    for cell, n, n1, e_xe, e_xt, e_xd in sorted(
            table, key=lambda x: -x[3])[:12]:
        print(f"  {cell} n={n} fires={n1} errsXE={e_xe} "
              f"errsXT={e_xt} errsXD={e_xd}")

if __name__ == "__main__":
    main()
