#!/usr/bin/env python3
"""h556: mine the residual selector eta's inputs from matched
contrast pairs (offline h479-style, in the j-frame).

Group rows by (stratum, tau12 = top-12 tail bits, gap quarter-log
bin).  Within a group, two rows with DISJOINT J-intervals require
different j at (nearly) the same tau and threshold — an eta
contrast.  Rows with overlapping J are controls.  For each pair
class, tabulate which quantities differ (deep tail bits, rdisc top
bits, rf low bits, sq low bits, m regions) — the systematic
differences are eta's candidate inputs, and the hardware straddle
list for next session.
"""
import math
import sys
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h539_D_library import qrow

FEATS = ["t4_b13_16", "t4_b17_20", "t4_b21_24", "rd_top4",
         "rd_b5_8", "rd_b9_12", "rf_low4", "rf_b5_8", "sq_low4",
         "sq_b5_8", "m_low8", "m_mid8"]


def work(rows):
    groups = defaultdict(list)
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
        tau12 = (t4 << 12) >> s4
        gap_up = (1 << kf) - Vlow
        gq = int(math.log2(gap_up) * 4)
        fv = (
            (t4 >> (s4 - 16)) & 15,
            (t4 >> (s4 - 20)) & 15,
            (t4 >> (s4 - 24)) & 15,
            (rdisc >> (rsh - 4)) & 15,
            (rdisc >> (rsh - 8)) & 15,
            (rdisc >> (rsh - 12)) & 15,
            rfv & 15,
            (rfv >> 4) & 15,
            sqv & 15,
            (sqv >> 4) & 15,
            m & 255,
            (m >> 20) & 255,
        )
        key = (dist, low3, ce, tau12, gq)
        groups[key].append((jlo, jhi, fv, mhex))
    return dict(groups)


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
    groups = defaultdict(list)
    for part in parts:
        for key, v in part.items():
            groups[key].extend(v)
    ncon = nctl = 0
    diff_con = defaultdict(int)
    diff_ctl = defaultdict(int)
    examples = []
    for key, members in groups.items():
        if len(members) < 2:
            continue
        for i in range(len(members)):
            for i2 in range(i + 1, min(i + 4, len(members))):
                a = members[i]
                b = members[i2]
                disjoint = a[1] < b[0] or b[1] < a[0]
                if disjoint:
                    ncon += 1
                    tab = diff_con
                    if len(examples) < 12:
                        examples.append((key, a, b))
                else:
                    nctl += 1
                    tab = diff_ctl
                for fi, name in enumerate(FEATS):
                    if a[2][fi] != b[2][fi]:
                        tab[name] += 1
    print(f"contrast pairs {ncon}, control pairs {nctl}")
    print(f"\n{'feature':12s} {'con_diff':>9s} {'ctl_diff':>9s} "
          f"{'ratio':>7s}")
    for name in FEATS:
        pc = diff_con.get(name, 0) / max(ncon, 1)
        pt = diff_ctl.get(name, 0) / max(nctl, 1)
        r = pc / pt if pt else float("inf")
        print(f"{name:12s} {pc:9.4f} {pt:9.4f} {r:7.3f}")
    print("\nexample contrast pairs (stratum tau12 gq | J_a J_b "
          "m_a m_b):")
    for key, a, b in examples:
        print(f"  {key[:3]} t12={key[3]} gq={key[4]} | "
              f"[{a[0]},{a[1]}] [{b[0]},{b[1]}] {a[3]} {b[3]}")


if __name__ == "__main__":
    main()
