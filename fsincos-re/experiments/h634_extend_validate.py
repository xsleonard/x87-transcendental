#!/usr/bin/env python3
"""h634: model v7 — close the uncovered zones.

Extension (justified by h631/h632/h633 fits: every fitted cell
of these strata admits j=0 with wide margins — never-fire
territory; j=0 = the EU default):
  (7,2/4/6,-72,dn), (10,1,-73,up/dn), (10,6,-73,up):
  add const-j=0 zones for every xd12 0-11 not already fitted.
Plus: fit the missing (9,2,-73,up) V5 cell (xd12=1, mf16=6)
from the h631 captures.
Validation (blind: none of the corpus rows entered any fit):
rescore ALL corpus in-zone rows (both-branch recovery) under
v7 — target: the 5 uncovered base-misses predicted, no new
breaks.  Output: h634_model_v3v7.json, h634_model_v5v7.json.
"""
import json
import math
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import (ROUNDING_MODES, load_labeled_rows,
                                  final_cosine_result)
from h453_chain_variants import (C6_1, C6_2, C6_3, C6_4, C6_5,
                                 C6_6, build_chain, mul_round)
from h588_select import split_words
from h598_jframe import QGRID, AGRID, jinterval
from h609_ref_predictor import V5_KEYS

EXT_KEYS = [(7, 2, -72, "dn"), (7, 4, -72, "dn"),
            (7, 6, -72, "dn"), (10, 1, -73, "dn"),
            (10, 1, -73, "up"), (10, 6, -73, "up")]


def fit_92_cell():
    recs = json.load(open("h631_rows.json"))
    st_f = {md: open(f"h631_{md}_status.txt").read()
            .splitlines() for md in ROUNDING_MODES}
    rows = []
    for i, rec in enumerate(recs):
        if tuple(rec["key"]) != (9, 2, -73, "up"):
            continue
        if rec["xd12"] != 1 or rec["mf16"] != 6:
            continue
        t = [st_f[md][i].split() for md in ROUNDING_MODES]
        if any(x[0] != "OK" for x in t):
            continue
        hw = [int(x[2], 16) for x in t]
        EU, Vlow, kf, rfv, ce = (int(rec["EU"]),
                                 int(rec["Vlow"]), rec["kf"],
                                 int(rec["rfv"]), rec["ce"])
        ivs = []
        for z in (-2, -1, 0, 1, 2):
            refs = [final_cosine_result(-(EU + z), ce, md)
                    for md in ROUNDING_MODES]
            if refs == hw:
                lo, hi = jinterval(Vlow, kf, rfv, z)
                if lo <= hi:
                    ivs.append((lo, hi))
        if not ivs:
            continue
        rows.append((rec["tau"], rec["mf"],
                     min(l for l, h in ivs),
                     max(h for l, h in ivs), rec["st"]))
    print(f"(9,2) cell rows: {len(rows)}")
    best = (-1, None)
    for j in range(-16, 17):
        n = sum(1 for tau, mf, lo, hi, st in rows
                if lo <= j <= hi)
        if n == len(rows) and rows:
            best = (n, (0.0, 0.0, float(j)))
            break
    if best[1] is None:
        for q in QGRID:
            for a in AGRID:
                ev = []
                for (tau, mf, lo, hi, st) in rows:
                    x = q * tau + a * mf
                    ev.append((lo - 0.5 - x, 1))
                    ev.append((hi + 0.5 - x, -1))
                ev.sort()
                cur, bc, bb = 0, -1, 0.0
                for pos, d in ev:
                    cur += d
                    if cur > bc:
                        bc, bb = cur, pos + 1e-9
                if bc > best[0]:
                    best = (bc, (q, a, bb))
        print(f"(9,2) cell fit covers {best[0]}/{len(rows)}")
    else:
        print("(9,2) cell: const-j")
    return best[1]


