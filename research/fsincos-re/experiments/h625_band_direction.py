#!/usr/bin/env python3
"""h625: THE BAND-DIRECTION FRAME — the residual as a tiebreak.

Population: labeled rows whose selector value x sits near a
rounding boundary (frac(x) in [0.5-W, 0.5+W]) and whose
hardware J-interval makes EXACTLY ONE of {floor(x), floor(x)+1}
feasible.  Label: which side hardware took.  Baseline: round()
(sign of frac - 0.5).  The 486-row miss set is exactly this
population's error set; here the signal is measurable per row.

Features per row (everything the replica expresses):
  frac (the margin itself), st, stA6, theta, xd12f (rdisc*48
  fine), t4 deep bits (t4 >> s4-16), rdisc deep (16 bits below
  top), ldisc top 8, sq low 8, m low 8, q-chain guards
  (asq/f4/left/right chop guard+sticky), kf, payload.
Mining: per-feature AUC on the tiebreak label (global +
per-stratum), then all PAIRS of the top-8 features via 2D
threshold grids (train/holdout by m-hash).
"""
import bisect
import json
from collections import defaultdict
from itertools import combinations
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h577_three_term import E2M
from h453_chain_variants import (C6_1, C6_3, C6_5, C6_2, C6_4,
                                 C6_6, build_chain, mul_round)
from h588_select import split_words
from h598_jframe import jinterval
from h609_ref_predictor import load_model, V5_KEYS

W = 0.20
FITS = CBEST = None


def initp():
    global FITS, CBEST
    FITS, CBEST = load_model()


