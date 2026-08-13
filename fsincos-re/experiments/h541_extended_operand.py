#!/usr/bin/env python3
"""h541: EXTENDED-OPERAND + STICKY-DROP terminal (exact scoring, all
theta, new EU frame).

Hypothesis class (assembled from the inversion measurements):
the terminal subtract consumes B' instead of the model's
B_full = chop67(f4) * rf, where
    f4ext = f4 kept with e extra bits (chop or RN at 67+e), and
    B'    = f4ext * rf * 2^-e with its low-w columns DROPPED
            (retired sticky region, value lost), optionally
            compensated by +2^w when the dropped chunk is nonzero
            (inj=1) or always (inj=2).
Prediction: res = (APf*2^e - B'') >> (kf+e), scored against the
hardware result for every labeled comb-7 row (all theta).

D_net = eps*rf*2^-e - dropped_chunk reproduces (candidate): XD steps
at 1/3 and 2/3 (rf ~ 2/3), both fire directions, the theta decay,
and the causal f4-tail / rdisc-top bits.  Config grid over
(e, rmode, w, inj); exact score; survivors must be exact or
near-exact in the law strata.
"""
import sys
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h539_D_library import qrow

ES = [0, 1, 2, 3, 4]
RMODES = ["chop", "rn"]
WS = [0, 27, 54, 60, 62, 63, 64, 65, 66, 67]
INJS = [0, 1, 2]
CONFIGS = [(e, rm, w, inj) for e in ES for rm in RMODES
           for w in WS for inj in INJS
           if not (e == 0 and rm == "rn")]


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
        fire = res_hw != EU
        f4_full = sqv * sqv
        s4 = f4_full.bit_length() - 67
        for cfg in CONFIGS:
            e, rm, w, inj = cfg
            fe = f4_full >> (s4 - e)
            if rm == "rn" and e < s4:
                if (f4_full >> (s4 - e - 1)) & 1:
                    fe += 1
            Bp = fe * rfv
            if w:
                chunk = Bp & ((1 << w) - 1)
                Bp -= chunk
                if inj == 1 and chunk:
                    Bp += 1 << w
                elif inj == 2:
                    Bp += 1 << w
            V = (APf << e) - Bp
            pred = V >> (kf + e)
            ok = pred == res_hw
            res[cfg][("f" if fire else "c", ok)] += 1
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
        n = cr + cw + fr + fw
        if not n:
            continue
        scored.append((cw + fw, cw, fw, cr, fr, cfg))
    scored.sort(key=lambda x: x[0])
    print(f"\n{'errs':>8s} {'cln_w':>8s} {'fire_w':>8s} "
          f"{'cln_r':>8s} {'fire_r':>8s}  (e, rmode, w, inj)")
    for errs, cw, fw, cr, fr, cfg in scored[:30]:
        print(f"{errs:8d} {cw:8d} {fw:8d} {cr:8d} {fr:8d}  {cfg}")
    nz = [s for s in scored if s[0] == 0]
    print(f"\nEXACT configs: {len(nz)}")
    for s in nz:
        print("  ", s[5])


if __name__ == "__main__":
    main()
