#!/usr/bin/env python3
"""h516: PHASE D1 — score the locked h515 rule against the ORIGINAL
corpus tie rows in pre-patch coordinates.

Per corpus tie row (h477c logic): label fire/clean/blind/other via
ok_for(0)/ok_for(-1); recover m from the traced square; recompute
(dist, low3, XT, XD, mf) with the comb build(); SELF-CHECK dist/low3
against the trace; apply the h515 rule.

Output: among observable ties — rule-correct / rule-wrong / in-band /
declared / uncovered; the D1 decision numbers (band+declared rows as a
fraction of ties; tie fires falling in band/declared).
"""
import json
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import (ROUNDING_MODES, load_labeled_rows,
                                  final_cosine_result)
from h453_chain_variants import recover_m
from h500_plane_m import build

RULE = json.load(open("h515_locked.json"))


def classify(dist, low3, XT, XD, mf):
    """-> (kind, pred) with kind in {'line','never','always',
    'declared','uncovered'}, pred in {0,1,None}."""
    if dist == 9 and 0.656 <= mf < 0.782:
        if low3 == 1:
            return "never", 0
        if low3 == 2:
            if XD >= 1/3 and mf - 0.25 * XT < 0.475:
                return "declared", None
            return "never", 0
        if low3 == 3:
            return line(0.125, 0.58325, 0.003, XT, mf)
        if low3 == 4:
            if XD < 1/3:
                return line(0.0833, 0.6186, 0.006, XT, mf)
            return line(0.084106, 0.707687, 0.003, XT, mf)
        if low3 == 5:
            return line(0.067505, 0.707687, 0.003, XT, mf)
        if low3 == 6:
            if XD < 1/3:
                return line(0.056366, 0.707687, 0.003, XT, mf)
            return line(0.053818, 0.763793, 0.003, XT, mf)
        if low3 == 7:
            return line(0.046380, 0.756040, 0.003, XT, mf)
    if dist == 8 and 0.781 <= mf < 0.938:
        if low3 == 1:
            return "declared", None
        if low3 == 2:
            if XD < 1/3:
                return "never", 0
            return "declared", None
        if low3 == 3:
            if XD < 2/3:
                return line(0.10332, 0.71321, 0.003, XT, mf)
            return line(0.1950, 0.8155, 0.006, XT, mf)
        if low3 == 4:
            if XD < 1/3:
                return line(0.0755, 0.7148, 0.008, XT, mf)
            return line(0.0714, 0.79190, 0.004, XT, mf)
        if low3 == 5:
            if XD < 2/3:
                k, p = line(0.0619, 0.7750, 0.003, XT, mf)
                if k == "line" and p == 0:
                    r = mf - 0.0619 * XT - 0.7750
                    if 0.004 <= r <= 0.05:
                        return "declared", None
                return k, p
            return line(0.0510, 0.8285, 0.012, XT, mf)
        if low3 == 6:
            if XD < 1/3:
                return line(0.05141, 0.76507, 0.003, XT, mf)
            return line(0.0977, 0.8163, 0.005, XT, mf)
        if low3 == 7:
            if XD < 2/3:
                return line(0.04320, 0.80194, 0.003, XT, mf)
            return line(0.08009, 0.84601, 0.003, XT, mf)
    if dist == 7 and 0.781 <= mf < 0.938:
        tw = min(11, int(XD * 12))
        if low3 == 1:
            if XD >= 2/3:
                return "always", 1
            t = {0: (0.33717, 0.63957), 1: (0.31898, 0.65565),
                 2: (0.31898, 0.65565), 3: (0.39510, 0.58911),
                 4: (0.36809, 0.61250), 5: (0.36055, 0.61987),
                 6: (0.36055, 0.61987), 7: (0.34966, 0.62838)}[tw]
            return line(t[0], t[1], 0.004, XT, mf)
        if low3 == 3:
            if XD < 1/3:
                return "never", 0
            t = {4: (0.12465, 0.85699), 5: (0.15678, 0.83706),
                 6: (0.14644, 0.84353), 7: (0.16063, 0.83509),
                 8: (0.15385, 0.83886), 9: (0.16972, 0.82932),
                 10: (0.16704, 0.83082), 11: (0.15932, 0.83565)}[tw]
            return line(t[0], t[1], 0.004, XT, mf)
        if low3 == 5:
            if XD < 2/3:
                return "never", 0
            t = {8: (0.09648, 0.89892), 9: (0.09978, 0.89790),
                 10: (0.08949, 0.90163), 11: (0.09871, 0.89831)}[tw]
            return line(t[0], t[1], 0.004, XT, mf)
        if low3 == 7:
            return "never", 0
    return "uncovered", None


