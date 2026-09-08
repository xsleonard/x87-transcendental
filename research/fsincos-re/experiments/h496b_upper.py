#!/usr/bin/env python3
"""h496b: structure of the rf >= 2/3 regime.  Within it, per stratum:
fire rate vs rf in fine bins (do further constants organize it?),
plus the 50-percent crossing in rf and the rf-value census of fires
vs cleans near candidate constants (2/3, 7/10, 5/7, 3/4, 7/9, 4/5,
5/6, 6/7, 7/8)."""
from collections import defaultdict
from multiprocessing import Pool
from h496_twothirds import build as build96
from h495d_magnitude import build as buildmag
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h453_chain_variants import (C6_2, C6_4, C6_6, build_chain,
                                 mul_round)
from h454_stale_carry import mul_state, add_state
from h453_chain_variants import C6_1, C6_3, C6_5
E2M = -66

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
    low3 = square[2] & 7
    dist = abs(left[1] - right[1])
    rprod = fourth[2] * positive[2]
    sR = rprod.bit_length() - 67
    rud = (rprod & ((1 << sR) - 1)) >> (sR - 1)
    return ((dist, low3, rud), positive[2], negative[2], int(fire))

def main():
    rows = []
    with open("h491_mapdata.tsv") as fh:
        fh.readline()
        for line in fh:
            f = line.rstrip("\n").split("\t")
            if f[7] in ("CLEAN", "FIRE"):
                rows.append((f[0], f[7] == "FIRE"))
    fresh = []
    seen = set()
    for line in open("ties_fresh.txt"):
        f = line.split()
        if f[0] not in seen:
            seen.add(f[0])
            fresh.append(f)
    inputs = sorted(f[0] for f in fresh)
    order = {mm: i for i, mm in enumerate(inputs)}
    st = {md: open(f"fcos2_{md}_status.txt").read().splitlines()
          for md in ROUNDING_MODES}
    for f in fresh:
        R = int(f[7], 16)
        ce = int(f[8])
        i = order[f[0]]
        hw = []
        bad = False
        for md in ROUNDING_MODES:
            t = st[md][i].split()
            if t[0] != "OK":
                bad = True
                break
            hw.append(int(t[2], 16))
        if bad:
            continue
        clean = [final_cosine_result(-R, ce, md)
                 for md in ROUNDING_MODES]
        fired = [final_cosine_result(-(R-1), ce, md)
                 for md in ROUNDING_MODES]
        if hw == clean:
            rows.append((f[0], False))
        elif hw == fired:
            rows.append((f[0], True))
    dedup = {}
    for mhex, fire in rows:
        dedup[mhex] = fire
    rows = sorted(dedup.items())
    with Pool(8) as pool:
        data = pool.map(build, rows, chunksize=500)

    TWO3 = (2 << 65) // 3 + 1
    upper = [d for d in data if 3 * d[1] >= 1 << 65]
    print(f"total {len(data)}, rf>=2/3 rows {len(upper)}, fires "
          f"{sum(d[3] for d in upper)}")

    # pooled fire rate vs rf in 1/96 bins over [2/3, 1)
    bins = defaultdict(lambda: [0, 0])
    for s, rf, lf, fire in upper:
        frac = (rf - (1 << 63)) * 96 // (1 << 63)   # 0..95 over [.5,1)
        b = bins[frac]
        b[0] += 1
        b[1] += fire
    print("\npooled rate vs rf (bins of 1/192 of binade, from 2/3):")
    for b in sorted(bins):
        lo = 0.5 + b / 192
        n, fi = bins[b]
        if n >= 200 and lo >= 0.66:
            bar = "#" * int(40 * fi / n)
            print(f"  rf~{lo:.4f} n={n:6d} rate={fi/n:.3f} {bar}")

    # also: is lf (left chain) involved? rate vs lf for rf>=2/3
    bins = defaultdict(lambda: [0, 0])
    for s, rf, lf, fire in upper:
        fl = (lf - (1 << 63)) * 24 // (1 << 63)
        b = bins[fl]
        b[0] += 1
        b[1] += fire
    print("\npooled rate vs lf (rf>=2/3):")
    for b in sorted(bins):
        n, fi = bins[b]
        if n >= 500:
            lo = 0.5 + b / 48
            bar = "#" * int(40 * fi / n)
            print(f"  lf~{lo:.4f} n={n:6d} rate={fi/n:.3f} {bar}")

if __name__ == "__main__":
    main()
