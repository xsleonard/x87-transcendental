#!/usr/bin/env python3
"""h535: THE CONVERGENCE EXPERIMENT — iterative-array CS pair
(h534, bit-level, verified exact) feeding the terminal
borrow-predict (h532 frame).

B's (S, C) comes from the 2-pass iterative array (pb, mult
parameterized).  The terminal subtract computes AP - S - C with the
borrow into the retained field (column kf) from a bounded predictor
over the compressed 3-addend low field.  Fire = predicted borrow
differs from exact.  Scored on all-theta comb-7 chop labels.

Config: pb x mult x w (predict window) x asm (below-window carry
assumption).  w=999 = exact control (must be all-clean)."""
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h528_structural import row_features
from h534_bitlevel_seam import simulate_pair, csa, WIDTH, MASK

CONFIGS = []
for pb in (27, 32, 37, 53):
    for mult in ("rf", "f4"):
        for w in (4, 6, 8, 12, 16, 999):
            for asm in (0, 1):
                CONFIGS.append((pb, mult, w, asm))


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
        lowm = (1 << kf) - 1
        pair_cache = {}
        for cfg in configs:
            pb, mult, w, asm = cfg
            key = (pb, mult)
            if key not in pair_cache:
                S, C, ret = simulate_pair(f4s, poss, (pb, mult))
                # fold retired bits back as a third component
                pair_cache[key] = (S, C, ret)
            S, C, ret = pair_cache[key]
            # terminal 4-addend field: APf + ~S + ~C + ~ret (+3)
            a_lo = APf & lowm
            s_lo = (~S) & lowm
            c_lo = (~C) & lowm
            r_lo = (~ret) & lowm
            tot = a_lo + s_lo + c_lo + r_lo + 3
            true_cin = tot >> kf
            # hardware: compress 4:2 then windowed predict
            ps1, pc1 = csa(a_lo, s_lo, c_lo, lowm | (lowm << 1))
            ps, pc = csa(ps1 & lowm, (pc1 | 3) & lowm, r_lo,
                         lowm | (lowm << 1))
            ps &= lowm
            pc &= lowm
            if w >= kf:
                hw_cin = (ps + pc) >> kf
            else:
                wm = (1 << w) - 1
                hw_cin = (((ps >> (kf - w)) & wm)
                          + ((pc >> (kf - w)) & wm) + asm) >> w
            delta = hw_cin - true_cin
            pred = ("clean" if delta == 0 else
                    "down" if delta < 0 else "up")
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
    print(f"\n{'config':28s} {'clean_acc':>9s} {'fire_acc':>8s}")
    for _, ca, fa, cfg in scored[:30]:
        print(f"{str(cfg):28s} {ca:9.4f} {fa:8.4f}")


if __name__ == "__main__":
    main()
