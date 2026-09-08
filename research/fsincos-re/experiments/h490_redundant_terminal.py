#!/usr/bin/env python3
"""h490: idea #1 — the terminal subtract consumes the right product
in unresolved carry-save form.

h488 proved the gate is f(input, schedule): same values, different
microcode schedule -> near-independent fire patterns.  The one
mechanism class where that is natural: an intermediate kept as an
unresolved (S, C) pair whose SPLIT depends on the reduction order
(schedule), consumed by the terminal subtract with truncation at the
retention boundary.  The f4 tail must ride in the array (t4 causality)
so the multiplicand is f4_full = sq^2 unchopped.

Model per config (radix, recode_op, topology, off, cmode, inc, ipos):
  PP rows of f4_full * rf (Booth radix 2/4/8, either operand recoded);
  reduced to (S, C) by topology in {seq, rev, tree, evenodd};
  subtract consumes ~S, ~C truncated at column c = sR + off
  (cmode 0: complement then truncate; 1: truncate then complement);
  increments inc in {0,1,2} at position ipos in {0, c};
  M_ext = (A + Pv)<<sR + S~ + C~ + inc; retained R' = M_ext >> (k+sR);
  fire_pred = R - R'.
Scored on the 1,310 FCOS labels AND the 978 comparable FSINCOS
labels.  The class prediction: best-fit topology DIFFERS between the
two instruction schedules.  Run from /tmp/stageA.
"""
import json
from collections import defaultdict
from multiprocessing import Pool
from h453_chain_variants import (C6_1, C6_2, C6_3, C6_4, C6_5, C6_6,
                                 build_chain, mul_round)
MODES = ("rn", "rd", "ru")
E2M = -66
W = 224
MASK = (1 << W) - 1
OFFS = list(range(-2, 9))
TOPOS = ("seq", "rev", "tree", "evenodd")

def sig(line):
    t = line.split()
    return f"{int(t[2],16):016x}" if t[0] == "OK" else "BAD"

def load_both():
    locked = json.load(open("h488_locked.json"))["inputs"]
    st = {m: open(f"sincos_{m}_status.txt").read().splitlines()
          for m in MODES}
    out = []
    for i, e in enumerate(locked):
        cos = []
        bad = False
        for m in MODES:
            t = st[m][i].split()
            if t[0] != "OK":
                bad = True
                break
            cos.append(f"{int(t[4],16):016x}")
        sc = None
        if not bad:
            if cos == e["clean"]:
                sc = 0
            elif cos == e["fired"]:
                sc = 1
        out.append((e["m"], e["fcos"], sc))
    return out

def recode(value, rb):
    if rb == 1:
        return [((value >> i) & 1, i)
                for i in range(value.bit_length())
                if (value >> i) & 1]
    digits = []
    base = 0
    top = value.bit_length()
    low_mask = (1 << (rb - 1)) - 1
    while base <= top:
        prev = (value >> (base - 1)) & 1 if base else 0
        window = (value >> base) & ((1 << rb) - 1)
        d = prev + (window & low_mask) \
            - (((window >> (rb - 1)) & 1) << (rb - 1))
        if d:
            digits.append((d, base))
        base += rb
    return digits

def pp_rows(a, b, rb):
    """Rows (values over W bits) of a*b with b recoded; negative
    digits as complement rows + correction rows so values sum
    exactly."""
    rows = []
    for d, p in recode(b, rb):
        v = ((-d if d < 0 else d) * a) << p
        if d > 0:
            rows.append(v)
        else:
            rows.append((MASK ^ v))
            rows.append(1 << 0)      # +1 completing ~v over W bits
            # NOTE: MASK^v + v = MASK, so MASK^v = -v - 1 + 2^W;
            # sum over all rows mod 2^W is exact.
    return rows

def c32(S, C, v):
    return (S ^ C ^ v) & MASK, (((S & C) | (S & v) | (C & v)) << 1) & MASK

def reduce_rows(rows, topo):
    if topo == "rev":
        rows = rows[::-1]
    elif topo == "evenodd":
        rows = rows[0::2] + rows[1::2]
    if topo in ("seq", "rev", "evenodd"):
        S, C = 0, 0
        for v in rows:
            S, C = c32(S, C, v)
        return S, C
    # tree: pairwise recursive
    layer = [(v, 0) for v in rows]
    while len(layer) > 1:
        nxt = []
        for i in range(0, len(layer) - 1, 2):
            (s1, c1), (s2, c2) = layer[i], layer[i + 1]
            S, C = c32(s1, c1, s2)
            S, C = c32(S, C, c2)
            nxt.append((S, C))
        if len(layer) % 2:
            nxt.append(layer[-1])
        layer = nxt
    return layer[0]

