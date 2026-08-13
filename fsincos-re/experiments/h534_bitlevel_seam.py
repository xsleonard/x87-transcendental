#!/usr/bin/env python3
"""h534: BIT-LEVEL ITERATIVE-SEAM MODEL (Tan/Lemonds/Schulte
architecture; Intel P4-style 2-pass EP variant included).

B = f4 * rf computed in passes over multiplier chunks (low chunk
first).  Per pass: radix-4 Booth PPs (hardware encoding: complement
+ hot-one as separate array entries), 4:2/3:2 tree -> CS pair;
feedback of the upper CS pair; the low `pb` columns RETIRE per pass
with a seam-carry.  Convention corners (the candidate gate):
  ovl:  pass-2 Booth overlap bit B[pb-1]: used | zeroed
  hot:  pass-2 hot-ones landing below the seam: kept (added into
        retired chunk resolve) | dropped
  fbs:  feedback sign-extension exact | off-by-one at seam
  seam: retired-chunk resolve: exact | window-8 with asm 0/1
Score against sampled all-theta comb-7 chop labels; verify the
exact-convention control reproduces hardware-clean everywhere.
"""
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h528_structural import row_features

WIDTH = 200
MASK = (1 << WIDTH) - 1

CONFIGS = []
for pb in (26, 27, 28, 32, 34, 37, 38, 53, 54):
    for mult in ("rf", "f4"):
        for ovl in ("used", "zeroed"):
            for hot in ("kept", "dropped"):
                for fbs in ("exact", "off1"):
                    for seam in ("exact", "win8a0"):
                        CONFIGS.append((pb, mult, ovl, hot, fbs,
                                        seam))


def booth4_pps(x, y_chunk, base_col, ovl_bit, width):
    """radix-4 Booth PPs of x * (y_chunk << base_col) with the
    overlap bit supplied explicitly.  Hardware encoding: negative
    digits contribute (complement_part, hot_one_column)."""
    mask = (1 << width) - 1
    out = []
    y2 = (y_chunk << 1) | (ovl_bit & 1)
    nb = y_chunk.bit_length() + 2
    for i in range(0, nb, 2):
        trip = (y2 >> i) & 7
        d = {0: 0, 1: 1, 2: 1, 3: 2, 4: -2, 5: -1, 6: -1, 7: 0}[trip]
        col = base_col + i
        if d == 0:
            continue
        if d > 0:
            out.append(((d * x << col) & mask, None))
        else:
            # complement under the full-width mask, THEN shift (low
            # columns stay zero); hot-one rides at the PP LSB column;
            # the 2^WIDTH excess cancels mod 2^WIDTH (h530 form)
            out.append(((((~((-d) * x)) & mask) << col) & mask, col))
    return out


def csa(a, b, c, mask):
    return (a ^ b ^ c) & mask, (((a & b) | (a & c) | (b & c)) << 1) \
        & mask


def reduce_tree(addends, mask):
    lvl = [a for a in addends if a] or [0]
    while len(lvl) > 2:
        if len(lvl) == 3:
            s, c = csa(lvl[0], lvl[1], lvl[2], mask)
            return s, c
        nxt = []
        i = 0
        while i + 2 < len(lvl):
            s, c = csa(lvl[i], lvl[i + 1], lvl[i + 2], mask)
            nxt.extend((s, c))
            i += 3
        nxt.extend(lvl[i:])
        lvl = nxt
    return (lvl + [0])[:2]


