#!/usr/bin/env python3
"""h589b: score the straddle-pair captures.

Per family: pairs with both members labeled; within-pair
discordance rate vs CTRL rate (two-proportion z); M3 accuracy
per family; for discordant pairs, which member fired (direction
vs the flipped feature, F-families only).
"""
import json
import math
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h577_three_term import qrow3

MODES = ROUNDING_MODES


def feat(mhex):
    (m, R, A, P, B_full, rsh, rdisc, lsh, ldisc, s4, t4,
     bshift, k, dist, low3) = qrow3(mhex)
    F = rsh - bshift
    kf = k + F
    APf = (A + P) << F
    EU = (APf - B_full) >> kf
    refs = {}
    for name, d in (("clean", 0), ("down", -1), ("up", 1)):
        refs[name] = [final_cosine_result(-(R + d), -72, md)
                      for md in MODES]
    return R, EU, refs


def main():
    sel = json.load(open("h589_locked.json"))
    st = {md: open(f"h589_{md}_status.txt").read().splitlines()
          for md in MODES}
    with Pool(15) as pool:
        feats = pool.map(feat, [rec["m"] for rec in sel],
                         chunksize=20)
    fires = {}
    other = bad = 0
    m3ok = defaultdict(lambda: [0, 0])
    for i, (rec, (R, EU, refs)) in enumerate(zip(sel, feats)):
        hw, badrow = [], False
        for md in MODES:
            t = st[md][i].split()
            if t[0] != "OK":
                badrow = True
                break
            hw.append(int(t[2], 16))
        if badrow:
            bad += 1
            continue
        lab = None
        for name in ("clean", "down", "up"):
            if hw == refs[name]:
                lab = name
                break
        if lab is None:
            other += 1
            continue
        res_hw = R + {"clean": 0, "down": -1, "up": 1}[lab]
        req2 = res_hw - EU
        fire = 1 if req2 == 1 else 0
        fires[(rec["fam"], rec["pair"], rec["member"])] = fire
        m3ok[rec["fam"]][0] += 1 if rec["M3"] == fire else 0
        m3ok[rec["fam"]][1] += 1
    print(f"badstat={bad} OTHER={other}")
    print(f"\n{'family':6s} {'pairs':>6s} {'disc':>5s} "
          f"{'rate':>7s} {'z_vs_CTRL':>9s} {'M3acc':>7s}")
    rates = {}
    for fam in ("CTRL", "F1", "F2", "F3", "F4"):
        pairs = defaultdict(dict)
        for (f, pid, mem), fire in fires.items():
            if f == fam:
                pairs[pid][mem] = fire
        full = [p for p in pairs.values() if len(p) == 2]
        disc = sum(1 for p in full if p["a"] != p["b"])
        n = len(full)
        rates[fam] = (disc, n)
        ok, tot = m3ok[fam]
        z = ""
        if fam != "CTRL" and n:
            d0, n0 = rates["CTRL"]
            p0 = d0 / n0
            p1 = disc / n
            pp = (d0 + disc) / (n0 + n)
            se = math.sqrt(pp * (1 - pp) * (1 / n0 + 1 / n))
            z = f"{(p1 - p0) / se:+9.2f}" if se else ""
        print(f"{fam:6s} {n:6d} {disc:5d} "
              f"{disc / max(n, 1):7.3f} {z:>9s} "
              f"{ok / max(tot, 1):7.3f}")
    # direction: for discordant F-family pairs, does the member
    # with the HIGHER flipped-feature value fire more?
    featidx = {"F1": 0, "F2": 1, "F3": 2, "F4": 3}
    bym = {}
    for rec in sel:
        bym[(rec["fam"], rec["pair"], rec["member"])] = rec
    print("\ndirection (discordant pairs, hi-feature member "
          "fires):")
    for fam, fi in featidx.items():
        hi = lo = 0
        pairs = defaultdict(dict)
        for (f, pid, mem), fire in fires.items():
            if f == fam:
                pairs[pid][mem] = fire
        for pid, p in pairs.items():
            if len(p) != 2 or p["a"] == p["b"]:
                continue
            ra = bym[(fam, pid, "a")]
            rb = bym[(fam, pid, "b")]
            fa, fb = ra["feat"][fi], rb["feat"][fi]
            firing = "a" if p["a"] == 1 else "b"
            hival = "a" if fa > fb else "b"
            if firing == hival:
                hi += 1
            else:
                lo += 1
        n = hi + lo
        z = (hi - n / 2) / math.sqrt(n / 4) if n else 0.0
        print(f"{fam}: hi-fires {hi} / lo-fires {lo}  "
              f"z={z:+.2f}")


if __name__ == "__main__":
    main()
