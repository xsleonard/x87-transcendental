#!/usr/bin/env python3
"""h592: alias-robust rescore of the h588 blind disagreement
test.  fire defined iff refs(EU) != refs(EU+1); fire = (hw ==
refs(EU+1)); blind rows excluded; anything matching neither ref
= OTHER."""
import json
import math
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h577_three_term import qrow3


def feat(mhex):
    (m, R, A, P, B_full, rsh, rd, lsh, ld, s4, t4, bsh, k,
     dist, low3) = qrow3(mhex)
    F = rsh - bsh
    kf = k + F
    APf = (A + P) << F
    EU = (APf - B_full) >> kf
    r0 = [final_cosine_result(-EU, -72, md)
          for md in ROUNDING_MODES]
    r1 = [final_cosine_result(-(EU + 1), -72, md)
          for md in ROUNDING_MODES]
    return r0, r1


def main():
    sel = json.load(open("h588_locked.json"))
    st = {md: open(f"h588_{md}_status.txt").read().splitlines()
          for md in ROUNDING_MODES}
    with Pool(15) as pool:
        feats = pool.map(feat, [rec["m"] for rec in sel],
                         chunksize=50)
    res = defaultdict(lambda: defaultdict(int))
    for i, (rec, (r0, r1)) in enumerate(zip(sel, feats)):
        key = (tuple(rec["key"][0]), rec["key"][1])
        r = res[key]
        hw, bad = [], False
        for md in ROUNDING_MODES:
            t = st[md][i].split()
            if t[0] != "OK":
                bad = True
                break
            hw.append(int(t[2], 16))
        if bad:
            r["badstat"] += 1
            continue
        if r0 == r1:
            r["blind"] += 1
            continue
        if hw == r1:
            fire = 1
        elif hw == r0:
            fire = 0
        else:
            r["OTHER"] += 1
            continue
        tag = "ctl" if rec["M2"] == rec["M3"] else "dis"
        r[f"{tag}_n"] += 1
        for mname in ("M1", "M2", "M3"):
            if rec[mname] == fire:
                r[f"{tag}_{mname}"] += 1
    print(f"{'stratum/side':26s} {'dis_n':>6s} {'M1':>5s} "
          f"{'M2':>5s} {'M3':>5s} {'z(M3)':>6s} {'blind':>6s} "
          f"{'ctl_n':>6s} {'ctl_M3':>7s} {'OTHER':>6s}")
    tot = defaultdict(int)
    for key in sorted(res):
        r = res[key]
        dn = r["dis_n"]
        z = (r["dis_M3"] - dn / 2) / math.sqrt(dn / 4) \
            if dn else 0.0
        print(f"{str(key):26s} {dn:6d} {r['dis_M1']:5d} "
              f"{r['dis_M2']:5d} {r['dis_M3']:5d} {z:+6.1f} "
              f"{r['blind']:6d} {r['ctl_n']:6d} "
              f"{r['ctl_M3']:7d} {r['OTHER']:6d}")
        for kk in ("dis_n", "dis_M1", "dis_M2", "dis_M3",
                   "blind", "ctl_n", "ctl_M3", "OTHER"):
            tot[kk] += r[kk]
    dn = tot["dis_n"]
    z = (tot["dis_M3"] - dn / 2) / math.sqrt(dn / 4) \
        if dn else 0.0
    print(f"{'TOTAL':26s} {dn:6d} {tot['dis_M1']:5d} "
          f"{tot['dis_M2']:5d} {tot['dis_M3']:5d} {z:+6.1f} "
          f"{tot['blind']:6d} {tot['ctl_n']:6d} "
          f"{tot['ctl_M3']:7d} {tot['OTHER']:6d}")


if __name__ == "__main__":
    main()
