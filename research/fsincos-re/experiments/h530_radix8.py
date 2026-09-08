#!/usr/bin/env python3
"""h530: radix-8 Booth structural model (the Pentium-lineage shape:
Shirriff — radix-8 Booth, x3 hard multiple, tree of 4:2 compressors,
low product bits resolved by a CARRY-PREDICT circuit, not an adder).

B = f4 * pos with pos ~ 2/3 = 0.5252..._8: Booth-8 digits alternate
(-3, +3, -3, ...), so the PP array is alternating +-(3*f4) copies —
the x3 multiple everywhere.  The (S, C) pair from the 4:2 tree then
has a highly periodic structure; the terminal borrow into the
retained field is computed by a carry-predict over a BOUNDED window
w of the low field, with an assumption bit below.

Config axes:
  topo:   seq42 | tree42          (4:2 compressor orders)
  off:    truncation/predict column = rsh + off, off in {0,2,4,6,8}
  w:      predict window width in bits: 8, 12, 16, 24, 999(=exact)
  asm:    below-window assumed carry: 0 | 1
  corr:   Booth negative-PP correction placement: in-array | dropped
Score vs sampled labeled ties (h528 sampler).
"""
from collections import defaultdict
from multiprocessing import Pool
from h528_structural import row_features
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result


def booth8_pps(x, y, width):
    """radix-8 Booth PPs of x*y (y recoded), digits in {-4..4},
    negatives as complement (+1 correction bit at LSB column when
    corr_in_array).  Returns list of (pp_pos_part, corr_bit_col)."""
    mask = (1 << width) - 1
    x3 = 3 * x
    mult = {0: 0, 1: x, 2: 2 * x, 3: x3, 4: 4 * x}
    pps = []
    y2 = y << 1
    nbits = y.bit_length() + 3
    for i in range(0, nbits, 3):
        quad = (y2 >> i) & 15
        d = {0: 0, 1: 1, 2: 1, 3: 2, 4: 2, 5: 3, 6: 3, 7: 4,
             8: -4, 9: -3, 10: -3, 11: -2, 12: -2, 13: -1, 14: -1,
             15: 0}[quad]
        if d == 0:
            pps.append((0, None))
        elif d > 0:
            pps.append(((mult[d] << i) & mask, None))
        else:
            pps.append((((~(mult[-d]) & mask) << i) & mask, i))
    return pps


def csa(a, b, c, mask):
    return (a ^ b ^ c) & mask, (((a & b) | (a & c) | (b & c)) << 1) \
        & mask


def comp42(a, b, c, d, mask):
    s1, c1 = csa(a, b, c, mask)
    s2, c2 = csa(s1, c1, d, mask)
    return s2, c2


def reduce42(pps, topo, mask):
    v = [p for p in pps if p] or [0]
    if topo == "seq42":
        S, C = v[0], 0
        i = 1
        while i < len(v):
            if i + 1 < len(v):
                S, C = comp42(S, C, v[i], v[i + 1], mask)
                i += 2
            else:
                S, C = csa(S, C, v[i], mask)
                i += 1
        return S, C
    # tree42: pair up leaves
    lvl = v
    while len(lvl) > 2:
        if len(lvl) == 3:
            s, c = csa(lvl[0], lvl[1], lvl[2], mask)
            lvl = [s, c]
            break
        nxt = []
        i = 0
        while i + 3 < len(lvl):
            s, c = comp42(lvl[i], lvl[i + 1], lvl[i + 2],
                          lvl[i + 3], mask)
            nxt.extend((s, c))
            i += 4
        nxt.extend(lvl[i:])
        lvl = nxt
    return (lvl + [0])[:2]


CONFIGS = []
for topo in ("seq42", "tree42"):
    for off in (0, 2, 4, 6, 8):
        for w in (8, 12, 16, 24, 999):
            for asm in (0, 1):
                for corr_in in (True, False):
                    CONFIGS.append((topo, off, w, asm, corr_in))


