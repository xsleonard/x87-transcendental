#!/usr/bin/env python3
"""h525: E1 — near-tie extension test on the original corpus.

Near-tie rows: terminal accumulator M with discarded field D = M & mk
in {1, 2} (near-all-zeros; candidate fire = R-1, downward) or
{mk-1, mk-2} (near-all-ones; candidate fire = R+1, upward), k >= 3.

Hypothesis (E1): the SAME per-stratum boundary lines that govern ties
govern near-ties with intercepts shifted by a function of theta
(theta = D for low side, D - 2^k for high side; theta=0 is the tie).

Per row: label via ok_for; recover m (value-normalized); compute the
tie law's residual r = mf - s*XT - c using fcos_tie_rule.boundary().
Per (theta, line-availability): the fire/clean split vs r — if E1
holds, fires separate from cleans at a shifted threshold r < d_theta
with few errors, and d_theta is consistent across strata.
"""
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import (ROUNDING_MODES, load_labeled_rows,
                                  final_cosine_result)
from h453_chain_variants import recover_m
from h500_plane_m import build
import fcos_tie_rule


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
    if k < 3:
        return None
    mk = (1 << k) - 1
    D = M & mk
    if D in (1, 2):
        theta = D
        fire_M = M - (1 << k)          # hardware resolves LOW
    elif D in (mk, mk - 1):
        theta = D - (1 << k)           # -1 or -2
        fire_M = M + (1 << k)          # hardware resolves HIGH
    else:
        return None
    hw = tuple(hw_sigs[m] for m in ROUNDING_MODES)

    def ok_val(val):
        # exact model value at 'scale' (keeps the discarded field, so
        # directed-mode rounding is exact)
        return all(final_cosine_result(-val, scale, m) == h
                   for m, h in zip(ROUNDING_MODES, hw))

    ideal_ok, fire_ok = ok_val(M), ok_val(fire_M)
    if ideal_ok and fire_ok:
        return ("blind", theta)
    if not ideal_ok and not fire_ok:
        return ("other", theta)
    fire = 1 if fire_ok else 0
    m = recover_m(int(fields["mul"], 16))
    if m is None:
        return ("no_m", theta)
    m <<= (64 - m.bit_length())
    cell, XT, XD, mf, _ = build((f"{m:016x}", 0))
    if cell[0] != dist or cell[1] != low3:
        return ("mismatch", theta)
    ln = fcos_tie_rule.boundary(dist, low3, XT, XD, mf)
    if ln is None:
        kind, pred = fcos_tie_rule.classify(dist, low3, XT, XD, mf)
        return ("noline", theta, kind, fire)
    s, c = ln
    r = mf - s * XT - c
    return ("ok", theta, dist, low3, fire, round(r, 6))


def main():
    rows = load_labeled_rows()
    with Pool(8) as pool:
        out = [o for o in pool.map(score_row, rows, chunksize=500)
               if o]
    census = defaultdict(int)
    for o in out:
        census[(o[0], o[1])] += 1
    print("census (status, theta):", dict(sorted(census.items(),
                                                 key=str)))
    # no-line region fire rates by kind
    nl = defaultdict(lambda: [0, 0])
    for o in out:
        if o[0] == "noline":
            nl[(o[1], o[2])][0] += 1
            nl[(o[1], o[2])][1] += o[3]
    if nl:
        print("\nno-line regions (theta, kind): n, fires")
        for key in sorted(nl, key=str):
            print(f"  {key}: {nl[key][0]}, {nl[key][1]}")
    # E1 core: residual separation per theta
    print("\nE1 SEPARATION TEST (rows on line-governed regions):")
    per_theta = defaultdict(list)
    for o in out:
        if o[0] == "ok":
            _, theta, dist, low3, fire, r = o
            per_theta[theta].append((r, fire, dist, low3))
    for theta in sorted(per_theta):
        pts = per_theta[theta]
        n1 = sum(p[1] for p in pts)
        vals = sorted((r, f) for r, f, _, _ in pts)
        ns = n1
        pre1 = 0
        best, bd = ns, None
        for i, (r, f) in enumerate(vals):
            pre1 += f
            e = (i + 1 - pre1) + (ns - pre1)
            if e < best:
                best, bd = e, r
        fr = [r for r, f, _, _ in pts if f]
        cl = [r for r, f, _, _ in pts if not f]
        print(f"\n theta={theta:+d}: n={len(pts)} fires={n1} | "
              f"best single shift d={bd if bd is None else round(bd,5)} "
              f"errs={best} ({best/max(1,len(pts)):.3f})")
        if fr:
            fr.sort()
            print(f"   fire r: min={fr[0]:.5f} med="
                  f"{fr[len(fr)//2]:.5f} max={fr[-1]:.5f}")
        if cl:
            cl.sort()
            print(f"   clean r: min={cl[0]:.5f} med="
                  f"{cl[len(cl)//2]:.5f} max={cl[-1]:.5f}")
        # per-stratum shift consistency (strata with >=8 rows)
        bys = defaultdict(list)
        for r, f, dist, low3 in pts:
            bys[(dist, low3)].append((r, f))
        rows_s = []
        for key, sub in sorted(bys.items()):
            if len(sub) < 8:
                continue
            sn1 = sum(f for _, f in sub)
            sv = sorted(sub)
            pre1, sbest, sbd = 0, sn1, None
            for i, (r, f) in enumerate(sv):
                pre1 += f
                e = (i + 1 - pre1) + (sn1 - pre1)
                if e < sbest:
                    sbest, sbd = e, r
            rows_s.append(f"   {key}: n={len(sub)} fires={sn1} "
                          f"shift={sbd if sbd is None else round(sbd,5)} "
                          f"errs={sbest}")
        for line in rows_s:
            print(line)


if __name__ == "__main__":
    main()