def line(s, c, w, XT, mf):
    r = mf - s * XT - c
    if abs(r) < w:
        return "band", None
    return "line", (1 if r < 0 else 0)


def score_row(job):
    fields, hw_sigs = job
    if fields.get("active") != "1" or fields["lsign"] != "1" \
            or fields["rsign"] != "0":
        return None
    dist, low3 = int(fields["dist"]), int(fields["low3"])
    le2, re2 = int(fields["le2"]), int(fields["re2"])
    ls, rs = int(fields["ls"], 16), int(fields["rs"], 16)
    prepay = low3 + 8 - dist
    scale = min(le2, re2, le2 - 8)
    A = ls << (le2 - scale)
    B = rs << (re2 - scale)
    unit = le2 - 8 - scale
    Pv = prepay << unit
    hw = tuple(hw_sigs[m] for m in ROUNDING_MODES)
    M = A - B + Pv
    if M <= 0:
        return None
    k = max(M.bit_length() - 67, 0)
    if k < 3 or (M & ((1 << k) - 1)):
        return None
    R = M >> k

    def ok_for(delta):
        corr, corr_e = -(R + delta), scale + k
        return all(final_cosine_result(corr, corr_e, m) == h
                   for m, h in zip(ROUNDING_MODES, hw))

    ideal_ok, fire_ok = ok_for(0), ok_for(-1)
    if ideal_ok and fire_ok:
        status = "blind"
    elif ideal_ok:
        status = "clean"
    elif fire_ok:
        status = "fire"
    else:
        return ("other", dist, low3, None)
    m = recover_m(int(fields["mul"], 16))
    if m is None:
        return ("no_m", dist, low3, status)
    while m.bit_length() > 64:
        m >>= 1
    cell, XT, XD, mf, _ = build((f"{m:016x}", 0))
    if cell[0] != dist or cell[1] != low3:
        return ("replica_mismatch", dist, low3, status)
    kind, pred = classify(dist, low3, XT, XD, mf)
    return ("ok", dist, low3, status, kind, pred, mf)


def main():
    rows = load_labeled_rows()
    print(f"corpus rows: {len(rows)}")
    with Pool(8) as pool:
        out = pool.map(score_row, rows, chunksize=500)
    out = [o for o in out if o]
    bad = defaultdict(int)
    tab = defaultdict(int)
    wrong_detail = defaultdict(int)
    for o in out:
        if o[0] != "ok":
            bad[(o[0], o[3] if len(o) > 3 else None)] += 1
            continue
        _, dist, low3, status, kind, pred, mf = o
        if status == "blind":
            tab[("blind", kind)] += 1
            continue
        actual = 1 if status == "fire" else 0
        if kind in ("line", "never", "always"):
            if pred == actual:
                tab[("correct", kind)] += 1
            else:
                tab[("WRONG", kind)] += 1
                wrong_detail[(dist, low3, actual)] += 1
        else:
            tab[(kind, f"actual={actual}")] += 1
    print("\nnon-scorable:", dict(bad))
    print("\nscore table:")
    for key in sorted(tab):
        print(f"  {key}: {tab[key]}")
    nobs = sum(v for k, v in tab.items() if k[0] != "blind")
    ncorrect = sum(v for k, v in tab.items() if k[0] == "correct")
    nwrong = sum(v for k, v in tab.items() if k[0] == "WRONG")
    nband = sum(v for k, v in tab.items() if k[0] == "band")
    ndecl = sum(v for k, v in tab.items() if k[0] == "declared")
    nuncov = sum(v for k, v in tab.items() if k[0] == "uncovered")
    nfire_band = tab[("band", "actual=1")] + tab[("declared",
                                                  "actual=1")]
    nfires = sum(v for k, v in tab.items()
                 if k[1] == "actual=1" or (k[0] in ("correct", "WRONG")
                                           and False))
    print(f"\nD1 NUMBERS (observable ties): n={nobs}")
    print(f"  predicted & correct: {ncorrect}")
    print(f"  predicted & WRONG:   {nwrong}")
    if wrong_detail:
        print(f"  wrong detail (dist, low3, actual): "
              f"{dict(wrong_detail)}")
    print(f"  in-band (declared-unpredicted): {nband} "
          f"({nband/max(1,nobs):.3%})")
    print(f"  declared regions: {ndecl} ({ndecl/max(1,nobs):.3%})")
    print(f"  uncovered (outside rule): {nuncov} "
          f"({nuncov/max(1,nobs):.3%})")
    print(f"  tie FIRES landing in band/declared: {nfire_band}")


if __name__ == "__main__":
    main()
