#!/usr/bin/env python3
"""h662l: BLIND transfer of the block-start law to fresh corpora.

The h662 chain (g/h/j/k) was mined entirely on comb7+comb8 and closed
at 1 error / 410,589 region rows:
  non-critical region rows: fire = 1
  critical ((pm_up+phw)%8==7, pm_up in {7,8}), bs = w+8+((8-phw)%8):
    up: fire <=> mag bit(bs) = 1
    dn: fire <=> mag bit(w+8) = 1 AND mag bit(bs) = 1
comb5/comb6 were never touched by any h662 mining pass.  Build their
labeled theta caches (h657m recipe), apply the h658 region gate, score
the law exactly, and autopsy any exception.
"""
import os, pickle, sys
from collections import defaultdict
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h453_chain_variants import (C6_1, C6_2, C6_3, C6_4, C6_5, C6_6,
                                 build_chain, mul_round)

E2M = -66
PIV = 0.70710678118654752
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
    ("dn", 1, (66, 0)): (1, 1, -1, 1, 0),
    ("dn", 2, (66, 0)): (12, 0, 0, 0, -3),
    ("up", 1, (66, 0)): (7, -1, 1, 1, -2),
    ("up", 2, (66, 0)): (8, 1, 0, 1, -2),
}


def load3(ties, prefix):
    rows, seen = [], set()
    for lineS in open(ties):
        f = lineS.split()
        if f[0] in seen:
            continue
        seen.add(f[0])
        rows.append(f)
    inputs = sorted(f[0] for f in rows)
    order = {mm: i for i, mm in enumerate(inputs)}
    st = {md: open(f"{prefix}_{md}_status.txt").read().splitlines()
          for md in ROUNDING_MODES}
    out = []
    for f in rows:
        theta = int(f[9])
        if theta == 0:
            continue
        R, ce, i = int(f[7], 16), int(f[8]), order[f[0]]
        hw, bad = [], False
        for md in ROUNDING_MODES:
            t = st[md][i].split()
            if t[0] != "OK":
                bad = True
                break
            hw.append(int(t[2], 16))
        if bad:
            continue
        clean = [final_cosine_result(-R, ce, md) for md in ROUNDING_MODES]
        dn = [final_cosine_result(-(R - 1), ce, md) for md in ROUNDING_MODES]
        up = [final_cosine_result(-(R + 1), ce, md) for md in ROUNDING_MODES]
        if hw == clean:
            out.append((f[0], 0, theta))
        elif hw == dn:
            out.append((f[0], 1, theta))
        elif hw == up:
            out.append((f[0], 2, theta))
    return out


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


