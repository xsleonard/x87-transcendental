#!/usr/bin/env python3
"""h621: THE SHIRRIFF-ARCHITECTURE HYPOTHESIS, BIT-LEVEL, ON
CLEAN LABELS.

Hypothesis: B = f4*rf is computed radix-8 (hard 3x multiple),
reduced to (S, C); the low rsh columns are NEVER SUMMED — a
carry-predict circuit supplies the carry into the retained
field.  The retained (chopped) product is
  B' = (S >> rsh) + (C >> rsh) + cin_pred,
and the borrow phenomenon = cin_pred errors vs the true carry
  cin_true = ((S & m) + (C & m)) >> rsh,  m = 2^rsh - 1.
Induced terminal deviation: e = cin_pred - cin_true adds
-e * 2^rsh at APf scale, i.e. j_row = -e * 2^(rsh+2) / rfv
ladder units (computed exactly per row).

Predict families (the netlist hypothesis space):
  P0  exact (control: e = 0 everywhere -> const-j)
  W:w   window carry: carry of the top w columns of the low
        field, zeros assumed below (w in 4..24)
  WS:w  window carry with sticky: OR of everything below the
        window forces a generate into the window base
  KS:g  carry-save -> (G, P) per column (G = S&C, P = S^C),
        Kogge-Stone prefix over groups of g columns with
        inter-group carry RIPPLED only once (single-pass
        group chain, no full prefix), g in {4, 8, 16}
  KT:g  same but inter-group combine is a 2-level tree with
        the bottom level truncated (span limit 2g)
Reduction arrangements for (S, C): seq / evenodd / tree(4:2
pairs) over the radix-8 rows, both operand roles.
Score: held-out J-interval hit rate of j0(stratum) + j_row on
the h616+h619 clean labeled rows; baseline = j0 only (0.9232).
An arrangement/predict pair that jumps toward 0.99+ is the
netlist's shadow.  Usage: h621_carry_predict.py [MAXROWS]
"""
import json
import sys
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h577_three_term import E2M
from h453_chain_variants import (C6_1, C6_3, C6_5, C6_2, C6_4,
                                 C6_6, build_chain, mul_round)
from h598_jframe import jinterval

WIDTH = 224
MASK = (1 << WIDTH) - 1
ARRS = ("seq", "eo", "tree", "seq_rf", "tree_rf")
PREDICTS = ([("P0", 0)] +
            [("W", w) for w in (4, 6, 8, 10, 12, 16, 20, 24)] +
            [("WS", w) for w in (4, 6, 8, 10, 12, 16)] +
            [("KS", g) for g in (4, 8, 16)] +
            [("KT", g) for g in (4, 8, 16)])


def csa(a, b, c):
    return (a ^ b ^ c) & MASK, \
        (((a & b) | (a & c) | (b & c)) << 1) & MASK


def booth8_rows(mcand, mplier):
    m3 = 3 * mcand
    y2 = mplier << 1
    rows = []
    pend = 0
    nb = y2.bit_length()
    for i in range(0, max(nb, 1), 3):
        v = (y2 >> i) & 15
        b0, b1, b2, b3 = v & 1, (v >> 1) & 1, (v >> 2) & 1, \
            (v >> 3) & 1
        d = b0 + b1 + 2 * b2 - 4 * b3
        mag = m3 if abs(d) == 3 else abs(d) * mcand
        row = 0
        if d > 0:
            row = (mag << i) & MASK
        elif d < 0:
            row = (((~mag) & MASK) << i) & MASK
        row |= pend
        pend = (1 << i) if d < 0 else 0
        rows.append(row)
    return rows