def prep(args):
    m, hw = args
    mag = (0, E2M, m)
    sq = mul_round(mag, mag, 67, "chop")
    f4 = mul_round(sq, sq, 67, "chop")
    neg = build_chain(f4, C6_5, C6_3, C6_1, 67, 64, "rn",
                      False, False, False)
    pos = build_chain(f4, C6_6, C6_4, C6_2, 67, 64, "rn",
                      False, False, False)
    B_full = f4[2] * pos[2]
    rsh = B_full.bit_length() - 67
    L_full = sq[2] * neg[2]
    lsh = L_full.bit_length() - 67
    ldisc = L_full & ((1 << lsh) - 1)
    f4_full = sq[2] * sq[2]
    s4 = f4_full.bit_length() - 67
    t4 = f4_full & ((1 << s4) - 1)
    rdisc = B_full & ((1 << rsh) - 1)
    left = mul_round(sq, neg, 67, "chop")
    right = mul_round(f4, pos, 67, "chop")
    low3 = sq[2] & 7
    dist = abs(left[1] - right[1])
    payload = low3 + 8 - dist
    scale = min(left[1], right[1], left[1] - 8)
    A = left[2] << (left[1] - scale)
    P = payload << (left[1] - 8 - scale)
    M = A + P - (right[2] << (right[1] - scale))
    k = M.bit_length() - 67
    ce = scale + k
    bshift = right[1] - scale
    F = rsh - bshift
    kf = k + F
    APf = (A + P) << F
    EU = (APf - B_full) >> kf
    Vlow = (APf - B_full) - (EU << kf)
    ivs = []
    for z in (-2, -1, 0, 1, 2):
        refs = [final_cosine_result(-(EU + z), ce, md)
                for md in ROUNDING_MODES]
        if refs == hw:
            lo, hi = jinterval(Vlow, kf, pos[2], z)
            if lo <= hi:
                ivs.append((lo, hi))
    if not ivs:
        return None
    disc = M & ((1 << k) - 1)
    theta = disc if disc <= 2 else disc - (1 << k)
    side = "up" if theta <= 0 else "dn"
    key = (dist, low3, ce, side)
    S, C = split_words(f4[2], pos[2])
    st = ((S + C) >> max(rsh - 59, 0)) & 63
    SA, CA = split_words(sq[2], neg[2])
    stA6 = ((SA + CA) >> max(lsh - 59, 0)) & 63
    tau = t4 / (1 << s4)
    mf = (m & ((1 << 63) - 1)) / (1 << 63)
    xd12 = min(11, (rdisc * 12) >> rsh)
    if key in V5_KEYS:
        zid = (key, xd12, min(15, int(mf * 16)))
    else:
        zid = (key, xd12)
    f = FITS.get(zid)
    if f is None:
        return None
    q, a, b = f
    c = CBEST.get((zid, st), 0)
    x = q * tau + a * mf + b + c
    kx = int(x // 1)
    frac = x - kx
    if not (0.5 - W <= frac <= 0.5 + W):
        return None
    fk = any(l <= kx <= h for l, h in ivs)
    fk1 = any(l <= kx + 1 <= h for l, h in ivs)
    if fk == fk1:
        return None  # both or neither feasible: uninformative
    label = 1 if fk1 else 0  # 1 = high side
    half = (m * 2654435761 >> 16) & 1
    feats = {
        "frac": frac,
        "st": int(st),
        "stA6": int(stA6),
        "theta": theta,
        "xd48": int(min(47, (rdisc * 48) >> rsh)),
        "t4d16": int((t4 >> max(s4 - 16, 0)) & 0xFFFF),
        "rd_d16": int((rdisc >> max(rsh - 20, 0)) & 0xFFFF),
        "ld8": int(ldisc >> max(lsh - 8, 0)),
        "sq8": int(sq[2] & 255),
        "m8": int(m & 255),
        "kf": kf,
        "pay": payload,
        "t4g": int((t4 >> (s4 - 1)) & 1) if s4 > 0 else 0,
        "sq_st": int(bool(sq[2] * sq[2] &
                          ((1 << max(s4 - 1, 0)) - 1))),
    }
    return (key, half, label, feats)


def auc_of(vals, labels):
    pos = sorted(v for v, l in zip(vals, labels) if l)
    neg = sorted(v for v, l in zip(vals, labels) if not l)
    if not pos or not neg:
        return 0.5
    s = sum(bisect.bisect_left(neg, v) for v in pos)
    a = s / (len(pos) * len(neg))
    return max(a, 1 - a)


def main():
    rows = []
    locked = json.load(open("h616_locked.json"))
    st6 = {md: open(f"h616_{md}_status.txt").read()
           .splitlines() for md in ROUNDING_MODES}
    for i, rec in enumerate(locked):
        hw = [int(st6[md][i].split()[2], 16)
              for md in ROUNDING_MODES]
        rows.append((int(rec["m"], 16), hw))
    recs = json.load(open("h619_rows.json"))
    st9 = {md: open(f"h619_{md}_status.txt").read()
           .splitlines() for md in ROUNDING_MODES}
    for i, rec in enumerate(recs):
        t = [st9[md][i].split() for md in ROUNDING_MODES]
        if any(x[0] != "OK" for x in t):
            continue
        rows.append((int(rec["m"], 16),
                     [int(x[2], 16) for x in t]))
    print(f"rows: {len(rows)}", flush=True)
    with Pool(14, initializer=initp) as pool:
        ps = pool.map(prep, rows, chunksize=200)
    ps = [p for p in ps if p is not None]
    n1 = sum(p[2] for p in ps)
    print(f"band rows: {len(ps)} (high-side {n1}, "
          f"low-side {len(ps) - n1})", flush=True)
    # baseline: round() = predict high iff frac >= 0.5
    ok = sum(1 for key, half, lab, f in ps
             if (1 if f["frac"] >= 0.5 else 0) == lab)
    print(f"round() baseline: {ok / len(ps):.4f}")
    names = sorted(ps[0][3])
    print("\nsingle-feature AUC (global):")
    scores = []
    for nm in names:
        a = auc_of([p[3][nm] for p in ps],
                   [p[2] for p in ps])
        scores.append((a, nm))
        print(f"  {nm:7s}: {a:.3f}")
    scores.sort(reverse=True)
    top = [nm for a, nm in scores[:8]]
    # pairwise 2D threshold mining, train/holdout
    tr = [p for p in ps if p[1] == 0]
    te = [p for p in ps if p[1] == 1]
    print(f"\npair mining on top-8 {top} "
          f"(train {len(tr)}, test {len(te)}):")
    base_te = sum(1 for key, half, lab, f in te
                  if (1 if f["frac"] >= 0.5 else 0) == lab) \
        / max(len(te), 1)
    best = []
    for na, nb in combinations(top, 2):
        # grid thresholds on quantiles
        av = sorted(set(p[3][na] for p in tr))
        bv = sorted(set(p[3][nb] for p in tr))
        aq = [av[len(av) * i // 8] for i in range(1, 8)]
        bq = [bv[len(bv) * i // 8] for i in range(1, 8)]
        bacc = 0
        bcfg = None
        for ta in aq:
            for tb in bq:
                for quad in range(16):
                    okq = 0
                    for key, half, lab, f in tr:
                        qd = (2 if f[na] >= ta else 0) | \
                            (1 if f[nb] >= tb else 0)
                        pred = (quad >> qd) & 1
                        okq += pred == lab
                    if okq > bacc:
                        bacc = okq
                        bcfg = (ta, tb, quad)
        ta, tb, quad = bcfg
        okt = 0
        for key, half, lab, f in te:
            qd = (2 if f[na] >= ta else 0) | \
                (1 if f[nb] >= tb else 0)
            okt += ((quad >> qd) & 1) == lab
        best.append((okt / max(len(te), 1), na, nb))
    best.sort(reverse=True)
    print(f"  round() baseline held-out: {base_te:.4f}")
    for acc, na, nb in best[:8]:
        print(f"  {na}+{nb}: held-out {acc:.4f}")


if __name__ == "__main__":
    main()
