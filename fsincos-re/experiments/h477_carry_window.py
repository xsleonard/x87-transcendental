#!/usr/bin/env python3
"""h477: approximate carry at the retention boundary (class shift).

Mechanism under test: the terminal subtract |acc| = A - B + P<<unit is
physically A + ~B + 1 + P_row, and the carry INTO the retained field
(above the 67-bit chop boundary k) is not propagated exactly but
computed by a bounded window / speculative scheme over the discarded
field.  A carry that must cross a long propagate run (= discarded field
near all-ones/all-zeros) is exactly what such schemes mispredict, by
exactly +-1 retained unit, with a PARTIAL deficit at exact ties (h476's
nested-outer family, which loses the carry always, overpredicted the
deficit; hardware fires ~35 percent of ties).

Families (boundary k = magnitude bit_length - 67, per row; window
covers discarded bits [k-w, k); cin0 = assumed carry from below it):
  CW1  flat 3-addend window over (A_low, ~B_low, Prow_low), the +1
       increment living BELOW the window (reaches it only via cin0):
         z: cin0 = 0 (below-bits and increment both dropped)
         o: cin0 = 1 (speculative: increment assumed to reach window)
         s: cin0 = 1 iff any below-window operand bit set (sticky-OR)
         g: cin0 = true carry of below bits WITHOUT the +1
            (pure increment loss, otherwise exact)
         G: exact carry incl. +1 -- CONTROL, must equal ideal
  CW2  same five cin0 kinds, but window applied to the CSA-compressed
       pair (S, C) of the three addends (one 3:2 level moves each
       position's carry up one slot before the CPA window sees it).

Scored in PRE-PATCH coordinates on the same rows as h475 (expected
baseline: 341,909 rows, 4,418 ideal-model mismatches).  First output:
hardware tie-row fire rate vs each variant's PREDICTED tie fire rate
(the free quantitative check on the class); then the h475-style
unexplained/broken table.  Run from /tmp/stageA.

Output: h477_results.json (per-variant stats) + stdout tables.
"""
import json
from multiprocessing import Pool

from h437_gate_extraction import (
    ROUNDING_MODES, parse_trace_line, load_labeled_rows,
    final_cosine_result)

W_GRID = list(range(0, 13))
KINDS = ("z", "o", "s", "g", "G")
VARIANTS = [(fam, w, kind)
            for fam in ("CW1", "CW2")
            for w in W_GRID
            for kind in KINDS]
N_VAR = len(VARIANTS)

# tie classes: 0 none/wide, 1 exact tie (disc==0), 2 near-low (1..2),
# 3 near-high (>= all-ones - 2)
TIE_NAMES = {0: "other", 1: "tie", 2: "near-lo", 3: "near-hi"}


