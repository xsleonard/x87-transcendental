#!/usr/bin/env python3
"""h519a: pre-flight for the neighboring-binade campaign.

Hypothesis: the h516 'replica_mismatch' corpus tie rows are operands
in the next binade down — recover_m returns m at 63 bits (value
m*2^-66 in [1/8, 1/4) instead of [1/4, 1/2)) and build() works
as-is when m is NOT forcibly normalized to 64 bits.

For every corpus tie row: recover m, use natural bit length, check
(dist, low3) against the trace.  Report match rates by m bit-length,
and for 63-bit matches the (le2, dist) census + mf windows — the
scan ranges the new comb must cover."""
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
    m = recover_m(int(fields["mul"], 16))
    if m is None:
        return ("no_m", None, None, None, None)
    bl = m.bit_length()
    cell, XT, XD, mf, _ = build((f"{m:x}", 0))
    ok = (cell[0] == dist and cell[1] == low3)
    return ("ok" if ok else "mismatch", bl, le2, dist, mf)


def main():
    rows = load_labeled_rows()
    with Pool(8) as pool:
        out = [o for o in pool.map(score_row, rows, chunksize=500)
               if o]
    tab = defaultdict(int)
    windows = defaultdict(list)
    for status, bl, le2, dist, mf in out:
        tab[(status, bl)] += 1
        if status == "ok" and bl is not None:
            windows[(bl, le2, dist)].append(mf)
    print("ties by (match-status, m bit-length):")
    for key in sorted(tab, key=str):
        print(f"  {key}: {tab[key]}")
    print("\nmatched windows (m_bits, le2, dist): n, mf range")
    for key in sorted(windows):
        mfs = sorted(windows[key])
        print(f"  {key}: n={len(mfs)} "
              f"mf [{mfs[0]:.4f}, {mfs[-1]:.4f}]")


if __name__ == "__main__":
    main()
