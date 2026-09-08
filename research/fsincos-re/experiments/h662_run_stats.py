#!/usr/bin/env python3
"""h662: theta ladder — exact terminal run/propagate statistics.

h660's nesting result (sincos fires strictly nested in cos fires)
predicts ONE monotone depth quantity D(m) with schedule-dependent
thresholds.  The physical candidate that was PROVABLY untestable at
ties (h477 theorem: at an exact tie the carry ripples the whole field
by construction) but varies freely at theta!=0: the terminal
subtract's borrow TRAVEL DISTANCE — how far the carry actually
ripples through the propagate chain to reach the retained field.

Per band row, rebuild the exact terminal (h453 terminal() recipe):
  S = A + P (minuend side), B subtrahend, mag = S - B, chop at w.
  propagate p_i = NOT(S_i XOR B_i)  [bits of S + ~B]
  generate  g_i = S_i AND NOT(B_i)
  travel = w - j*, j* = highest j < w with g_j and p_{j+1..w-1} all 1
  (the exact distance the borrow rippled to enter the retained field)
plus discard-field run stats (trailing/leading ones/zeros, zero count)
and propagate-run length across the chop boundary.

Cross-tab fire vs each statistic (per theta, per direction); then the
sincos second-threshold check on comb7 (fire_sc | fire_cos vs the
same statistic).
"""
import pickle, sys
from collections import defaultdict
from multiprocessing import Pool

sys.path.insert(0, "/Users/steve/llm/x87-transcendental/fsincos-re/experiments")
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
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


def trailing_ones(x):
    n = 0
    while x & 1:
        x >>= 1
        n += 1
    return n


def stats(args):
    mhex, sign, th, fire, fire_sc = args
    m = int(mhex, 16)
    mag0 = (0, E2M, m)
    square = mul_round(mag0, mag0, 67, "chop")
    fourth = mul_round(square, square, 67, "chop")
    neg = build_chain(fourth, C6_5, C6_3, C6_1, 67, 64, "rn", False, False, False)
    pos = build_chain(fourth, C6_6, C6_4, C6_2, 67, 64, "rn", False, False, False)
    left = mul_round(square, neg, 67, "chop")
    right = mul_round(fourth, pos, 67, "chop")
    # payload logic verbatim from h453 terminal()
    product = square[2] * neg[2]
    shift = max(product.bit_length() - 67, 0)
    discarded = product & ((1 << shift) - 1) if shift > 0 else 0
    ud = (discarded << 3) >> shift if shift > 0 else 0
    u5d = (discarded << 5) >> shift if shift > 0 else 0
    rproduct = fourth[2] * pos[2]
    rshift = max(rproduct.bit_length() - 67, 0)
    rdisc = rproduct & ((1 << rshift) - 1) if rshift > 0 else 0
    rud = (rdisc << 1) >> rshift if rshift > 0 else 0
    low3 = square[2] & 7
    distance = abs(left[1] - right[1])
    active = 1 if (low3 and (ud or (distance == 7 and u5d))) else 0
    payload = low3 + 8 - distance if active else 0
    if active and distance == 10 and low3 == 6 and rud:
        lane_shift = (left[1] - 8) - right[1]
        lane = (right[2] >> lane_shift) if lane_shift >= 0 \
            else (right[2] << -lane_shift)
        lane_payload = lane & 0xFF
        difference = (lane_payload - payload) & 0xFF
        if difference >= 128:
            difference -= 256
        if difference == -2:
            payload = lane_payload
    if active and distance == 8 and low3 == 7 and ud >= 3:
        lane_shift = (left[1] - 8) - right[1]
        lane = (right[2] >> lane_shift) if lane_shift >= 0 \
            else (right[2] << -lane_shift)
        lane_payload = lane & 0xFF
        difference = (lane_payload - payload) & 0xFF
        if difference >= 128:
            difference -= 256
        if difference == 0:
            payload -= 1
    scale = min(left[1], right[1])
    if payload and left[1] - 8 < scale:
        scale = left[1] - 8
    # band rows: lsign=1, rsign=0 -> |acc| = A + P - B
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
    maskw = (1 << w) - 1
    disc = mag & maskw

    # discard-field run statistics
    tr1 = trailing_ones(disc)
    tr0 = trailing_ones(~disc & maskw)
    nz = w - bin(disc).count("1")

    # propagate/generate of S + ~B (the subtract)
    Wd = max(S.bit_length(), B.bit_length()) + 2
    maskW = (1 << Wd) - 1
    pmask = (~(S ^ B)) & maskW          # p_i for S + ~B
    gmask = S & (~B) & maskW            # g_i
    # exact borrow travel into retained field: highest j < w with g_j
    # and p_{j+1..w-1} all set
    travel = -1
    pm_run = 0                          # propagate run just below boundary
    j = w - 1
    while j >= 0 and (pmask >> j) & 1:
        pm_run += 1
        j -= 1
    if j >= 0 and (gmask >> j) & 1:
        travel = w - j                  # carry from j reaches bit w
    # propagate run upward from boundary (into retained field)
    pm_up = 0
    j = w
    while (pmask >> j) & 1:
        pm_up += 1
        j += 1
    return (sign, th, fire, fire_sc, w, min(tr1, 20), min(tr0, 20),
            min(nz, 12), min(pm_run, 24), travel if travel < 0
            else min(travel, 24), min(pm_up, 20), payload)


