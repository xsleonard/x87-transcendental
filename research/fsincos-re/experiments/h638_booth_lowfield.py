#!/usr/bin/env python3
"""h638: Booth generate-column model, stage 2 — real digits, real low field.

h637 confirmed the BASIS (the low3 tilt is the lowest radix-8 Booth digit
d0 of the f4 = sq*sq multiply: sign gate exact; 1/s = 23.36 + 2.85*d0 on
the pencil) but tested d0 only as a proxy and only CONJECTURED that the
XD 1/3-2/3 pivot zones are the next digit d1.

PART 1 (this script, tree-free and decisive):
  - rebuild the dist-9 window rows with full INTEGER internals (sq, f4,
    rprod, pos, fourth) — cached to h638_rows.pkl, verified against the
    h628 feature cache row-by-row;
  - compute the ACTUAL radix-8 Booth digits: d1, d2 of sq (the sq*sq
    multiply) and the low digits of pos[2] / fourth[2] (the rprod
    multiply whose discard is XD; pos ~ 0x5555... is the natural home
    of thirds);
  - crosstab each digit against the XD-third branches, then refit the
    (XT, m) boundary per (low3, digit) stratum vs per (low3, XD-third):
    if a digit IS the zone selector, conditioning on it must reproduce
    (or sharpen) the h518 branch structure.

Run from /tmp/stageA.  Booth recode verified exactly per row.
"""
import os, pickle, sys
from collections import defaultdict, Counter
from multiprocessing import Pool

sys.path.insert(0, "/Users/steve/llm/x87-transcendental/fsincos-re/experiments")
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h453_chain_variants import (C6_1, C6_2, C6_3, C6_4, C6_5, C6_6,
                                 build_chain, mul_round)

E2M = -66
SC = 60
TIES = "ties_comb4.txt"
PREFIX = "comb4"
FEATCACHE = "h628_feats.pkl"
ROWCACHE = "h638_rows.pkl"


# ---------- labels (verbatim from h636/h628) ----------
def load():
    rows, seen = [], set()
    for lineS in open(TIES):
        f = lineS.split()
        if f[0] in seen:
            continue
        seen.add(f[0])
        rows.append(f)
    inputs = sorted(f[0] for f in rows)
    order = {mm: i for i, mm in enumerate(inputs)}
    st = {md: open(f"{PREFIX}_{md}_status.txt").read().splitlines()
          for md in ROUNDING_MODES}
    out = []
    for f in rows:
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
        clean = [final_cosine_result(-R, ce, md) for md in ROUNDING_MODES]
        fired = [final_cosine_result(-(R - 1), ce, md) for md in ROUNDING_MODES]
        if hw == clean:
            out.append((f[0], False))
        elif hw == fired:
            out.append((f[0], True))
    return out


# ---------- integer internals for one row ----------
def internals(args):
    mhex, fire = args
    m = int(mhex, 16)
    mag = (0, E2M, m)
    square = mul_round(mag, mag, 67, "chop")
    fourth = mul_round(square, square, 67, "chop")
    neg = build_chain(fourth, C6_5, C6_3, C6_1, 67, 64, "rn", False, False, False)
    pos = build_chain(fourth, C6_6, C6_4, C6_2, 67, 64, "rn", False, False, False)
    left = mul_round(square, neg, 67, "chop")
    right = mul_round(fourth, pos, 67, "chop")
    dist = abs(left[1] - right[1])
    sq = square[2]
    f4 = sq * sq
    s4 = f4.bit_length() - 67
    t4 = f4 & ((1 << s4) - 1)
    XT = ((t4 << SC) >> s4) / 2**SC
    rprod = fourth[2] * pos[2]
    sR = rprod.bit_length() - 67
    rdisc = rprod & ((1 << sR) - 1)
    XD = ((rdisc << SC) >> sR) / 2**SC
    return (mhex, int(fire), dist, sq, fourth[2], pos[2], neg[2],
            s4, XT, sR, XD, m / 2**64)


def booth8(y, ndig):
    """Radix-8 Booth digits of integer y (LSB first), exact recode."""
    ds = []
    prev = 0
    for i in range(ndig):
        trip = (y >> (3 * i)) & 7
        d = trip + prev - (8 if trip >= 4 else 0)
        ds.append(d)
        prev = (y >> (3 * i + 2)) & 1
    return ds


# ---------- boundary fitter (h627-corrected, as h637) ----------
def best_c(pts, s):
    arr = sorted((y - s * x, fr) for x, y, fr in pts)
    n = len(arr); tot1 = sum(fr for _, fr in arr)
    below1, above0 = 0, n - tot1
    b1 = (n + 1, None)
    for idx in range(n + 1):
        e = below1 + above0
        if e < b1[0]:
            rlo = arr[idx - 1][0] if idx > 0 else arr[0][0] - 1e-9
            rhi = arr[idx][0] if idx < n else arr[-1][0] + 1e-9
            b1 = (e, 0.5 * (rlo + rhi))
        if idx < n:
            _, fr = arr[idx]
            below1 += fr; above0 -= (1 - fr)
    below0, above1 = 0, tot1
    b2 = (n + 1, None)
    for idx in range(n + 1):
        e = below0 + above1
        if e < b2[0]:
            rlo = arr[idx - 1][0] if idx > 0 else arr[0][0] - 1e-9
            rhi = arr[idx][0] if idx < n else arr[-1][0] + 1e-9
            b2 = (e, 0.5 * (rlo + rhi))
        if idx < n:
            _, fr = arr[idx]
            below0 += (1 - fr); above1 -= fr
    return b1 if b1[0] <= b2[0] else b2


