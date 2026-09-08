#!/usr/bin/env python3
"""h533: ITERATIVE-SEAM structural model (arXiv:1110.4675 template).

The multiplier computes B = f4*rf iteratively: radix-4 Booth PPs of
one multiplier CHUNK per iteration (low chunk first), 4:2 tree, the
product kept in carry-save; each iteration RETIRES the lowest
`stride` columns into an iterative (carry, sticky) summary via a
seam-resolve; the upper CS pair feeds back.  Gate hypothesis: the
seam resolve mishandles, by one unit, the interaction of (incoming
carry, Booth hot-ones landing at/below the seam, feedback sign-carry)
under parameterized conventions; the terminal subtract then sees B
off by one ulp of the retained product — fire R-1/R+1.

Config axes:
  stride: 24 | 27 | 32   (columns retired per iteration)
  phase:  seam alignment relative to the product LSB: 0 | half | u
          (u = the M-unit column — le2-anchored)
  hot:    hot-ones of NEXT chunk's negative digits land in the
          retiring chunk: counted | dropped
  fbc:    the tree's combined sign-carry bit rides in feedback:
          yes | no
  resolve: seam carry from full chunk add (exact) | top-8 window
Score on sampled comb-7 all-theta chop labels (h532 sampler).
"""
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h528_structural import row_features

CONFIGS = []
for stride in (24, 27, 32):
    for phase in ("zero", "half", "unit"):
        for hot in ("counted", "dropped"):
            for fbc in ("yes", "no"):
                for resolve in ("exact", "win8"):
                    CONFIGS.append((stride, phase, hot, fbc, resolve))


def booth4_chunk_pps(x, y, lo, hi, width):
    """radix-4 Booth PPs for multiplier bits [lo, hi) of y, hardware
    encoding: positive part and hot-one column separately."""
    mask = (1 << width) - 1
    pps = []
    y2 = y << 1
    for i in range(lo, hi, 2):
        trip = (y2 >> i) & 7
        d = {0: 0, 1: 1, 2: 1, 3: 2, 4: -2, 5: -1, 6: -1, 7: 0}[trip]
        if d == 0:
            continue
        if d > 0:
            pps.append(((d * x << i) & mask, None))
        else:
            pps.append((((~((-d) * x) & mask) << i) & mask
                        | 0, i))
    return pps


def simulate(f4s, poss, cfg, width=140):
    """Iterative accumulation; returns B_model (integer) = the
    resolved product INCLUDING seam-carry conventions, plus exact
    B for comparison."""
    stride, phase, hot, fbc, resolve = cfg
    mask = (1 << width) - 1
    nbits = poss.bit_length() + 2
    chunks = []
    lo = 0
    while lo < nbits:
        chunks.append((lo, min(lo + stride, nbits)))
        lo += stride
    S = C = 0
    retired = 0           # resolved retired bits (value, aligned)
    ret_carry = 0
    ret_col = 0
    exact = f4s * poss
    for ci, (lo, hi) in enumerate(chunks):
        pps = booth4_chunk_pps(f4s, poss, lo, hi, width)
        addends = [S, C]
        for pp, hcol in pps:
            addends.append(pp)
            if hcol is not None:
                if hot == "counted" or hcol >= ret_col + stride:
                    addends.append(1 << hcol)
                elif hcol >= ret_col:
                    addends.append(1 << hcol)
                # hot below current retire window: dropped
        acc = sum(addends) & mask
        # (value-level accumulate; CS structure matters only at the
        # seam resolve, modeled via the carry conventions below)
        seam = ret_col + stride
        low = (acc + (ret_carry << ret_col)) & ((1 << seam) - 1)
        low_chunk = low >> ret_col
        if resolve == "exact":
            cout = (low_chunk >> stride) & 1
            keep = low_chunk & ((1 << stride) - 1)
        else:
            w = 8
            top = (low_chunk >> max(0, stride - w))
            cout = (top + 1) >> min(stride, w) if fbc == "yes" \
                else top >> min(stride, w)
            cout &= 1
            keep = low_chunk & ((1 << stride) - 1)
        retired |= keep << ret_col
        ret_carry = cout
        ret_col = seam
        S = (acc >> ret_col) << ret_col
        C = 0
        if fbc == "no" and ci + 1 < len(chunks):
            # feedback loses the sign-carry bit: subtract one unit
            # at the seam column from the running sum
            S = (S - (1 << ret_col)) & mask
    B_model = (S | retired) + (ret_carry << ret_col)
    return B_model, exact