def main():
    # sincos labels for comb7 (for the second-threshold check)
    sc = {}
    rows7, seen = [], set()
    for lineS in open("ties_comb7.txt"):
        f = lineS.split()
        if f[0] in seen:
            continue
        seen.add(f[0])
        rows7.append(f)
    inputs = sorted(f[0] for f in rows7)
    order = {mm: i for i, mm in enumerate(inputs)}
    st = {md: open(f"comb7_sc_{md}_status.txt").read().splitlines()
          for md in ROUNDING_MODES}
    for f in rows7:
        R, ce, i = int(f[7], 16), int(f[8]), order[f[0]]
        hw, bad = [], False
        for md in ROUNDING_MODES:
            t = st[md][i].split()
            if t[0] != "OK":
                bad = True
                break
            hw.append(int(t[4], 16))
        if bad:
            sc[f[0]] = -1
            continue
        clean = [final_cosine_result(-R, ce, md) for md in ROUNDING_MODES]
        dn = [final_cosine_result(-(R - 1), ce, md) for md in ROUNDING_MODES]
        up = [final_cosine_result(-(R + 1), ce, md) for md in ROUNDING_MODES]
        sc[f[0]] = (0 if hw == clean else 1 if hw == dn
                    else 2 if hw == up else -1)
    print("sincos labels ready", flush=True)

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
            sl = sc.get(mhex, -2)       # -2 = comb8 (no sc capture)
            fire_sc = (int(sl == (1 if sign == "dn" else 2))
                       if sl >= 0 else -1)
            work.append((mhex, sign, abs(theta), fire, fire_sc))
        print(f"{name} loaded", flush=True)
    print(f"band rows: {len(work)}", flush=True)

    with Pool(8) as pool:
        out = pool.map(stats, work, chunksize=2000)
    out = [o for o in out if o is not None]
    print(f"terminal rebuilt for {len(out)} rows", flush=True)

    NAMES = ["w", "tr1", "tr0", "nz", "pm_run", "travel", "pm_up",
             "payload"]

    def xtab(tag, idx):
        t = defaultdict(lambda: [0, 0])
        for o in out:
            t[(o[0], o[1], o[idx])][o[2]] += 1
        flags = []
        print(f"\n  [{tag}] fire rate by (sign, theta, value):")
        for k in sorted(t, key=str):
            c0, c1 = t[k]
            n = c0 + c1
            if n < 300:
                continue
            r = c1 / n
            mark = ""
            if not 0.70 <= r <= 0.82:
                mark = "  <== STRUCTURE"
                flags.append((k, n, r))
            print(f"    {k}: n={n} rate={r:.4f}{mark}", flush=True)
        return flags

    allflags = []
    for i, nm in enumerate(NAMES):
        allflags += xtab(nm, 4 + i)
    print(f"\nTOTAL flags: {len(allflags)}")

    # sincos second threshold: among comb7 cos-fires, sc rate by stats
    print("\n=== sincos second threshold (comb7, cos-fire rows only) ===")
    for i, nm in enumerate(NAMES):
        t = defaultdict(lambda: [0, 0])
        for o in out:
            if o[2] == 1 and o[3] >= 0:
                t[(o[0], o[1], o[4 + i])][o[3]] += 1
        print(f"  [{nm}] P(sc-fire | cos-fire) by (sign, theta, value):")
        for k in sorted(t, key=str):
            c0, c1 = t[k]
            n = c0 + c1
            if n < 300:
                continue
            print(f"    {k}: n={n} rate={c1/n:.4f}", flush=True)


if __name__ == "__main__":
    main()
