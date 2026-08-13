#!/usr/bin/env python3
"""h477d: within-cell screen of the tie stratum.

h477c proved the exact-tie discarded field is BIT-IDENTICAL for every
row of a (k, unit, prepay) cell (left operand zeros, rs_low = prepay <<
unit, ~B + P = all-ones, CSA carry word = 0), yet fire-ness (the lost
+1 carry, always exactly R-1) is mixed within cells.  So the loss
condition reads retained-side or upstream state.  This screens every
candidate the replica can express, inside cells where the whole
discarded field is pinned:

  cell key: (dist, low3, k, rud)   [pins prepay and the full field]
  features: rs nibbles above the pinned zone, ls windows, retained
  accumulator low byte and trailing-ones run length, both products'
  discarded-field tops (recomputed exactly), chain low bytes, and the
  h466 upstream replica panel (m, square disc, all product-chop and
  chain-add guard/sticky/round-up bits).

Outputs:
  1. paired wins/losses z per feature, split-half replicated (h473
     protocol);
  2. exact-purity test per feature: fraction of (cell, value) buckets
     mixed, and half0->half1 transfer accuracy of the pure-bucket rule;
  3. direct crosstab of the two mechanism-shaped features (R_trail1,
     R_low bits).

Run from /tmp/stageA.  Writes h477d_ties_features.tsv.
"""
import math
from collections import defaultdict
from multiprocessing import Pool

from h437_gate_extraction import (
    ROUNDING_MODES, parse_trace_line, load_labeled_rows,
    final_cosine_result)
