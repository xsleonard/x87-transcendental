#!/usr/bin/env python3
"""h496: THE 2/3 COMPARE.  fire <=> unrounded even-chain value
(C6_2 + p4, exact) < 2/3 of its binade.  Also scores the rounded-rf
variant and +-1ulp neighborhood variants.  Exact integer compares,
all 205k merged labeled rows."""
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h453_chain_variants import (C6_1, C6_2, C6_3, C6_4, C6_5, C6_6,
                                 build_chain, mul_round)
from h454_stale_carry import mul_state, add_state
E2M = -66

def build(args):
    mhex, fire = args
    m = int(mhex, 16)
    mag = (0, E2M, m)
    square = mul_round(mag, mag, 67, "chop")
    fourth = mul_round(square, square, 67, "chop")
    p3, _ = mul_state(fourth, C6_6, 67, "chop")
    a3, _ = add_state(C6_4, p3, 64, "rn")
    p4, _ = mul_state(fourth, a3, 67, "chop")
    pos, _ = add_state(C6_2, p4, 64, "rn")
    # exact chain value V = C6_2 - |p4| (signs: C6_2 +, p4 sign?)
    # align exactly:
    s = min(C6_2[1], p4[1])
    v = (-1 if C6_2[0] else 1) * (C6_2[2] << (C6_2[1] - s)) \
        + (-1 if p4[0] else 1) * (p4[2] << (p4[1] - s))
    assert v > 0
    B = v.bit_length()
    exact_lt = 3 * v < (1 << (B + 1))
    rf = pos[2]
    rf_lt = 3 * rf < (1 << 65)
    return (int(fire), int(exact_lt), int(rf_lt))

def main():
    rows = []
    with open("h491_mapdata.tsv") as fh:
        fh.readline()
        for line in fh:
            f = line.rstrip("\n").split("\t")
            if f[7] in ("CLEAN", "FIRE"):
                rows.append((f[0], f[7] == "FIRE"))
    fresh = []
    seen = set()
    for line in open("ties_fresh.txt"):
        f = line.split()
        if f[0] not in seen:
            seen.add(f[0])
            fresh.append(f)
    inputs = sorted(f[0] for f in fresh)
    order = {mm: i for i, mm in enumerate(inputs)}
    st = {md: open(f"fcos2_{md}_status.txt").read().splitlines()
          for md in ROUNDING_MODES}
    for f in fresh:
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
            rows.append((f[0], False))
        elif hw == fired:
            rows.append((f[0], True))
    dedup = {}
    for mhex, fire in rows:
        dedup[mhex] = fire
    rows = sorted(dedup.items())
    print(f"rows: {len(rows)}")
    with Pool(8) as pool:
        out = pool.map(build, rows, chunksize=500)
    n = len(out)
    for name, idx in (("exact-chain < 2/3", 1),
                      ("rounded rf < 2/3", 2)):
        exc = sum(1 for f, e, r in out if (e if idx == 1 else r) != f)
        fp = sum(1 for f, e, r in out
                 if (e if idx == 1 else r) == 1 and f == 0)
        print(f"  {name:20s} exceptions={exc} ({1-exc/n:.6f})  "
              f"fp={fp} fn={exc-fp}")

if __name__ == "__main__":
    main()
