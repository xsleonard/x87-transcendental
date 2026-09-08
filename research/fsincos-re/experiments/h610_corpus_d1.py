#!/usr/bin/env python3
"""h610: PHASE D1 (2026-08-12) — the Round-57 rule scored against
the ORIGINAL corpus in pre-patch coordinates, EU frame, blind
filter mandatory (h595).

Per corpus row (h437 loader; h516 arithmetic):
  M = A - B + P from the trace; k = bitlen(M) - 67; require
  k >= 3; disc = M & (2^k - 1); zone: disc <= 2 (theta = disc,
  dn side for theta >= 1) or disc >= 2^k - 2 (theta = disc -
  2^k, up side); ce = scale + k.
Labels (EU-anchored): refs at EU / EU+1 (up) or EU-1 / EU (dn);
blind iff equal; OTHER counted separately.
Rule: h609 merged predictor (h604 v3 + h606 v5) on replica
features from recover_m -> qrow3 (self-check dist/low3 + R).
Scores:
  baseline (pre-patch model) = refs(R);
  ported   = refs(EU + req2_pred) where covered, else baseline.
D1 numbers: in-zone rows, baseline mismatches there, ported
mismatches, fixed/broken, uncovered, blind mass, OTHER, plus
whole-corpus totals.
"""
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import (ROUNDING_MODES, load_labeled_rows,
                                  final_cosine_result)
from h453_chain_variants import recover_m
from h577_three_term import qrow3
from h588_select import split_words
from h609_ref_predictor import load_model, predict
import h539_D_library as DL

FITS = CBEST = None


def init():
    global FITS, CBEST
    FITS, CBEST = load_model()


def score_row(job):
    fields, hw_sigs = job
    if fields.get("active") != "1" or fields["lsign"] != "1" \
            or fields["rsign"] != "0":
        return ("outside_form",)
    le2, re2 = int(fields["le2"]), int(fields["re2"])
    ls, rs = int(fields["ls"], 16), int(fields["rs"], 16)
    dist, low3 = int(fields["dist"]), int(fields["low3"])
    prepay = low3 + 8 - dist
    scale = min(le2, re2, le2 - 8)
    A = ls << (le2 - scale)
    B = rs << (re2 - scale)
    unit = le2 - 8 - scale
    Pv = prepay << unit
    M = A - B + Pv
    if M <= 0:
        return ("outside_form",)
    k = max(M.bit_length() - 67, 0)
    if k < 3:
        return ("out_of_zone",)
    disc = M & ((1 << k) - 1)
    R = M >> k
    ce = scale + k
    hw = [hw_sigs[md] for md in ROUNDING_MODES]
    base_ref = [final_cosine_result(-R, ce, md)
                for md in ROUNDING_MODES]
    base_ok = hw == base_ref
    if disc <= 2:
        theta = disc
    elif disc >= (1 << k) - 2:
        theta = disc - (1 << k)
    else:
        return ("out_of_zone", None, base_ok)
    side = "up" if theta <= 0 else "dn"
    m = recover_m(int(fields["mul"], 16))
    if m is None:
        return ("no_m", side, base_ok)
    while m.bit_length() > 64:
        m >>= 1
    while 0 < m.bit_length() < 64:
        m <<= 1
    mhex = f"{m:016x}"
    (m2, R2, A2, P2, B_full, rsh, rdisc, lsh, ldisc, s4, t4,
     bshift, k2, dist2, low32) = qrow3(mhex)
    F = rsh - bshift
    if F < 0 or dist2 != dist or low32 != low3:
        return ("replica_mismatch", side, base_ok)
    kf = k2 + F
    APf = (A2 + P2) << F
    EU = (APf - B_full) >> kf
    if abs(EU - R) > 2:
        return ("replica_mismatch", side, base_ok)
    za, zb = (0, 1) if side == "up" else (-1, 0)
    ra = [final_cosine_result(-(EU + za), ce, md)
          for md in ROUNDING_MODES]
    rb = [final_cosine_result(-(EU + zb), ce, md)
          for md in ROUNDING_MODES]
    if ra == rb:
        return ("blind", side, base_ok)
    if hw == rb:
        fire = 1 if side == "up" else 0
    elif hw == ra:
        fire = 0 if side == "up" else 1
    else:
        return ("OTHER", side, base_ok)
    Vlow = (APf - B_full) - (EU << kf)
    qr = DL.qrow(mhex)
    f4v, rfv = qr[2], qr[3]
    S, C = split_words(f4v, rfv)
    st = ((S + C) >> max(rsh - 59, 0)) & 63
    tau = t4 / (1 << s4)
    mf = (m & ((1 << 63) - 1)) / (1 << 63)
    xd12 = min(11, (rdisc * 12) >> rsh)
    key = (dist, low3, ce, side)
    p = predict(FITS, CBEST, key, xd12, mf, st, tau, Vlow, kf,
                rfv)
    if p is None:
        return ("uncovered", side, base_ok, key)
    predf, req2p, src = p
    port_ref = [final_cosine_result(-(EU + req2p), ce, md)
                for md in ROUNDING_MODES]
    port_ok = hw == port_ref
    return ("scored", side, base_ok, port_ok, fire, predf, key,
            theta)


def main():
    rows = load_labeled_rows()
    print(f"corpus rows: {len(rows)}", flush=True)
    with Pool(14, initializer=init) as pool:
        out = pool.map(score_row, rows, chunksize=200)
    tab = defaultdict(int)
    per_key = defaultdict(lambda: [0, 0, 0, 0])
    fixed = broken = 0
    base_mis_zone = port_mis_zone = 0
    for o in out:
        tab[o[0]] += 1
        if o[0] in ("blind", "no_m", "replica_mismatch",
                    "uncovered", "OTHER", "out_of_zone"):
            if not o[2]:
                tab[(o[0], "base_mismatch")] += 1
        if o[0] == "scored":
            _, side, base_ok, port_ok, fire, predf, key, th = o
            base_mis_zone += not base_ok
            port_mis_zone += not port_ok
            fixed += (not base_ok) and port_ok
            broken += base_ok and (not port_ok)
            pk = per_key[key]
            pk[0] += 1
            pk[1] += predf == fire
            pk[2] += not base_ok
            pk[3] += not port_ok
    print("\nrow census:", {k: v for k, v in sorted(
        tab.items(), key=str) if isinstance(k, str)})
    print("\nbase mismatches among non-scored zone rows:",
          {k: v for k, v in sorted(tab.items(), key=str)
           if isinstance(k, tuple)})
    ns = tab["scored"]
    print(f"\nD1 (scored in-zone observable rows): n={ns}")
    print(f"  baseline mismatches: {base_mis_zone}")
    print(f"  ported   mismatches: {port_mis_zone}")
    print(f"  fixed {fixed}, broken {broken}")
    print("\nper stratum-side (n, pred-acc, base-mis, "
          "port-mis):")
    for key in sorted(per_key, key=str):
        n, ok, bm, pm = per_key[key]
        print(f"  {key}: n={n:5d} acc={ok / n:.4f} "
              f"base_mis={bm:4d} port_mis={pm:4d}")


if __name__ == "__main__":
    main()
