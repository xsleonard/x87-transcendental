#!/usr/bin/env python3
"""h557: redesigned eta mining — tight cells + SIGNED value diffs.

Cells: (stratum, tau16 = top-16 tail bits, m>>48).  Within a cell,
pairs with DISJOINT J-intervals are eta contrasts; orient each pair
by its higher-j member and record the SIGN of each feature delta.
A feature eta reads shows sign agreement far from 0.5 (binomial).
Features: deep tau (beyond 16 bits), XD, rf low bits, sq low bits,
m (within-cell remainder), log2 gap, theta, kf.
Reported globally and per stratum (direction may be cell-dependent
per h486 — per-stratum splits catch sign flips).
"""
import math
import sys
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h539_D_library import qrow

FEATS = ["tau_deep", "XD", "rf_low", "sq_low", "m_rem",
         "gap_log", "theta", "kf"]


def work(rows):
    cells = defaultdict(list)
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
        base = Vlow << 2
        top = 1 << (kf + 2)
        jlo = jhi = None
        for j in range(-16, 17):
            T = base - j * rfv
            pred = 1 if T >= top else (-1 if T < 0 else 0)
            if pred == req2:
                if jlo is None:
                    jlo = j
                jhi = j
        if jlo is None:
            continue
        f4_full = sqv * sqv
        s4 = f4_full.bit_length() - 67
        tau16 = (t4 << 16) >> s4
        tau_deep = ((t4 << 32) >> s4) & 0xFFFF
        gap_up = (1 << kf) - Vlow
        feats = (tau_deep, rdisc / 2**rsh, rfv & 0xFFFFF,
                 sqv & 0xFFFFF, m & ((1 << 48) - 1),
                 math.log2(gap_up), theta, kf)
        key = (dist, low3, ce, tau16, m >> 48)
        cells[key].append((jlo, jhi, feats))
    return dict(cells)


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
    stride = int(sys.argv[1]) if len(sys.argv) > 1 else 2
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
    cells = defaultdict(list)
    for part in parts:
        for key, v in part.items():
            cells[key].extend(v)
    ncon = 0
    sign_glob = defaultdict(lambda: [0, 0])
    sign_strat = defaultdict(lambda: [0, 0])
    for key, members in cells.items():
        if len(members) < 2:
            continue
        strat = key[:3]
        for i in range(len(members)):
            for i2 in range(i + 1, min(i + 6, len(members))):
                a, b = members[i], members[i2]
                if a[1] < b[0]:
                    lo_row, hi_row = a, b
                elif b[1] < a[0]:
                    lo_row, hi_row = b, a
                else:
                    continue
                ncon += 1
                for fi, name in enumerate(FEATS):
                    d = hi_row[2][fi] - lo_row[2][fi]
                    if d == 0:
                        continue
                    s = 1 if d > 0 else 0
                    sign_glob[name][s] += 1
                    sign_strat[(strat, name)][s] += 1
    print(f"contrast pairs (tight cells): {ncon}")
    print(f"\n{'feature':9s} {'pos':>7s} {'neg':>7s} {'agree':>7s}")
    for name in FEATS:
        p, ng = sign_glob[name][1], sign_glob[name][0]
        if p + ng == 0:
            continue
        print(f"{name:9s} {p:7d} {ng:7d} "
              f"{max(p, ng)/(p+ng):7.4f}")
    print("\nper-stratum sign agreement (features with global "
          "signal or flips):")
    strata = sorted(set(kk[0] for kk in sign_strat))
    for name in FEATS:
        lines = []
        for s2 in strata:
            p, ng = sign_strat[(s2, name)]
            tot = p + ng
            if tot < 30:
                continue
            frac = p / tot
            if frac > 0.65 or frac < 0.35:
                lines.append(f"{s2}:{frac:.2f}({tot})")
        if lines:
            print(f"  {name}: " + " ".join(lines))


if __name__ == "__main__":
    main()
