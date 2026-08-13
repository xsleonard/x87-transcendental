#!/usr/bin/env python3
"""h495d: magnitude-variable screen.  The range probe shows fire rate
is monotone-decaying in m within every stratum.  Screen the TOP-bits
variables (m, R, ls, rf, sq) as conditioners at 8-bit resolution on
the merged map+fresh labeled data; then test the collapsed rule:
fire <=> magnitude-quantity < theta(stratum) with free thresholds
(step_errs both directions), reporting exactness per stratum."""
import random
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h453_chain_variants import (C6_1, C6_2, C6_3, C6_4, C6_5, C6_6,
                                 build_chain, mul_round)
from h492c_le2_threshold import step_errs
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
    payload = low3 + 8 - dist
    scale = min(left[1], right[1])
    if payload and left[1] - 8 < scale:
        scale = left[1] - 8
    M = (left[2] << (left[1]-scale)) + (payload << (left[1]-8-scale)) \
        - (right[2] << (right[1]-scale))
    k = M.bit_length() - 67
    R = M >> k
    rprod = fourth[2] * positive[2]
    sR = rprod.bit_length() - 67
    rud = (rprod & ((1 << sR) - 1)) >> (sR - 1)
    stratum = (dist, low3, left[1], rud)
    return (stratum, m, int(R), left[2], positive[2], square[2],
            fire)

def main():
    # merged labels
    rows = []
    with open("h491_mapdata.tssv") if False else open(
            "h491_mapdata.tsv") as fh:
        fh.readline()
        for line in fh:
            f = line.rstrip("\n").split("\t")
            if f[7] in ("CLEAN", "FIRE"):
                rows.append((f[0], f[7] == "FIRE"))
    # fresh
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
    print(f"merged labeled rows: {len(rows)}")
    with Pool(8) as pool:
        data = pool.map(build, rows, chunksize=500)

    strata = defaultdict(list)
    for stratum, m, R, ls, rf, sq, fire in data:
        strata[stratum].append((m, R, ls, rf, sq, fire))

    QIDX = {"m": 0, "R": 1, "ls": 2, "rf": 3, "sq": 4}
    print(f"\n{'stratum':22s} {'n':>6s} " +
          " ".join(f"{q:>6s}" for q in QIDX) + "   best")
    tot = {q: 0 for q in QIDX}
    totn = 0
    for stratum in sorted(strata, key=lambda s: -len(strata[s])):
        pts = strata[stratum]
        if len(pts) < 300:
            continue
        n1 = sum(p[5] for p in pts)
        if n1 == 0 or n1 == len(pts):
            continue
        errs = {}
        for q, qi in QIDX.items():
            e, _ = step_errs([(p[qi], p[5]) for p in pts])
            errs[q] = e
        totn += len(pts)
        for q in QIDX:
            tot[q] += errs[q]
        best = min(errs, key=errs.get)
        print(f"{str(stratum):22s} {len(pts):6d} " +
              " ".join(f"{errs[q]:6d}" for q in QIDX) +
              f"   {best} ({errs[best]/len(pts):.3f})")
    print(f"\nTOTALS over {totn}: " +
          " ".join(f"{q}={tot[q]} ({1-tot[q]/totn:.4f})"
                   for q in QIDX))

if __name__ == "__main__":
    main()
