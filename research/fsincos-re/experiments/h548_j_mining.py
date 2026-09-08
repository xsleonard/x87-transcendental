#!/usr/bin/env python3
"""h548: REQUIRED-j MINING over the rf/4 ladder (final inversion
turn on the comb-7 data).

Per row: J(row) = { j in [-6..6] :
    floor(((Vlow<<2) - j*rfv) / 2^(kf+2)) == req2 }.
(h546 fixed the ladder; h547's fixed Booth map failed — so learn the
map.)  For each grouping key K, intersect J within groups; a
consistent map j = g(K) exists iff every group's intersection is
nonempty.  Report feasibility and the learned map sizes:
  K1: (s4 parity, top-8 f4 tail bits)
  K2: K1 + (dist, low3, ce)
  K3: K2 + next 4 tail bits (12 deep)
Also: rows whose J excludes ALL of [-6..6] (ladder violations).
"""
import sys
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h539_D_library import qrow

JS = list(range(-6, 7))


def work(rows):
    groups = {1: defaultdict(int), 2: defaultdict(int),
              3: defaultdict(int)}
    # value = intersection bitmask over 13 j's; store per key:
    # (mask_and, count) — encode running AND in dict of ints
    inter = {1: {}, 2: {}, 3: {}}
    counts = {1: defaultdict(int), 2: defaultdict(int),
              3: defaultdict(int)}
    nladder_viol = 0
    n = 0
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
        base = Vlow << 2
        top = 1 << (kf + 2)
        mask = 0
        for ji, j in enumerate(JS):
            T = base - j * rfv
            pred = 1 if T >= top else (-1 if T < 0 else 0)
            if pred == req2:
                mask |= 1 << ji
        n += 1
        if not mask:
            nladder_viol += 1
            continue
        t8 = (f4_full >> (s4 - 8)) & 255
        t12 = (f4_full >> (s4 - 12)) & 4095
        k1 = (s4 & 1, t8)
        k2 = (s4 & 1, t8, dist, low3, ce)
        k3 = (s4 & 1, t12, dist, low3, ce)
        for lvl, key in ((1, k1), (2, k2), (3, k3)):
            if key in inter[lvl]:
                inter[lvl][key] &= mask
            else:
                inter[lvl][key] = mask
            counts[lvl][key] += 1
    return inter, counts, nladder_viol, n


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
    inter = {1: {}, 2: {}, 3: {}}
    counts = {1: defaultdict(int), 2: defaultdict(int),
              3: defaultdict(int)}
    nv = n = 0
    for pi, pc, pv, pn in parts:
        nv += pv
        n += pn
        for lvl in (1, 2, 3):
            for key, mask in pi[lvl].items():
                if key in inter[lvl]:
                    inter[lvl][key] &= mask
                else:
                    inter[lvl][key] = mask
            for key, c in pc[lvl].items():
                counts[lvl][key] += c
    print(f"rows {n}, ladder violations (J empty): {nv} "
          f"({nv/n:.5f})")
    for lvl, name in ((1, "(s4par, t8)"),
                      (2, "(s4par, t8, stratum)"),
                      (3, "(s4par, t12, stratum)")):
        ng = len(inter[lvl])
        empty_rows = sum(counts[lvl][key]
                         for key, mask2 in inter[lvl].items()
                         if mask2 == 0)
        nonempty = sum(1 for m2 in inter[lvl].values() if m2)
        print(f"K{lvl} {name}: groups {ng}, consistent {nonempty}, "
              f"rows in EMPTY groups {empty_rows} "
              f"({empty_rows/n:.4f})")


if __name__ == "__main__":
    main()
