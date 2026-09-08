#!/usr/bin/env python3
"""h503: band decomposition — resolvable vs irreducible width.

Per mixed dist=9 stratum: fit the linear boundary m*(XT) from
crossings; residual r = m - m*(XT).  Baseline band width W0 = the
r-interval between P(fire)=0.9 and 0.1.  Then condition on candidate
variables (deeper t4 bits, deeper rdisc bits, rf low byte, sq low
byte, XD fine bits): per bucket re-center r by the bucket's own
50-percent point and measure the pooled conditional width Wc.
Wc << W0 -> variable resolves band structure; the floor after the
best conditioning estimates the irreducible (h488-state) component.
"""
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h453_chain_variants import (C6_1, C6_2, C6_3, C6_4, C6_5, C6_6,
                                 build_chain, mul_round)
from h500_plane_m import load_comb
E2M = -66
TARGETS = [(9, 4, 1), (9, 5, 0), (9, 5, 1), (9, 6, 1), (9, 7, 0)]

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
    f4_full = square[2] * square[2]
    s4 = f4_full.bit_length() - 67
    t4 = f4_full & ((1 << s4) - 1)
    rprod = fourth[2] * positive[2]
    sR = rprod.bit_length() - 67
    rdisc = rprod & ((1 << sR) - 1)
    rud = rdisc >> (sR - 1)
    XT = ((t4 << 60) >> s4) / 2**60
    XD = ((rdisc << 60) >> sR) / 2**60
    feats = {
        "t4_b4_9": int(XT * 2**10) & 0x3F,
        "rd_b4_9": int(XD * 2**10) & 0x3F,
        "rf_lo8": positive[2] & 0xFF,
        "sq_lo8": square[2] & 0xFF,
        "XD_fine": int(XD * 48) % 8,
    }
    return ((dist, low3, rud), XT, XD, m / 2**64, feats, int(fire))

def width(vals):
    """vals: (r, fire) -> 10-90 width via binned rates."""
    vals = sorted(vals)
    B = max(10, len(vals) // 200)
    prof = []
    for b in range(B):
        seg = vals[b*len(vals)//B:(b+1)*len(vals)//B]
        if seg:
            prof.append((seg[len(seg)//2][0],
                         sum(o for _, o in seg)/len(seg)))
    def cross(level):
        for i in range(len(prof)-1):
            a, b2 = prof[i], prof[i+1]
            if (a[1]-level)*(b2[1]-level) <= 0 and a[1] != b2[1]:
                t = (a[1]-level)/(a[1]-b2[1])
                return a[0] + t*(b2[0]-a[0])
        return None
    c10, c90 = cross(0.9), cross(0.1)
    c50 = cross(0.5)
    if c10 is None or c90 is None:
        return None, c50
    return abs(c90 - c10), c50

def main():
    rows = load_comb()
    with Pool(8) as pool:
        data = pool.map(build, rows, chunksize=1000)
    strata = defaultdict(list)
    for cell, XT, XD, mf, feats, fire in data:
        if cell in TARGETS:
            strata[cell].append((XT, XD, mf, feats, fire))
    for cell in TARGETS:
        pts = strata[cell]
        if len(pts) < 5000:
            continue
        # boundary fit: crossings per XT bin
        bins = defaultdict(list)
        for XT, XD, mf, feats, fire in pts:
            bins[int(XT*12)].append((mf, fire))
        fitpts = []
        for b, sub in bins.items():
            if len(sub) >= 500:
                w, c50 = width(sub)
                if c50 is not None:
                    fitpts.append((b/12 + 1/24, c50))
        if len(fitpts) < 4:
            print(f"{cell}: cannot fit boundary")
            continue
        n = len(fitpts)
        sx = sum(x for x, _ in fitpts)
        sy = sum(y for _, y in fitpts)
        sxx = sum(x*x for x, _ in fitpts)
        sxy = sum(x*y for x, y in fitpts)
        sl = (n*sxy - sx*sy)/(n*sxx - sx*sx)
        ic = (sy - sl*sx)/n
        rvals = [(mf - (ic + sl*XT), feats, fire)
                 for XT, XD, mf, feats, fire in pts]
        W0, _ = width([(r, o) for r, _, o in rvals])
        print(f"\n{cell}: boundary m* = {ic:.4f} + {sl:.4f}*XT; "
              f"baseline band W0 = {W0:.4f}" if W0 else
              f"\n{cell}: W0 n/a")
        if W0 is None:
            continue
        for name in ("t4_b4_9", "rd_b4_9", "rf_lo8", "sq_lo8",
                     "XD_fine"):
            buckets = defaultdict(list)
            for r, feats, o in rvals:
                buckets[feats[name]].append((r, o))
            pooled = []
            for bk, sub in buckets.items():
                if len(sub) < 400:
                    continue
                w, c50 = width(sub)
                if c50 is None:
                    continue
                pooled.extend((r - c50, o) for r, o in sub)
            if len(pooled) > 3000:
                Wc, _ = width(pooled)
                if Wc:
                    print(f"    cond {name:8s}: Wc = {Wc:.4f} "
                          f"({100*(1-Wc/W0):.0f} percent narrower)")

if __name__ == "__main__":
    main()
