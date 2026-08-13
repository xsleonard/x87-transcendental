#!/usr/bin/env python3
"""h521: value-semantics test on corpus ties.

recover_m returns the operand at an arbitrary power-of-2 scale; the
replica is value-semantic (chop at significant bits, value-aligned
adds), so normalize m UP to 64 bits and run build() at E2M=-66.
If (dist, low3) then matches the trace for the former 'mismatch'
rows, the 'neighboring binade' collapses into the already-scanned
64-bit coordinate system.

Also: per-row probe of the residual nohit/family-2 class done in the
same process pool (file-based, so macOS spawn workers can import)."""
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import load_labeled_rows
from h453_chain_variants import recover_m
from h500_plane_m import build


def score(job):
    fields, hw = job
    if fields.get("active") != "1" or fields["lsign"] != "1" \
            or fields["rsign"] != "0":
        return None
    dist, low3 = int(fields["dist"]), int(fields["low3"])
    le2, re2 = int(fields["le2"]), int(fields["re2"])
    ls, rs = int(fields["ls"], 16), int(fields["rs"], 16)
    prepay = low3 + 8 - dist
    scale = min(le2, re2, le2 - 8)
    M = (ls << (le2 - scale)) - (rs << (re2 - scale)) \
        + (prepay << (le2 - 8 - scale))
    if M <= 0:
        return None
    k = max(M.bit_length() - 67, 0)
    if k < 3 or (M & ((1 << k) - 1)):
        return None
    m = recover_m(int(fields["mul"], 16))
    if m is None:
        return ("no_m", None, None)
    m <<= (64 - m.bit_length())
    cell, XT, XD, mf, _ = build((f"{m:016x}", 0))
    ok = cell[0] == dist and cell[1] == low3
    return ("ok" if ok else "mismatch", (le2, dist), round(mf, 3))


def main():
    rows = load_labeled_rows()
    with Pool(8) as pool:
        out = [o for o in pool.map(score, rows, chunksize=500) if o]
    tab = defaultdict(int)
    wins = defaultdict(list)
    for st, key, mf in out:
        tab[st] += 1
        if st == "ok":
            wins[key].append(mf)
    print("census:", dict(tab))
    for key in sorted(wins):
        mfs = sorted(wins[key])
        print(f"  le2={key[0]} dist={key[1]}: n={len(mfs)} "
              f"mf [{mfs[0]:.3f},{mfs[-1]:.3f}]")


if __name__ == "__main__":
    main()
