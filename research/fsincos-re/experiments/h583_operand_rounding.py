#!/usr/bin/env python3
"""h583: OPERAND-ROUNDING SEMANTICS — the possible endgame.

h581 decode: pinned thresholds are rsh-RELATIVE: T = rdisc
(chopped-B semantics = replica), T = rdisc/2 (round-to-nearest
B).  Test the pure semantic model: hardware result =
  (A'(+P) - B') >> kf
with each product independently re-rounded at 67 bits:
  conventions: chop, rn_up (half rounds up), rn_even, ceil, exact
  (exact = keep full product, no rounding)
Left product L (-> A) and right product B each get a convention;
25 combos; score EXACT res match per (stratum, side) on comb-7
near-ties (all theta).  No thresholds, no fitted constants.
"""
import sys
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h453_chain_variants import (C6_1, C6_2, C6_3, C6_4, C6_5,
                                 C6_6, build_chain, mul_round)

E2M = -66
CONVS = ("chop", "rnup", "rnev", "ceil", "exact")


def rrnd(full, sh, conv):
    """Return (value_scaled_by_2^sh_kept_exact) as integer at
    full scale: rounded-to-67-bits value << sh, or full for
    'exact'."""
    if conv == "exact":
        return full
    hi = full >> sh
    disc = full & ((1 << sh) - 1)
    if conv == "chop":
        pass
    elif conv == "rnup":
        hi += 1 if disc >= (1 << (sh - 1)) else 0
    elif conv == "rnev":
        half = 1 << (sh - 1)
        if disc > half or (disc == half and (hi & 1)):
            hi += 1
    elif conv == "ceil":
        hi += 1 if disc else 0
    return hi << sh


def work(rows):
    cen = defaultdict(int)
    for mhex, theta, lab, ce in rows:
        m = int(mhex, 16)
        mag = (0, E2M, m)
        sq = mul_round(mag, mag, 67, "chop")
        f4 = mul_round(sq, sq, 67, "chop")
        neg = build_chain(f4, C6_5, C6_3, C6_1, 67, 64, "rn",
                          False, False, False)
        pos = build_chain(f4, C6_6, C6_4, C6_2, 67, 64, "rn",
                          False, False, False)
        low3 = sq[2] & 7
        L_full = sq[2] * neg[2]
        lsh = L_full.bit_length() - 67
        B_full = f4[2] * pos[2]
        rsh = B_full.bit_length() - 67
        left = mul_round(sq, neg, 67, "chop")
        right = mul_round(f4, pos, 67, "chop")
        dist = abs(left[1] - right[1])
        payload = low3 + 8 - dist
        scale = min(left[1], right[1], left[1] - 8)
        lshift = left[1] - scale
        bshift = right[1] - scale
        P = payload << (left[1] - 8 - scale)
        A0 = left[2] << lshift
        M = A0 + P - (right[2] << bshift)
        k = M.bit_length() - 67
        R = M >> k
        res_hw = R + {"clean": 0, "down": -1, "up": 1}[lab]
        F = rsh - bshift
        if F < 0:
            continue
        kf = k + F
        FL = lsh - lshift  # scale factor for left full product
        if FL < 0:
            continue
        strat = (dist, low3, ce)
        side = "up" if theta <= 0 else "dn"
        # frame: everything << F relative to raw B units
        # A' from L_full rounded: rrnd(L_full, lsh, conv) is at
        # raw L scale; A0<<F == (L_chop>>lsh<<lsh)<<F/2^... :
        # left[2] = L_full >> lsh (chop);  A0 = left[2] << lshift
        # so A' = (rrnd(L)>>lsh) << lshift ; exact: needs frac —
        # use common denominator 2^(lsh - lshift) = 2^FL:
        # A'_num = rrnd(L) >> (lsh - lshift)?? keep exact:
        # compute in units of 2^-FL of A-scale: A'_u =
        # rrnd(L, lsh, conv) (raw L units) ; A-scale unit =
        # 2^lshift = raw L * 2^-FL... So express the subtract at
        # raw-L-<<F... Simplest: common frame = raw L units << F2
        # where everything integer:
        for cl in CONVS:
            Lr = rrnd(L_full, lsh, cl)  # raw L units
            for cb in CONVS:
                Br = rrnd(B_full, rsh, cb)  # raw B units
                # A-frame: A0 = (L>>lsh)<<lshift ; raw L unit =
                # 2^(lshift-lsh) of A units -> A' = Lr *
                # 2^(lshift-lsh) = Lr >> FL (may drop bits if
                # not multiple — Lr is multiple of 2^lsh unless
                # exact)
                if cl == "exact":
                    num = (Lr << F) + ((P + 0) << (FL + F)) \
                        - (Br << FL)
                    den = kf + FL
                else:
                    Ar = Lr >> FL if FL >= 0 else Lr << -FL
                    # Lr multiple of 2^lsh, FL = lsh-lshift
                    # so Lr>>FL exact multiple of 2^lshift
                    num = ((Ar + P) << F) - Br
                    den = kf
                res = num >> den
                cen[(strat, side, cl, cb,
                     res == res_hw)] += 1
    return dict(cen)


def main():
    seen = set()
    raw = []
    for line in open("ties_comb7.txt"):
        f = line.split()
        if f[0] in seen:
            continue
        seen.add(f[0])
        raw.append(f)
    inputs = sorted(f[0] for f in raw)
    order = {m2: i for i, m2 in enumerate(inputs)}
    st = {md: open(f"comb7_{md}_status.txt").read().splitlines()
          for md in ROUNDING_MODES}
    stride = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    labeled = []
    for j, f in enumerate(raw):
        if j % stride:
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
                labeled.append((f[0], theta, name, ce))
                break
    print(f"labeled sample: {len(labeled)}", flush=True)
    chunks = [labeled[i::8] for i in range(8)]
    with Pool(8) as pool:
        parts = pool.map(work, chunks)
    cen = defaultdict(int)
    for part in parts:
        for kk, v in part.items():
            cen[kk] += v
    keys = sorted(set((kk[0], kk[1]) for kk in cen))
    for strat, side in keys:
        tot = defaultdict(lambda: [0, 0])
        for cl in CONVS:
            for cb in CONVS:
                good = cen.get((strat, side, cl, cb, True), 0)
                bad = cen.get((strat, side, cl, cb, False), 0)
                tot[(cl, cb)] = [good, good + bad]
        ranked = sorted(tot.items(),
                        key=lambda x: -(x[1][0] /
                                        max(x[1][1], 1)))
        n = ranked[0][1][1]
        line = [f"{str((strat, side)):22s} n={n:6d}"]
        for (cl, cb), (g, nn) in ranked[:3]:
            line.append(f"L={cl}/B={cb}:{g/max(nn,1):.5f}")
        print("  ".join(line))


if __name__ == "__main__":
    main()
