#!/usr/bin/env python3
"""h627c: fit the table-path borrow rule.

Rows: h627_zone.tsv (input + terminal trace) + h627 captures.
Frame: table-frame EU (h626c): B_full = f4_field * rf_field,
APf from traced ls/payload, alias-robust J-intervals on the
rf/4 ladder.  Ladder feasibility is itself a result.
Model ladder per stratum-side (dist, low3, ce, side):
  L0 const-j;  L1 + xd12 zones (const-j per zone);
  L2 + SUM6 comparator (c_lo/c_hi/t per zone, c in [-4,4]).
Held-out by input-hash.  Then: score the 7 corpus miss rows
(features from their corpus traces) under the fitted rule.
"""
import json
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import (ROUNDING_MODES, load_labeled_rows,
                                  final_cosine_result)
from h453_chain_variants import mul_round, recover_m, \
    build_chain, C6_1, C6_3, C6_5
from h588_select import split_words
from h598_jframe import jinterval


def frame_from_trace(f):
    le2, re2 = int(f["le2"]), int(f["re2"])
    ls, rs = int(f["ls"], 16), int(f["rs"], 16)
    dist, low3 = int(f["dist"]), int(f["low3"])
    prepay = low3 + 8 - dist
    scale = min(le2, re2, le2 - 8)
    A = ls << (le2 - scale)
    P = prepay << (le2 - 8 - scale)
    M = A - (rs << (re2 - scale)) + P
    if M <= 0:
        return None
    k = M.bit_length() - 67
    if k < 3:
        return None
    disc = M & ((1 << k) - 1)
    if disc > 2 and disc < (1 << k) - 2:
        return None
    theta = disc if disc <= 2 else disc - (1 << k)
    side = "up" if theta <= 0 else "dn"
    ce = scale + k
    f4v = int(f["f4"], 16)
    rfv = int(f["rf"], 16)
    B_full = f4v * rfv
    rsh = B_full.bit_length() - 67
    if (B_full >> rsh) != rs:
        return None
    rdisc = B_full & ((1 << rsh) - 1)
    bshift = re2 - scale
    F = rsh - bshift
    if F < 0:
        return None
    kf = k + F
    APf = (A + P) << F
    EU = (APf - B_full) >> kf
    Vlow = (APf - B_full) - (EU << kf)
    return (dist, low3, ce, side, theta, EU, Vlow, kf, f4v,
            rfv, rsh, rdisc)


def label_row(args):
    f, hw = args
    fr = frame_from_trace(f)
    if fr is None:
        return None
    (dist, low3, ce, side, theta, EU, Vlow, kf, f4v, rfv,
     rsh, rdisc) = fr
    ivs = []
    for z in (-2, -1, 0, 1, 2):
        refs = [final_cosine_result(-(EU + z), ce, md)
                for md in ROUNDING_MODES]
        if refs == hw:
            lo, hi = jinterval(Vlow, kf, rfv, z)
            if lo <= hi:
                ivs.append((lo, hi))
    if not ivs:
        return ("noiv", None)
    jlo = min(l for l, h in ivs)
    jhi = max(h for l, h in ivs)
    S, C = split_words(f4v, rfv)
    st = ((S + C) >> max(rsh - 59, 0)) & 63
    xd12 = min(11, (rdisc * 12) >> rsh)
    key = (dist, low3, ce, side)
    h = (int(f["mul"], 16) * 2654435761 >> 16) & 1
    return ("ok", (key, h, jlo, jhi, int(st), int(xd12)))


def fit(rows):
    # returns model dict + held-out ladder
    bykey = defaultdict(list)
    for key, h, jlo, jhi, st, xd12 in rows:
        bykey[key].append((h, jlo, jhi, st, xd12))
    model = {}
    lad = defaultdict(lambda: [0, 0, 0, 0])
    for key, rl in sorted(bykey.items(), key=lambda kv:
                          str(kv[0])):
        tr = [r for r in rl if r[0] == 0]
        te = [r for r in rl if r[0] == 1]
        if not tr or not te:
            continue
        # L0 const-j
        cnt = defaultdict(int)
        for h, jlo, jhi, st, xd in tr:
            for j in range(jlo, jhi + 1):
                cnt[j] += 1
        j0 = max(cnt, key=cnt.get) if cnt else 0
        # L1 per-xd12 const-j
        jz = {}
        for xd in set(r[4] for r in tr):
            c2 = defaultdict(int)
            for h, jlo, jhi, st, x2 in tr:
                if x2 != xd:
                    continue
                for j in range(jlo, jhi + 1):
                    c2[j] += 1
            jz[xd] = max(c2, key=c2.get) if c2 else j0
        # L2 comparator per zone
        comp = {}
        for xd in jz:
            best = (-1, None)
            pts = [(st, jlo, jhi) for h, jlo, jhi, st, x2
                   in tr if x2 == xd]
            for t0 in range(0, 65):
                for clo in range(-4, 5):
                    for chi in range(-4, 5):
                        ok = sum(1 for st, jlo, jhi in pts
                                 if jlo <= jz[xd] +
                                 (clo if st < t0 else chi)
                                 <= jhi)
                        if ok > best[0]:
                            best = (ok, (t0, clo, chi))
            comp[xd] = best[1]
        model[key] = (j0, jz, comp)
        for h, jlo, jhi, st, xd in te:
            row = lad[key]
            row[0] += 1
            row[1] += jlo <= j0 <= jhi
            jx = jz.get(xd, j0)
            row[2] += jlo <= jx <= jhi
            t0, clo, chi = comp.get(xd, (0, 0, 0))
            row[3] += jlo <= jx + (clo if st < t0 else chi) \
                <= jhi
    return model, lad


