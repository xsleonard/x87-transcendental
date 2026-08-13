#!/usr/bin/env python3
"""h524: FINAL D1 — the complete validated rule (fcos_tie_rule, all
windows W1+W2+combs1-4 laws) scored against every original-corpus tie
row, with value-normalized m recovery (h521)."""
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import (ROUNDING_MODES, load_labeled_rows,
                                  final_cosine_result)
from h453_chain_variants import recover_m
from h500_plane_m import build
from fcos_tie_rule import classify


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
    M = (ls << (le2 - scale)) - (rs << (re2 - scale)) \
        + (prepay << (le2 - 8 - scale))
    if M <= 0:
        return None
    k = max(M.bit_length() - 67, 0)
    if k < 3 or (M & ((1 << k) - 1)):
        return None
    R = M >> k
    hw = tuple(hw_sigs[m] for m in ROUNDING_MODES)

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
        return ("other",)
    m = recover_m(int(fields["mul"], 16))
    if m is None:
        return ("no_m",)
    m <<= (64 - m.bit_length())
    cell, XT, XD, mf, _ = build((f"{m:016x}", 0))
    if cell[0] != dist or cell[1] != low3:
        return ("replica_mismatch", status)
    kind, pred = classify(dist, low3, XT, XD, mf)
    return ("ok", dist, low3, status, kind, pred)


def main():
    rows = load_labeled_rows()
    with Pool(8) as pool:
        out = [o for o in pool.map(score_row, rows, chunksize=500)
               if o]
    bad = defaultdict(int)
    tab = defaultdict(int)
    wrong = defaultdict(int)
    for o in out:
        if o[0] != "ok":
            bad[o[0] if len(o) == 1 else (o[0], o[1])] += 1
            continue
        _, dist, low3, status, kind, pred = o
        if status == "blind":
            tab[("blind",)] += 1
            continue
        actual = 1 if status == "fire" else 0
        if kind in ("line", "never", "always"):
            if pred == actual:
                tab[("correct",)] += 1
            else:
                tab[("WRONG",)] += 1
                wrong[(dist, low3, actual)] += 1
        else:
            tab[(kind, actual)] += 1
    print("non-scorable:", dict(bad))
    nobs = sum(v for k, v in tab.items() if k[0] != "blind")
    print(f"\nFINAL D1 (observable original-corpus ties): n={nobs}")
    print(f"  correct:  {tab[('correct',)]}")
    print(f"  WRONG:    {tab[('WRONG',)]}  {dict(wrong)}")
    print(f"  band:     {tab[('band', 0)] + tab[('band', 1)]} "
          f"(fires {tab[('band', 1)]})")
    print(f"  declared: {tab[('declared', 0)] + tab[('declared', 1)]} "
          f"(fires {tab[('declared', 1)]})")
    print(f"  uncovered: {tab[('uncovered', 0)] + tab[('uncovered', 1)]} "
          f"(fires {tab[('uncovered', 1)]})")
    print(f"  blind:    {tab[('blind',)]}")


if __name__ == "__main__":
    main()
