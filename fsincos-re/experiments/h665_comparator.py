#!/usr/bin/env python3
"""h665: bracket the hardware thirds-comparator constant exactly.

Task 1 of SESSION-GUIDE-fsin-fcos-closure.md.  The u-floor taps
    b1 = [3*rdisc >= 2^sR],   b2 = [3*rdisc >= 2^(sR+1)]
model hardware with EXACT thirds; the true comparator sits ~2^-17
ABOVE exact (h645/h649 boundary-row brackets).  This script:

1. gathers every labeled row within EPS of a thirds boundary across
   comb3..comb12, theta=0 AND theta!=0;
2. per row, determines which tap value the hardware must have used
   (vote): evaluate the shipped closed-form prediction under b=0 and
   b=1; if the predictions differ, the observed label names the bit;
3. brackets the threshold K (in rdisc units) per (boundary j,
   quadrant, sR): K in [max(vote0 rdisc)+1, min(vote1 rdisc)];
4. sweeps candidate closed forms against every vote:
     A(w): K = ceil(j*2^w/3) << (sR-w)    (ceil constant, width w)
     E(t): K = ceil(j*2^sR/3) + 2^(sR-t)  (exact + absolute offset)
   plus the exact-thirds baseline; also per-quadrant sweeps to
   detect a second-order input (bracket-to-bracket variation).

Sources: h649_<c>.pkl (comb3-8 theta0; xd60 = top-60 bits of
rdisc/2^sR — exact for candidate widths w<=60), h657m_<c>.pkl
(comb7/8 theta!=0, exact rdisc + mhex), h664_comb11/12.pkl (full),
fresh comb9 pass over all thetas (near rows -> h665_comb9.pkl).
Votes cached to h665_votes.pkl.
"""
import os
import pickle
import sys
from collections import defaultdict
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h453_chain_variants import (C6_1, C6_2, C6_3, C6_4, C6_5, C6_6,
                                 build_chain, mul_round)

E2M = -66
PIV = 0.70710678118654752
UNIT = 2 ** 66
EPS = 1e-3
T60 = 1 << 60

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


