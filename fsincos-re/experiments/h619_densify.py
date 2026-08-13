#!/usr/bin/env python3
"""h619 phase 1: densify the miss cells.

Target cells = every (key, xd12, mf16) cell holding at least 2
of the h618 miss rows, plus their mf16 neighbors.  From the
h616 constructible pool (comb near-tie m's with a valid
x = (M66 +- m/2)/4 construction), select up to CAP rows per
cell (excluding the 56,190 already-captured), emit
h619_inputs.txt for capture and h619_rows.json with per-row
frame data for the refit (tau, mf, st, xd12, Vlow, kf, rfv,
EU, ce, key, side refs).
Usage: h619_densify.py
"""
import json
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h577_three_term import E2M
from h453_chain_variants import (C6_1, C6_3, C6_5, C6_2, C6_4,
                                 C6_6, build_chain, mul_round)
from h588_select import split_words

M66 = (3 << 64) | 0x243F6A8885A308D3
CAP = 3000
TARGET_CELLS = None


def cells_from_misses():
    locked = json.load(open("h616_locked.json"))
    st_files = {md: open(f"h616_{md}_status.txt").read()
                .splitlines() for md in ROUNDING_MODES}
    cnt = defaultdict(int)
    for i, rec in enumerate(locked):
        hw = [f"{int(st_files[md][i].split()[2], 16):x}"
              for md in ROUNDING_MODES]
        if hw == rec["on"]:
            continue
        m = int(rec["m"], 16)
        mf16 = min(15, int(((m & ((1 << 63) - 1)) / (1 << 63))
                           * 16))
        cnt[(tuple(rec["key"]), rec["theta"], mf16)] += 1
    cells = set()
    for (key, theta, mf16), n in cnt.items():
        if n < 2:
            continue
        for d in (-1, 0, 1):
            if 0 <= mf16 + d <= 15:
                cells.add((key, mf16 + d))
    return cells


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
    ce = scale + k
    if ce not in (-72, -73):
        return None
    side = "up" if theta <= 0 else "dn"
    key = (dist, low3, ce, side)
    mf = (m & ((1 << 63) - 1)) / (1 << 63)
    mf16 = min(15, int(mf * 16))
    if TARGET_CELLS is not None and (key, mf16) not in \
            TARGET_CELLS:
        return None
    bshift = right[1] - scale
    F = rsh - bshift
    if F < 0:
        return None
    kf = k + F
    APf = (A + P) << F
    EU = (APf - B_full) >> kf
    Vlow = (APf - B_full) - (EU << kf)
    # observable?
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
    xd12 = min(11, (rdisc * 12) >> rsh)
    return (m, key, theta, xd12, mf16, int(st), tau, mf,
            str(Vlow), kf, str(pos[2]), str(EU), ce)


def init_cells(c):
    global TARGET_CELLS
    TARGET_CELLS = c


def main():
    cells = cells_from_misses()
    print(f"target cells: {len(cells)}", flush=True)
    captured = {int(r["m"], 16)
                for r in json.load(open("h616_locked.json"))}
    ms = set()
    for fn in ("ties_comb5.txt", "ties_comb6.txt",
               "ties_comb7.txt", "ties_comb8.txt"):
        for line in open(fn):
            m = int(line.split()[0], 16)
            if m & 1 or m in captured:
                continue
            ms.add(m)
    cands = []
    for m in ms:
        for sgn in (1, -1):
            Aint = M66 + sgn * (m // 2)
            if Aint % 4 == 0:
                cands.append((m, Aint // 4))
                break
    print(f"constructible fresh: {len(cands)}", flush=True)
    todo = [m for m, xs in cands]
    with Pool(14, initializer=init_cells,
              initargs=(cells,)) as pool:
        rows = pool.map(build_row, todo, chunksize=500)
    xsig_of = dict(cands)
    percell = defaultdict(int)
    out = []
    for r in rows:
        if r is None:
            continue
        m, key, theta, xd12, mf16, st, tau, mf = r[:8]
        cell = (key, mf16)
        if percell[cell] >= CAP:
            continue
        percell[cell] += 1
        out.append({"m": f"{m:x}", "x": f"3fff {xsig_of[m]:016x}",
                    "key": list(key), "theta": theta,
                    "xd12": xd12, "mf16": mf16, "st": st,
                    "tau": tau, "mf": mf, "Vlow": r[8],
                    "kf": r[9], "rfv": r[10], "EU": r[11],
                    "ce": r[12]})
    print(f"selected rows: {len(out)}")
    for cell in sorted(percell, key=str):
        print(f"  {cell}: {percell[cell]}")
    json.dump(out, open("h619_rows.json", "w"))
    with open("h619_inputs.txt", "w") as fh:
        for rec in out:
            fh.write(rec["x"] + "\n")


if __name__ == "__main__":
    main()