def fit(pts, slo=-0.05, shi=0.40):
    best = (len(pts) + 1, None, None)
    lo, hi, step = slo, shi, (shi - slo) / 380
    for _ in range(4):
        loc = (len(pts) + 1, None, None); si = lo
        while si <= hi:
            e, c = best_c(pts, si)
            if e < loc[0]:
                loc = (e, si, c)
            si += step
        best = loc
        lo, hi, step = best[1] - step, best[1] + step, step / 10
    return best


def build_rows():
    labeled = load()
    print(f"labeled rows: {len(labeled)}", flush=True)
    feats = pickle.load(open(FEATCACHE, "rb"))
    assert len(feats) == len(labeled), (len(feats), len(labeled))
    sel = [i for i, (dist, low3, s4, XT, XTabs, XD, mf, fire) in enumerate(feats)
           if dist == 9 and 0.656 <= mf < 0.938]
    print(f"dist-9 window rows: {len(sel)}", flush=True)
    todo = [labeled[i] for i in sel]
    with Pool(8) as pool:
        rows = pool.map(internals, todo, chunksize=500)
    # verify against the feature cache row-by-row
    nver = 0
    for i, r in zip(sel, rows):
        dist, low3, s4, XT, XTabs, XD, mf, fire = feats[i]
        (mhex, rfire, rdist, sq, f2, p2, n2, rs4, rXT, sR, rXD, rmf) = r
        assert rdist == dist and rs4 == s4 and rfire == fire
        assert (sq & 7) == low3
        assert abs(rXT - XT) < 1e-12 and abs(rXD - XD) < 1e-12
        nver += 1
    print(f"verified {nver} rows against h628 cache", flush=True)
    with open(ROWCACHE, "wb") as fh:
        pickle.dump(rows, fh)
    return rows


def main():
    if os.path.exists(ROWCACHE):
        rows = pickle.load(open(ROWCACHE, "rb"))
        print(f"loaded {len(rows)} rows from {ROWCACHE}")
    else:
        rows = build_rows()

    # Booth digit features + exact recode verification
    enriched = []
    for (mhex, fire, dist, sq, f2, p2, n2, s4, XT, sR, XD, mf) in rows:
        ds = booth8(sq, 23)
        assert sum(d << (3 * i) for i, d in enumerate(ds)) == sq
        dp = booth8(p2, 23)
        assert sum(d << (3 * i) for i, d in enumerate(dp)) == p2
        df = booth8(f2, 23)
        assert sum(d << (3 * i) for i, d in enumerate(df)) == f2
        third = 0 if XD < 1/3 else (1 if XD < 2/3 else 2)
        enriched.append(dict(fire=fire, sq=sq, f2=f2, p2=p2, s4=s4,
                             XT=XT, XD=XD, mf=mf, low3=sq & 7,
                             d0=ds[0], d1=ds[1], d2=ds[2],
                             p0=dp[0], p1=dp[1], f0=df[0], f1=df[1],
                             third=third))
    print(f"Booth recode verified exactly on {len(enriched)} rows "
          f"(sq, pos, fourth)\n")

    side = lambda r: r["s4"]  # 66 = above pivot

    # ---- crosstabs: which digit tracks the XD third? ----
    for dig in ("d1", "d2", "p0", "p1", "f0", "f1"):
        tab = defaultdict(Counter)
        for r in enriched:
            if r["s4"] != 66:
                continue
            tab[(r["low3"], r[dig])][r["third"]] += 1
        # summarize concentration: fraction of rows in the modal third
        tot = conc = 0
        for k, c in tab.items():
            n = sum(c.values()); tot += n; conc += c.most_common(1)[0][1]
        print(f"{dig}: modal-third concentration "
              f"{conc}/{tot} = {conc/tot:.3f}" if tot else f"{dig}: empty")
    print()

    # ---- baseline: per (low3, third) fits on s4=66 (h518 frame) ----
    def fit_table(keyfn, label, keys=None):
        strata = defaultdict(list)
        for r in enriched:
            if r["s4"] != 66:
                continue
            strata[keyfn(r)].append((r["XT"], r["mf"], r["fire"]))
        print(f"=== {label} (s4=66) ===")
        print(f"{'stratum':>14} {'n':>7} {'frac':>6} {'errs':>6} "
              f"{'slope':>10} {'pivot':>10} {'1/s':>9}")
        out = {}
        for k in sorted(strata, key=str) if keys is None else keys:
            pts = strata.get(k, [])
            if len(pts) < 250:
                print(f"{str(k):>14} {len(pts):>7}  (sparse)")
                continue
            frv = sum(p[2] for p in pts) / len(pts)
            if min(frv, 1 - frv) < 0.02:
                print(f"{str(k):>14} {len(pts):>7} {frv:>6.3f}  (near-pure)")
                continue
            e, s, c = fit(pts)
            inv = 1 / s if s > 1e-9 else float("inf")
            print(f"{str(k):>14} {len(pts):>7} {frv:>6.3f} {e:>6} "
                  f"{s:>10.6f} {c:>10.6f} {inv:>9.3f}")
            out[k] = (len(pts), e, s, c)
        tote = sum(v[1] for v in out.values())
        totn = sum(v[0] for v in out.values())
        print(f"   total fitted errs {tote} / {totn}\n")
        return out

    fit_table(lambda r: (r["low3"], r["third"]), "low3 x XD-third (baseline)")
    fit_table(lambda r: (r["low3"], r["d1"]), "low3 x d1(sq)")
    fit_table(lambda r: (r["low3"], r["p0"]), "low3 x p0(pos)")
    fit_table(lambda r: (r["low3"], r["f0"]), "low3 x f0(fourth)")


if __name__ == "__main__":
    main()
