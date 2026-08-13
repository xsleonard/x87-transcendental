#!/usr/bin/env python3
"""h538: MODEL-FREE VALUE-DELTA BRACKETING (the inversion payoff).

Class: hardware terminal = exact unchopped subtract of a value
modified by a structural delta D(m); result deviates from exact iff
D crosses the retention boundary at kf.  Then, with
Vlow = (APf - B_full) mod 2^kf:
    req2 = +1  requires  D >= gap_up = 2^kf - Vlow
    req2 = -1  requires  D <= -gap_dn = -(Vlow + 1)
    req2 =  0  requires  -gap_dn < D < gap_up
Per row this brackets |D| on the near side with NO model of the
pair, tree, or resolver.  Consistency = in every neighborhood of m
(per stratum, per side) max(gap of fires) < min(gap of cleans).
Violations refute the class; consistency MEASURES log2|D|(m).

Output: h538_rows.tsv (mhex theta req2 side dist low3 ce kf glog
XT XD mf) + per-stratum m-binned bracket census.
"""
import math
import sys
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h453_chain_variants import (C6_1, C6_2, C6_3, C6_4, C6_5, C6_6,
                                 build_chain, mul_round)

E2M = -66
SC = 60


def features(mhex):
    m = int(mhex, 16)
    mag = (0, E2M, m)
    sq = mul_round(mag, mag, 67, "chop")
    f4 = mul_round(sq, sq, 67, "chop")
    neg = build_chain(f4, C6_5, C6_3, C6_1, 67, 64, "rn",
                      False, False, False)
    pos = build_chain(f4, C6_6, C6_4, C6_2, 67, 64, "rn",
                      False, False, False)
    left = mul_round(sq, neg, 67, "chop")
    right = mul_round(f4, pos, 67, "chop")
    low3 = sq[2] & 7
    dist = abs(left[1] - right[1])
    payload = low3 + 8 - dist
    scale = min(left[1], right[1], left[1] - 8)
    A = left[2] << (left[1] - scale)
    P = payload << (left[1] - 8 - scale)
    Bres = right[2] << (right[1] - scale)
    M = A + P - Bres
    k = M.bit_length() - 67
    R = M >> k
    B_full = f4[2] * pos[2]
    rsh = B_full.bit_length() - 67
    f4_full = sq[2] * sq[2]
    s4 = f4_full.bit_length() - 67
    t4 = f4_full & ((1 << s4) - 1)
    rprod = B_full
    sR = rsh
    rdisc = rprod & ((1 << sR) - 1)
    XT = ((t4 << SC) >> s4) / 2**SC
    XD = ((rdisc << SC) >> sR) / 2**SC
    return (A, P, M, k, R, B_full, rsh, right[1] - scale,
            dist, low3, XT, XD, m / 2**64)


def work(rows):
    out = []
    for mhex, theta, lab, ce in rows:
        (A, P, M, k, R, B_full, rsh, bshift, dist, low3,
         XT, XD, mf) = features(mhex)
        F = rsh - bshift
        if F < 0:
            continue
        kf = k + F
        APf = (A + P) << F
        EU = (APf - B_full) >> kf
        Vlow = (APf - B_full) - (EU << kf)
        req2 = (R + {"clean": 0, "down": -1, "up": 1}[lab]) - EU
        gap_dn = Vlow + 1
        gap_up = (1 << kf) - Vlow
        if req2 == 1:
            side, gap = "u", gap_up
        elif req2 == -1:
            side, gap = "d", gap_dn
        else:
            # clean: near side only (the binding constraint)
            if gap_dn <= gap_up:
                side, gap = "d", gap_dn
            else:
                side, gap = "u", gap_up
        glog = math.log2(gap)
        out.append((mhex, theta, req2, side, dist, low3, ce, kf,
                    glog, XT, XD, mf))
    return out


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
    order = {m: i for i, m in enumerate(inputs)}
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
    print(f"labeled {len(labeled)} rows", flush=True)
    chunks = [labeled[i::8] for i in range(8)]
    with Pool(8) as pool:
        parts = pool.map(work, chunks)
    allrows = [r for part in parts for r in part]
    with open("h538_rows.tsv", "w") as fh:
        fh.write("mhex\ttheta\treq2\tside\tdist\tlow3\tce\tkf\t"
                 "glog\tXT\tXD\tmf\n")
        for r in allrows:
            fh.write("\t".join(str(x) for x in r) + "\n")
    # bracket census: per (side, dist, low3, ce), 64 m-bins
    strata = defaultdict(lambda: defaultdict(
        lambda: [-1.0, 999.0, 0, 0]))   # maxfire minclean nf nc
    for (mhex, theta, req2, side, dist, low3, ce, kf, glog,
         XT, XD, mf) in allrows:
        b = int(mf * 256) if mf < 1 else 255
        cell = strata[(side, dist, low3, ce)][b]
        if req2:
            cell[0] = max(cell[0], glog)
            cell[2] += 1
        else:
            cell[1] = min(cell[1], glog)
            cell[3] += 1
    print("\nbracket census (only bins with both classes):")
    nviol = ncons = 0
    viol_by = defaultdict(int)
    for key in sorted(strata):
        for b in sorted(strata[key]):
            mx, mn, nf, nc = strata[key][b]
            if nf and nc:
                if mx >= mn:
                    nviol += 1
                    viol_by[key] += 1
                else:
                    ncons += 1
    print(f"bins consistent: {ncons}, VIOLATED: {nviol}")
    for key in sorted(viol_by, key=lambda k2: -viol_by[k2])[:20]:
        print(f"  {key}: {viol_by[key]} violated bins")


if __name__ == "__main__":
    main()