def score_chunk(args):
    rows, configs = args
    res = {cfg: defaultdict(int) for cfg in configs}
    for mhex, theta, lab in rows:
        (f4s, poss, B_full, rsh, A, P, M, k, R, bshift,
         dist, low3) = row_features(mhex)
        for cfg in configs:
            B_model, exact = simulate(f4s, poss, cfg)
            dB = B_model - exact
            # B off by delta units at LSB -> chop67 may shift by 1
            b_chop_model = B_model >> rsh
            b_chop = exact >> rsh
            d67 = b_chop_model - b_chop
            if d67 == 0:
                pred = "clean"
            elif d67 == 1:
                pred = "down"     # B larger -> M smaller -> R-1
            elif d67 == -1:
                pred = "up"
            else:
                pred = "far"
            res[cfg][(lab, pred)] += 1
    return res


def main():
    rows = []
    seen = set()
    raw = []
    for line in open("ties_comb7.txt"):
        f = line.split()
        if f[0] in seen:
            continue
        seen.add(f[0])
        raw.append(f)
    inputs = sorted(f[0] for f in raw)
    order = {m: i for i, m in enumerate(inputs)}
    st = {md: open(f"comb7_{md}_status.txt").read().splitlines()
          for md in ROUNDING_MODES}
    for j, f in enumerate(raw):
        if j % 400:
            continue
        R, ce, theta = int(f[7], 16), int(f[8]), int(f[9])
        i = order[f[0]]
        hw, bad = [], False
        for md in ROUNDING_MODES:
            t = st[md][i].split()
            if t[0] != "OK":
                bad = True
                break
            hw.append(int(t[2], 16))
        if bad:
            continue
        refs = {name: [final_cosine_result(-(R + d), ce, md)
                       for md in ROUNDING_MODES]
                for name, d in (("clean", 0), ("down", -1),
                                ("up", 1))}
        for name in ("clean", "down", "up"):
            if hw == refs[name]:
                rows.append((f[0], theta, name))
                break
    print(f"sampled {len(rows)} rows")
    chunks = [rows[i::8] for i in range(8)]
    with Pool(8) as pool:
        parts = pool.map(score_chunk,
                         [(ch, CONFIGS) for ch in chunks])
    agg = {cfg: defaultdict(int) for cfg in CONFIGS}
    for part in parts:
        for cfg, d in part.items():
            for kk, v in d.items():
                agg[cfg][kk] += v
    scored = []
    for cfg, d in agg.items():
        n = sum(d.values())
        fire_n = sum(v for (lab, _), v in d.items()
                     if lab != "clean")
        fire_right = sum(v for (lab, pred), v in d.items()
                         if lab != "clean" and lab == pred)
        clean_n = n - fire_n
        clean_right = d.get(("clean", "clean"), 0)
        if clean_n and fire_n:
            scored.append((min(clean_right / clean_n,
                               fire_right / fire_n),
                           clean_right / clean_n,
                           fire_right / fire_n, cfg))
    scored.sort(reverse=True)
    print(f"\n{'config':44s} {'clean_acc':>9s} {'fire_acc':>8s}")
    for _, ca, fa, cfg in scored[:20]:
        print(f"{str(cfg):44s} {ca:9.4f} {fa:8.4f}")


if __name__ == "__main__":
    main()
