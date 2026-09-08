#!/usr/bin/env python3
"""h661: theta ladder — terminal-frame cross-tab of the 3/4 bit.

h660: sincos fires are a STRICT SUBSET of cos fires (0 reverse rows /
177,481) — the pair-bit is a monotone propagate-depth-like condition,
not schedule noise.  All h657/h659 features were operand-side; the
propagate story lives in the TERMINAL frame: the retention-boundary
position.  h492 proved le2 (absolute exponent) was the missing frame
variable at theta=0.  Nobody has tested it on the theta band.

Cross-tab fire (inside the h658 region) against: left/right product
exponents (le, re), the result exponent ce, R low bits, and their
joints with theta and quadrant.
"""
import pickle, sys
from collections import defaultdict
from multiprocessing import Pool

sys.path.insert(0, "/Users/steve/llm/x87-transcendental/fsincos-re/experiments")
from h453_chain_variants import (C6_1, C6_2, C6_3, C6_4, C6_5, C6_6,
                                 build_chain, mul_round)

E2M = -66
UNIT = 2**66

QUAD = {
    (66, 1): (2, 2, 1,  0, 4, 1, 0, lambda d: -5 * (d - 7)),
    (66, 0): (4, 1, 0,  0, 2, 1, 0, lambda d: -9 - 5 * (d - 9)),
    (67, 0): (4, 2, 1, -2, 4, 2, 1, lambda d: -5 * (d - 7)),
    (67, 1): (2, 2, 3, -3, 8, 2, 1, lambda d: -4 - 2 * (d - 7)),
}
TAPS = {
    ("dn", 1, (66, 1)): (8, 1, -1, 1, -3),
    ("dn", 1, (67, 0)): (8, 1, -1, 1, -3),
    ("dn", 1, (67, 1)): (2, 1, 0, 0, 4),
    ("dn", 2, (66, 1)): (18, 0, 0, 0, -6),
    ("dn", 2, (67, 0)): (18, 0, 0, 0, -6),
    ("up", 1, (66, 1)): (6, -1, 0, 1, -1),
    ("up", 1, (67, 0)): (6, -1, 0, 1, -1),
    ("up", 1, (67, 1)): (6, 1, 0, -2, 0),
    ("up", 2, (66, 1)): (6, 0, 0, 1, 0),
    ("up", 2, (67, 0)): (6, 0, 0, 1, 0),
    ("up", 2, (67, 1)): (12, 0, 0, 0, 0),
}


def in_region(sign, th, quad, dist, L, b1, b2, M):
    tap = TAPS.get((sign, th, quad))
    if tap is None:
        return False
    a, G1, G2, p, Q, K, par, W = QUAD[quad]
    lp = L % 2
    base = a * L + G1 * b1 + G2 * b2 + p * lp + W(dist)
    c0, cb1, cb2, clp, cd = tap
    T = c0 + cb1 * b1 + cb2 * b2 + clp * lp + cd * (dist - 7)
    if sign == "dn":
        u = K * ((base - T) // Q) + par * lp
        return M < u * UNIT
    u = K * ((base + T) // Q) + par * lp
    return M >= u * UNIT


def terminal(args):
    mhex, sign, th, fire, R, ce = args
    m = int(mhex, 16)
    mag = (0, E2M, m)
    square = mul_round(mag, mag, 67, "chop")
    fourth = mul_round(square, square, 67, "chop")
    neg = build_chain(fourth, C6_5, C6_3, C6_1, 67, 64, "rn", False, False, False)
    pos = build_chain(fourth, C6_6, C6_4, C6_2, 67, 64, "rn", False, False, False)
    left = mul_round(square, neg, 67, "chop")
    right = mul_round(fourth, pos, 67, "chop")
    le, re = left[1], right[1]
    return {
        "sign": sign, "th": th, "fire": fire,
        "le": le, "re": re, "ce": ce,
        "R0": R & 1, "R1": (R >> 1) & 1, "R2": (R >> 2) & 1,
        "lece": le - ce, "rece": re - ce,
        "lm3": left[2] & 7, "rm3": right[2] & 7,
    }


def main():
    # join ties files for (R, ce)
    meta = {}
    for name in ("comb7", "comb8"):
        for lineS in open(f"ties_{name}.txt"):
            f = lineS.split()
            if f[0] not in meta:
                meta[f[0]] = (int(f[7], 16), int(f[8]))
    work = []
    for name in ("comb7", "comb8"):
        rows = pickle.load(open(f"h657m_{name}.pkl", "rb"))
        for mhex, theta, dist, s4, side, L, rdisc, sR, label, M, sqlow in rows:
            b1 = 1 if 3 * rdisc >= (1 << sR) else 0
            b2 = 1 if 3 * rdisc >= (1 << (sR + 1)) else 0
            sign = "dn" if theta > 0 else "up"
            if not in_region(sign, abs(theta), (s4, side), dist, L, b1, b2, M):
                continue
            fire = int(label == (1 if sign == "dn" else 2))
            R, ce = meta[mhex]
            work.append((mhex, sign, abs(theta), fire, R, ce))
        print(f"{name} loaded", flush=True)
    print(f"band rows: {len(work)}", flush=True)

    with Pool(8) as pool:
        out = pool.map(terminal, work, chunksize=2000)

    def xtab(tag, fn, group_by_sign=True):
        t = defaultdict(lambda: [0, 0])
        for o in out:
            k = (o["sign"], o["th"], fn(o)) if group_by_sign else fn(o)
            t[k][o["fire"]] += 1
        flags = []
        lines = []
        for k in sorted(t, key=str):
            c0, c1 = t[k]
            n = c0 + c1
            if n < 300:
                continue
            r = c1 / n
            lines.append(f"    {k}: n={n} rate={r:.4f}")
            if not 0.70 <= r <= 0.82:
                flags.append((k, n, r))
        print(f"\n  [{tag}]")
        for ln in lines[:40]:
            print(ln)
        if flags:
            print(f"  <== STRUCTURE: {flags[:10]}")
        return flags

    allflags = []
    allflags += xtab("le", lambda o: o["le"])
    allflags += xtab("re", lambda o: o["re"])
    allflags += xtab("ce", lambda o: o["ce"])
    allflags += xtab("le-ce", lambda o: o["lece"])
    allflags += xtab("re-ce", lambda o: o["rece"])
    allflags += xtab("R low bits", lambda o: (o["R0"], o["R1"], o["R2"]))
    allflags += xtab("left mant low3", lambda o: o["lm3"])
    allflags += xtab("right mant low3", lambda o: o["rm3"])
    allflags += xtab("(le-ce, R0)", lambda o: (o["lece"], o["R0"]))
    print(f"\nTOTAL structure flags: {len(allflags)}")


if __name__ == "__main__":
    main()