def u_of(quad, dist, L, b1, b2):
    a, G1, G2, p, Q, K, par, W = QUAD[quad]
    lp = L % 2
    return K * ((a * L + G1 * b1 + G2 * b2 + p * lp + W(dist)) // Q) \
        + par * lp


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


def sched_frame(mhex):
    """(S, B, w, phw) of the terminal subtract, or None (h664c port)."""
    m = int(mhex, 16)
    mag0 = (0, E2M, m)
    square = mul_round(mag0, mag0, 67, "chop")
    fourth = mul_round(square, square, 67, "chop")
    neg = build_chain(fourth, C6_5, C6_3, C6_1, 67, 64, "rn",
                      False, False, False)
    pos = build_chain(fourth, C6_6, C6_4, C6_2, 67, 64, "rn",
                      False, False, False)
    left = mul_round(square, neg, 67, "chop")
    right = mul_round(fourth, pos, 67, "chop")
    rprod = fourth[2] * pos[2]
    sR = rprod.bit_length() - 67
    rdisc = rprod & ((1 << sR) - 1)
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
    return (S, B, w, (scale + w) % 8)


def pred_theta(sign, th, quad, dist, L, b1, b2, M, frame):
    """Full r59/r61 prediction (region + block-start law)."""
    if not in_region(sign, th, quad, dist, L, b1, b2, M):
        return 0
    if frame is None:
        return None
    S, B, w, phw = frame
    mag = S - B
    pmask_all = ~(S ^ B)
    pm_up = 0
    j = w
    while (pmask_all >> j) & 1:
        pm_up += 1
        j += 1
    if (pm_up + phw) % 8 == 7 and pm_up in (7, 8):
        bs = w + 8 + ((8 - phw) % 8)
        b8 = (mag >> (w + 8)) & 1
        bbs = (mag >> bs) & 1
        return bbs if sign == "up" else (b8 & bbs)
    return 1


def near_j(v3, den):
    """v3 = 3*rdisc-like numerator, den = 2^sR-like; -> [(j, margin)]."""
    out = []
    for j in (1, 2):
        bound = j * den
        if abs(v3 - bound) <= int(bound * EPS):
            out.append(j)
    return out


# ---------------------------------------------------------------- ingest

def load3(ties, prefix):
    rows, seen = [], set()
    for lineS in open(ties):
        f = lineS.split()
        if len(f) < 9 or f[0] in seen:
            continue
        seen.add(f[0])
        rows.append(f)
    inputs = sorted(f[0] for f in rows)
    order = {mm: i for i, mm in enumerate(inputs)}
    st = {md: open(f"{prefix}_{md}_status.txt").read().splitlines()
          for md in ROUNDING_MODES}
    out = []
    for f in rows:
        theta = int(f[9]) if len(f) > 9 else 0
        R, ce, i = int(f[7], 16), int(f[8]), order[f[0]]
        hw, bad = [], False
        for md in ROUNDING_MODES:
            t = st[md][i].split()
            if t[0] != "OK":
                bad = True
                break
            hw.append(int(t[2], 16))
        if not bad:
            out.append((f[0], theta, R, ce, tuple(hw)))
    return out


def label_row(args):
    mhex, theta, R, ce, hw = args
    hw = list(hw)
    if hw == [final_cosine_result(-R, ce, md) for md in ROUNDING_MODES]:
        return (mhex, 0, theta)
    if hw == [final_cosine_result(-(R - 1), ce, md)
              for md in ROUNDING_MODES]:
        return (mhex, 1, theta)
    if hw == [final_cosine_result(-(R + 1), ce, md)
              for md in ROUNDING_MODES]:
        return (mhex, 2, theta)
    return (mhex, -1, theta)


def internals_near(args):
    """h664-format row, but only if near a thirds boundary."""
    mhex, label, theta = args
    m = int(mhex, 16)
    mag0 = (0, E2M, m)
    square = mul_round(mag0, mag0, 67, "chop")
    fourth = mul_round(square, square, 67, "chop")
    neg = build_chain(fourth, C6_5, C6_3, C6_1, 67, 64, "rn",
                      False, False, False)
    pos = build_chain(fourth, C6_6, C6_4, C6_2, 67, 64, "rn",
                      False, False, False)
    left = mul_round(square, neg, 67, "chop")
    right = mul_round(fourth, pos, 67, "chop")
    rprod = fourth[2] * pos[2]
    sR = rprod.bit_length() - 67
    rdisc = rprod & ((1 << sR) - 1)
    if not near_j(3 * rdisc, 1 << sR):
        return None
    dist = abs(left[1] - right[1])
    sq = square[2]
    f4 = sq * sq
    s4 = f4.bit_length() - 67
    t4 = f4 & ((1 << s4) - 1)
    sqlow = sq - (1 << 66)
    M = (sq & 7) * sqlow - t4
    side = 0 if m / 2 ** 64 < PIV else 1
    return (mhex, theta, dist, s4, side, sq & 7, rdisc, sR, label,
            M, sqlow)


def build_comb9():
    cache = "h665_comb9.pkl"
    if os.path.exists(cache):
        return pickle.load(open(cache, "rb"))
    print("comb9: parsing ...", flush=True)
    parsed = load3("ties_comb9.txt", "comb9")
    print(f"comb9: {len(parsed)} rows; labeling ...", flush=True)
    with Pool(os.cpu_count()) as pool:
        lab = pool.map(label_row, parsed, chunksize=2000)
    del parsed
    print("comb9: internals (near-boundary filter) ...", flush=True)
    with Pool(os.cpu_count()) as pool:
        rows = pool.map(internals_near, lab, chunksize=2000)
    rows = [r for r in rows if r is not None]
    pickle.dump(rows, open(cache, "wb"))
    print(f"comb9: {len(rows)} near-boundary rows cached", flush=True)
    return rows


# ----------------------------------------------------------------- votes
# vote record: (corpus, j, quad, sR, dist, L, theta, kind, num, vote,
#               mhex) — kind "rd": num = exact rdisc; kind "x6": num =
#               xd60 (= top-60 bits of rdisc/2^sR, exact for w<=60).

def vote_theta0(corpus, quad, dist, L, sR, fire, req, j, kind, num,
                mhex, votes, anom):
    bits = {1: ((0, 0), (1, 0)), 2: ((1, 0), (1, 1))}[j]
    u0 = u_of(quad, dist, L, *bits[0])
    u1 = u_of(quad, dist, L, *bits[1])
    ok0 = (u0 >= req) if fire else (u0 <= req)
    ok1 = (u1 >= req) if fire else (u1 <= req)
    if ok0 == ok1:
        if not ok0:
            anom.append((corpus, j, quad, sR, dist, L, fire, req,
                         kind, num, mhex))
        return
    if ok0 and not ok1:
        v = 0
    else:
        v = 1
    votes.append((corpus, j, quad, sR, dist, L, 0, kind, num, v, mhex))


def vote_thetaN(corpus, row, j, votes, anom):
    mhex, theta, dist, s4, side, L, rdisc, sR, label, M, _ = row
    quad = (s4, side)
    sign = "dn" if theta > 0 else "up"
    fire = int(label == (1 if sign == "dn" else 2))
    bits = {1: ((0, 0), (1, 0)), 2: ((1, 0), (1, 1))}[j]
    # region test first (cheap); frame only if predictions can differ
    r0 = in_region(sign, abs(theta), quad, dist, L, *bits[0], M)
    r1 = in_region(sign, abs(theta), quad, dist, L, *bits[1], M)
    if r0 == r1 and not r0:
        return
    frame = sched_frame(mhex)
    p0 = pred_theta(sign, abs(theta), quad, dist, L, *bits[0], M, frame)
    p1 = pred_theta(sign, abs(theta), quad, dist, L, *bits[1], M, frame)
    if p0 is None or p1 is None or p0 == p1:
        return
    v = 0 if p0 == fire else 1
    votes.append((corpus, j, quad, sR, dist, L, theta, "rd", rdisc, v,
                  mhex))


def collect_votes():
    cache = "h665_votes.pkl"
    if os.path.exists(cache):
        return pickle.load(open(cache, "rb"))
    votes, anom = [], []

    # comb3-8 theta=0 via h649 caches (xd60 frame)
    for nm in ("comb3", "comb4", "comb5", "comb6", "comb7", "comb8"):
        n = 0
        for (d, s4, side, L, xd60, sR, fire, req) in pickle.load(
                open(f"h649_{nm}.pkl", "rb")):
            for j in near_j(3 * xd60, T60):
                vote_theta0(nm, (s4, side), d, L, sR, fire, req, j,
                            "x6", xd60, None, votes, anom)
                n += 1
        print(f"{nm}: {n} near-boundary theta0 rows", flush=True)

    # comb7/8 theta!=0 via h657m caches (exact rdisc + mhex)
    for nm in ("comb7", "comb8"):
        n = 0
        for row in pickle.load(open(f"h657m_{nm}.pkl", "rb")):
            rdisc, sR = row[6], row[7]
            for j in near_j(3 * rdisc, 1 << sR):
                vote_thetaN(nm, row, j, votes, anom)
                n += 1
        print(f"{nm}: {n} near-boundary theta rows", flush=True)

    # comb11/12 full via h664 caches; comb9 fresh
    named = [("comb11", pickle.load(open("h664_comb11.pkl", "rb"))),
             ("comb12", pickle.load(open("h664_comb12.pkl", "rb"))),
             ("comb9", build_comb9())]
    for nm, rows in named:
        n = 0
        for row in rows:
            mhex, theta, d, s4, side, L, rdisc, sR, label, M, _ = row
            if label == -1:
                continue
            js = near_j(3 * rdisc, 1 << sR)
            if not js:
                continue
            for j in js:
                n += 1
                if theta == 0:
                    if label == 2:
                        continue
                    req = M // UNIT + (1 if label == 1 else 0)
                    vote_theta0(nm, (s4, side), d, L, sR, label == 1,
                                req, j, "rd", rdisc, mhex, votes, anom)
                else:
                    vote_thetaN(nm, row, j, votes, anom)
        print(f"{nm}: {n} near-boundary rows", flush=True)

    pickle.dump((votes, anom), open(cache, "wb"))
    return votes, anom


# -------------------------------------------------------------- analysis

def ratio_off(j, sR, kind, num):
    """(3*rdisc/(j*2^sR) - 1) in 1e-6 units, lower bound for x6."""
    if kind == "rd":
        return (3 * num / (j * 2 ** sR) - 1) * 1e6
    return (3 * num / (j * T60) - 1) * 1e6


def cand_pred(K, sR, kind, num):
    """[rdisc >= K] under the row's representation; -1 = ambiguous."""
    if kind == "rd":
        return 1 if num >= K else 0
    if sR <= 60:
        return 1 if (num >> (60 - sR)) >= K else 0
    g = 1 << (sR - 60)
    c_hi = -(-K // g)
    if num >= c_hi:
        return 1
    if num < K // g:
        return 0
    return -1


def x6_bounds(sR, num):
    """exact-rdisc [lo, hi] interval represented by an xd60 value."""
    if sR <= 60:
        rd = num >> (60 - sR)
        return rd, rd
    g = 1 << (sR - 60)
    return num * g, (num + 1) * g - 1


def sweep(votes, keyfn, Kfn, tag):
    """Count violations of candidate Kfn(j, sR) over votes in groups."""
    viol = defaultdict(int)
    amb = defaultdict(int)
    tot = defaultdict(int)
    bad = defaultdict(list)
    for (corpus, j, quad, sR, d, L, th, kind, num, v, mhex) in votes:
        k = keyfn(j, quad, sR)
        K = Kfn(j, sR)
        p = cand_pred(K, sR, kind, num)
        tot[k] += 1
        if p == -1:
            amb[k] += 1
        elif p != v:
            viol[k] += 1
            bad[k].append((corpus, j, quad, sR, d, L, th, kind, num,
                           v, mhex))
    return viol, amb, tot, bad


def main():
    votes, anom = collect_votes()
    print(f"\ntotal votes: {len(votes)}  anomalies: {len(anom)}")

    # brackets per (j, quad, sR)
    groups = defaultdict(lambda: [None, None, 0, 0, None, None])
    for (corpus, j, quad, sR, d, L, th, kind, num, v, mhex) in votes:
        if kind == "rd":
            rd_lo = rd_hi = num
        else:
            rd_lo, rd_hi = x6_bounds(sR, num)
        g = groups[(j, quad, sR)]
        if v == 0:
            g[2] += 1
            if g[0] is None or rd_hi > g[0]:
                g[0] = rd_hi          # K > this (conservative upper rep)
                g[4] = (corpus, kind, num, mhex, th)
        else:
            g[3] += 1
            if g[1] is None or rd_lo < g[1]:
                g[1] = rd_lo          # K <= this
                g[5] = (corpus, kind, num, mhex, th)
    print("\nbrackets per (j, quad, sR): K in (lo, hi]; offsets in "
          "1e-6 of j*2^sR/3")
    for key in sorted(groups, key=str):
        j, quad, sR = key
        lo, hi, n0, n1, w0, w1 = groups[key]
        base = j * 2 ** sR / 3
        los = f"{(lo / base - 1) * 1e6:+9.3f}" if lo is not None else \
            "     none"
        his = f"{(hi / base - 1) * 1e6:+9.3f}" if hi is not None else \
            "     none"
        flag = ""
        if lo is not None and hi is not None and lo > hi:
            flag = "  << CONTRADICTION"
        print(f"  j={j} quad={quad} sR={sR}: n0={n0:4d} n1={n1:4d} "
              f"lo{los} hi{his}{flag}")
        if flag:
            print(f"    w0={w0}\n    w1={w1}")

    # candidate sweeps (global)
    print("\ncandidate sweep (global):")
    results = []

    def Kexact(j, sR):
        return -(-(j << sR) // 3)

    viol, amb, tot, bad = sweep(votes, lambda j, q, s: 0, Kexact, "ex")
    results.append(("exact-thirds", sum(viol.values()),
                    sum(amb.values()), sum(tot.values())))
    for w in range(8, 46):
        def KA(j, sR, w=w):
            return (-(-(j << w) // 3)) << (sR - w)
        viol, amb, tot, bad = sweep(votes, lambda j, q, s: 0, KA, "A")
        results.append((f"A(w={w}) ceil@{w}bits", sum(viol.values()),
                        sum(amb.values()), sum(tot.values())))
    for t in range(8, 46):
        def KE(j, sR, t=t):
            return -(-(j << sR) // 3) + (1 << (sR - t))
        viol, amb, tot, bad = sweep(votes, lambda j, q, s: 0, KE, "E")
        results.append((f"E(t={t}) exact+2^-{t}", sum(viol.values()),
                        sum(amb.values()), sum(tot.values())))
    for name, v, a, t in results:
        mark = "  <<< SURVIVES" if v == 0 else ""
        print(f"  {name:24s} viol {v:5d}  amb {a:4d}  / {t}{mark}")

    # per-quadrant best-w map (second-order-input probe)
    print("\nper-(j,quad) surviving A(w) ranges:")
    perq = defaultdict(list)
    for v in votes:
        perq[(v[1], v[2])].append(v)
    for key in sorted(perq, key=str):
        ok_w = []
        for w in range(8, 46):
            def KA(j, sR, w=w):
                return (-(-(j << w) // 3)) << (sR - w)
            viol, amb, tot, bad = sweep(perq[key], lambda j, q, s: 0,
                                        KA, "A")
            if sum(viol.values()) == 0:
                ok_w.append(w)
        print(f"  j={key[0]} quad={key[1]}: n={len(perq[key])} "
              f"A(w) survivors {ok_w}")

    if anom:
        print("\nanomalous rows (no tap value satisfies the row):")
        for a in anom[:20]:
            print(f"  {a}")


if __name__ == "__main__":
    main()