def main():
    v3 = json.load(open("h604_model_v3.json"))
    v5 = json.load(open("h606_v5_model.json"))
    added = 0
    for key in EXT_KEYS:
        jj = -16.0 if key[3] == "dn" else 16.0
        for xd12 in range(12):
            zk = str((key, xd12))
            if zk not in v3["fits"]:
                v3["fits"][zk] = [0.0, 0.0, jj]
                added += 1
    print(f"extension zones added: {added}")
    f92 = fit_92_cell()
    if f92 is None:
        # no population anywhere (range-shift corner): nearest
        # fitted cell (same xd12, mf16=8), validated below on
        # the only known rows
        f92 = v5["fits"][str(((9, 2, -73, "up"), 1, 5))]
        for st in range(64):
            ck = str((((9, 2, -73, "up"), 1, 5), st))
            if ck in v5["cbest"]:
                v5["cbest"][str((((9, 2, -73, "up"), 1, 6),
                                 st))] = v5["cbest"][ck]
        print("(9,2) cell: nearest-cell (mf16=5) parameters")
    v5["fits"][str(((9, 2, -73, "up"), 1, 6))] = list(f92)
    json.dump(v3, open("h634_model_v3v7.json", "w"))
    json.dump(v5, open("h634_model_v5v7.json", "w"))
    # ---- corpus validation with v7
    import h609_ref_predictor as RP
    fits, cbest = {}, {}
    for k, v in v3["fits"].items():
        key, xd12 = eval(k)
        if tuple(key) in RP.V5_KEYS:
            continue
        fits[(tuple(key), xd12)] = tuple(v)
    for k, c in v3["cbest"].items():
        (key, xd12), st = eval(k)
        if tuple(key) in RP.V5_KEYS:
            continue
        cbest[((tuple(key), xd12), st)] = c
    for k, v in v5["fits"].items():
        key, xd12, mf16 = eval(k)
        fits[(tuple(key), xd12, mf16)] = tuple(v)
    for k, c in v5["cbest"].items():
        (key, xd12, mf16), st = eval(k)
        cbest[((tuple(key), xd12, mf16), st)] = c

    def recover_both(t):
        outs = []
        for sh in (60, 61):
            s0 = math.isqrt(t << sh)
            for s in range(s0 - 2, s0 + 3):
                if s <= 0:
                    continue
                s2 = s * s
                r2 = s2.bit_length() - 67
                if r2 >= 0 and (s2 >> r2) == t:
                    mm = s
                    while mm.bit_length() > 64:
                        mm >>= 1
                    while 0 < mm.bit_length() < 64:
                        mm <<= 1
                    outs.append(mm)
        return outs

    cens = defaultdict(int)
    for fields, hw_sigs in load_labeled_rows():
        if fields.get("active") != "1" or \
                fields["lsign"] != "1" or \
                fields["rsign"] != "0":
            continue
        le2, re2 = int(fields["le2"]), int(fields["re2"])
        ls, rs = int(fields["ls"], 16), int(fields["rs"], 16)
        dist, low3 = int(fields["dist"]), int(fields["low3"])
        prepay = low3 + 8 - dist
        scale = min(le2, re2, le2 - 8)
        A = ls << (le2 - scale)
        P = prepay << (le2 - 8 - scale)
        M = A - (rs << (re2 - scale)) + P
        if M <= 0:
            continue
        k = max(M.bit_length() - 67, 0)
        if k < 3:
            continue
        disc = M & ((1 << k) - 1)
        if disc > 2 and disc < (1 << k) - 2:
            continue
        mul = int(fields["mul"], 16)
        good = None
        for mm in recover_both(mul):
            mag = (0, -66, mm)
            sq = mul_round(mag, mag, 67, "chop")
            if sq[2] != mul:
                continue
            f4 = mul_round(sq, sq, 67, "chop")
            neg = build_chain(f4, C6_5, C6_3, C6_1, 67, 64,
                              "rn", False, False, False)
            pos = build_chain(f4, C6_6, C6_4, C6_2, 67, 64,
                              "rn", False, False, False)
            if f4[2] == int(fields["f4"], 16) and \
                    neg[2] == int(fields["lf"], 16) and \
                    pos[2] == int(fields["rf"], 16):
                good = (mm, sq, f4, neg, pos)
                break
        if good is None:
            cens["unrecovered"] += 1
            continue
        mm, sq, f4, neg, pos = good
        theta = disc if disc <= 2 else disc - (1 << k)
        side = "up" if theta <= 0 else "dn"
        ce = scale + k
        R = M >> k
        hw = [hw_sigs[md] for md in ROUNDING_MODES]
        base_ok = hw == [final_cosine_result(-R, ce, md)
                         for md in ROUNDING_MODES]
        B_full = f4[2] * pos[2]
        rsh = B_full.bit_length() - 67
        rdisc = B_full & ((1 << rsh) - 1)
        f4_full = sq[2] * sq[2]
        s4 = f4_full.bit_length() - 67
        t4 = f4_full & ((1 << s4) - 1)
        left = mul_round(sq, neg, 67, "chop")
        right = mul_round(f4, pos, 67, "chop")
        scale2 = min(left[1], right[1], left[1] - 8)
        bshift = right[1] - scale2
        F = rsh - bshift
        if F < 0:
            continue
        kf = k + F
        A2 = left[2] << (left[1] - scale2)
        P2 = prepay << (left[1] - 8 - scale2)
        APf = (A2 + P2) << F
        EU = (APf - B_full) >> kf
        Vlow = (APf - B_full) - (EU << kf)
        za, zb = (0, 1) if side == "up" else (-1, 0)
        ra = [final_cosine_result(-(EU + za), ce, md)
              for md in ROUNDING_MODES]
        rb = [final_cosine_result(-(EU + zb), ce, md)
              for md in ROUNDING_MODES]
        if ra == rb:
            cens[("blind", base_ok)] += 1
            continue
        S, C = split_words(f4[2], pos[2])
        st = ((S + C) >> max(rsh - 59, 0)) & 63
        tau = t4 / (1 << s4)
        mf = (mm & ((1 << 63) - 1)) / (1 << 63)
        xd12 = min(11, (rdisc * 12) >> rsh)
        key = (dist, low3, ce, side)
        zid = (key, xd12, min(15, int(mf * 16))) if key in \
            RP.V5_KEYS else (key, xd12)
        f = fits.get(zid)
        if f is None:
            cens[("STILL_uncovered", base_ok, key)] += 1
            continue
        q, a, b = f
        c = cbest.get((zid, st), 0)
        j = round(q * tau + a * mf + b + c)
        req2p = (4 * Vlow - j * pos[2]) >> (kf + 2)
        port_ok = hw == [final_cosine_result(-(EU + req2p),
                                             ce, md)
                         for md in ROUNDING_MODES]
        cens[("scored", base_ok, port_ok)] += 1
    print(dict(sorted(cens.items(), key=str)))


if __name__ == "__main__":
    main()
