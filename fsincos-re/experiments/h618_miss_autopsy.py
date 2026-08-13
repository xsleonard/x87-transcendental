#!/usr/bin/env python3
"""h618: autopsy of the 486 doubly-confirmed rule-miss rows
(h616 categories chop=330 / other=156; identical outcomes on
FSIN and FCOS hardware).

Per miss row: recompute the full frame + required j-interval
from the HARDWARE outcome; measure how the selector missed:
  delta = signed distance from x_sel (= q*tau + a*mf + b + c)
          to the feasible interval [jlo - 0.5, jhi + 0.5)
Aggregates:
  1. |delta| census: <=0.5 (boundary), <=1.5 (one step), gross;
  2. per (key, xd12, mf16) cell concentration;
  3. mf position inside its 16th (edge concentration);
  4. st adjacency to the zone's c-transition (comparator edge);
  5. required-vs-selected j: is the TRUE j feasible under a
     DIFFERENT c in [-8,8] (i.e. state-read miss) or not even
     under the best c (zone-line miss)?
"""
import json
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h577_three_term import E2M
from h453_chain_variants import (C6_1, C6_3, C6_5, C6_2, C6_4,
                                 C6_6, build_chain, mul_round)
from h588_select import split_words
from h598_jframe import jinterval
from h609_ref_predictor import load_model, V5_KEYS

FITS = CBEST = None


def initp():
    global FITS, CBEST
    FITS, CBEST = load_model()


def feats(args):
    m, cat = args
    mag = (0, E2M, m)
    sq = mul_round(mag, mag, 67, "chop")
    f4 = mul_round(sq, sq, 67, "chop")
    neg = build_chain(f4, C6_5, C6_3, C6_1, 67, 64, "rn",
                      False, False, False)
    pos = build_chain(f4, C6_6, C6_4, C6_2, 67, 64, "rn",
                      False, False, False)
    low3 = sq[2] & 7
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
    disc = M & ((1 << k) - 1)
    theta = disc if disc <= 2 else disc - (1 << k)
    R = M >> k
    ce = scale + k
    bshift = right[1] - scale
    F = rsh - bshift
    kf = k + F
    APf = (A + P) << F
    EU = (APf - B_full) >> kf
    Vlow = (APf - B_full) - (EU << kf)
    side = "up" if theta <= 0 else "dn"
    # hardware z from category: chop -> z = R - EU;
    # other -> the z in {-1,0,1} minus {pred, R-EU}
    S, C = split_words(f4[2], pos[2])
    st = ((S + C) >> max(rsh - 59, 0)) & 63
    tau = t4 / (1 << s4)
    mf = (m & ((1 << 63) - 1)) / (1 << 63)
    xd12 = min(11, (rdisc * 12) >> rsh)
    key = (dist, low3, ce, side)
    if key in V5_KEYS:
        zid = (key, xd12, min(15, int(mf * 16)))
    else:
        zid = (key, xd12)
    f = FITS.get(zid)
    q, a, b = f
    c = CBEST.get((zid, st), 0)
    x = q * tau + a * mf + b + c
    j_sel = round(x)
    req2_sel = (4 * Vlow - j_sel * pos[2]) >> (kf + 2)
    return (m, cat, key, xd12, min(15, int(mf * 16)), st, mf,
            tau, x, j_sel, req2_sel, Vlow, kf, pos[2], EU, R,
            theta, zid)


def main():
    locked = json.load(open("h616_locked.json"))
    st_files = {md: open(f"h616_{md}_status.txt").read()
                .splitlines() for md in ROUNDING_MODES}
    rows = []
    for i, rec in enumerate(locked):
        hw = [f"{int(st_files[md][i].split()[2], 16):x}"
              for md in ROUNDING_MODES]
        if hw == rec["on"]:
            continue
        cat = "chop" if hw == rec["off"] else "other"
        rows.append((int(rec["m"], 16), cat, hw, rec))
    print(f"miss rows: {len(rows)}")
    with Pool(14, initializer=initp) as pool:
        fs = pool.map(feats, [(m, cat) for m, cat, hw, rec
                              in rows], chunksize=20)
    initp()
    dl = defaultdict(int)
    cellc = defaultdict(int)
    mfpos = defaultdict(int)
    stedge = defaultdict(int)
    fixable = defaultdict(int)
    for (m, cat, hw, rec), ft in zip(rows, fs):
        (m2, cat2, key, xd12, mf16, st, mf, tau, x, j_sel,
         req2_sel, Vlow, kf, rfv, EU, R, theta, zid) = ft
        # hardware z: FULL alias set (h572 caution), union of
        # j-intervals
        ivs = []
        for z in (-2, -1, 0, 1, 2):
            refs = [f"{final_cosine_result(-(EU + z), key[2], md):x}"
                    for md in ROUNDING_MODES]
            if refs == hw:
                lo, hi = jinterval(Vlow, kf, rfv, z)
                if lo <= hi:
                    ivs.append((lo, hi))
        if not ivs:
            dl["infeasible"] += 1
            continue
        delta = None
        for lo, hi in ivs:
            if lo - 0.5 <= x < hi + 0.5:
                d = 0.0
            elif x < lo - 0.5:
                d = x - (lo - 0.5)
            else:
                d = x - (hi + 0.5)
            if delta is None or abs(d) < abs(delta):
                delta = d
        jlo, jhi = min(iv[0] for iv in ivs), \
            max(iv[1] for iv in ivs)
        ad = abs(delta)
        band = ("boundary<=0.5" if ad <= 0.5 else
                "step<=1.5" if ad <= 1.5 else "gross")
        dl[band] += 1
        cellc[(key, xd12, mf16)] += 1
        mffrac = mf * 16 - int(mf * 16)
        mfpos[round(min(mffrac, 1 - mffrac) * 8)] += 1
        # would another c have worked?
        q, a, b = FITS[zid]
        okc = any(jlo <= round(q * tau + a * mf + b + c2) <= jhi
                  for c2 in range(-8, 9))
        fixable["c_could_fix" if okc else "line_miss"] += 1
        # st adjacency to a c transition in this zone
        cz = {s: CBEST.get((zid, s)) for s in range(64)
              if (zid, s) in CBEST}
        near = any(abs(st - s) <= 1 and cz[s] !=
                   CBEST.get((zid, st), 0) for s in cz)
        stedge[near] += 1
    print("\n|delta| bands:", dict(dl))
    print("\nfixable by other c:", dict(fixable))
    print("\nst adjacent to a c-transition:", dict(stedge))
    print("\nmf distance to 16th edge (units of 1/128):",
          dict(sorted(mfpos.items())))
    print("\ntop cells:")
    for cell, n in sorted(cellc.items(), key=lambda kv: -kv[1])[:15]:
        print(f"  {cell}: {n}")


if __name__ == "__main__":
    main()