def window_carry(parts, k, w, kind):
    """Carry out of the window [k-w, k) over `parts` (each < 2^k) with
    the +1 increment below the window, under assumption `kind`."""
    if w > k:
        w = k
    if w == 0:
        if kind == "z":
            return 0
        if kind == "o":
            return 1
        if kind == "s":
            return 1 if any(parts) else 0
        if kind == "g":
            return sum(parts) >> k if k else 0
        return (sum(parts) + 1) >> k if k else 1          # G
    sh = k - w
    lo_mask = (1 << sh) - 1
    hi = sum(x >> sh for x in parts)
    belows = [x & lo_mask for x in parts]
    if kind == "z":
        cin = 0
    elif kind == "o":
        cin = 1
    elif kind == "s":
        cin = 1 if any(belows) else 0
    elif kind == "g":
        cin = sum(belows) >> sh if sh else 0
    else:                                                  # G: exact
        cin = (sum(belows) + 1) >> sh if sh else 1
    return (hi + cin) >> w


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
    mk = (1 << k) - 1
    disc = M & mk
    R = M >> k

    cache = {}

    def ok_for(delta):
        if delta not in cache:
            corr, corr_e = -(R + delta), scale + k
            cache[delta] = all(
                final_cosine_result(corr, corr_e, m) == h
                for m, h in zip(ROUNDING_MODES, hw))
        return cache[delta]

    ideal_ok = ok_for(0)

    tie_class = 0
    if k >= 3:
        if disc == 0:
            tie_class = 1
        elif disc <= 2:
            tie_class = 2
        elif disc >= mk - 2:
            tie_class = 3

    dev_mask = 0
    ok_mask = 0
    if k == 0:
        ok_mask = (1 << N_VAR) - 1 if ideal_ok else 0
        return (ideal_ok, dev_mask, ok_mask, tie_class, dist)

    width = max(A.bit_length(), B.bit_length()) + 2
    mask = (1 << width) - 1
    Bt = mask ^ B
    a_lo, b_lo, p_lo = A & mk, Bt & mk, Pv & mk
    c1_ideal = (a_lo + b_lo + p_lo + 1) >> k

    S = (A ^ Bt ^ Pv) & mask
    C = (((A & Bt) | (A & Pv) | (Bt & Pv)) << 1) & mask
    s_lo, c_lo = S & mk, C & mk
    c2_ideal = (s_lo + c_lo + 1) >> k

    parts1 = (a_lo, b_lo, p_lo)
    parts2 = (s_lo, c_lo)
    for vi, (fam, w, kind) in enumerate(VARIANTS):
        if fam == "CW1":
            delta = window_carry(parts1, k, w, kind) - c1_ideal
        else:
            delta = window_carry(parts2, k, w, kind) - c2_ideal
        if delta:
            dev_mask |= 1 << vi
        if ok_for(delta):
            ok_mask |= 1 << vi
    return (ideal_ok, dev_mask, ok_mask, tie_class, dist)


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
    print(f"scoring rows: {len(jobs)}, variants: {N_VAR}")

    with Pool(8) as pool:
        rows = [r for r in pool.map(score_row, jobs, chunksize=500)
                if r is not None]
    n_rows = len(rows)
    n_fire = sum(1 for r in rows if not r[0])
    print(f"active rows: {n_rows}, ideal-model mismatches (pre-patch "
          f"fires): {n_fire}   [h475 baseline: 341909 / 4418]")

    # sanity: the exact-control variants must never deviate from ideal
    g_bits = 0
    for vi, (fam, w, kind) in enumerate(VARIANTS):
        if kind == "G":
            g_bits |= 1 << vi
    bad_control = sum(1 for r in rows if r[1] & g_bits)
    print(f"control check (G variants deviating anywhere): {bad_control}"
          f"  <-- must be 0")

    # tie census (hardware)
    print("\n=== tie census (hardware vs ideal model) ===")
    for tc in (1, 2, 3, 0):
        sub = [r for r in rows if r[3] == tc]
        f = sum(1 for r in sub if not r[0])
        rate = f / len(sub) if sub else 0.0
        print(f"{TIE_NAMES[tc]:8s} rows={len(sub):7d} hw-fires={f:5d} "
              f"rate={rate:.3f}")

    tie_rows = [r for r in rows if r[3] == 1]
    n_tie = len(tie_rows)
    tie_hw = sum(1 for r in tie_rows if not r[0])

    # per-variant stats
    stats = []
    for vi, (fam, w, kind) in enumerate(VARIANTS):
        bit = 1 << vi
        fixed = broken = 0
        tie_pred = tie_hit = 0
        for ideal_ok, dev, okm, tc, dist in rows:
            ok = bool(okm & bit)
            if ok and not ideal_ok:
                fixed += 1
            elif not ok and ideal_ok:
                broken += 1
            if tc == 1 and (dev & bit):
                tie_pred += 1
                if not ideal_ok and ok:
                    tie_hit += 1
        unexplained = n_fire - fixed
        stats.append({
            "family": fam, "w": w, "kind": kind,
            "unexplained": unexplained, "broken": broken,
            "total_bad": unexplained + broken,
            "tie_pred_rate": tie_pred / n_tie if n_tie else 0.0,
            "tie_pred": tie_pred, "tie_fixed": tie_hit,
        })

    print(f"\n=== tie-rate check (hardware tie fire rate: "
          f"{tie_hw}/{n_tie} = {tie_hw/n_tie if n_tie else 0:.3f}) ===")
    print(f"{'family':4s} {'kind':4s} " +
          " ".join(f"w={w:<2d}" for w in W_GRID))
    for fam in ("CW1", "CW2"):
        for kind in KINDS:
            if kind == "G":
                continue
            rates = [s["tie_pred_rate"] for s in stats
                     if s["family"] == fam and s["kind"] == kind]
            print(f"{fam:4s} {kind:4s} " +
                  " ".join(f"{r:4.2f}" for r in rates))

    print("\n=== full scoring, best 20 by total-bad ===")
    ordered = sorted(stats, key=lambda s: (s["total_bad"],
                                           s["unexplained"]))
    print(f"{'family':6s} {'kind':4s} {'w':3s}  unexplained  broken  "
          f"total-bad  tie_pred  tie_fixed")
    for s in ordered[:20]:
        tag = "  <== EXACT" if s["total_bad"] == 0 else ""
        print(f"{s['family']:6s} {s['kind']:4s} {s['w']:3d}  "
              f"{s['unexplained']:10d}  {s['broken']:6d}  "
              f"{s['total_bad']:9d}  {s['tie_pred']:8d}  "
              f"{s['tie_fixed']:9d}{tag}")

    with open("h477_results.json", "w") as fh:
        json.dump({"rows": n_rows, "fires": n_fire, "tie_rows": n_tie,
                   "tie_hw_fires": tie_hw, "variants": stats}, fh,
                  indent=1)
    print("\nwrote h477_results.json")


if __name__ == "__main__":
    main()