def score_chunk(args):
    rows, configs = args
    width = 140
    mask = (1 << width) - 1
    res = {cfg: [0, 0, 0, 0] for cfg in configs}
    for mhex, fire in rows:
        (f4s, poss, B_full, rsh, A, P, M, k, R, bshift,
         dist, low3) = row_features(mhex)
        base_pps = booth8_pps(f4s, poss, width)
        pair_cache = {}
        for cfg in configs:
            topo, off, w, asm, corr_in = cfg
            key = (topo, corr_in)
            if key not in pair_cache:
                pps = []
                ncorr = 0
                for pp, ci in base_pps:
                    if ci is not None:
                        if corr_in:
                            pp = pp + (1 << ci)
                        else:
                            ncorr += 1
                    pps.append(pp & mask)
                if not corr_in:
                    # corrections lumped as one extra constant row
                    pps.append(0)
                pair_cache[key] = reduce42(pps, topo, mask)
            S, C = pair_cache[key]
            co = rsh + off
            if co <= 0 or co < w == 999:
                pass
            lowmask = (1 << co) - 1
            S_lo, C_lo = S & lowmask, C & lowmask
            if w >= co:
                carry = (S_lo + C_lo) >> co
            else:
                wmask = (1 << w) - 1
                top_s = (S_lo >> (co - w)) & wmask
                top_c = (C_lo >> (co - w)) & wmask
                carry = (top_s + top_c + asm) >> w
            B_hw67 = ((S >> co) + (C >> co) + carry) \
                & ((1 << (width - co)) - 1)
            B_hw = B_hw67 >> (rsh - co) if co < rsh \
                else B_hw67 << (co - rsh)
            hw_M = A + P - (B_hw << bshift)
            v = hw_M >> k
            p = 0 if v == R else (1 if v == R - 1 else -1)
            if fire:
                res[cfg][3 if p == 1 else 2] += 1
            else:
                res[cfg][0 if p == 0 else 1] += 1
    return res


def main():
    from h528_structural import main as _unused  # noqa
    # reuse h528's sampler inline
    samples = []
    for ties, statpre, stride in (("ties_comb.txt", "comb", 250),
                                  ("ties_comb3.txt", "comb3", 600)):
        rows = []
        seen = set()
        for line in open(ties):
            f = line.split()
            if f[0] in seen:
                continue
            seen.add(f[0])
            rows.append(f)
        inputs = sorted(f[0] for f in rows)
        order = {m: i for i, m in enumerate(inputs)}
        st = {md: open(f"{statpre}_{md}_status.txt").read()
              .splitlines() for md in ROUNDING_MODES}
        for j, f in enumerate(rows):
            if j % stride:
                continue
            R, ce, i = int(f[7], 16), int(f[8]), order[f[0]]
            hw, bad = [], False
            for md in ROUNDING_MODES:
                t = st[md][i].split()
                if t[0] != "OK":
                    bad = True
                    break
                hw.append(int(t[2], 16))
            if bad:
                continue
            clean = [final_cosine_result(-R, ce, md)
                     for md in ROUNDING_MODES]
            fired = [final_cosine_result(-(R - 1), ce, md)
                     for md in ROUNDING_MODES]
            if hw == clean:
                samples.append((f[0], 0))
            elif hw == fired:
                samples.append((f[0], 1))
    print(f"sampled {len(samples)} ties "
          f"({sum(s[1] for s in samples)} fires)")
    chunks = [samples[i::8] for i in range(8)]
    with Pool(8) as pool:
        parts = pool.map(score_chunk,
                         [(ch, CONFIGS) for ch in chunks])
    agg = {cfg: [0, 0, 0, 0] for cfg in CONFIGS}
    for part in parts:
        for cfg, v in part.items():
            for i in range(4):
                agg[cfg][i] += v[i]
    scored = []
    for cfg, (cc, cf, fc, ff) in agg.items():
        ncl, nfi = cc + cf, fc + ff
        if ncl and nfi:
            scored.append((min(cc / ncl, ff / nfi), cc / ncl,
                           ff / nfi, cfg))
    scored.sort(reverse=True)
    print(f"\n{'config':40s} {'clean_acc':>9s} {'fire_acc':>8s}")
    for _, ca, fa, cfg in scored[:20]:
        print(f"{str(cfg):40s} {ca:9.4f} {fa:8.4f}")


if __name__ == "__main__":
    main()
