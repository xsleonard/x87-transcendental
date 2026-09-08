#!/usr/bin/env python3
"""h666: rebuild comb3-7 theta=0 near-boundary rows WITH mhex + exact
rdisc (the h649 caches store only xd60, losing the low bits that the
truncated-3x comparator hypothesis needs).  comb8 theta0 == comb3
byte-identically (h657 bookkeeping) — skipped.  Output rows in the
h664 format: (mhex, theta, dist, s4, side, L, rdisc, sR, label, M,
sqlow) -> h666_<c>.pkl, near-boundary only (EPS 1e-3).
"""
import os
import pickle
import sys
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from h665_comparator import load3, label_row, internals_near


def main():
    for name in ("comb3", "comb4", "comb5", "comb6", "comb7"):
        cache = f"h666_{name}.pkl"
        if os.path.exists(cache):
            print(f"{cache} exists", flush=True)
            continue
        print(f"{name}: parsing ...", flush=True)
        parsed = load3(f"ties_{name}.txt", name)
        print(f"{name}: {len(parsed)} rows; labeling ...", flush=True)
        with Pool(os.cpu_count()) as pool:
            lab = pool.map(label_row, parsed, chunksize=2000)
        del parsed
        print(f"{name}: internals (near filter) ...", flush=True)
        with Pool(os.cpu_count()) as pool:
            rows = pool.map(internals_near, lab, chunksize=2000)
        rows = [r for r in rows if r is not None]
        pickle.dump(rows, open(cache, "wb"))
        print(f"{name}: {len(rows)} near-boundary rows cached", flush=True)


if __name__ == "__main__":
    main()
