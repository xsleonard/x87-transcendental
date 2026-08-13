#!/usr/bin/env python3
"""h532: THE REFRAMED STRUCTURAL MODEL — borrow-predict over the
TERMINAL SUBTRACT's redundant low field.

Chain of evidence: terminal chops at the R boundary (h529 chop
convention) => the subtract consumes the FULL redundant product
(S, C) of B = f4*rf, un-chopped => its low field holds rdisc AND the
tie structure => the borrow into the retained field is produced by a
bounded predictor over the 3-addend field (AP_lo, ~S_lo, ~C_lo)
(Pentium lineage: carry-predict circuits, radix-8 Booth, x3 multiple;
rf ~ 2/3 makes the array alternating +-3*f4).

Model per config:
  (S, C) from Booth-8 PPs of f4*pos reduced by topo;
  fine frame at B_full's LSB: APf = (A+P) << F, F = rsh - bshift;
  true M_fine = APf - S - C;  retained R = (M_fine >> kf) at
  kf = k + F (must reproduce the scanner's R at theta=0: control);
  hardware borrow: compress (APf_lo, (~S)_lo, (~C)_lo) 3:2 -> pair,
  carry into kf from window w at kf with assumption asm; +2
  complement correction at column ccol in {0, F, kf-w}.
  predicted outcome: retained_hw - retained_true in {-1, 0, +1}
  -> down/clean/up; scored against comb-7 chop labels at ALL theta.
"""
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h528_structural import row_features
from h530_radix8 import booth8_pps, reduce42, csa

WIDTH = 200
MASK = (1 << WIDTH) - 1

CONFIGS = []
for topo in ("seq42", "tree42"):
    for w in (4, 6, 8, 12, 16):
        for asm in (0, 1):
            for ccol in ("lsb", "win"):
                CONFIGS.append((topo, w, asm, ccol))


def score_chunk(args):
    rows, configs = args
    res = {cfg: defaultdict(int) for cfg in configs}
    for mhex, theta, lab in rows:
        (f4s, poss, B_full, rsh, A, P, M, k, R, bshift,
         dist, low3) = row_features(mhex)
        F = rsh - bshift
        if F < 0:
            continue
        APf = (A + P) << F
        kf = k + F
        pps_raw = booth8_pps(f4s, poss, WIDTH)
        pps = [(p + (1 << ci) if ci is not None else p) & MASK
               for p, ci in pps_raw]
        pair_cache = {}
        Mf_true = APf - B_full
        R_true = Mf_true >> kf
        if R_true != R + (theta if False else 0) and (Mf_true >> kf) \
                not in (R, R - 1, R + 1):
            pass
        for cfg in configs:
            topo, w, asm, ccol = cfg
            if topo not in pair_cache:
                pair_cache[topo] = reduce42(pps, topo, MASK)
            S, C = pair_cache[topo]
            lowm = (1 << kf) - 1
            a_lo = APf & lowm
            s_lo = (~S) & lowm
            c_lo = (~C) & lowm
            corr = 2 if ccol == "lsb" else 0
            # true borrow-side carry into kf of the 3-addend low sum
            tot_lo = a_lo + s_lo + c_lo + 2
            true_cin = tot_lo >> kf
            # hardware: 3:2 compress then windowed predict
            ps, pc = csa(a_lo, s_lo, c_lo, lowm | (lowm << 1))
            ps &= lowm
            pc = (pc | (2 if ccol == "lsb" else 0)) & lowm
            if ccol == "win":
                pc = (pc + (2 << max(0, kf - w))) & lowm
            if w >= kf:
                hw_cin = (ps + pc) >> kf
            else:
                wm = (1 << w) - 1
                ts = (ps >> (kf - w)) & wm
                tc = (pc >> (kf - w)) & wm
                hw_cin = (ts + tc + asm) >> w
            delta = hw_cin - true_cin
            pred = ("clean" if delta == 0 else
                    "down" if delta < 0 else "up")
            res[cfg][(lab, pred)] += 1
    return res


def main():
    # sample comb-7 rows with chop labels across all theta
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
    lab_census = defaultdict(int)
    for _, theta, lab in rows:
        lab_census[(theta, lab)] += 1
    print(f"sampled {len(rows)} labeled rows; census:",
          dict(sorted(lab_census.items(), key=str)))
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
        right = sum(v for (lab, pred), v in d.items()
                    if lab == pred)
        fire_n = sum(v for (lab, _), v in d.items()
                     if lab != "clean")
        fire_right = sum(v for (lab, pred), v in d.items()
                         if lab != "clean" and lab == pred)
        clean_n = n - fire_n
        clean_right = right - fire_right
        if clean_n and fire_n:
            scored.append((min(clean_right / clean_n,
                               fire_right / fire_n),
                           clean_right / clean_n,
                           fire_right / fire_n, cfg))
    scored.sort(reverse=True)
    print(f"\n{'config':32s} {'clean_acc':>9s} {'fire_acc':>8s}")
    for _, ca, fa, cfg in scored[:20]:
        print(f"{str(cfg):32s} {ca:9.4f} {fa:8.4f}")


if __name__ == "__main__":
    main()
