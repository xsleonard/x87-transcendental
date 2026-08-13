#!/usr/bin/env python3
"""h487b: per-cell free-threshold sweep on FULL-PRECISION normalized
quantities.  All prior tests binned t4/rdisc into top-j windows or
capped constants; this normalizes each quantity to a common 72-bit
fraction scale and sweeps thresholds freely per cell:
  XT = t4 / 2^s4, XD = rdisc / 2^sR, XP = t4*rf / 2^(s4+64),
  XE = (rdisc*2^s4 + t4*rf) / 2^(sR+s4)   [extended discard]
  composites: singles, XP+XD, XP-XD, XT+XD, XT-XD, XE, 2XT+XD, XT+2XD
Exact iff labels form a step in the quantity (either direction).
"""
from collections import defaultdict
from multiprocessing import Pool
from h453_chain_variants import (C6_1, C6_2, C6_3, C6_4, C6_5, C6_6,
                                 build_chain, mul_round)
from h484_cegis import load_labels
E2M = -66
SC = 72

def build_row(item):
    mhex, o = item
    if o == 2:
        return None
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
    dist = abs(left[1] - right[1])
    payload = low3 + 8 - dist
    scale = min(left[1], right[1])
    if payload and left[1] - 8 < scale:
        scale = left[1] - 8
    M = (left[2] << (left[1]-scale)) + (payload << (left[1]-8-scale)) \
        - (right[2] << (right[1]-scale))
    k = M.bit_length() - 67
    cell = (dist, low3, k, rdisc >> (sR - 1))
    XT = (t4 << SC) >> s4
    XD = (rdisc << SC) >> sR
    XP = (t4 * positive[2] << SC) >> (s4 + 64)
    XE = ((rdisc << s4) + t4 * positive[2] << SC) >> (sR + s4)
    return (o, cell, {"XT": XT, "XD": XD, "XP": XP, "XE": XE})

def step_fit(vals):
    byx = defaultdict(set)
    for x, o in vals:
        byx[x].add(o)
    if any(len(s) > 1 for s in byx.values()):
        return None
    xs = sorted(byx)
    seq = [next(iter(byx[x])) for x in xs]
    if all(seq[i] <= seq[i+1] for i in range(len(seq)-1)):
        return ("up", next((xs[i] for i, s in enumerate(seq)
                            if s == 1), None))
    if all(seq[i] >= seq[i+1] for i in range(len(seq)-1)):
        return ("down", next((xs[i] for i, s in enumerate(seq)
                              if s == 0), None))
    return None

COMPS = [
    ("XT", lambda q: q["XT"]), ("XD", lambda q: q["XD"]),
    ("XP", lambda q: q["XP"]), ("XE", lambda q: q["XE"]),
    ("XP+XD", lambda q: q["XP"] + q["XD"]),
    ("XP-XD", lambda q: q["XP"] - q["XD"]),
    ("XT+XD", lambda q: q["XT"] + q["XD"]),
    ("XT-XD", lambda q: q["XT"] - q["XD"]),
    ("2XT+XD", lambda q: 2*q["XT"] + q["XD"]),
    ("XT+2XD", lambda q: q["XT"] + 2*q["XD"]),
    ("2XP+XD", lambda q: 2*q["XP"] + q["XD"]),
    ("XP+2XD", lambda q: q["XP"] + 2*q["XD"]),
]

def main():
    rows = load_labels()
    with Pool(8) as pool:
        data = [r for r in pool.map(build_row, sorted(rows.items()),
                                    chunksize=50) if r]
    cells = defaultdict(list)
    for o, cell, q in data:
        cells[cell].append((o, q))
    solved = 0
    total = 0
    for cell in sorted(cells):
        rs_ = cells[cell]
        if len(rs_) < 8:
            continue
        n1 = sum(o for o, _ in rs_)
        if n1 == 0 or n1 == len(rs_):
            continue
        total += 1
        hits = []
        for name, fn in COMPS:
            r = step_fit([(fn(q), o) for o, q in rs_])
            if r:
                hits.append((name, r[0], r[1]))
        if hits:
            solved += 1
            frac = [f"{n}:{d}@{t/2**SC:.6f}" for n, d, t in hits[:3]]
            print(f"  {cell} n={len(rs_)} f={n1}: " + "; ".join(frac))
        else:
            # report best near-miss: min violations over sweeps
            best = None
            for name, fn in COMPS:
                vals = sorted((fn(q), o) for o, q in rs_)
                labs = [o for _, o in vals]
                # min errors for a monotone step either direction
                nf = labs.count(1)
                pre1 = 0
                best_up = nf
                for i, o in enumerate(labs):
                    pre1 += o
                    best_up = min(best_up, pre1 + (nf - pre1) -
                                  (nf - pre1) + (labs[:i+1].count(1)
                                  - 0)*0 + 0)
                # simpler: dp
                e_up = min(sum(labs[:i]) + (len(labs)-i-sum(labs[i:]))
                           - (len(labs)-i-sum(labs[i:]))
                           + sum(1 for x in labs[i:] if x == 0)*0
                           + sum(1 for x in labs[:i] if x == 1)
                           + sum(1 for x in labs[i:] if x == 0)*0
                           for i in range(len(labs)+1)) \
                    if labs else 0
                errs = min(
                    min(sum(1 for x in labs[:i] if x == 1)
                        + sum(1 for x in labs[i:] if x == 0)
                        for i in range(len(labs)+1)),
                    min(sum(1 for x in labs[:i] if x == 0)
                        + sum(1 for x in labs[i:] if x == 1)
                        for i in range(len(labs)+1)))
                if best is None or errs < best[1]:
                    best = (name, errs)
            print(f"  {cell} n={len(rs_)} f={n1}: none "
                  f"(best {best[0]} errs={best[1]})")
    print(f"\nsolved {solved}/{total}")

if __name__ == "__main__":
    main()
