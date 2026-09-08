#!/usr/bin/env python3
"""h477h: exact-rule enumeration for the rs-increment gate on ties.

At an observable exact tie, fire <=> hardware used rs+1 (right terminal
operand one unit up) <=> retained R-1.  This scores exact candidate
rules for when the increment happens, each computable from the traces:

  A_rnb   : f4 consumed as RN_b(sq^2) (round-to-nearest-even at width
            b) instead of chop67; pred = chop67(RN_b(sq^2)*rf) != rs
  B_rnb   : right product retained at width b with RNE, then re-chopped
            to 67 (two-stage retention); pred = chop67(RN_b(f4*rf))!=rs
  Bs_rnb  : same with sticky (RN with sticky-OR of dropped tail)
  C_deep  : sq consumed unchopped: pred = chop67(chop67((m*m)**2 ... )
            actually f4_deep = chop_b((m^2)^2) variants via b
  E_thr   : fire <=> rdisc >= 2^sR - (rf >> t)  (tail-threshold form)

Exactness = zero exceptions on the 4,907 observable ties (1,684 fires).
Reports exceptions per variant + f4_g/prepay breakdown for the best.
"""
from multiprocessing import Pool
from collections import defaultdict
from h437_gate_extraction import (ROUNDING_MODES, parse_trace_line,
                                  load_labeled_rows, final_cosine_result)
from h453_chain_variants import recover_m

def rne(x, bits, sticky_extra=0):
    """Round x to `bits` bits, nearest-even, returning integer at that
    width (no normalization overflow handling needed for comparisons
    -- callers re-shift)."""
    sh = x.bit_length() - bits
    if sh <= 0:
        return x << -sh, 0
    top = x >> sh
    guard = (x >> (sh - 1)) & 1
    below = (x & ((1 << (sh - 1)) - 1)) | sticky_extra
    if guard and (below or (top & 1)):
        top += 1
    return top, sh

A_B = list(range(67, 73))
B_B = list(range(68, 76))
T_G = list(range(0, 6))
VARIANTS = ([("A", b, 0) for b in A_B] +
            [("B", b, 0) for b in B_B] +
            [("Bs", b, 0) for b in B_B] +
            [("C", b, 0) for b in A_B] +
            [("E", 0, t) for t in T_G])
N_VAR = len(VARIANTS)

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
    if r0 == rm1: return None
    fire = 1 if hw == rm1 else (0 if hw == r0 else 2)
    if fire == 2: return None

    sq = int(fields["mul"], 16)
    rf = int(fields["rf"], 16)
    f4 = int(fields["f4"], 16)
    f4_full = sq * sq
    s4 = max(f4_full.bit_length() - 67, 0)
    f4_g = (f4_full >> (s4 - 1)) & 1 if s4 else 0
    prod = f4 * rf
    sR = max(prod.bit_length() - 67, 0)
    rdisc = prod & ((1 << sR) - 1)
    m = recover_m(sq)

    preds = 0
    for vi, (fam, b, t) in enumerate(VARIANTS):
        if fam == "A":
            f4r, sh4 = rne(f4_full, b)
            p = (f4r << sh4 >> s4 if False else f4r) * rf
            # keep f4r at width b; product then chopped to 67
            shp = max(p.bit_length() - 67, 0)
            pred = (p >> shp) != rs
        elif fam in ("B", "Bs"):
            st = 0
            if fam == "Bs":
                shx = prod.bit_length() - b
                if shx > 1:
                    st = 1 if prod & ((1 << (shx - 1)) - 1) else 0
            pr, shr = rne(prod, b, sticky_extra=st)
            shp = max(pr.bit_length() - 67, 0)
            pred = (pr >> shp) != rs
        elif fam == "C":
            if m is None:
                pred = False
            else:
                msq = m * m
                f4d_full = msq * msq
                sd = max(f4d_full.bit_length() - b, 0)
                f4d = f4d_full >> sd
                p = f4d * rf
                shp = max(p.bit_length() - 67, 0)
                pred = (p >> shp) != rs
        else:                                              # E
            pred = rdisc >= (1 << sR) - (rf >> t)
        if pred:
            preds |= 1 << vi
    return (fire, preds, f4_g, prepay)

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
                for mm in ROUNDING_MODES:
                    tk = hw_files[mm][i].split()
                    hw_sigs[mm] = int(tk[2], 16) if tk[0] == "OK" else -1
                jobs.append((fields, hw_sigs))
    jobs.extend(load_labeled_rows())
    with Pool(8) as pool:
        rows = [r for r in pool.map(score_row, jobs, chunksize=500) if r]
    n = len(rows); nf = sum(1 for r in rows if r[0])
    print(f"observable ties: {n}, fires: {nf}  [expect 4907/1684]")
    print(f"{'fam':4s} {'b':3s} {'t':2s}  pred  hits  f-pos  f-neg  "
          f"exceptions")
    best = []
    for vi, (fam, b, t) in enumerate(VARIANTS):
        bit = 1 << vi
        tp = fp = fn = 0
        for fire, preds, f4g, pp in rows:
            p = bool(preds & bit)
            if p and fire: tp += 1
            elif p: fp += 1
            elif fire: fn += 1
        exc = fp + fn
        best.append((exc, fam, b, t, vi))
        tag = "  <== EXACT" if exc == 0 else ""
        print(f"{fam:4s} {b:3d} {t:2d}  {tp+fp:5d} {tp:5d} {fp:6d} "
              f"{fn:6d}  {exc:9d}{tag}")
    best.sort()
    exc, fam, b, t, vi = best[0]
    bit = 1 << vi
    print(f"\nbest: {fam} b={b} t={t}, exceptions {exc}; breakdown:")
    for cond, name in ((lambda r: r[2] == 0, "f4_g=0"),
                       (lambda r: r[2] == 1, "f4_g=1")):
        sub = [r for r in rows if cond(r)]
        tp = sum(1 for r in sub if (r[1] & bit) and r[0])
        fp = sum(1 for r in sub if (r[1] & bit) and not r[0])
        fn = sum(1 for r in sub if not (r[1] & bit) and r[0])
        print(f"  {name}: n={len(sub)}, hits {tp}, f-pos {fp}, "
              f"f-neg {fn}")
if __name__ == "__main__":
    main()
