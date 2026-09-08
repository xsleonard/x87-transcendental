#!/usr/bin/env python3
"""h477c: mine the tie stratum directly.

h477/h477b established: every tie-row fire (1,684 of 5,789 exact-tie
rows) is exactly R-1 -- the hardware loses the terminal subtract's +1
carry across the discarded field on 29 percent of ties, with the rate
RISING with discarded width k (25 percent at k<=8, 45 at k=9, 63 at
k>9).  Ties are pure gate signal (ideal model exactly on the boundary,
zero rounding ambiguity), so instead of guessing another mechanism
family, dump every tie row with rich per-row state and crosstab the
loss condition.

Output: h477c_ties.tsv (one row per exact-tie row) + stdout crosstabs.
Run from /tmp/stageA.
"""
from collections import defaultdict
from multiprocessing import Pool

from h437_gate_extraction import (
    ROUNDING_MODES, parse_trace_line, load_labeled_rows,
    final_cosine_result)

COLS = ("fire", "k", "dist", "low3", "prepay", "unit", "a_lo_len",
        "b_lo_len", "ud", "u5d", "rud", "payload_f", "ls_low8",
        "rs_low4", "rs_b4_7", "rs_b8_11", "c_lo_nz", "run_top_gap")


def score_row(job):
    fields, hw_sigs = job
    if fields.get("active") != "1" or fields["lsign"] != "1" \
            or fields["rsign"] != "0":
        return None
    dist, low3 = int(fields["dist"]), int(fields["low3"])
    prepay = low3 + 8 - dist
    le2, re2 = int(fields["le2"]), int(fields["re2"])
    ls, rs = int(fields["ls"], 16), int(fields["rs"], 16)
    scale = min(le2, re2, le2 - 8)
    A = ls << (le2 - scale)
    B = rs << (re2 - scale)
    unit = le2 - 8 - scale
    Pv = prepay << unit
    hw = tuple(hw_sigs[m] for m in ROUNDING_MODES)

    M = A - B + Pv
    if M <= 0:
        return None
    k = max(M.bit_length() - 67, 0)
    if k < 3:
        return None
    mk = (1 << k) - 1
    if M & mk:
        return None                                        # ties only
    R = M >> k

    def ok_for(delta):
        corr, corr_e = -(R + delta), scale + k
        return all(final_cosine_result(corr, corr_e, m) == h
                   for m, h in zip(ROUNDING_MODES, hw))

    ideal_ok = ok_for(0)
    fire = 0 if ideal_ok else 1
    if fire and not ok_for(-1):
        fire = 2                                           # non-R-1 fire

    width = max(A.bit_length(), B.bit_length()) + 2
    mask = (1 << width) - 1
    Bt = mask ^ B
    c_lo = ((((A & Bt) | (A & Pv) | (Bt & Pv)) << 1) & mask) & mk
    # top of the all-ones-sum run: distance from boundary k down to the
    # highest slot where the 3-addend digit sum deviates from exactly 1
    gap = 0
    for i in range(k - 1, -1, -1):
        dsum = ((A >> i) & 1) + ((Bt >> i) & 1) + ((Pv >> i) & 1)
        if dsum != 1:
            gap = k - i
            break
    else:
        gap = k + 1                                        # pure run

    return (fire, k, dist, low3, prepay, unit,
            le2 - scale, re2 - scale,
            int(fields.get("ud", -1)), int(fields.get("u5d", -1)),
            int(fields.get("rud", -1)), int(fields.get("payload", -1)),
            ls & 0xFF, rs & 0xF, (rs >> 4) & 0xF, (rs >> 8) & 0xF,
            1 if c_lo else 0, gap)


def main():
    jobs = []
    for pkg in ("h464_package", "h469_package"):
        hw_files = {m: open(f"{pkg}/hw_{m}.txt").read().splitlines()
                    for m in ROUNDING_MODES}
        with open(f"{pkg}/selected.tsv") as fh:
            for i, line in enumerate(fh):
                se, sig, theta, trace = line.rstrip("\n").split("\t")
                fields = parse_trace_line(trace)
                hw_sigs = {}
                for m in ROUNDING_MODES:
                    tokens = hw_files[m][i].split()
                    hw_sigs[m] = int(tokens[2], 16) if tokens[0] == "OK" \
                        else -1
                jobs.append((fields, hw_sigs))
    jobs.extend(load_labeled_rows())

    with Pool(8) as pool:
        rows = [r for r in pool.map(score_row, jobs, chunksize=500)
                if r is not None]
    n = len(rows)
    n_fire = sum(1 for r in rows if r[0] == 1)
    n_weird = sum(1 for r in rows if r[0] == 2)
    print(f"tie rows: {n}, R-1 fires: {n_fire}, non-R-1 fires: "
          f"{n_weird}   [expect 5789 / 1684 / 0]")

    with open("h477c_ties.tsv", "w") as fh:
        fh.write("\t".join(COLS) + "\n")
        for r in rows:
            fh.write("\t".join(str(x) for x in r) + "\n")

    def crosstab(name, idx):
        buckets = defaultdict(lambda: [0, 0])
        for r in rows:
            b = buckets[r[idx]]
            b[0] += 1
            b[1] += 1 if r[0] else 0
        print(f"\n--- fire rate by {name} ---")
        for v in sorted(buckets):
            tot, f = buckets[v]
            print(f"  {name}={v:<6} n={tot:6d} fires={f:5d} "
                  f"rate={f/tot:.3f}")

    for name in ("k", "dist", "low3", "prepay", "unit", "a_lo_len",
                 "b_lo_len", "ud", "u5d", "rud", "rs_low4", "c_lo_nz",
                 "run_top_gap"):
        crosstab(name, COLS.index(name))

    # two-way: dist x k
    buckets = defaultdict(lambda: [0, 0])
    for r in rows:
        b = buckets[(r[2], r[1])]
        b[0] += 1
        b[1] += 1 if r[0] else 0
    print("\n--- fire rate by (dist, k) ---")
    for v in sorted(buckets):
        tot, f = buckets[v]
        if tot >= 20:
            print(f"  dist={v[0]:2d} k={v[1]:2d} n={tot:6d} "
                  f"fires={f:5d} rate={f/tot:.3f}")
    print("\nwrote h477c_ties.tsv")


if __name__ == "__main__":
    main()