def main():
    rows = []
    st_f = {md: open(f"h627_{md}_status.txt").read()
            .splitlines() for md in ROUNDING_MODES}
    zone = open("h627_zone.tsv").read().splitlines()
    for i, line in enumerate(zone):
        x, trace = line.split("\t")
        f = {}
        for tok in trace.split()[1:]:
            kk, v = tok.split("=")
            f[kk] = v
        hw = []
        ok = True
        for md in ROUNDING_MODES:
            t = st_f[md][i].split()
            if t[0] != "OK":
                ok = False
                break
            hw.append(int(t[2], 16))
        if ok:
            rows.append((f, hw))
    print(f"captured zone rows: {len(rows)}", flush=True)
    with Pool(14) as pool:
        ls = pool.map(label_row, rows, chunksize=200)
    good = [r[1] for r in ls if r is not None and r[0] == "ok"]
    noiv = sum(1 for r in ls if r is not None and
               r[0] == "noiv")
    print(f"labeled {len(good)}, no-interval {noiv}")
    model, lad = fit(good)
    print(f"\n{'stratum-side':22s} {'n_te':>6s} {'L0':>7s} "
          f"{'L1':>7s} {'L2':>7s}")
    g = [0, 0, 0, 0]
    for key in sorted(lad, key=str):
        n, l0, l1, l2 = lad[key]
        for i in range(4):
            g[i] += lad[key][i]
        print(f"{str(key):22s} {n:6d} {l0 / n:7.4f} "
              f"{l1 / n:7.4f} {l2 / n:7.4f}")
    print(f"{'TOTAL':22s} {g[0]:6d} {g[1] / g[0]:7.4f} "
          f"{g[2] / g[0]:7.4f} {g[3] / g[0]:7.4f}")
    json.dump({str(k): (v[0], {str(a): b for a, b in
                               v[1].items()},
                        {str(a): b for a, b in v[2].items()})
               for k, v in model.items()},
              open("h627_model.json", "w"))
    # ---- score the corpus table rows (incl. the 7 misses)
    print("\ncorpus table rows under the fitted rule:")
    crows = load_labeled_rows()
    nsc = defaultdict(int)
    for fields, hw_sigs in crows:
        if fields.get("active") != "1" or \
                fields["lsign"] != "1" or \
                fields["rsign"] != "0":
            continue
        fr = frame_from_trace(fields)
        if fr is None:
            continue
        # poly rows: replica matches -> skip
        mul = int(fields["mul"], 16)
        m = recover_m(mul)
        if m is not None:
            while m.bit_length() > 64:
                m >>= 1
            while 0 < m.bit_length() < 64:
                m <<= 1
            mag = (0, -66, m)
            sq = mul_round(mag, mag, 67, "chop")
            f4r = mul_round(sq, sq, 67, "chop")
            neg = build_chain(f4r, C6_5, C6_3, C6_1, 67, 64,
                              "rn", False, False, False)
            if f4r[2] == int(fields["f4"], 16) and \
                    neg[2] == int(fields["lf"], 16):
                continue
        (dist, low3, ce, side, theta, EU, Vlow, kf, f4v, rfv,
         rsh, rdisc) = fr
        hw = [hw_sigs[md] for md in ROUNDING_MODES]
        key = (dist, low3, ce, side)
        mk = model.get(key)
        R_chop = None
        le2, re2 = int(fields["le2"]), int(fields["re2"])
        ls2, rs2 = int(fields["ls"], 16), int(fields["rs"], 16)
        prepay = low3 + 8 - dist
        scale = min(le2, re2, le2 - 8)
        M = (ls2 << (le2 - scale)) - (rs2 << (re2 - scale)) \
            + (prepay << (le2 - 8 - scale))
        k2 = M.bit_length() - 67
        R_chop = M >> k2
        base_ok = hw == [final_cosine_result(-R_chop, ce, md)
                         for md in ROUNDING_MODES]
        if mk is None:
            nsc[("uncovered", base_ok)] += 1
            continue
        j0, jz, comp = mk
        S, C = split_words(f4v, rfv)
        st = ((S + C) >> max(rsh - 59, 0)) & 63
        xd12 = min(11, (rdisc * 12) >> rsh)
        j = jz.get(xd12, j0)
        t0, clo, chi = comp.get(xd12, (0, 0, 0))
        j += clo if st < t0 else chi
        req2p = (4 * Vlow - j * rfv) >> (kf + 2)
        rule_ok = hw == [final_cosine_result(-(EU + req2p),
                                             ce, md)
                         for md in ROUNDING_MODES]
        nsc[("scored", base_ok, rule_ok)] += 1
    print(dict(sorted(nsc.items(), key=str)))


if __name__ == "__main__":
    main()
