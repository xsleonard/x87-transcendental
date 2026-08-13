#!/usr/bin/env python3
"""h516b: tally the original-corpus tie rows by input-exponent context
(le2, dist) and replica-match status — sizes the per-window law-table
work a full-exactness port would require."""
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import (ROUNDING_MODES, load_labeled_rows,
                                  final_cosine_result)
from h453_chain_variants import recover_m
from h500_plane_m import build


def score_row(job):
    fields, hw_sigs = job
    if fields.get("active") != "1" or fields["lsign"] != "1" \
            or fields["rsign"] != "0":
        return None
    dist, low3 = int(fields["dist"]), int(fields["low3"])
    le2, re2 = int(fields["le2"]), int(fields["re2"])
    ls, rs = int(fields["ls"], 16), int(fields["rs"], 16)
    prepay = low3 + 8 - dist
    scale = min(le2, re2, le2 - 8)
    A = ls << (le2 - scale)
    B = rs << (re2 - scale)
    Pv = prepay << (le2 - 8 - scale)
    M = A - B + Pv
    if M <= 0:
        return None
    k = max(M.bit_length() - 67, 0)
    if k < 3 or (M & ((1 << k) - 1)):
        return None
    R = M >> k
    hw = tuple(hw_sigs[m] for m in ROUNDING_MODES)

    def ok_for(delta):
        corr, corr_e = -(R + delta), scale + k
        return all(final_cosine_result(corr, corr_e, m) == h
                   for m, h in zip(ROUNDING_MODES, hw))

    ideal_ok, fire_ok = ok_for(0), ok_for(-1)
    status = ("blind" if ideal_ok and fire_ok else
              "clean" if ideal_ok else
              "fire" if fire_ok else "other")
    m = recover_m(int(fields["mul"], 16))
    if m is None:
        return (le2, dist, low3, status, "no_m", None)
    while m.bit_length() > 64:
        m >>= 1
    cell, XT, XD, mf, _ = build((f"{m:016x}", 0))
    match = "match" if (cell[0] == dist and cell[1] == low3) \
        else "MISMATCH"
    return (le2, dist, low3, status, match, round(mf, 4))


def main():
    rows = load_labeled_rows()
    with Pool(8) as pool:
        out = [o for o in pool.map(score_row, rows, chunksize=500)
               if o]
    tab = defaultdict(int)
    mfr = defaultdict(list)
    for le2, dist, low3, status, match, mf in out:
        tab[(le2, dist, match)] += 1
        if status == "fire":
            tab[(le2, dist, match, "fire")] += 1
        if mf is not None:
            mfr[(le2, dist, match)].append(mf)
    print("ties by (le2, dist, replica-match) [fires]:")
    for key in sorted(k for k in tab if len(k) == 3):
        le2, dist, match = key
        f = tab.get((le2, dist, match, "fire"), 0)
        mfs = sorted(mfr.get(key, []))
        rng = (f"mf [{mfs[0]:.3f},{mfs[-1]:.3f}]" if mfs else "")
        print(f"  le2={le2:4d} dist={dist:2d} {match:8s} "
              f"n={tab[key]:5d} fires={f:4d}  {rng}")


if __name__ == "__main__":
    main()
