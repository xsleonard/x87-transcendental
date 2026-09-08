#!/usr/bin/env python3
"""h485: truncated multiplier arrays with VARIABLE compensation, over
the extended right operand — the space h441 did not cover.

h441 audit: it eliminated truncation of the CHOPPED-operand array
(f4*rf) with CONSTANT compensation at ABSOLUTE columns.  It never
included the f4 tail as array rows (the hardware-proven causal
driver), never tested data-dependent compensation (the canonical
variable-correction truncated-multiplier design, whose error is a
carry-like function windowed comparisons cannot express — matching
the h484 CEGIS failure), and used absolute not boundary-relative
columns.

Model per config (ext, radix_bits, swap, off, corr_mode, d, K):
  operands: a = f4 (ext=0) or f4_full = f4*2^s4 + t4 (ext=1); b = rf;
  swap recodes the other operand;  radix 2/4/8 Booth (rb = 1,2,3);
  truncation column C = shift - off (boundary-relative; shift =
  bitlen(full) - 67);  negative-row corrections below C: dropped /
  lumped at C / kept (corr_mode 0/1/2);
  VARIABLE compensation: sum of actual PP bits in columns C-1..C-d
  added at their true weights (d = 0 none, 1, 2);
  constant K in units of 2^(C-1), K = 0..2.
Prediction: delta = (trunc >> shift) - rs, required to equal the fire
label (0/1) on every constructed tie row.  Exact survivors -> fresh
validation batch.  Run from /tmp/stageA.
"""
import json
from collections import defaultdict
from multiprocessing import Pool

from h453_chain_variants import (C6_1, C6_2, C6_3, C6_4, C6_5, C6_6,
                                 build_chain, mul_round)

MODES = ("rn", "rd", "ru")
E2M = -66
W = 224
MASK_W = (1 << W) - 1
OFFS = list(range(0, 17))
DS = (0, 1, 2)
KS = (0, 1, 2)


def sig(line):
    t = line.split()
    return f"{int(t[2],16):016x}" if t[0] == "OK" else "BAD"


def load_labels():
    rows = {}
    d479 = json.load(open("h479_locked.json"))
    order = []
    for p in d479["pairs"]:
        order += [p["g0"], p["g1"]]
    order += d479["controls"]
    st = {m: open(f"h479_cos_{m}_status.txt").read().splitlines()
          for m in MODES}
    for i, e in enumerate(order):
        hw = [sig(st[m][i]) for m in MODES]
        rows[e["m"]] = 1 if hw == e["fired"] else \
            (0 if hw == e["clean"] else 2)
    for line in open("h480_outcomes.tsv").read().splitlines()[1:]:
        f = line.split("\t")
        rows[f[0]] = {"CLEAN": 0, "FIRE": 1}.get(f[6], 2)
    d482 = json.load(open("h482_locked.json"))
    st = {m: open(f"cos_{m}_status.txt").read().splitlines()
          for m in MODES}
    for i, e in enumerate(d482["inputs"]):
        hw = [sig(st[m][i]) for m in MODES]
        rows[e["m"]] = 1 if hw == e["fired"] else \
            (0 if hw == e["clean"] else 2)
    return rows


def operands(mhex):
    m = int(mhex, 16)
    mag = (0, E2M, m)
    square = mul_round(mag, mag, 67, "chop")
    fourth = mul_round(square, square, 67, "chop")
    positive = build_chain(fourth, C6_6, C6_4, C6_2, 67, 64, "rn",
                           False, False, False)
    right = mul_round(fourth, positive, 67, "chop")
    f4_full = square[2] * square[2]
    s4 = f4_full.bit_length() - 67
    return fourth[2], positive[2], f4_full, s4, right[2]


def recode(value, rb):
    if rb == 1:
        return [(value >> i) & 1 for i in range(value.bit_length())]
    digits = []
    base = 0
    top = value.bit_length()
    low_mask = (1 << (rb - 1)) - 1
    while base <= top:
        prev = (value >> (base - 1)) & 1 if base else 0
        window = (value >> base) & ((1 << rb) - 1)
        digits.append(prev + (window & low_mask)
                      - (((window >> (rb - 1)) & 1) << (rb - 1)))
        base += rb
    return digits


