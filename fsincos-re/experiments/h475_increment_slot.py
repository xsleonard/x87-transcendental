#!/usr/bin/env python3
"""h475: two's-complement increment placement in the terminal subtract.

Lead: the subtract is physically A + ~B + 1 (+P); nobody has tested
where the +1 enters.  If the increment bit occupies a CSA slot that can
COLLIDE with a data bit (merged by OR, losing the increment, or XOR),
the result is a data-dependent +-1..2^j lowest-unit error, visible only
near all-zeros/all-ones discarded fields, with a strict deficit at
exact ties — the exact observed signature.  Scored in PRE-PATCH
coordinates: a correct variant must reproduce every fire AND the two
ported Round-52 patches natively AND break no clean row.

Families (P = prepay = low3+8-dist at bit position `unit`):
  F1  single subtract: |acc| = A + ~B + P_row, the ~B increment merged
      into the P row at slot j (absolute, in scale units):
        or : P_row = P<<0 | 2^j        (increment LOST if P bit j set)
        xor: P_row = P     ^ 2^j       (lost and bit cleared)
        add: P_row = P     + 2^j       (control; j=0 is the ideal)
  F2  nested subtract: T = B - P via B + ~P + 1 (inner slot ji into the
      ~P row), then |acc| = A - T via A + ~T + 1 (outer slot jo into
      the ~T row), same three semantics per stage; one stage varied at
      a time, the other ideal.

Stage 1 scores every variant on all labeled zone rows (both batches +
legacy corpus, ~50k with hardware); variants with zero mismatches
proceed to stage-2 full-legacy validation.  Reports the best ten by
(fires unexplained + clean rows broken).

Run from /tmp/stageA.
"""
from collections import Counter
from multiprocessing import Pool

from h437_gate_extraction import (
    ROUNDING_MODES, parse_trace_line, load_labeled_rows,
    chop_to_67_bits, final_cosine_result)

VARIANTS = []
for j in range(0, 11):
    for sem in ("or", "xor", "add"):
        if sem == "add" and j == 0:
            continue
        VARIANTS.append(("F1", sem, j, None))
for ji in range(0, 11):
    for sem in ("or", "xor"):
        VARIANTS.append(("F2i", sem, ji, None))
for jo in range(0, 11):
    for sem in ("or", "xor"):
        VARIANTS.append(("F2o", sem, jo, None))


def merged(row_value, j, sem):
    bit = 1 << j
    if sem == "or":
        return row_value | bit
    if sem == "xor":
        return row_value ^ bit
    return row_value + bit


def variant_acc(A, B, P, unit, family, sem, j):
    """Return |acc| under the variant; ideal is A - B + (P<<unit)."""
    Pv = P << unit
    W = A.bit_length() + 2
    mask = (1 << W) - 1
    if family == "F1":
        # A + ~B + P_row  (increment for ~B merged into the P row)
        p_row = merged(Pv, j, sem)
        return (A + (mask ^ B) + p_row) & mask
    if family == "F2i":
        # inner: T = B - P as B + ~P + 1, increment into ~P at slot j
        if Pv <= 0:
            T = B - Pv
        else:
            pc_row = merged(mask ^ Pv, j, sem)
            T = (B + pc_row) & mask
        return (A - T) & mask
    if family == "F2o":
        # outer: |acc| = A - T as A + ~T + 1, increment into ~T at slot j
        T = (B - Pv) & mask
        t_row = merged(mask ^ T, j, sem)
        return (A + t_row) & mask
    raise ValueError(family)


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
    hw = tuple(hw_sigs[m] for m in ROUNDING_MODES)

    def outcome(acc_mag):
        corr, corr_e = chop_to_67_bits(-acc_mag, scale)
        return tuple(final_cosine_result(corr, corr_e, m)
                     for m in ROUNDING_MODES)

    ideal = outcome(A - B + (prepay << unit))
    ideal_ok = ideal == hw
    results = []
    for family, sem, j, _ in VARIANTS:
        var = outcome(variant_acc(A, B, prepay, unit, family, sem, j))
        ok = var == hw
        results.append(ok)
    return (ideal_ok, tuple(results))


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
    print(f"scoring rows: {len(jobs)}, variants: {len(VARIANTS)}")

    with Pool(8) as pool:
        rows = [r for r in pool.map(score_row, jobs, chunksize=500)
                if r is not None]
    n_fire = sum(1 for ideal_ok, _ in rows if not ideal_ok)
    print(f"active rows: {len(rows)}, ideal-model mismatches (pre-patch "
          f"fires incl. patch rows): {n_fire}")

    stats = []
    for vi, (family, sem, j, _) in enumerate(VARIANTS):
        fixed = broken = 0
        for ideal_ok, results in rows:
            if results[vi] and not ideal_ok:
                fixed += 1
            elif not results[vi] and ideal_ok:
                broken += 1
        unexplained = n_fire - fixed
        stats.append((unexplained + broken, unexplained, broken,
                      family, sem, j))
    stats.sort()
    print(f"\n{'family':6s} {'sem':4s} {'slot':4s}  unexplained  broken  "
          f"total-bad")
    for total, unexplained, broken, family, sem, j in stats[:14]:
        tag = "  <== EXACT" if total == 0 else ""
        print(f"{family:6s} {sem:4s} {j:4d}  {unexplained:10d}  "
              f"{broken:6d}  {total:9d}{tag}")


if __name__ == "__main__":
    main()
