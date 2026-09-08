#!/usr/bin/env python3
"""h616: FSIN cross-schedule blind test — construction + lock.

FCOS comb operands are value m*2^-66 (E2M).  For
x_sig = (M66 +- m/2) / 4 at se=3fff (x = pi/2 +- r, r =
m*2^-66), the model's reduction yields N=1 (odd quadrant ->
cosine producer) with reduced magnitude exactly m*2^-66 — the
SAME terminal row as the FCOS comb input m.  Constraints:
m even and (M66 +- m/2) == 0 mod 4.

Select m's from the comb near-tie lists (all windows), keep
rows the Round-57 rule ENGAGES (in-zone, covered, observable,
lsign/rsign form); emit constructed inputs for capture and
lock per-row predictions:
  off = refs(R)           (chop model, pre-patch frame)
  on  = refs(EU + req2p)  (rule)
Rows with off != on in any mode = DISAGREEMENT set; engaged
rows with off == on = controls.  (8,7)/(10,6) strata excluded
(Round-52 patch conditions).  Outputs: h616_inputs.txt,
h616_locked.json.
"""
import json
from collections import defaultdict
from multiprocessing import Pool
from h577_three_term import E2M
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h453_chain_variants import (C6_1, C6_3, C6_5, C6_2, C6_4,
                                 C6_6, build_chain, mul_round)
from h588_select import split_words
from h609_ref_predictor import load_model, predict
import h539_D_library as DL

M66 = (3 << 64) | 0x243F6A8885A308D3
CAP_PER_CELL = 300
FITS = CBEST = None


def initp():
    global FITS, CBEST
    FITS, CBEST = load_model()


def build_row(m):
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
    if left[0] != 1 or right[0] != 0:
        return None
    dist = abs(left[1] - right[1])
    if (dist, low3) in ((8, 7), (10, 6)):
        return None
    payload = low3 + 8 - dist
    scale = min(left[1], right[1], left[1] - 8)
    A = left[2] << (left[1] - scale)
    P = payload << (left[1] - 8 - scale)
    M = A + P - (right[2] << (right[1] - scale))
    if M <= 0:
        return None
    k = M.bit_length() - 67
    if k < 3:
        return None
    disc = M & ((1 << k) - 1)
    if disc <= 2:
        theta = disc
    elif disc >= (1 << k) - 2:
        theta = disc - (1 << k)
    else:
        return None
    R = M >> k
    ce = scale + k
    if ce not in (-72, -73):
        return None
    bshift = right[1] - scale
    F = rsh - bshift
    if F < 0:
        return None
    kf = k + F
    APf = (A + P) << F
    EU = (APf - B_full) >> kf
    Vlow = (APf - B_full) - (EU << kf)
    side = "up" if theta <= 0 else "dn"
    za, zb = (0, 1) if side == "up" else (-1, 0)
    ra = tuple(final_cosine_result(-(EU + za), ce, md)
               for md in ROUNDING_MODES)
    rb = tuple(final_cosine_result(-(EU + zb), ce, md)
               for md in ROUNDING_MODES)
    if ra == rb:
        return None  # blind
    S, C = split_words(f4[2], pos[2])
    st = ((S + C) >> max(rsh - 59, 0)) & 63
    tau = t4 / (1 << s4)
    mf = (m & ((1 << 63) - 1)) / (1 << 63)
    xd12 = min(11, (rdisc * 12) >> rsh)
    key = (dist, low3, ce, side)
    p = predict(FITS, CBEST, key, xd12, mf, st, tau, Vlow, kf,
                pos[2])
    if p is None:
        return None
    fire, req2p, src = p
    off = tuple(final_cosine_result(-R, ce, md)
                for md in ROUNDING_MODES)
    on = tuple(final_cosine_result(-(EU + req2p), ce, md)
               for md in ROUNDING_MODES)
    return (m, key, theta, off, on, req2p, int(R != EU + req2p))


def main():
    ms = set()
    for fn in ("ties_comb5.txt", "ties_comb6.txt",
               "ties_comb7.txt", "ties_comb8.txt"):
        for line in open(fn):
            w = line.split()[0]
            m = int(w, 16)
            if m & 1:
                continue
            ms.add(m)
    print(f"even comb m's: {len(ms)}", flush=True)
    cands = []
    for m in ms:
        for sgn in (1, -1):
            Aint = M66 + sgn * (m // 2)
            if Aint % 4 == 0:
                cands.append((m, sgn, Aint // 4))
    print(f"constructible (m, side): {len(cands)}", flush=True)
    todo = sorted({m for m, sgn, xs in cands})
    with Pool(14, initializer=initp) as pool:
        rows = pool.map(build_row, todo, chunksize=200)
    info = {m: r for m, r in zip(todo, rows) if r is not None}
    print(f"engaged rows: {len(info)}", flush=True)
    percell = defaultdict(int)
    locked = []
    seen_sig = set()
    ndis = nctl = 0
    for m, sgn, xsig in sorted(cands):
        r = info.get(m)
        if r is None:
            continue
        _, key, theta, off, on, req2p, dis = r
        cell = (key, theta, dis)
        if percell[cell] >= CAP_PER_CELL:
            continue
        if xsig in seen_sig:
            continue
        seen_sig.add(xsig)
        percell[cell] += 1
        ndis += dis
        nctl += 1 - dis
        locked.append({"x": f"3fff {xsig:016x}", "m": f"{m:x}",
                       "key": list(key), "theta": theta,
                       "req2p": req2p, "dis": dis,
                       "off": [f"{s:x}" for s in off],
                       "on": [f"{s:x}" for s in on]})
    print(f"locked: {len(locked)} (disagree {ndis}, "
          f"control {nctl})")
    cc = defaultdict(int)
    for rec in locked:
        cc[(tuple(rec["key"]), rec["dis"])] += 1
    for k in sorted(cc, key=str):
        print(f"  {k}: {cc[k]}")
    json.dump(locked, open("h616_locked.json", "w"))
    with open("h616_inputs.txt", "w") as fh:
        for rec in locked:
            fh.write(rec["x"] + "\n")


if __name__ == "__main__":
    main()