def row_state(mhex):
    m = int(mhex, 16)
    mag = (0, E2M, m)
    square = mul_round(mag, mag, 67, "chop")
    fourth = mul_round(square, square, 67, "chop")
    negative = build_chain(fourth, C6_5, C6_3, C6_1, 67, 64, "rn",
                           False, False, False)
    positive = build_chain(fourth, C6_6, C6_4, C6_2, 67, 64, "rn",
                           False, False, False)
    left = mul_round(square, negative, 67, "chop")
    right = mul_round(fourth, positive, 67, "chop")
    low3 = square[2] & 7
    dist = abs(left[1] - right[1])
    payload = low3 + 8 - dist
    scale = min(left[1], right[1])
    if payload and left[1] - 8 < scale:
        scale = left[1] - 8
    A = left[2] << (left[1] - scale)
    Pv = payload << (left[1] - 8 - scale)
    M = A + Pv - (right[2] << (right[1] - scale))
    k = M.bit_length() - 67
    f4_full = square[2] * square[2]
    s4 = f4_full.bit_length() - 67
    prod = f4_full * positive[2]
    sR = prod.bit_length() - 67 - s4 + s4  # placeholder, fix below
    # rs chop is on f4*rf; extended product scale is s4 higher
    base_prod = fourth[2] * positive[2]
    sR = base_prod.bit_length() - 67
    sE = sR + s4                      # extended product's chop width
    return (f4_full, positive[2], A, Pv, M >> k, k, sE, right[2])

def score_chunk(job):
    combo, rows_data = job
    rb, swap, topo = combo
    counts = defaultdict(lambda: [0, 0, 0, 0])
    # counts[cfg] = [fcos_exc, fcos_n, sincos_exc, sincos_n]
    for (f4f, rf, A, Pv, R, k, sE, rs, fcos, sc) in rows_data:
        a, b = (f4f, rf) if not swap else (rf, f4f)
        S, C = reduce_rows(pp_rows(a, b, rb), topo)
        AAP = (A + Pv) << sE
        shift = k + sE
        for off in OFFS:
            c = sE + off
            if c < 0:
                continue
            keep = MASK & ~((1 << c) - 1)
            for cmode in (0, 1):
                if cmode == 0:
                    Sb = (MASK ^ S) & keep
                    Cb = (MASK ^ C) & keep
                else:
                    Sb = MASK ^ (S & keep)
                    Cb = MASK ^ (C & keep)
                base = (AAP + Sb + Cb) & MASK
                for inc in (0, 1, 2):
                    for ipos_sym, ipos in (("b0", 0), ("atC", c)):
                        tot = (base + (inc << ipos)) & MASK
                        Rp = tot >> shift
                        pred = R - Rp
                        cfg = (off, cmode, inc, ipos_sym)
                        cc = counts[cfg]
                        cc[1] += 1
                        if pred != fcos:
                            cc[0] += 1
                        if sc is not None:
                            cc[3] += 1
                            if pred != sc:
                                cc[2] += 1
    return combo, dict(counts)

def main():
    labels = load_both()
    ms = [m for m, f, s in labels]
    with Pool(8) as pool:
        states = pool.map(row_state, ms, chunksize=50)
    rows_data = [s + (f, sc) for s, (m, f, sc) in zip(states, labels)]
    nf = sum(1 for r in rows_data if r[8])
    print(f"rows: {len(rows_data)}, fcos fires: {nf}, sincos "
          f"comparable: {sum(1 for r in rows_data if r[9] is not None)}")

    combos = [(rb, swap, topo) for rb in (1, 2, 3) for swap in (0, 1)
              for topo in TOPOS]
    with Pool(8) as pool:
        results = pool.map(score_chunk,
                           [(c, rows_data) for c in combos],
                           chunksize=1)
    flat = []
    for combo, counts in results:
        for cfg, (fe, fn_, se, sn) in counts.items():
            flat.append((fe, se, combo, cfg, fn_, sn))
    flat.sort()
    print(f"\n=== best 20 by FCOS exceptions "
          f"(rb, swap, topo | off, cmode, inc, ipos) ===")
    for fe, se, combo, cfg, fn_, sn in flat[:20]:
        print(f"  fcos_exc={fe:4d}/{fn_}  sincos_exc={se:4d}/{sn}  "
              f"{combo} {cfg}")
    print(f"\n=== best 10 by SINCOS exceptions ===")
    flat2 = sorted(flat, key=lambda x: (x[1], x[0]))
    for fe, se, combo, cfg, fn_, sn in flat2[:10]:
        print(f"  sincos_exc={se:4d}/{sn}  fcos_exc={fe:4d}/{fn_}  "
              f"{combo} {cfg}")

if __name__ == "__main__":
    main()
