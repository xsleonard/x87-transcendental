#!/usr/bin/env python3
"""h477b: deferred-carry speculation from the CSA carry word.

h477 proved (by census, and it is a theorem) that at an exact tie the
terminal subtract's carry always originates at bit 0 and ripples the
whole discarded field, so any UNIFORM window/cin0 scheme predicts tie
fires at rate exactly 0 or exactly 1 -- hardware fires 29.1 percent.
The only state that varies across tie rows is the carry-save split:
every discarded slot has s_i XOR c_i = 1, but which word holds the 1
varies.  A scheme that speculates the base carry-in from the C-word
bits below the window (the canonical block-chaining over an unresolved
CSA pair) therefore CAN split ties, and mispredicts near-all-ones
fields upward (spurious speculated carry) -- the observed census shape.

Variant = (w, btype): exact CPA over discarded slots [k-w, k) of the
compressed pair (S, C) of (A, ~B, P_row); the real +1 increment enters
only if the window reaches bit 0 (w >= k); base carry-in speculated as:
  b0  : 0                          (control; = h477 CW2/z)
  cb1 : C bit at the adjacent slot below the window base
  cb2 : OR of the two C bits below the base
  cOR : OR of ALL C bits below the base
  sb1 : S bit at the adjacent slot (contrast)
  gb1 : generate (S AND C) at the adjacent slot (finite lookahead)

Same rows, baseline, and outputs as h477 (341,909 rows / 4,418 fires).
Run from /tmp/stageA.  Output: h477b_results.json + stdout tables.
"""
import json
from multiprocessing import Pool

from h437_gate_extraction import (
    ROUNDING_MODES, parse_trace_line, load_labeled_rows,
    final_cosine_result)

W_GRID = list(range(0, 13))
BTYPES = ("b0", "cb1", "cb2", "cOR", "sb1", "gb1")
VARIANTS = [(w, b) for b in BTYPES for w in W_GRID]
N_VAR = len(VARIANTS)

TIE_NAMES = {0: "other", 1: "tie", 2: "near-lo", 3: "near-hi"}


def spec_carry(s_lo, c_lo, k, w, btype):
    """Speculated carry out of the discarded field [0, k)."""
    if w > k:
        w = k
    sh = k - w
    if btype == "b0" or sh == 0:
        cin = 0
    elif btype == "cb1":
        cin = (c_lo >> (sh - 1)) & 1
    elif btype == "cb2":
        cin = 1 if (c_lo >> max(sh - 2, 0)) & (3 if sh >= 2 else 1) else 0
    elif btype == "cOR":
        cin = 1 if c_lo & ((1 << sh) - 1) else 0
    elif btype == "sb1":
        cin = (s_lo >> (sh - 1)) & 1
    else:                                                  # gb1
        cin = ((s_lo & c_lo) >> (sh - 1)) & 1
    inc = 1 if sh == 0 else 0
    return ((s_lo >> sh) + (c_lo >> sh) + cin + inc) >> w


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
    S = (A ^ Bt ^ Pv) & mask
    C = (((A & Bt) | (A & Pv) | (Bt & Pv)) << 1) & mask
    s_lo, c_lo = S & mk, C & mk
    c_ideal = (s_lo + c_lo + 1) >> k

    for vi, (w, btype) in enumerate(VARIANTS):
        delta = spec_carry(s_lo, c_lo, k, w, btype) - c_ideal
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
    print(f"active rows: {n_rows}, pre-patch fires: {n_fire}   "
          f"[baseline: 341909 / 4418]")

    tie_rows = [r for r in rows if r[3] == 1]
    n_tie = len(tie_rows)
    tie_hw = sum(1 for r in tie_rows if not r[0])

    stats = []
    for vi, (w, btype) in enumerate(VARIANTS):
        bit = 1 << vi
        fixed = broken = tie_pred = tie_fixed = 0
        for ideal_ok, dev, okm, tc, dist in rows:
            ok = bool(okm & bit)
            if ok and not ideal_ok:
                fixed += 1
            elif not ok and ideal_ok:
                broken += 1
            if tc == 1 and (dev & bit):
                tie_pred += 1
                if not ideal_ok and ok:
                    tie_fixed += 1
        stats.append({
            "w": w, "btype": btype,
            "unexplained": n_fire - fixed, "broken": broken,
            "total_bad": n_fire - fixed + broken,
            "tie_pred": tie_pred, "tie_fixed": tie_fixed,
            "tie_pred_rate": tie_pred / n_tie if n_tie else 0.0,
        })

    print(f"\n=== tie-rate check (hardware: {tie_hw}/{n_tie} = "
          f"{tie_hw/n_tie if n_tie else 0:.3f}) ===")
    print(f"{'btype':5s} " + " ".join(f"w={w:<2d}" for w in W_GRID))
    for b in BTYPES:
        rates = [s["tie_pred_rate"] for s in stats if s["btype"] == b]
        print(f"{b:5s} " + " ".join(f"{r:4.2f}" for r in rates))

    print("\n=== full scoring, best 20 by total-bad ===")
    ordered = sorted(stats, key=lambda s: (s["total_bad"],
                                           s["unexplained"]))
    print(f"{'btype':5s} {'w':3s}  unexplained  broken  total-bad  "
          f"tie_pred  tie_fixed")
    for s in ordered[:20]:
        tag = "  <== EXACT" if s["total_bad"] == 0 else ""
        print(f"{s['btype']:5s} {s['w']:3d}  {s['unexplained']:10d}  "
              f"{s['broken']:6d}  {s['total_bad']:9d}  "
              f"{s['tie_pred']:8d}  {s['tie_fixed']:9d}{tag}")

    with open("h477b_results.json", "w") as fh:
        json.dump({"rows": n_rows, "fires": n_fire, "tie_rows": n_tie,
                   "tie_hw_fires": tie_hw, "variants": stats}, fh,
                  indent=1)
    print("\nwrote h477b_results.json")


if __name__ == "__main__":
    main()
