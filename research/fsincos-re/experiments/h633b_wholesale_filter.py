#!/usr/bin/env python3
"""h633b: zone-filter the wholesale neighborhood captures into
labeled fit rows (h632 row format + status passthrough).
Targets: (10,1,-73) both sides, (10,6,-73,'up'), (9,2,-73,'up')
— strata the scanner cannot or did not emit."""
import json
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h577_three_term import E2M
from h453_chain_variants import (C6_1, C6_2, C6_3, C6_4, C6_5,
                                 C6_6, build_chain, mul_round)
from h588_select import split_words

TARGET = {(10, 1, -73, "dn"), (10, 1, -73, "up"),
          (10, 6, -73, "up"), (9, 2, -73, "up")}


def build_row(args):
    m, hw = args
    mag = (0, E2M, m)
    sq = mul_round(mag, mag, 67, "chop")
    f4 = mul_round(sq, sq, 67, "chop")
    low3 = sq[2] & 7
    if low3 == 0:
        return None
    neg = build_chain(f4, C6_5, C6_3, C6_1, 67, 64, "rn",
                      False, False, False)
    pos = build_chain(f4, C6_6, C6_4, C6_2, 67, 64, "rn",
                      False, False, False)
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
    side = "up" if theta <= 0 else "dn"
    ce = scale + k
    key = (dist, low3, ce, side)
    if key not in TARGET:
        return None
    bshift = right[1] - scale
    F = rsh - bshift
    if F < 0:
        return None
    kf = k + F
    APf = (A + P) << F
    EU = (APf - B_full) >> kf
    Vlow = (APf - B_full) - (EU << kf)
    za, zb = (0, 1) if side == "up" else (-1, 0)
    ra = tuple(final_cosine_result(-(EU + za), ce, md)
               for md in ROUNDING_MODES)
    rb = tuple(final_cosine_result(-(EU + zb), ce, md)
               for md in ROUNDING_MODES)
    if ra == rb:
        return None
    S, C = split_words(f4[2], pos[2])
    st = ((S + C) >> max(rsh - 59, 0)) & 63
    tau = t4 / (1 << s4)
    mf = (m & ((1 << 63) - 1)) / (1 << 63)
    xd12 = min(11, (rdisc * 12) >> rsh)
    return ({"m": f"{m:x}", "key": list(key), "theta": theta,
             "xd12": int(xd12), "mf16": min(15, int(mf * 16)),
             "st": int(st), "tau": tau, "mf": mf,
             "Vlow": str(Vlow), "kf": kf,
             "rfv": str(pos[2]), "EU": str(EU), "ce": ce},
            hw)


def main():
    inputs = [int(l.split()[1], 16)
              for l in open("h633_wholesale.txt")]
    st_f = {md: open(f"h633w_{md}_status.txt").read()
            .splitlines() for md in ROUNDING_MODES}
    jobs = []
    for i, m in enumerate(inputs):
        t = [st_f[md][i].split() for md in ROUNDING_MODES]
        if any(x[0] != "OK" for x in t):
            continue
        jobs.append((m, [int(x[2], 16) for x in t]))
    print(f"captured: {len(jobs)}", flush=True)
    with Pool(14) as pool:
        rows = pool.map(build_row, jobs, chunksize=500)
    recs = []
    hws = []
    cc = defaultdict(int)
    for r in rows:
        if r is None:
            continue
        rec, hw = r
        recs.append(rec)
        hws.append(hw)
        cc[(tuple(rec["key"]), rec["xd12"])] += 1
    print(f"in-zone target rows: {len(recs)}")
    for kk in sorted(cc, key=str):
        print(f"  {kk}: {cc[kk]}")
    json.dump(recs, open("h633_rows.json", "w"))
    json.dump(hws, open("h633_hw.json", "w"))


if __name__ == "__main__":
    main()
