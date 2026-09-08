#!/usr/bin/env python3
"""h626: ATTACK THE 248 REPLICA-MISMATCH CORPUS ROWS.

These are near-boundary corpus rows where recover_m + the
fixed-scale replica fail to reproduce the traced terminal
(h610: dist/low3 disagree or |EU - R| > 2) — the h519 64-row
family and relatives.  Two suspects:
  A. m-recovery ambiguity: chop67 of m^2 does not always
     invert uniquely; try m + delta for delta in [-3, 3] at
     both 63->64 normalizations.
  B. binade dependence: the replica hardwires the e=-3 scale
     (E2M = -66); other input binades change the chain adds
     against fixed-exponent ROM constants.  Parameterize the
     scale: E2M' = -66 + d, d in [-12, 12].
Validator: the FULL traced operands — sq (mul), f4, lf (neg),
rf (pos) significands must all match exactly.
Output: per-row category (recovery-fix / scale-fix / both /
UNFIXED), and for fixed rows a rescore under the Round-57 rule
(are the 7 baseline mismatches among them now predicted?).
"""
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import (ROUNDING_MODES, load_labeled_rows,
                                  final_cosine_result)
from h453_chain_variants import (C6_1, C6_2, C6_3, C6_4, C6_5,
                                 C6_6, build_chain, mul_round,
                                 recover_m)
from h588_select import split_words
from h609_ref_predictor import load_model, predict

FITS = CBEST = None


def initp():
    global FITS, CBEST
    FITS, CBEST = load_model()


def replica(m, d):
    """Parameterized replica: operand value m * 2^(-66 + d).
    Returns dict of significands + terminal frame."""
    mag = (0, -66 + d, m)
    sq = mul_round(mag, mag, 67, "chop")
    f4 = mul_round(sq, sq, 67, "chop")
    neg = build_chain(f4, C6_5, C6_3, C6_1, 67, 64, "rn",
                      False, False, False)
    pos = build_chain(f4, C6_6, C6_4, C6_2, 67, 64, "rn",
                      False, False, False)
    return mag, sq, f4, neg, pos


def diagnose(job):
    fields, hw_sigs = job
    mul = int(fields["mul"], 16)
    tlf = int(fields["lf"], 16)
    trf = int(fields["rf"], 16)
    tf4 = int(fields["f4"], 16)
    m0 = recover_m(mul)
    if m0 is None:
        return ("no_m", None)
    while m0.bit_length() > 64:
        m0 >>= 1
    while 0 < m0.bit_length() < 64:
        m0 <<= 1
    cands = set()
    # widths 63..66 bits: the kernel's reduced argument can be
    # wider than 64 bits (wide rw.sig); do NOT renormalize
    for base in (m0 >> 1, m0, m0 << 1, m0 << 2):
        for delta in range(-4, 5):
            mm = base + delta
            if mm > 0:
                cands.add(mm)
    for mm in sorted(cands):
        for d in range(-12, 13):
            mag, sq, f4, neg, pos = replica(mm, d)
            if sq[2] != mul:
                break  # sq scale-free: mismatch means wrong m
            if f4[2] == tf4 and neg[2] == tlf and \
                    pos[2] == trf:
                cat = []
                if mm != m0 and mm != (m0 << 1 if
                                       m0.bit_length() < 64
                                       else m0):
                    cat.append("recovery")
                if d != 0:
                    cat.append(f"scale{d:+d}")
                return ("FIXED" if cat else "baseline??",
                        (mm, d, "+".join(cat) or "none"))
    return ("UNFIXED", (m0, None, None))