def reduce_rows(rows, arr):
    if arr.startswith("seq"):
        S = C = 0
        for r in rows:
            S, C = csa(S, C, r)
        return S, C
    if arr == "eo":
        s1 = c1 = s2 = c2 = 0
        for r in rows[0::2]:
            s1, c1 = csa(s1, c1, r)
        for r in rows[1::2]:
            s2, c2 = csa(s2, c2, r)
        s3, c3 = csa(s1, c1, s2)
        return csa(s3, c3, c2)
    # tree: pairwise 4:2 tower
    pairs = []
    rr = rows + [0] * ((-len(rows)) % 4)
    for i in range(0, len(rr), 4):
        s1, c1 = csa(rr[i], rr[i + 1], rr[i + 2])
        pairs.append(csa(s1, c1, rr[i + 3]))
    while len(pairs) > 1:
        nxt = []
        for i in range(0, len(pairs) - 1, 2):
            s1, c1 = csa(pairs[i][0], pairs[i][1],
                         pairs[i + 1][0])
            nxt.append(csa(s1, c1, pairs[i + 1][1]))
        if len(pairs) % 2:
            nxt.append(pairs[-1])
        pairs = nxt
    return pairs[0]


def cin_variants(S, C, rsh):
    m = (1 << rsh) - 1
    Sl, Cl = S & m, C & m
    true = (Sl + Cl) >> rsh
    out = {"P0": true}
    for kind, p in PREDICTS:
        if kind == "P0":
            continue
        if kind in ("W", "WS"):
            w = min(p, rsh)
            Sw = Sl >> (rsh - w)
            Cw = Cl >> (rsh - w)
            base = Sw + Cw
            if kind == "WS":
                below = (Sl | Cl) & ((1 << (rsh - w)) - 1)
                if below:
                    base += 1
            out[f"{kind}:{p}"] = base >> w
        else:
            g = p
            G = Sl & Cl
            P = Sl ^ Cl
            ngr = (rsh + g - 1) // g
            gm = (1 << g) - 1
            carry = 0
            if kind == "KS":
                # two-group lookahead: top group's carry-out
                # with cin = second group's carry-out at cin=0;
                # everything below the two groups assumed 0
                def gco(gi, cin):
                    if gi < 0:
                        return 0
                    Gg = (G >> (gi * g)) & gm
                    Pg = (P >> (gi * g)) & gm
                    return 1 if ((Gg * 2 + Pg + cin) >> g) \
                        else 0
                c2 = gco(ngr - 2, 0)
                out[f"KS:{g}"] = gco(ngr - 1, c2)
            else:
                # KT: two-level, spans limited to 2g; groups
                # beyond distance 2g from the top cannot
                # propagate into the final carry
                top = max(0, rsh - 2 * g)
                Gt = G >> top
                Pt = P >> top
                w2 = rsh - top
                tot = Gt * 2 + Pt
                out[f"KT:{g}"] = 1 if (tot >> w2) else 0
    return out, true


def row_feats(args):
    m, key, hw = args
    mag = (0, E2M, m)
    sq = mul_round(mag, mag, 67, "chop")
    f4 = mul_round(sq, sq, 67, "chop")
    neg = build_chain(f4, C6_5, C6_3, C6_1, 67, 64, "rn",
                      False, False, False)
    pos = build_chain(f4, C6_6, C6_4, C6_2, 67, 64, "rn",
                      False, False, False)
    B_full = f4[2] * pos[2]
    rsh = B_full.bit_length() - 67
    left = mul_round(sq, neg, 67, "chop")
    right = mul_round(f4, pos, 67, "chop")
    low3 = sq[2] & 7
    dist = abs(left[1] - right[1])
    payload = low3 + 8 - dist
    scale = min(left[1], right[1], left[1] - 8)
    A = left[2] << (left[1] - scale)
    P = payload << (left[1] - 8 - scale)
    M = A + P - (right[2] << (right[1] - scale))
    k = M.bit_length() - 67
    ce = scale + k
    bshift = right[1] - scale
    F = rsh - bshift
    kf = k + F
    APf = (A + P) << F
    EU = (APf - B_full) >> kf
    Vlow = (APf - B_full) - (EU << kf)
    ivs = []
    for z in (-2, -1, 0, 1, 2):
        refs = [final_cosine_result(-(EU + z), ce, md)
                for md in ROUNDING_MODES]
        if refs == hw:
            lo, hi = jinterval(Vlow, kf, pos[2], z)
            if lo <= hi:
                ivs.append((lo, hi))
    if not ivs:
        return None
    jlo = min(l for l, h in ivs)
    jhi = max(h for l, h in ivs)
    half = (m * 2654435761 >> 16) & 1
    ju = (1 << (rsh + 2)) / pos[2]  # ladder units per e
    es = {}
    for arr in ARRS:
        role_rf = arr.endswith("_rf")
        mcand, mplier = ((pos[2], f4[2]) if role_rf
                         else (f4[2], pos[2]))
        rows = booth8_rows(mcand, mplier)
        S, C = reduce_rows(rows, arr.replace("_rf", ""))
        cins, true = cin_variants(S, C, rsh)
        for name, cp in cins.items():
            es[(arr, name)] = -(cp - true) * ju
    return (key, half, jlo, jhi, es)


