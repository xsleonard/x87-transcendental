#!/usr/bin/env python3
"""h590e: cross-schedule discordance on the h589 straddle pairs.

The h589 pairs sit in near-fc-threshold cells (residual-variance
territory) and are now captured under BOTH schedules.  For each
pair with defined fc outcomes (h589 cos captures) and
unambiguous sc cos-lane labels (h589_sc_* sincos captures):
  - fc_disc = members differ in fc fire
  - sc_disc = members differ in sc fire (d >= 1)
2x2 table fc_disc x sc_disc + odds/z: shared arrangement state
=> positive association (a pair differing in the hidden state
differs in BOTH lanes); schedule-generated state =>
independence.  Also member-level: among fc-discordant pairs,
does the fc-firing member sc-fire more than the other?
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
    for d in range(-3, 4):
        refs[d] = [final_cosine_result(-(R + d), -72, md)
                   for md in MODES]
    return R, EU, refs


def main():
    sel = json.load(open("h589_locked.json"))
    stc = {md: open(f"h589_{md}_status.txt").read().splitlines()
           for md in MODES}
    sts = {md: open(f"h589_sc_{md}_status.txt").read()
           .splitlines() for md in MODES}
    with Pool(15) as pool:
        feats = pool.map(feat, [rec["m"] for rec in sel],
                         chunksize=20)
    fc_fire = {}
    sc_fire = {}
    amb = 0
    for i, (rec, (R, EU, refs)) in enumerate(zip(sel, feats)):
        pid = (rec["fam"], rec["pair"], rec["member"])
        # fc label
        hw, bad = [], False
        for md in MODES:
            t = stc[md][i].split()
            if t[0] != "OK":
                bad = True
                break
            hw.append(int(t[2], 16))
        if not bad:
            for d in range(-3, 4):
                if hw == refs[d]:
                    fc_fire[pid] = 1 if R + d - EU == 1 else 0
                    break
        # sc cos-lane label (alias-aware)
        hw, bad = [], False
        for md in MODES:
            t = sts[md][i].split()
            if t[0] != "OK":
                bad = True
                break
            hw.append(int(t[4], 16))
        if bad:
            continue
        ds = [d for d in range(-3, 4) if hw == refs[d]]
        if len(ds) == 1:
            sc_fire[pid] = 1 if ds[0] >= 1 else 0
        else:
            amb += 1
    print(f"sc ambiguous members: {amb} / {len(sel)}")
    # pair-level
    tab = defaultdict(int)
    memdir = [0, 0]
    nsc = 0
    for fam in ("CTRL", "F1", "F2", "F3", "F4"):
        pairs = defaultdict(dict)
        for (f, pid, mem) in fc_fire:
            if f != fam:
                continue
            key = (f, pid)
            a = fc_fire.get((f, pid, "a"))
            b = fc_fire.get((f, pid, "b"))
            sa = sc_fire.get((f, pid, "a"))
            sb = sc_fire.get((f, pid, "b"))
            if None in (a, b, sa, sb):
                continue
            pairs[pid] = (a, b, sa, sb)
        for pid, (a, b, sa, sb) in pairs.items():
            fd = a != b
            sd = sa != sb
            tab[(fd, sd)] += 1
            if fd and sd:
                # directions align?
                fcm = "a" if a == 1 else "b"
                scm = "a" if sa == 1 else "b"
                memdir[0 if fcm == scm else 1] += 1
    n = sum(tab.values())
    n11 = tab[(True, True)]
    n10 = tab[(True, False)]
    n01 = tab[(False, True)]
    n00 = tab[(False, False)]
    print(f"pairs with full 4-way labels: {n}")
    print(f"          sc_disc  sc_conc")
    print(f"fc_disc   {n11:7d}  {n10:7d}")
    print(f"fc_conc   {n01:7d}  {n00:7d}")
    r1 = n11 + n10
    c1 = n11 + n01
    if n and r1 and c1 and r1 < n and c1 < n:
        e = r1 * c1 / n
        v = r1 * (n - r1) * c1 * (n - c1) / (n * n * (n - 1))
        z = (n11 - e) / math.sqrt(v)
        print(f"association: obs11={n11} exp11={e:.1f} "
              f"z={z:+.2f}")
    if sum(memdir):
        nm = sum(memdir)
        z = (memdir[0] - nm / 2) / math.sqrt(nm / 4)
        print(f"double-discordant pairs: same-member aligned "
              f"{memdir[0]} / opposed {memdir[1]}  z={z:+.2f}")


if __name__ == "__main__":
    main()
