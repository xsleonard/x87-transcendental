#!/usr/bin/env python3
"""h585b: score the locked disagreement-row predictions against
the fresh i7 captures.

For each input: recompute R/EU/side from the replica, label the
hardware outcome (clean/down/up via 3-mode refs), fire bit, then
compare against the LOCKED M1 (margin-only) and M2
(margin+split-state) predictions.  Report per stratum: n, OTHER
count, M1 correct, M2 correct, controls separately, binomial z
for M2-vs-M1 on disagreement rows (each row: exactly one of
M1/M2 is right).
"""
import json
import math
from collections import defaultdict
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h577_three_term import qrow3

sel = json.load(open("h585_locked.json"))
st = {md: open(f"h585_{md}_status.txt").read().splitlines()
      for md in ROUNDING_MODES}
res = defaultdict(lambda: defaultdict(int))
for i, rec in enumerate(sel):
    mhex = rec["m"]
    strat = tuple(rec["key"][0])
    side = rec["key"][1]
    ce = strat[2]
    hw, bad = [], False
    for md in ROUNDING_MODES:
        t = st[md][i].split()
        if t[0] != "OK":
            bad = True
            break
        hw.append(int(t[2], 16))
    key = (strat, side)
    r = res[key]
    if bad:
        r["badstat"] += 1
        continue
    (m, R, A, P, B_full, rsh, rdisc, lsh, ldisc, s4, t4,
     bshift, k, dist, low3) = qrow3(mhex)
    F = rsh - bshift
    kf = k + F
    APf = (A + P) << F
    EU = (APf - B_full) >> kf
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
    fire = 1 if (req2 == 1 if side == "up" else
                 req2 == -1) else 0
    is_ctrl = rec["M1"] == rec["M2"]
    tag = "ctl" if is_ctrl else "dis"
    r[f"{tag}_n"] += 1
    if rec["M1"] == fire:
        r[f"{tag}_M1"] += 1
    if rec["M2"] == fire:
        r[f"{tag}_M2"] += 1

print(f"{'stratum/side':26s} {'dis_n':>6s} {'M1':>6s} {'M2':>6s}"
      f" {'z(M2)':>6s} {'ctl_n':>6s} {'ctl_ok':>7s} {'OTHER':>6s}")
for key in sorted(res):
    r = res[key]
    dn = r["dis_n"]
    m1, m2 = r["dis_M1"], r["dis_M2"]
    z = (m2 - dn / 2) / math.sqrt(dn / 4) if dn else 0.0
    print(f"{str(key):26s} {dn:6d} {m1:6d} {m2:6d} {z:+6.1f} "
          f"{r['ctl_n']:6d} {r['ctl_M1']:7d} {r['OTHER']:6d}")
