#!/usr/bin/env python3
"""h668: comb13 near-boundary pipeline — the comparator's blind test.

comb13 (run_scan19.sh) is a fresh-lattice tie scan of BOTH operand
windows.  This script: (1) filters its ties to near-thirds-boundary
rows (EPS 1e-3), (2) emits capture inputs, and — after the capture
stage has produced comb13n_{rn,rd,ru}_status.txt — (3) labels, votes
(h665 machinery), and scores the locked truncated-3x prediction
    b_j = [3*rdisc - (2*rdisc mod 2^47) - (rdisc mod 2^47) >= j*2^sR]
on the fresh rows, stratified by direction, against exact thirds.

Stage select: argv[1] in {filter, votes}.
"""
import os
import pickle
import sys
from collections import defaultdict
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from h665_comparator import (label_row, internals_near, near_j,
                             vote_theta0, vote_thetaN, UNIT)
from h437_gate_extraction import ROUNDING_MODES


def stage_filter():
    seen = set()
    keep = []
    n = 0
    for line in open("/root/h491/ties_comb13.txt"):
        f = line.split()
        if len(f) < 10 or f[0] in seen:
            continue
        seen.add(f[0])
        n += 1
        keep.append((f[0], int(f[9]), int(f[7], 16), int(f[8])))
    print(f"comb13: {n} unique ties; computing internals ...", flush=True)
    with Pool(os.cpu_count()) as pool:
        rows = pool.map(prefilter, keep, chunksize=2000)
    rows = [r for r in rows if r is not None]
    pickle.dump(rows, open("h668_meta.pkl", "wb"))
    with open("/root/h491/comb13n_inputs.txt", "w") as f:
        for mhex, theta, R, ce in sorted(rows):
            f.write(f"3ffc {mhex}\n")
    print(f"comb13: {len(rows)} near-boundary rows -> comb13n_inputs.txt",
          flush=True)


def prefilter(args):
    mhex, theta, R, ce = args
    from h453_chain_variants import (C6_1, C6_2, C6_3, C6_4, C6_5,
                                     C6_6, build_chain, mul_round)
    m = int(mhex, 16)
    mag = (0, -66, m)
    square = mul_round(mag, mag, 67, "chop")
    fourth = mul_round(square, square, 67, "chop")
    pos = build_chain(fourth, C6_6, C6_4, C6_2, 67, 64, "rn",
                      False, False, False)
    rprod = fourth[2] * pos[2]
    sR = rprod.bit_length() - 67
    rdisc = rprod & ((1 << sR) - 1)
    if not near_j(3 * rdisc, 1 << sR):
        return None
    return (mhex, theta, R, ce)


def stage_votes():
    meta = {m: (theta, R, ce)
            for (m, theta, R, ce) in pickle.load(open("h668_meta.pkl",
                                                      "rb"))}
    inputs = [l.split()[1]
              for l in open("/root/h491/comb13n_inputs.txt")]
    st = {md: open(f"/root/h491/comb13n_{md}_status.txt")
          .read().splitlines() for md in ROUNDING_MODES}
    lab = []
    for i, mhex in enumerate(inputs):
        theta, R, ce = meta[mhex]
        hw, bad = [], False
        for md in ROUNDING_MODES:
            t = st[md][i].split()
            if t[0] != "OK":
                bad = True
                break
            hw.append(int(t[2], 16))
        if not bad:
            lab.append((mhex, theta, R, ce, tuple(hw)))
    print(f"labeling {len(lab)} rows ...", flush=True)
    with Pool(os.cpu_count()) as pool:
        lab2 = pool.map(label_row, [(m, t, R, ce, hw)
                                    for (m, t, R, ce, hw) in lab],
                        chunksize=500)
    with Pool(os.cpu_count()) as pool:
        rows = pool.map(internals_near, lab2, chunksize=500)
    rows = [r for r in rows if r is not None]
    pickle.dump(rows, open("h668_comb13.pkl", "wb"))

    votes, anom = [], []
    for row in rows:
        mhex, theta, d, s4, side, L, rdisc, sR, label, M, _ = row
        if label == -1:
            continue
        for j in near_j(3 * rdisc, 1 << sR):
            if theta == 0:
                if label == 2:
                    continue
                req = M // UNIT + (1 if label == 1 else 0)
                vote_theta0("comb13", (s4, side), d, L, sR, label == 1,
                            req, j, "rd", rdisc, mhex, votes, anom)
            else:
                vote_thetaN("comb13", row, j, votes, anom)
    pickle.dump((votes, anom), open("h668_votes.pkl", "wb"))
    print(f"comb13 votes: {len(votes)}  anomalies: {len(anom)}")

    def dirclass(th):
        return "t0" if th == 0 else ("dn" if th > 0 else "up")

    def pred_trunc(j, sR, r, t):
        mask = (1 << t) - 1
        comp = 3 * r - ((2 * r) & mask) - (r & mask)
        return 1 if comp >= (j << sR) else 0

    def pred_exact(j, sR, r):
        return 1 if 3 * r >= (j << sR) else 0

    for dc in ("t0", "dn", "up"):
        sel = [v for v in votes if dirclass(v[6]) == dc]
        for name, fn in (("exact", lambda j, s, r: pred_exact(j, s, r)),
                         ("t47", lambda j, s, r: pred_trunc(j, s, r, 47)),
                         ("t46", lambda j, s, r: pred_trunc(j, s, r, 46))):
            viol = [v for v in sel if fn(v[1], v[3], v[8]) != v[9]]
            print(f"BLIND comb13 {dc} {name}: {len(viol)} viol "
                  f"/ {len(sel)}")
            for v in viol[:12]:
                corpus, j, quad, sR, d, L, th, kind, r, vote, mhex = v
                g = (3 * r - (j << sR)) / 2 ** sR * 1e6
                print(f"    q={quad} j={j} sR={sR} d={d} L={L} "
                      f"th={th:+d} v={vote} g={g:+8.3f}e-6 {mhex}")


if __name__ == "__main__":
    if sys.argv[1] == "filter":
        stage_filter()
    else:
        stage_votes()
