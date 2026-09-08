#!/usr/bin/env python3
"""h649: exact XD-breakpoint census — the comparator unmasked.

h648 hand-analysis (s4=67 hi): in binade units U = T/2^s4 the base is
floor(L/4) - 1 + (L%2)/2, dist-invariant, and the XD step position
rotates/doubles with dist — the signature of a FIXED absolute comparator
constant seen through an alignment-dependent normalization.

This script drops the thirds pre-binning: per cell (dist, s4, side, low3)
it recovers u(XD) as an exact step function — per-XD-bin lattice pins,
then exact rational bracketing of every jump (xd60 = (rdisc<<60)>>sR).
Prints jump positions as multiples of 1/3 (and finer), plus each cell's
sR range for the absolute-frame doubling test.

Caches (theta=0 only, exact xd60): h649_<corpus>.pkl
"""
import os, pickle, sys
from collections import defaultdict
from multiprocessing import Pool

sys.path.insert(0, "/Users/steve/llm/x87-transcendental/fsincos-re/experiments")
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h453_chain_variants import (C6_1, C6_2, C6_3, C6_4, C6_5, C6_6,
                                 build_chain, mul_round)

E2M = -66
PIV = 0.70710678118654752
UNIT = 2**66

CORPORA = [
    ("comb4", "ties_comb4.txt", False),
    ("comb3", "ties_comb3.txt", False),
    ("comb5", "ties_comb5.txt", False),
    ("comb6", "ties_comb6.txt", False),
    ("comb7", "ties_comb7.txt", True),
    ("comb8", "ties_comb8.txt", True),
]


def load(ties, prefix, with_theta):
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
        if with_theta and int(f[9]) != 0:
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
        fired = [final_cosine_result(-(R - 1), ce, md) for md in ROUNDING_MODES]
        if hw == clean:
            out.append((f[0], 0))
        elif hw == fired:
            out.append((f[0], 1))
    return out


def internals(args):
    mhex, fire = args
    m = int(mhex, 16)
    mag = (0, E2M, m)
    square = mul_round(mag, mag, 67, "chop")
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
    M = (sq & 7) * (sq - (1 << 66)) - t4
    rprod = fourth[2] * pos[2]
    sR = rprod.bit_length() - 67
    rdisc = rprod & ((1 << sR) - 1)
    xd60 = (rdisc << 60) >> sR
    mf = m / 2**64
    side = 0 if mf < PIV else 1
    # per-row lattice constraint: fire -> u >= floor(M/U)+1; clean -> u <= floor(M/U)
    q = M // UNIT
    req = q + 1 if fire else q
    return (dist, s4, side, sq & 7, xd60, sR, fire, req)


def get_corpus(name, ties, wt):
    cache = f"h649_{name}.pkl"
    if os.path.exists(cache):
        return pickle.load(open(cache, "rb"))
    lab = load(ties, name, wt)
    print(f"{name}: {len(lab)} theta-0 labeled; internals ...", flush=True)
    with Pool(8) as pool:
        rows = pool.map(internals, lab, chunksize=1000)
    pickle.dump(rows, open(cache, "wb"))
    return rows


def bin_pin(rows):
    """rows: [(xd60, fire, req)] -> (ge, le) lattice interval or None"""
    ge = None; le = None
    for xd, fire, req in rows:
        if fire:
            ge = req if ge is None else max(ge, req)
        else:
            le = req if le is None else min(le, req)
    return ge, le


def ival_str(ge, le):
    if ge is None and le is None:
        return "."
    if ge is None:
        return f"<={le}"
    if le is None:
        return f">={ge}"
    if ge == le:
        return f"{ge}"
    if ge < le:
        return f"{ge}..{le}"
    return f"X({ge},{le})"


def main():
    cells = defaultdict(list)
    for name, ties, wt in CORPORA:
        rows = get_corpus(name, ties, wt)
        print(f"{name}: {len(rows)} rows", flush=True)
        for (dist, s4, side, L, xd60, sR, fire, req) in rows:
            cells[(dist, s4, side, L)].append((xd60, sR, fire, req))

    NB = 24
    print("\nper-cell u(XD) profiles; bins of 1/24; sR range shown")
    for key in sorted(cells):
        rows = cells[key]
        if len(rows) < 300:
            continue
        d, s4, side, L = key
        sRs = sorted({r[1] for r in rows})
        bins = defaultdict(list)
        for xd, sR, fire, req in rows:
            bins[min(NB - 1, (xd * NB) >> 60)].append((xd, fire, req))
        prof = []
        for i in range(NB):
            ge, le = bin_pin(bins.get(i, []))
            prof.append((ge, le))
        # compress: contiguous runs with same pinned value
        s = " ".join(ival_str(*prof[i]) for i in range(NB))
        print(f"\ncell d={d} s4={s4} side={'hi' if side else 'lo'} L={L} "
              f"n={len(rows)} sR={sRs}")
        print(f"  bins: {s}")
        # exact jump bracketing: find bin boundaries where pinned value changes
        pinned = [(i, prof[i][0]) for i in range(NB)
                  if prof[i][0] is not None and prof[i][0] == prof[i][1]]
        for j in range(len(pinned) - 1):
            i1, u1 = pinned[j]
            i2, u2 = pinned[j + 1]
            if u1 == u2:
                continue
            # rows between bin i1 start and i2 end; classify by consistency
            seg = [r for i in range(i1, i2 + 1) for r in bins.get(i, [])]
            # a row is right-regime-only if it violates u1 (and vice versa)
            lmax = None; rmin = None
            for xd, fire, req in seg:
                viol1 = (fire and req > u1) or ((not fire) and req < u1)
                viol2 = (fire and req > u2) or ((not fire) and req < u2)
                if viol1 and not viol2:
                    rmin = xd if rmin is None else min(rmin, xd)
                if viol2 and not viol1:
                    lmax = xd if lmax is None else max(lmax, xd)
            if lmax is not None and rmin is not None:
                print(f"  JUMP u:{u1}->{u2} in 3*XD ({3*lmax/2**60:.6f}, "
                      f"{3*rmin/2**60:.6f})")
            else:
                print(f"  JUMP u:{u1}->{u2} between bins {i1}..{i2} "
                      f"(bracket incomplete: lmax={lmax} rmin={rmin})")


if __name__ == "__main__":
    main()
