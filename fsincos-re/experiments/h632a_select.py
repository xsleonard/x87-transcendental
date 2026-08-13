#!/usr/bin/env python3
"""h632a: select capture rows (fresh h632 scan) for the uncovered zones.

Zones (h630b): (7,2/4/6,-72,dn) at xd12x{6..11}, mf16 13-15;
(10,1,-73) both sides; (10,6,-73,up) xd12 11; (9,2,-73,up)
xd12 1 mf16 6.  Sources: ties_h603 (W1+[0xC8,0xF0)+W2
near-ties), ties_h604 (W1), ties_comb5/comb8 leftovers.
Emit h632_inputs.txt (3ffc m) + h632_rows.json with frame
features, capped per zone.
"""
import json
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h577_three_term import E2M
from h453_chain_variants import (C6_1, C6_2, C6_3, C6_4, C6_5,
                                 C6_6, build_chain, mul_round)
from h588_select import split_words

CAP = 700
TARGET_KEYS = {
    (7, 2, -72, "dn"), (7, 4, -72, "dn"), (7, 6, -72, "dn"),
    (10, 1, -73, "dn"), (10, 1, -73, "up"),
    (10, 6, -73, "up"), (9, 2, -73, "up"),
}


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
    if key not in TARGET_KEYS:
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
    return {"m": f"{m:x}", "key": list(key), "theta": theta,
            "xd12": int(xd12), "mf16": min(15, int(mf * 16)),
            "st": int(st), "tau": tau, "mf": mf,
            "Vlow": str(Vlow), "kf": kf, "rfv": str(pos[2]),
            "EU": str(EU), "ce": ce}


def main():
    ms = set()
    for fn in ("ties_h632.txt",):
        try:
            for line in open(fn):
                f = line.split()
                d, l3 = int(f[1]), int(f[2])
                if (d, l3) not in ((7, 2), (7, 4), (7, 6),
                                   (10, 1), (10, 6), (9, 2)):
                    continue
                ms.add(int(f[0], 16))
        except FileNotFoundError:
            print(f"missing {fn}")
    print(f"candidate m's: {len(ms)}", flush=True)
    with Pool(14) as pool:
        rows = pool.map(build_row, sorted(ms), chunksize=500)
    percell = defaultdict(int)
    out = []
    for r in rows:
        if r is None:
            continue
        cell = (tuple(r["key"]), r["xd12"], r["mf16"])
        if percell[cell] >= CAP:
            continue
        percell[cell] += 1
        out.append(r)
    print(f"selected: {len(out)}")
    cc = defaultdict(int)
    for r in out:
        cc[(tuple(r["key"]), r["xd12"] if
            tuple(r["key"])[0] != 7 else
            (r["xd12"], r["mf16"]))] += 1
    for kk in sorted(cc, key=str):
        print(f"  {kk}: {cc[kk]}")
    json.dump(out, open("h632_rows.json", "w"))
    with open("h632_inputs.txt", "w") as fh:
        for r in out:
            fh.write(f"3ffc {int(r['m'], 16):016x}\n")


if __name__ == "__main__":
    main()
