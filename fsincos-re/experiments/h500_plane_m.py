#!/usr/bin/env python3
"""h500: per-stratum plane fit in (XT, XD, m) on the comb data.
The fine profiles show theta drifts SMOOTHLY with m; if the drift is
linear the gate is a plane: a*XT + b*XD + g*m >= c per stratum.
Perceptron with exact verification (h487e machinery) on the comb's
dist=9 strata (full transitions in-window) + pocket best-error
reporting."""
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h453_chain_variants import (C6_1, C6_2, C6_3, C6_4, C6_5, C6_6,
                                 build_chain, mul_round)
E2M = -66
SC = 60

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
    XT = (t4 << SC) >> s4
    XD = (rdisc << SC) >> sR
    return ((dist, low3, rud), XT / 2**SC, XD / 2**SC, m / 2**64,
            int(fire))

def load_comb():
    rows = []
    seen = set()
    for line in open("ties_comb.txt"):
        f = line.split()
        if f[0] in seen:
            continue
        seen.add(f[0])
        rows.append(f)
    inputs = sorted(f[0] for f in rows)
    order = {m: i for i, m in enumerate(inputs)}
    st = {md: open(f"comb_{md}_status.txt").read().splitlines()
          for md in ROUNDING_MODES}
    out = []
    for f in rows:
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
            out.append((f[0], False))
        elif hw == fired:
            out.append((f[0], True))
    return out

def fit_plane(args):
    cell, pts = args
    n = len(pts)
    w = [0.0, 0.0, 0.0, 0.0]
    best_err = n
    best_w = None
    for ep in range(3000):
        errs = 0
        for x, y, z, o in pts:
            s = w[0]*x + w[1]*y + w[2]*z + w[3]
            pred = 1 if s > 0 else 0
            if pred != o:
                errs += 1
                sgn = 1.0 if o else -1.0
                w[0] += sgn * x * 0.5
                w[1] += sgn * y * 0.5
                w[2] += sgn * z * 0.5
                w[3] += sgn * 0.5
        if errs < best_err:
            best_err = errs
            best_w = list(w)
        if errs == 0:
            break
    # exact re-verify pocket
    errs = sum(1 for x, y, z, o in pts
               if (1 if best_w[0]*x + best_w[1]*y + best_w[2]*z
                   + best_w[3] > 0 else 0) != o)
    return cell, n, errs, best_w

def main():
    rows = load_comb()
    print(f"comb labeled: {len(rows)}")
    with Pool(8) as pool:
        data = pool.map(build, rows, chunksize=1000)
    strata = defaultdict(list)
    for cell, XT, XD, mf, fire in data:
        strata[cell].append((XT, XD, mf, fire))
    jobs = []
    for cell in sorted(strata):
        pts = strata[cell]
        n1 = sum(p[3] for p in pts)
        if len(pts) >= 3000 and 0 < n1 < len(pts):
            jobs.append((cell, pts))
    with Pool(8) as pool:
        out = pool.map(fit_plane, jobs, chunksize=1)
    print(f"{'stratum':12s} {'n':>7s} {'plane-errs':>10s} "
          f"{'rate':>7s}   a(XT) b(XD) g(m) c")
    for cell, n, errs, w in out:
        nz = max(abs(v) for v in w[:3]) or 1
        print(f"{str(cell):12s} {n:7d} {errs:10d} {errs/n:7.4f}   "
              f"{w[0]/nz:+.3f} {w[1]/nz:+.3f} {w[2]/nz:+.3f} "
              f"{w[3]/nz:+.3f}")

if __name__ == "__main__":
    main()
