#!/usr/bin/env python3
"""h597b: score the locked dn-side M1-vs-M3 predictions against
the fresh captures, alias-robust (dn side: fire iff hw ==
refs(EU-1); blind rows impossible by selection, counted if any).
"""
import json
import math
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h577_three_term import qrow3

MODES = ROUNDING_MODES


def feat(mhex):
    (m, R, A, P, B_full, rsh, rd, lsh, ld, s4, t4, bsh, k,
     dist, low3) = qrow3(mhex)
    F = rsh - bsh
    kf = k + F
    APf = (A + P) << F
    EU = (APf - B_full) >> kf
    ra = [final_cosine_result(-(EU - 1), -73, md)
          for md in MODES]
    r0 = [final_cosine_result(-EU, -73, md) for md in MODES]
    return ra, r0


def main():
    sel = json.load(open("h597_locked.json"))
    st = {md: open(f"h597_{md}_status.txt").read().splitlines()
          for md in MODES}
    with Pool(15) as pool:
        feats = pool.map(feat, [rec["m"] for rec in sel],
                         chunksize=50)
    res = defaultdict(lambda: defaultdict(int))
    for i, (rec, (ra, r0)) in enumerate(zip(sel, feats)):
        key = tuple(rec["key"])
        r = res[key]
        hw, bad = [], False
        for md in MODES:
            t = st[md][i].split()
            if t[0] != "OK":
                bad = True
                break
            hw.append(int(t[2], 16))
        if bad:
            r["badstat"] += 1
            continue
        if ra == r0:
            r["blind"] += 1
            continue
        if hw == ra:
            fire = 1
        elif hw == r0:
            fire = 0
        else:
            r["OTHER"] += 1
            continue
        tag = "ctl" if rec["M1"] == rec["M3"] else "dis"
        r[f"{tag}_n"] += 1
        for mname in ("M1", "M3"):
            if rec[mname] == fire:
                r[f"{tag}_{mname}"] += 1
    print(f"{'stratum':10s} {'dis_n':>6s} {'M1':>5s} "
          f"{'M3':>5s} {'z(M3)':>6s} {'ctl_n':>6s} "
          f"{'ctl_M3':>7s} {'OTHER':>6s} {'blind':>6s}")
    tot = defaultdict(int)
    for key in sorted(res):
        r = res[key]
        dn = r["dis_n"]
        z = (r["dis_M3"] - dn / 2) / math.sqrt(dn / 4) \
            if dn else 0.0
        print(f"{str(key):10s} {dn:6d} {r['dis_M1']:5d} "
              f"{r['dis_M3']:5d} {z:+6.1f} {r['ctl_n']:6d} "
              f"{r['ctl_M3']:7d} {r['OTHER']:6d} "
              f"{r['blind']:6d}")
        for kk in ("dis_n", "dis_M1", "dis_M3", "ctl_n",
                   "ctl_M3", "OTHER", "blind"):
            tot[kk] += r[kk]
    dn = tot["dis_n"]
    z = (tot["dis_M3"] - dn / 2) / math.sqrt(dn / 4) \
        if dn else 0.0
    print(f"{'TOTAL':10s} {dn:6d} {tot['dis_M1']:5d} "
          f"{tot['dis_M3']:5d} {z:+6.1f} {tot['ctl_n']:6d} "
          f"{tot['ctl_M3']:7d} {tot['OTHER']:6d} "
          f"{tot['blind']:6d}")


if __name__ == "__main__":
    main()
