#!/usr/bin/env python3
"""h588b: score the locked M2-vs-M3 disagreement predictions
against the fresh i7 captures (h588_locked.json, h588_*_status).
Per stratum: n, OTHER, M1/M2/M3 correct on disagreement rows,
binomial z for M3-vs-M2, controls separately.
"""
import json
import math
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h577_three_term import qrow3

def feat(mhex):
    (m, R, A, P, B_full, rsh, rdisc, lsh, ldisc, s4, t4,
     bshift, k, dist, low3) = qrow3(mhex)
    F = rsh - bshift
    kf = k + F
    APf = (A + P) << F
    EU = (APf - B_full) >> kf
    return R, EU


def main():
    sel = json.load(open("h588_locked.json"))
    st = {md: open(f"h588_{md}_status.txt").read().splitlines()
          for md in ROUNDING_MODES}

    with Pool(10) as pool:
        feats = pool.map(feat, [rec["m"] for rec in sel],
                         chunksize=50)
    
    res = defaultdict(lambda: defaultdict(int))
    for i, (rec, (R, EU)) in enumerate(zip(sel, feats)):
        strat = tuple(rec["key"][0])
        ce = strat[2]
        hw, bad = [], False
        for md in ROUNDING_MODES:
            t = st[md][i].split()
            if t[0] != "OK":
                bad = True
                break
            hw.append(int(t[2], 16))
        key = (strat, rec["key"][1])
        r = res[key]
        if bad:
            r["badstat"] += 1
            continue
        lab = None
        for name, d in (("clean", 0), ("down", -1), ("up", 1)):
            refs = [final_cosine_result(-(R + d), ce, md)
                    for md in ROUNDING_MODES]
            if hw == refs:
                lab = name
                break
        if lab is None:
            r["OTHER"] += 1
            continue
        res_hw = R + {"clean": 0, "down": -1, "up": 1}[lab]
        req2 = res_hw - EU
        fire = 1 if req2 == 1 else 0
        is_ctrl = rec["M2"] == rec["M3"]
        tag = "ctl" if is_ctrl else "dis"
        r[f"{tag}_n"] += 1
        for mname in ("M1", "M2", "M3"):
            if rec[mname] == fire:
                r[f"{tag}_{mname}"] += 1
    
    print(f"{'stratum/side':26s} {'dis_n':>6s} {'M1':>5s} "
          f"{'M2':>5s} {'M3':>5s} {'z(M3)':>6s} {'ctl_n':>6s} "
          f"{'ctl_M3':>7s} {'OTHER':>6s}")
    tot = defaultdict(int)
    for key in sorted(res):
        r = res[key]
        dn = r["dis_n"]
        z = (r["dis_M3"] - dn / 2) / math.sqrt(dn / 4) if dn else 0.0
        print(f"{str(key):26s} {dn:6d} {r['dis_M1']:5d} "
              f"{r['dis_M2']:5d} {r['dis_M3']:5d} {z:+6.1f} "
              f"{r['ctl_n']:6d} {r['ctl_M3']:7d} {r['OTHER']:6d}")
        for kk in ("dis_n", "dis_M1", "dis_M2", "dis_M3", "ctl_n",
                   "ctl_M3", "OTHER"):
            tot[kk] += r[kk]
    dn = tot["dis_n"]
    z = (tot["dis_M3"] - dn / 2) / math.sqrt(dn / 4) if dn else 0.0
    print(f"{'TOTAL':26s} {dn:6d} {tot['dis_M1']:5d} "
          f"{tot['dis_M2']:5d} {tot['dis_M3']:5d} {z:+6.1f} "
          f"{tot['ctl_n']:6d} {tot['ctl_M3']:7d} {tot['OTHER']:6d}")


if __name__ == "__main__":
    main()