def simulate(f4s, poss, cfg):
    """Fixed absolute-column frame: pass-2 PPs generated at their
    true columns; retirement clears the low field in place; the seam
    carry re-enters pass 2 as an addend at the seam column."""
    pb, mult, ovl, hot, fbs, seam = cfg
    if mult == "f4":
        f4s, poss = poss, f4s
    chunks = [(0, pb), (pb, poss.bit_length())]
    S = C = 0
    retired_val = 0
    for ci, (lo, hi) in enumerate(chunks):
        y_chunk = (poss >> lo) & ((1 << (hi - lo)) - 1)
        ovl_bit = ((poss >> (lo - 1)) & 1) if (lo > 0 and
                                              ovl == "used") else 0
        pps = booth4_pps(f4s, y_chunk, lo, ovl_bit, WIDTH)
        addends = [S, C]
        for pi, (pp, hcol) in enumerate(pps):
            addends.append(pp)
            if hcol is None:
                continue
            if ci > 0 and pi == 0 and hcol == lo and hot == "dropped":
                continue          # boundary hot-one lost at the seam
            addends.append(1 << hcol)
        if ci > 0 and fbs == "off1":
            addends.append((-(1 << lo)) % (1 << WIDTH))
        S, C = reduce_tree(addends, MASK)
        if ci + 1 < len(chunks):
            rl = chunks[ci + 1][0]
            lowm = (1 << rl) - 1
            s_lo, c_lo = S & lowm, C & lowm
            tot = s_lo + c_lo
            if seam == "exact":
                cout = tot >> rl
            else:
                w = 8
                asm = 1 if seam.endswith("a1") else 0
                cout = ((s_lo >> (rl - w)) + (c_lo >> (rl - w))
                        + asm) >> w
            retired_val = tot & lowm
            S &= ~lowm
            C &= ~lowm
            if cout:
                S, C = csa(S, C, cout << rl, MASK)
    B_model = ((S + C) & MASK) + retired_val
    return B_model


def simulate_pair(f4s, poss, cfg):
    """Same passes with EXACT conventions; returns the FINAL CS pair
    (S, C, retired_val) BEFORE resolution — the terminal's operand
    form under the iterative hypothesis."""
    pb, mult = cfg
    if mult == "f4":
        f4s, poss = poss, f4s
    chunks = [(0, pb), (pb, poss.bit_length())]
    S = C = 0
    retired_val = 0
    for ci, (lo, hi) in enumerate(chunks):
        y_chunk = (poss >> lo) & ((1 << (hi - lo)) - 1)
        pps = booth4_pps(f4s, y_chunk, lo, 0, WIDTH)
        addends = [S, C]
        for pp, hcol in pps:
            addends.append(pp)
            if hcol is not None:
                addends.append(1 << hcol)
        S, C = reduce_tree(addends, MASK)
        if ci + 1 < len(chunks):
            rl = chunks[ci + 1][0]
            lowm = (1 << rl) - 1
            tot = (S & lowm) + (C & lowm)
            retired_val = tot & lowm
            cout = tot >> rl
            S &= ~lowm
            C &= ~lowm
            if cout:
                S, C = csa(S, C, cout << rl, MASK)
    return S, C, retired_val


def hot_dropped_variant(f4s, poss, cfg):
    return simulate(f4s, poss, cfg)


def score_chunk(args):
    rows, configs = args
    res = {cfg: defaultdict(int) for cfg in configs}
    for mhex, theta, lab in rows:
        (f4s, poss, B_full, rsh, A, P, M, k, R, bshift,
         dist, low3) = row_features(mhex)
        for cfg in configs:
            B_model = hot_dropped_variant(f4s, poss, cfg)
            d67 = (B_model >> rsh) - (B_full >> rsh)
            pred = ("clean" if d67 == 0 else
                    "down" if d67 == 1 else
                    "up" if d67 == -1 else "far")
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
    # control check first: exact conventions must equal B_full
    ctrl_bad = 0
    for mhex, _, _ in rows[:50]:
        (f4s, poss, B_full, rsh, *_rest) = row_features(mhex)
        Bm = simulate(f4s, poss, (27, "rf", "zeroed", "kept",
                                  "exact", "exact"))
        if Bm != B_full:
            ctrl_bad += 1
    print(f"control (exact conventions) mismatches: {ctrl_bad}/50")
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
    for _, ca, fa, cfg in scored[:24]:
        print(f"{str(cfg):44s} {ca:9.4f} {fa:8.4f}")


if __name__ == "__main__":
    main()
