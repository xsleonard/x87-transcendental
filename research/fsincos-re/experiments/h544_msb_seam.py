#!/usr/bin/env python3
"""h544: MSB-ANCHORED SEAM + f4-TAIL EXTENSION (exact, all theta).

B' = fe * rf, fe = f4 kept with e extra tail bits (chop/rn);
retirement drops B''s low columns up to w = bitlen(B') - c (seam at
fixed distance c from the product MSB — the paper's normalized
alignment; reproduces per-stratum shifts and h492 le2-anchoring),
optionally +2^w back when the chunk is nonzero (inj).
chunk_src 'base' drops from the UNextended product instead (the
tail-extension and the retirement acting at different pipeline
points).

pred req2 = floor((Vlow*2^e + Dn) / 2^(kf+e)) vs label, exact.
"""
import sys
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h539_D_library import qrow

CS = list(range(62, 71))
ES = [0, 1, 2, 3, 4]
RMODES = ["chop", "rn"]
INJS = [0, 1]
SRCS = ["ext", "base"]
CONFIGS = [(c, e, rm, inj, src) for c in CS for e in ES
           for rm in RMODES for inj in INJS for src in SRCS
           if not (e == 0 and (rm == "rn" or src == "base"))]


def work(rows):
    res = {cfg: defaultdict(int) for cfg in CONFIGS}
    for mhex, theta, lab, ce in rows:
        (m, sqv, f4v, rfv, t4, rdisc, A, P, M, k, R, B_full,
         rsh, bshift, dist, low3) = qrow(mhex)
        F = rsh - bshift
        if F < 0:
            continue
        kf = k + F
        APf = (A + P) << F
        res_hw = R + {"clean": 0, "down": -1, "up": 1}[lab]
        EU = (APf - B_full) >> kf
        req2 = res_hw - EU
        Vlow = (APf - B_full) - (EU << kf)
        f4_full = sqv * sqv
        s4 = f4_full.bit_length() - 67
        fes = {}
        for e in ES:
            fe = f4_full >> (s4 - e)
            fes[(e, "chop")] = fe
            fes[(e, "rn")] = fe + ((f4_full >> (s4 - e - 1)) & 1)
        for cfg in CONFIGS:
            c, e, rm, inj, src = cfg
            fe = fes[(e, rm)]
            Bp = fe * rfv
            blp = Bp.bit_length()
            w = blp - c
            if w <= 0:
                continue
            if src == "ext":
                chunk = Bp & ((1 << w) - 1)
            else:
                wb = (f4v * rfv).bit_length() - c
                chunk = ((f4v * rfv) & ((1 << wb) - 1)) << e \
                    if wb > 0 else 0
            eps = fe - (f4v << e)
            Dn = chunk - eps * rfv
            if inj and chunk:
                Dn -= 1 << w
            T = (Vlow << e) + Dn
            top = 1 << (kf + e)
            pred = 1 if T >= top else (-1 if T < 0 else 0)
            ok = pred == req2
            res[cfg][("f" if req2 else "c", ok)] += 1
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
    order = {m2: i for i, m2 in enumerate(inputs)}
    st = {md: open(f"comb7_{md}_status.txt").read().splitlines()
          for md in ROUNDING_MODES}
    stride = int(sys.argv[1]) if len(sys.argv) > 1 else 8
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
    agg = {cfg: defaultdict(int) for cfg in CONFIGS}
    for part in parts:
        for cfg, d in part.items():
            for kk, v in d.items():
                agg[cfg][kk] += v
    scored = []
    for cfg, d in agg.items():
        cr = d.get(("c", True), 0)
        cw = d.get(("c", False), 0)
        fr = d.get(("f", True), 0)
        fw = d.get(("f", False), 0)
        if cr + cw + fr + fw == 0:
            continue
        scored.append((cw + fw, cw, fw, cr, fr, cfg))
    scored.sort(key=lambda x: x[0])
    print(f"\n{'errs':>8s} {'cln_w':>8s} {'fire_w':>8s} "
          f"{'cln_r':>8s} {'fire_r':>8s}  (c, e, rmode, inj, src)")
    for errs, cw, fw, cr, fr, cfg in scored[:25]:
        print(f"{errs:8d} {cw:8d} {fw:8d} {cr:8d} {fr:8d}  {cfg}")
    nz = [s for s in scored if s[0] == 0]
    print(f"\nEXACT configs: {len(nz)}")
    for s in nz:
        print("  ", s[5])


if __name__ == "__main__":
    main()
