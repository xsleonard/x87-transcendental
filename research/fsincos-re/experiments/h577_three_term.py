#!/usr/bin/env python3
"""h577: THREE-TERM THRESHOLD on the hard sides.

Easy sides are closed (h576: universal Tr(col 64/65) - Tl(67)
- 2^(kf-7)).  Hard sides miss at specific theta slices.  Add the
causally-proven t4 tail as a third term:
  T = sr*(rdisc<<cr>>rsh) + sl*(ldisc<<cl>>lsh)
      + st*(t4<<ct>>s4) + c*2^(kf-10)
  up: fire <=> Vlow >= 2^kf - T ; dn: fire <=> Vlow < T
Hard sides only; coarse subsample scan over (sr,cr,sl,cl,st,ct),
refine c; split-half held-out; miss census by theta for winners.
"""
import sys
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h453_chain_variants import (C6_1, C6_2, C6_3, C6_4, C6_5,
                                 C6_6, build_chain, mul_round)

E2M = -66
HARD = {((8, 1, -73), "up"), ((8, 2, -73), "up"),
        ((8, 2, -73), "dn"), ((8, 3, -73), "dn"),
        ((8, 4, -73), "dn"), ((8, 5, -73), "dn"),
        ((8, 6, -73), "dn"), ((8, 7, -73), "dn"),
        ((9, 1, -72), "up"), ((9, 2, -72), "up"),
        ((9, 3, -72), "up"), ((9, 4, -72), "up"),
        ((9, 5, -72), "up"), ((9, 6, -72), "up"),
        ((9, 7, -72), "up"), ((9, 5, -72), "dn"),
        ((9, 6, -72), "dn"), ((9, 7, -72), "dn")}


def qrow3(mhex):
    m = int(mhex, 16)
    mag = (0, E2M, m)
    sq = mul_round(mag, mag, 67, "chop")
    f4 = mul_round(sq, sq, 67, "chop")
    neg = build_chain(f4, C6_5, C6_3, C6_1, 67, 64, "rn",
                      False, False, False)
    pos = build_chain(f4, C6_6, C6_4, C6_2, 67, 64, "rn",
                      False, False, False)
    low3 = sq[2] & 7
    L_full = sq[2] * neg[2]
    lsh = L_full.bit_length() - 67
    ldisc = L_full & ((1 << lsh) - 1)
    B_full = f4[2] * pos[2]
    rsh = B_full.bit_length() - 67
    rdisc = B_full & ((1 << rsh) - 1)
    f4_full = sq[2] * sq[2]
    s4 = f4_full.bit_length() - 67
    t4 = f4_full & ((1 << s4) - 1)
    left = mul_round(sq, neg, 67, "chop")
    right = mul_round(f4, pos, 67, "chop")
    dist = abs(left[1] - right[1])
    payload = low3 + 8 - dist
    scale = min(left[1], right[1], left[1] - 8)
    A = left[2] << (left[1] - scale)
    P = payload << (left[1] - 8 - scale)
    M = A + P - (right[2] << (right[1] - scale))
    k = M.bit_length() - 67
    R = M >> k
    return (m, R, A, P, B_full, rsh, rdisc, lsh, ldisc, s4, t4,
            right[1] - scale, k, dist, low3)


def work(rows):
    out = []
    for mhex, theta, lab, ce in rows:
        (m, R, A, P, B_full, rsh, rdisc, lsh, ldisc, s4, t4,
         bshift, k, dist, low3) = qrow3(mhex)
        F = rsh - bshift
        if F < 0:
            continue
        kf = k + F
        APf = (A + P) << F
        res_hw = R + {"clean": 0, "down": -1, "up": 1}[lab]
        EU = (APf - B_full) >> kf
        req2 = res_hw - EU
        Vlow = (APf - B_full) - (EU << kf)
        strat = (dist, low3, ce)
        side = "up" if theta <= 0 else "dn"
        if (strat, side) not in HARD:
            continue
        half = (m * 2654435761) & 1
        out.append((strat, side, half, kf, Vlow, rsh, rdisc,
                    lsh, ldisc, s4, t4, req2, theta))
    return out


GROUP = None


def init_g(g):
    global GROUP
    GROUP = g


def score(rows2, side, cfg, cq, misses=None):
    sr, cr, sl, cl, st, ct = cfg
    ok = 0
    for kf, Vlow, rsh, rdisc, lsh, ldisc, s4, t4, req2, theta \
            in rows2:
        T = cq * (1 << kf) >> 10
        if sr:
            T += sr * (rdisc << cr >> rsh)
        if sl:
            T += sl * (ldisc << cl >> lsh)
        if st:
            T += st * (t4 << ct >> s4)
        if side == "up":
            pred = 1 if Vlow >= (1 << kf) - T else 0
        else:
            pred = -1 if Vlow < T else 0
        if pred == req2:
            ok += 1
        elif misses is not None:
            misses[theta] += 1
    return ok


def eval_group(key):
    strat, side = key
    tr, te = GROUP[key]
    sub = tr[:5000]
    coarse = []
    for sr, cr in [(1, c) for c in range(61, 67)] + [(0, 0)]:
        for sl, cl in [(0, 0)] + \
                [(s, c) for s in (1, -1) for c in range(60, 68)]:
            for st, ct in [(0, 0)] + \
                    [(s, c) for s in (1, -1)
                     for c in range(60, 68)]:
                cfg = (sr, cr, sl, cl, st, ct)
                coarse.append((score(sub, side, cfg, 0), cfg))
    coarse.sort(reverse=True, key=lambda x: x[0])
    best = (-1, None, None)
    for _, cfg in coarse[:10]:
        for cq in (-16, -8, -4, -2, -1, 0, 1, 2, 4, 8, 16):
            ok = score(tr, side, cfg, cq)
            if ok > best[0]:
                best = (ok, cfg, cq)
    _, cfg, cq = best
    thm = defaultdict(int)
    ok = score(te, side, cfg, cq, thm)
    return key, best[0], len(tr), ok, len(te), cfg, cq, dict(thm)


def main():
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
    groups = defaultdict(lambda: ([], []))
    for part in parts:
        for strat, side, half, kf, Vlow, rsh, rdisc, lsh, \
                ldisc, s4, t4, req2, theta in part:
            pt = (kf, Vlow, rsh, rdisc, lsh, ldisc, s4, t4,
                  req2, theta)
            groups[(strat, side)][0 if half == 0 else 1].append(pt)
    groups = {k: v for k, v in groups.items()
              if len(v[0]) >= 1000}
    keys = sorted(groups)
    with Pool(8, initializer=init_g,
              initargs=(groups,)) as pool:
        results = pool.map(eval_group, keys)
    print(f"\n{'stratum':14s} {'side':4s} {'train':>7s} "
          f"{'HELDOUT':>8s} {'config':>28s} {'c':>3s}  miss_theta")
    for key, otr, ntr, ote, nte, cfg, cq, thm in results:
        strat, side = key
        print(f"{str(strat):14s} {side:4s} {otr/ntr:7.5f} "
              f"{ote/max(nte,1):8.5f} {str(cfg):>28s} {cq:3d}  "
              f"{dict(sorted(thm.items()))}")


if __name__ == "__main__":
    main()