def main():
    maxrows = int(sys.argv[1]) if len(sys.argv) > 1 else 40000
    rows = []
    locked = json.load(open("h616_locked.json"))
    st6 = {md: open(f"h616_{md}_status.txt").read()
           .splitlines() for md in ROUNDING_MODES}
    for i, rec in enumerate(locked):
        hw = [int(st6[md][i].split()[2], 16)
              for md in ROUNDING_MODES]
        rows.append((int(rec["m"], 16), tuple(rec["key"]), hw))
    recs = json.load(open("h619_rows.json"))
    st9 = {md: open(f"h619_{md}_status.txt").read()
           .splitlines() for md in ROUNDING_MODES}
    for i, rec in enumerate(recs):
        t = [st9[md][i].split() for md in ROUNDING_MODES]
        if any(x[0] != "OK" for x in t):
            continue
        rows.append((int(rec["m"], 16), tuple(rec["key"]),
                     [int(x[2], 16) for x in t]))
    per = defaultdict(int)
    sel = []
    for r in sorted(rows, key=lambda r: (r[0] * 2654435761)
                    & 0xFFFFFFFF):
        if per[r[1]] >= maxrows // 60:
            continue
        per[r[1]] += 1
        sel.append(r)
        if len(sel) >= maxrows:
            break
    print(f"rows: {len(sel)}", flush=True)
    with Pool(14) as pool:
        fs = pool.map(row_feats, sel, chunksize=50)
    fs = [f for f in fs if f is not None]
    print(f"usable: {len(fs)}", flush=True)
    variants = sorted({v for f in fs for v in f[4]}, key=str)
    print(f"variants: {len(variants)}", flush=True)
    out = []
    for var in variants:
        ev = defaultdict(list)
        for key, half, jlo, jhi, es in fs:
            if half:
                continue
            x = es[var]
            ev[key].append((jlo - 0.5 - x, 1))
            ev[key].append((jhi + 0.5 - x, -1))
        betas = {}
        for key, e in ev.items():
            e.sort()
            cur, bc, bb = 0, -1, 0.0
            for p, d in e:
                cur += d
                if cur > bc:
                    bc, bb = cur, p + 1e-9
            betas[key] = bb
        ok = n = 0
        for key, half, jlo, jhi, es in fs:
            if not half:
                continue
            n += 1
            j = round(es[var] + betas.get(key, 0))
            ok += jlo <= j <= jhi
        out.append((ok / max(n, 1), var))
    out.sort(reverse=True)
    base = [a for a, v in out if v[1] == "P0"]
    print(f"\ncontrol (exact carry, const-j): "
          f"{base[0] if base else '?':.4f}")
    print("TOP 15:")
    for acc, var in out[:15]:
        print(f"  {acc:.4f}  {var}")
    print("BOTTOM 5:")
    for acc, var in out[-5:]:
        print(f"  {acc:.4f}  {var}")


if __name__ == "__main__":
    main()
