#!/usr/bin/env python3
"""h537: exact scoring of drop/inject resolver families against the
required carry (h536 inversion frame).

Terminal field (h536, verified zero-impossible): four kf-bit words
a = APf low, s = ~S, c = ~C, r = ~ret, plus +3.  True carry into kf
crun; required hardware carry crun_hw = crun XOR wrong(req2 != 0).

FAMILY: hardware computes the carry over columns [w, kf) only; below
w each word's chunk is independently kept (numeric) or dropped
(zeroed); an injected constant J rides at column w (retired-chunk /
hot-one compensation).  J in {0..4} fixed, or 'nd' = number of
dropped complement words, or 'st' = 1 if any dropped chunk nonzero.
cin_hw = (sum of modified words + 3*[K kept] ) >> kf.

Wide grid over w (both absolute small columns = seams, and near-top
windows), drop masks, J.  Exact score vs crun_hw on a row sample;
survivors (0 errors) re-verified on more rows.  Also reports best
few by error count to show the landscape.
"""
import sys
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h528_structural import row_features
from h534_bitlevel_seam import simulate_pair

PB, MULT = 27, "rf"

# drop masks over words (a, s, c, r): 1 = drop below w
DROPS = []
for da in (0, 1):
    for ds in (0, 1):
        for dc in (0, 1):
            for dr in (0, 1):
                if da + ds + dc + dr:
                    DROPS.append((da, ds, dc, dr))
WS = list(range(2, 56, 2)) + [27, 54]
WS = sorted(set(WS))
JS = [0, 1, 2, 3, 4, "nd", "st"]
# K constant (+3) below w: kept at column 0, or dropped (rides in J)
KKEEP = (0, 1)

CONFIGS = [(w, dm, j, kk) for w in WS for dm in DROPS for j in JS
           for kk in KKEEP]


def load_labeled(stride):
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
    out = []
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
                out.append((f[0], theta, name))
                break
    return out


def score_chunk(args):
    rows, configs = args
    res = {cfg: [0, 0, 0, 0] for cfg in configs}   # rr rw wr ww
    for mhex, theta, lab in rows:
        (f4s, poss, B_full, rsh, A, P, M, k, R, bshift,
         dist, low3) = row_features(mhex)
        F = rsh - bshift
        if F < 0:
            continue
        kf = k + F
        lowm = (1 << kf) - 1
        APf = (A + P) << F
        a_lo = APf & lowm
        EU = (APf - B_full) >> kf
        res_hw = R + {"clean": 0, "down": -1, "up": 1}[lab]
        req2 = res_hw - EU
        S, C, ret = simulate_pair(f4s, poss, (PB, MULT))
        words = (a_lo, (~S) & lowm, (~C) & lowm, (~ret) & lowm)
        tot = sum(words) + 3
        cin_true = tot >> kf
        cin_req = cin_true + req2
        wrong = req2 != 0
        for cfg in configs:
            w, (da, ds, dc, dr), j, kk = cfg
            if w >= kf:
                continue
            wm = (1 << w) - 1
            drops = (da, ds, dc, dr)
            acc = 0
            nd = 0
            stk = 0
            for word, dbit in zip(words, drops):
                if dbit:
                    nd += 1
                    if word & wm:
                        stk = 1
                    acc += word & ~wm
                else:
                    acc += word
            if kk:
                acc += 3
            jv = (nd if j == "nd" else stk if j == "st" else j)
            acc += jv << w
            cin_hw = acc >> kf
            ok = cin_hw == cin_req
            idx = (0 if ok else 1) if not wrong else (2 if ok else 3)
            # idx semantics: rr=clean-right rw=clean-wrong
            #                wr=fire-right  ww=fire-wrong
            res[cfg][0 if (not wrong and ok) else
                     1 if (not wrong) else
                     2 if ok else 3] += 1
    return res


def main():
    stride = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    rows = load_labeled(stride)
    print(f"labeled sample: {len(rows)} rows", flush=True)
    chunks = [rows[i::8] for i in range(8)]
    with Pool(8) as pool:
        parts = pool.map(score_chunk,
                         [(ch, CONFIGS) for ch in chunks])
    agg = {cfg: [0, 0, 0, 0] for cfg in CONFIGS}
    for part in parts:
        for cfg, v in part.items():
            for i in range(4):
                agg[cfg][i] += v[i]
    scored = []
    for cfg, (rr, rw, wr, ww) in agg.items():
        n = rr + rw + wr + ww
        if not n:
            continue
        errs = rw + ww
        scored.append((errs, rw, ww, rr, wr, cfg))
    scored.sort(key=lambda x: x[:5])
    print(f"\n{'errs':>7s} {'cln_w':>7s} {'fire_w':>7s} "
          f"{'cln_r':>8s} {'fire_r':>7s}  config (w, drops, J, K)")
    for errs, rw, ww, rr, wr, cfg in scored[:40]:
        print(f"{errs:7d} {rw:7d} {ww:7d} {rr:8d} {wr:7d}  {cfg}")
    nz = [s for s in scored if s[0] == 0]
    print(f"\nEXACT configs: {len(nz)}")


if __name__ == "__main__":
    main()
