#!/usr/bin/env python3
"""h477g: extended-precision fourth power flowing into the right
terminal product -- exact test on the observable tie stratum.

Candidate: hardware's terminal right product consumes f4 with j extra
bits below its 67-bit chop (optionally a sticky OR of the rest).  Then
rs_hw = (f4_ext * rf) >> (shift), and rs bumps by +1 exactly when the
extra tail carries the product's discarded field over the boundary.
At an exact tie, rs+1 gives retained R-1 -- the observed fire, always
exactly R-1.  Prediction per row is deterministic from the traces:
  fire_pred(j, sticky) = ( chop67(f4ext_j * rf) != rs )
Scored on observable ties (4,907 rows, 1,684 fires, rate 0.343).
"""
from multiprocessing import Pool
from collections import defaultdict
from h437_gate_extraction import (ROUNDING_MODES, parse_trace_line,
                                  load_labeled_rows, final_cosine_result)

JS = list(range(1, 9))
VARIANTS = [(j, s) for j in JS for s in (0, 1)]

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
    A = ls << (le2 - scale); B = rs << (re2 - scale)
    unit = le2 - 8 - scale
    Pv = prepay << unit
    hw = tuple(hw_sigs[m] for m in ROUNDING_MODES)
    M = A - B + Pv
    if M <= 0: return None
    k = max(M.bit_length() - 67, 0)
    if k < 3 or (M & ((1 << k) - 1)): return None
    R = M >> k
    def res(delta):
        return tuple(final_cosine_result(-(R+delta), scale+k, m)
                     for m in ROUNDING_MODES)
    r0, rm1 = res(0), res(-1)
    if r0 == rm1: return None            # blind row
    fire = 1 if hw == rm1 else (0 if hw == r0 else 2)
    if fire == 2: return None

    sq = int(fields["mul"], 16)
    rf = int(fields["rf"], 16)
    f4 = int(fields["f4"], 16)
    f4_full = sq * sq
    s4 = max(f4_full.bit_length() - 67, 0)
    if (f4_full >> s4) != f4:
        return None                       # trace f4 not chop(sq^2)?
    preds = 0
    for vi, (j, st) in enumerate(VARIANTS):
        jj = min(j, s4)
        ext = (f4_full >> (s4 - jj))
        if st and (f4_full & ((1 << (s4 - jj)) - 1)):
            ext |= 1                      # sticky into lowest extra bit
        prod = ext * rf
        sh = max(prod.bit_length() - 67, 0)
        if (prod >> sh) != rs:
            preds |= 1 << vi
    return (fire, preds, dist, prepay)

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
                    t = hw_files[m][i].split()
                    hw_sigs[m] = int(t[2], 16) if t[0] == "OK" else -1
                jobs.append((fields, hw_sigs))
    jobs.extend(load_labeled_rows())
    with Pool(8) as pool:
        rows = [r for r in pool.map(score_row, jobs, chunksize=500) if r]
    n = len(rows); nf = sum(1 for r in rows if r[0])
    print(f"observable tie rows: {n}, fires: {nf}  [expect 4907/1684]")
    print(f"{'j':2s} {'sticky':6s}  pred-fires  hits  false-pos  "
          f"false-neg  accuracy")
    for vi, (j, st) in enumerate(VARIANTS):
        bit = 1 << vi
        tp = fp = fn = tn = 0
        for fire, preds, dist, prepay in rows:
            p = bool(preds & bit)
            if p and fire: tp += 1
            elif p: fp += 1
            elif fire: fn += 1
            else: tn += 1
        acc = (tp + tn) / n
        tag = "  <== EXACT" if fp == 0 and fn == 0 else ""
        print(f"{j:2d} {st:6d}  {tp+fp:10d}  {tp:4d}  {fp:9d}  "
              f"{fn:9d}  {acc:.4f}{tag}")
if __name__ == "__main__":
    main()