from h466_paired_mining import upstream_features


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
    if k < 3 or (M & ((1 << k) - 1)):
        return None                                        # ties only
    R = M >> k

    def ok_for(delta):
        corr, corr_e = -(R + delta), scale + k
        return all(final_cosine_result(corr, corr_e, m) == h
                   for m, h in zip(ROUNDING_MODES, hw))

    fire = 0 if ok_for(0) else (1 if ok_for(-1) else 2)
    if fire == 2:
        return None

    square = int(fields["mul"], 16)
    lf = int(fields["lf"], 16)
    rf = int(fields["rf"], 16)
    f4 = int(fields["f4"], 16)
    full_L = square * lf
    full_R = f4 * rf
    sL = max(full_L.bit_length() - 67, 0)
    sR = max(full_R.bit_length() - 67, 0)
    ldisc16 = ((full_L & ((1 << sL) - 1)) >> max(sL - 16, 0)) & 0xFFFF
    rdisc16 = ((full_R & ((1 << sR) - 1)) >> max(sR - 16, 0)) & 0xFFFF

    trail = 0
    rr = R
    while rr & 1:
        trail += 1
        rr >>= 1

    feats = {
        "rs_b8_11": (rs >> 8) & 0xF,
        "rs_b12_15": (rs >> 12) & 0xF,
        "rs_b16_23": (rs >> 16) & 0xFF,
        "ls_low8": ls & 0xFF,
        "ls_b8_15": (ls >> 8) & 0xFF,
        "R_low8": R & 0xFF,
        "R_trail1": trail,
        "ldisc16": ldisc16,
        "rdisc16": rdisc16,
        "mul_low8": square & 0xFF,
        "lf_low8": lf & 0xFF,
        "rf_low8": rf & 0xFF,
        "f4_low8": f4 & 0xFF,
        "ud": int(fields.get("ud", -1)),
        "u5d": int(fields.get("u5d", -1)),
    }
    up = upstream_features(fields)
    if up is not None:
        feats.update(up)
    else:
        feats["no_upstream"] = 1
    key = (dist, low3, k, int(fields.get("rud", -1)))
    return (key, fire, feats)


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
    n_up = sum(1 for _, _, f in rows if "no_upstream" not in f)
    print(f"tie rows: {len(rows)}, fires: "
          f"{sum(1 for _, fi, _ in rows if fi)}, with upstream replica: "
          f"{n_up}")

    names = sorted({k for _, _, f in rows for k in f
                    if k != "no_upstream"})
    with open("h477d_ties_features.tsv", "w") as fh:
        fh.write("dist\tlow3\tk\trud\tfire\t" + "\t".join(names) + "\n")
        for key, fire, f in rows:
            fh.write("\t".join(str(x) for x in key) + f"\t{fire}\t" +
                     "\t".join(str(f.get(nm, -1)) for nm in names) + "\n")

    # ---- 1. paired split-half z screen -------------------------------
    groups = defaultdict(list)
    for key, fire, f in rows:
        groups[key].append((fire, f))
    pairs = []
    for key, members in groups.items():
        half = hash(key) & 1
        fires = [m for m in members if m[0]]
        cools = [m for m in members if not m[0]]
        for F in fires:
            for N in cools:
                pairs.append((half, F[1], N[1]))
    print(f"contrast cells: "
          f"{sum(1 for g in groups.values() if any(m[0] for m in g) and any(not m[0] for m in g))}, "
          f"pairs: {len(pairs)}")

    results = []
    for name in names:
        zs = []
        for half in (0, 1):
            wins = losses = 0
            for h, F, N in pairs:
                if h != half or name not in F or name not in N:
                    continue
                if F[name] > N[name]:
                    wins += 1
                elif F[name] < N[name]:
                    losses += 1
            n = wins + losses
            zs.append((wins - losses) / math.sqrt(n) if n else 0.0)
        repl = min(abs(z) for z in zs) if zs[0] * zs[1] > 0 else 0.0
        results.append((repl, name, zs))
    results.sort(reverse=True)
    print(f"\n=== paired screen ===\n{'feature':12s}  z(half0)  "
          f"z(half1)   [replicated |z|]")
    for repl, name, zs in results[:18]:
        print(f"{name:12s}  {zs[0]:+7.1f}  {zs[1]:+7.1f}   {repl:5.1f}")

    # ---- 2. exact-purity / determinism test --------------------------
    print(f"\n=== purity test (fire as function of cell x value) ===")
    print(f"{'feature':12s}  mixed-buckets  mixed-rows  transfer-acc")
    purity = []
    for name in names:
        buckets = defaultdict(lambda: [0, 0])
        for key, fire, f in rows:
            if name not in f:
                continue
            b = buckets[(key, f[name])]
            b[fire and 1] += 1
        mixed = sum(1 for v in buckets.values() if v[0] and v[1])
        mixed_rows = sum(v[0] + v[1] for v in buckets.values()
                        if v[0] and v[1])
        # transfer: majority rule per bucket learned on half0 rows
        rule = defaultdict(lambda: [0, 0])
        for key, fire, f in rows:
            if name not in f or (hash(key) & 1) != 0:
                continue
            rule[(key, f[name])][fire and 1] += 1
        hit = tot = 0
        for key, fire, f in rows:
            if name not in f or (hash(key) & 1) != 1:
                continue
            rk = (key, f[name])
            if rk in rule:
                pred = 1 if rule[rk][1] > rule[rk][0] else 0
                hit += 1 if pred == (fire and 1) else 0
                tot += 1
        purity.append((mixed_rows, name, mixed, hit / tot if tot else 0))
    purity.sort()
    for mixed_rows, name, mixed, acc in purity[:14]:
        print(f"{name:12s}  {mixed:13d}  {mixed_rows:10d}  {acc:11.3f}")

    # ---- 3. mechanism-shaped direct crosstabs ------------------------
    for name in ("R_trail1", "R_low8"):
        buckets = defaultdict(lambda: [0, 0])
        for key, fire, f in rows:
            v = f[name] if name == "R_trail1" else f[name] & 7
            b = buckets[v]
            b[0] += 1
            b[1] += 1 if fire else 0
        label = name if name == "R_trail1" else "R_low3"
        print(f"\n--- fire rate by {label} ---")
        for v in sorted(buckets):
            tot, fi = buckets[v]
            if tot >= 10:
                print(f"  {label}={v:<3} n={tot:5d} fires={fi:5d} "
                      f"rate={fi/tot:.3f}")


if __name__ == "__main__":
    main()