def build_rows_for(a, b, rb):
    """PP rows: list of (row_value_over_W_bits, position, is_neg)."""
    out = []
    for i, d in enumerate(recode(b, rb)):
        if d == 0:
            continue
        p = rb * i
        v = ((-d if d < 0 else d) * a) << p
        if d > 0:
            out.append((v, p, 0))
        else:
            out.append(((MASK_W ^ v) & ~((1 << p) - 1), p, 1))
    return out


def score_combo(job):
    """One (ext, rb, swap) combo across all rows and all
    (off, corr_mode, d, K); returns list of (exc, config)."""
    combo, rowdata = job
    ext, rb, swap = combo
    corr_modes = (0,) if rb == 1 else (0, 1, 2)
    counts = {(off, cm, d, K): 0
              for off in OFFS for cm in corr_modes
              for d in DS for K in KS}
    for fire, f4, rf, f4f, s4, rs in rowdata:
        a = f4f if ext else f4
        b = rf
        if swap:
            a, b = b, a
        full = a * b
        shift = full.bit_length() - 67
        base_ret = full >> shift
        rows = build_rows_for(a, b, rb)
        n_neg = sum(neg for _, _, neg in rows)
        for off in OFFS:
            C = shift - off
            if C <= 1:
                continue
            keep = MASK_W & ~((1 << C) - 1)
            tsum = 0
            corr_hi = 0          # corrections at/above C (always kept)
            n_low_corr = 0       # negative-row corrections below C
            low_corr_true = 0    # their true-position sum
            col1 = col2 = 0      # PP bits at columns C-1, C-2
            for v, p, neg in rows:
                tsum += v & keep
                if neg:
                    if p >= C:
                        corr_hi += 1 << p
                    else:
                        n_low_corr += 1
                        low_corr_true += 1 << p
                col1 += (v >> (C - 1)) & 1
                if C >= 2:
                    col2 += (v >> (C - 2)) & 1
            for cm in corr_modes:
                if cm == 0:
                    corr = corr_hi
                elif cm == 1:
                    corr = corr_hi + (n_low_corr << C)
                else:
                    corr = corr_hi + low_corr_true
                for d in DS:
                    comp = 0
                    if d >= 1:
                        comp += col1 << (C - 1)
                    if d >= 2:
                        comp += col2 << (C - 2)
                    for K in KS:
                        total = (tsum + corr + comp
                                 + (K << (C - 1))) & MASK_W
                        # delta vs the UNextended retained rs
                        delta = (total >> shift) - rs
                        if delta != fire:
                            counts[(off, cm, d, K)] += 1
    return [(exc, (ext, rb, swap) + cfg)
            for cfg, exc in counts.items()]


def main():
    labels = load_labels()
    with Pool(8) as pool:
        ops = pool.map(operands,
                       [m for m, o in sorted(labels.items()) if o != 2],
                       chunksize=50)
    ms = [m for m, o in sorted(labels.items()) if o != 2]
    rowdata = []
    for mhex, (f4, rf, f4f, s4, rs) in zip(ms, ops):
        rowdata.append((labels[mhex], f4, rf, f4f, s4, rs))
    print(f"rows: {len(rowdata)}, fires: "
          f"{sum(r[0] for r in rowdata)}")

    combos = [(ext, rb, swap)
              for ext in (0, 1) for rb in (1, 2, 3)
              for swap in (0, 1)]
    with Pool(8) as pool:
        allres = pool.map(score_combo,
                          [(c, rowdata) for c in combos], chunksize=1)
    res = [x for r in allres for x in r]
    res.sort(key=lambda x: x[0])
    n = len(rowdata)
    print(f"configs scored: {len(res)}")
    print("\n=== best 25 (ext, rb, swap, off, corr, d, K) ===")
    for exc, cfg in res[:25]:
        tag = "  <== EXACT" if exc == 0 else ""
        print(f"  exceptions={exc:4d}/{n}  {cfg}{tag}")
    exact = [cfg for exc, cfg in res if exc == 0]
    if exact:
        with open("h485_exact.json", "w") as fh:
            json.dump(exact, fh)
        print(f"\nEXACT configs: {len(exact)} -> h485_exact.json "
              f"(VALIDATE ON FRESH BATCH before belief)")
    else:
        print("\nno exact config in this family")


if __name__ == "__main__":
    main()