def internals(args):
    """h657m internals + h662e terminal-frame stats, fused."""
    mhex, label, theta = args
    m = int(mhex, 16)
    mag0 = (0, E2M, m)
    square = mul_round(mag0, mag0, 67, "chop")
    fourth = mul_round(square, square, 67, "chop")
    neg = build_chain(fourth, C6_5, C6_3, C6_1, 67, 64, "rn", False, False, False)
    pos = build_chain(fourth, C6_6, C6_4, C6_2, 67, 64, "rn", False, False, False)
    left = mul_round(square, neg, 67, "chop")
    right = mul_round(fourth, pos, 67, "chop")
    dist = abs(left[1] - right[1])
    sq = square[2]
    f4 = sq * sq
    s4 = f4.bit_length() - 67
    t4 = f4 & ((1 << s4) - 1)
    sqlow = sq - (1 << 66)
    M = (sq & 7) * sqlow - t4
    rprod = fourth[2] * pos[2]
    sR = rprod.bit_length() - 67
    rdisc = rprod & ((1 << sR) - 1)
    side = 0 if m / 2**64 < PIV else 1
    b1 = 1 if 3 * rdisc >= (1 << sR) else 0
    b2 = 1 if 3 * rdisc >= (1 << (sR + 1)) else 0
    sign = "dn" if theta > 0 else "up"
    if not in_region(sign, abs(theta), (s4, side), dist, sq & 7, b1, b2, M):
        return None
    fire = int(label == (1 if sign == "dn" else 2))

    product = square[2] * neg[2]
    shift = max(product.bit_length() - 67, 0)
    discarded = product & ((1 << shift) - 1) if shift > 0 else 0
    ud = (discarded << 3) >> shift if shift > 0 else 0
    u5d = (discarded << 5) >> shift if shift > 0 else 0
    rud = (rdisc << 1) >> sR if sR > 0 else 0
    low3 = square[2] & 7
    distance = abs(left[1] - right[1])
    active = 1 if (low3 and (ud or (distance == 7 and u5d))) else 0
    payload = low3 + 8 - distance if active else 0
    if active and distance == 10 and low3 == 6 and rud:
        lane_shift = (left[1] - 8) - right[1]
        lane = (right[2] >> lane_shift) if lane_shift >= 0 \
            else (right[2] << -lane_shift)
        lp8 = lane & 0xFF
        d8 = (lp8 - payload) & 0xFF
        if d8 >= 128:
            d8 -= 256
        if d8 == -2:
            payload = lp8
    if active and distance == 8 and low3 == 7 and ud >= 3:
        lane_shift = (left[1] - 8) - right[1]
        lane = (right[2] >> lane_shift) if lane_shift >= 0 \
            else (right[2] << -lane_shift)
        lp8 = lane & 0xFF
        d8 = (lp8 - payload) & 0xFF
        if d8 >= 128:
            d8 -= 256
        if d8 == 0:
            payload -= 1
    scale = min(left[1], right[1])
    if payload and left[1] - 8 < scale:
        scale = left[1] - 8
    A = left[2] << (left[1] - scale)
    B = right[2] << (right[1] - scale)
    P = (payload << (left[1] - 8 - scale)) if payload else 0
    S = A + P
    mag = S - B
    if mag <= 0:
        return None
    w = mag.bit_length() - 67
    if w <= 0:
        return None
    pmask_all = ~(S ^ B)
    pm_up = 0
    j = w
    while (pmask_all >> j) & 1:
        pm_up += 1
        j += 1
    return (sign, abs(theta), fire, min(pm_up, 24), w, (scale + w) % 8,
            scale, S, B)


def main():
    for name in sys.argv[1:] or ("comb5", "comb6"):
        cache = f"h664c_{name}.pkl"
        if os.path.exists(cache):
            out = pickle.load(open(cache, "rb"))
            print(f"{name}: {len(out)} region rows from cache", flush=True)
        else:
            lab = load3(f"ties_{name}.txt", name)
            print(f"{name}: {len(lab)} labeled; internals ...", flush=True)
            with Pool(os.cpu_count()) as pool:
                out = pool.map(internals, lab, chunksize=1000)
            out = [o for o in out if o is not None]
            pickle.dump(out, open(cache, "wb"))
            print(f"{name}: {len(out)} region rows", flush=True)

        err = defaultdict(int)
        bad = []
        ncrit = 0
        for o in out:
            sign, th, fire, pm_up, w, phw, scale, S, B = o
            critical = (pm_up + phw) % 8 == 7 and pm_up in (7, 8)
            if critical:
                ncrit += 1
                mag = S - B
                bs = w + 8 + ((8 - phw) % 8)
                b8 = (mag >> (w + 8)) & 1
                bbs = (mag >> bs) & 1
                pred = bbs if sign == "up" else (b8 & bbs)
            else:
                pred = 1
            if pred != fire:
                err[(sign, th, "crit" if critical else "pure")] += 1
                bad.append(o)
        print(f"{name}: BLIND errors {sum(err.values())} / {len(out)} "
              f"({ncrit} critical)", flush=True)
        for k in sorted(err, key=str):
            print(f"  {k}: {err[k]}")
        for o in bad[:10]:
            sign, th, fire, pm_up, w, phw, scale, S, B = o
            mag = S - B
            print(f"  exc: sign={sign} th={th} fire={fire} pm_up={pm_up} "
                  f"w={w} phw={phw} scale={scale} mag={mag:#x}")


if __name__ == "__main__":
    main()