def rescore(job, mm, d):
    """Rule evaluation for a fixed row at (mm, d)."""
    fields, hw_sigs = job
    le2, re2 = int(fields["le2"]), int(fields["re2"])
    ls, rs = int(fields["ls"], 16), int(fields["rs"], 16)
    dist, low3 = int(fields["dist"]), int(fields["low3"])
    prepay = low3 + 8 - dist
    scale = min(le2, re2, le2 - 8)
    A = ls << (le2 - scale)
    B = rs << (re2 - scale)
    M = A - B + (prepay << (le2 - 8 - scale))
    if M <= 0:
        return None
    k = max(M.bit_length() - 67, 0)
    if k < 3:
        return ("out_of_zone",)
    disc = M & ((1 << k) - 1)
    if disc > 2 and disc < (1 << k) - 2:
        return ("out_of_zone",)
    theta = disc if disc <= 2 else disc - (1 << k)
    R = M >> k
    ce = scale + k
    hw = [hw_sigs[md] for md in ROUNDING_MODES]
    base_ok = hw == [final_cosine_result(-R, ce, md)
                     for md in ROUNDING_MODES]
    mag, sq, f4, neg, pos = replica(mm, d)
    B_full = f4[2] * pos[2]
    rsh = B_full.bit_length() - 67
    rdisc = B_full & ((1 << rsh) - 1)
    f4_full = sq[2] * sq[2]
    s4 = f4_full.bit_length() - 67
    t4 = f4_full & ((1 << s4) - 1)
    right = mul_round(f4, pos, 67, "chop")
    left = mul_round(sq, neg, 67, "chop")
    scale2 = min(left[1], right[1], left[1] - 8)
    bshift = right[1] - scale2
    F = rsh - bshift
    if F < 0:
        return ("noF",)
    kf = k + F
    # frame via replica quantities directly:
    A2 = left[2] << (left[1] - scale2)
    P2 = prepay << (left[1] - 8 - scale2)
    APf2 = (A2 + P2) << F
    EU = (APf2 - B_full) >> kf
    Vlow = (APf2 - B_full) - (EU << kf)
    side = "up" if theta <= 0 else "dn"
    za, zb = (0, 1) if side == "up" else (-1, 0)
    ra = [final_cosine_result(-(EU + za), ce, md)
          for md in ROUNDING_MODES]
    rb = [final_cosine_result(-(EU + zb), ce, md)
          for md in ROUNDING_MODES]
    if ra == rb:
        return ("blind", base_ok)
    S, C = split_words(f4[2], pos[2])
    st = ((S + C) >> max(rsh - 59, 0)) & 63
    tau = t4 / (1 << s4)
    bl = mm.bit_length()
    mf = (mm - (1 << (bl - 1))) / (1 << (bl - 1))
    xd12 = min(11, (rdisc * 12) >> rsh)
    key = (dist, low3, ce, side)
    p = predict(FITS, CBEST, key, xd12, mf, st, tau, Vlow, kf,
                pos[2])
    if p is None:
        return ("uncovered", base_ok)
    _, req2p, _ = p
    port_ok = hw == [final_cosine_result(-(EU + req2p), ce, md)
                     for md in ROUNDING_MODES]
    return ("scored", base_ok, port_ok)


def worker(job):
    fields, hw_sigs = job
    if fields.get("active") != "1" or fields["lsign"] != "1" \
            or fields["rsign"] != "0":
        return None
    le2, re2 = int(fields["le2"]), int(fields["re2"])
    ls, rs = int(fields["ls"], 16), int(fields["rs"], 16)
    dist, low3 = int(fields["dist"]), int(fields["low3"])
    prepay = low3 + 8 - dist
    scale = min(le2, re2, le2 - 8)
    M = (ls << (le2 - scale)) - (rs << (re2 - scale)) \
        + (prepay << (le2 - 8 - scale))
    if M <= 0:
        return None
    k = max(M.bit_length() - 67, 0)
    if k < 3:
        return None
    disc = M & ((1 << k) - 1)
    if disc > 2 and disc < (1 << k) - 2:
        return None
    # in-zone: is it a replica mismatch under the h610 recipe?
    m = recover_m(int(fields["mul"], 16))
    if m is not None:
        while m.bit_length() > 64:
            m >>= 1
        while 0 < m.bit_length() < 64:
            m <<= 1
        mag, sq, f4, neg, pos = replica(m, 0)
        if f4[2] == int(fields["f4"], 16) and \
                neg[2] == int(fields["lf"], 16) and \
                pos[2] == int(fields["rf"], 16):
            return None  # replica fine (h610 matched these)
    cat, info = diagnose(job)
    out = [cat, info]
    if cat in ("FIXED", "baseline??"):
        mm, d, how = info
        out.append(rescore(job, mm, d))
    return tuple(out)


def main():
    rows = load_labeled_rows()
    print(f"corpus rows: {len(rows)}", flush=True)
    with Pool(14, initializer=initp) as pool:
        res = pool.map(worker, rows, chunksize=200)
    res = [r for r in res if r is not None]
    print(f"in-zone replica-mismatch rows: {len(res)}")
    cats = defaultdict(int)
    hows = defaultdict(int)
    sc = defaultdict(int)
    for r in res:
        cats[r[0]] += 1
        if r[0] in ("FIXED", "baseline??"):
            hows[r[1][2]] += 1
            if len(r) > 2 and r[2] is not None:
                t = r[2]
                if t[0] == "scored":
                    sc[("base_ok", t[1])] += 1
                    sc[("port_ok", t[2])] += 1
                else:
                    sc[t[0]] += 1
    print("categories:", dict(cats))
    print("fix modes:", dict(sorted(hows.items(), key=str)))
    print("rescore of fixed rows:", dict(sorted(sc.items(),
                                                key=str)))


if __name__ == "__main__":
    main()
