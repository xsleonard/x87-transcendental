#!/usr/bin/env python3
"""h590g: cross-schedule 2x2 on the h590f pairs.

Classification-level alias handling: a lane's label is usable
iff ALL matched d in [-3,3] agree on the fire class
(fc: req2 = R+d-EU == 1;  sc: d >= 1).
Table fc_disc x sc_disc over pairs with all four labels +
member-alignment among double-discordant pairs.
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
    sel = json.load(open("h590f_locked.json"))
    stc = {md: open(f"h590f_{md}_status.txt").read()
           .splitlines() for md in MODES}
    sts = {md: open(f"h590f_sc_{md}_status.txt").read()
           .splitlines() for md in MODES}
    with Pool(15) as pool:
        feats = pool.map(feat, [rec["m"] for rec in sel],
                         chunksize=20)
    fc_fire = {}
    sc_fire = {}
    amb_fc = amb_sc = 0
    for i, (rec, (R, EU, refs)) in enumerate(zip(sel, feats)):
        pid = (rec["pair"], rec["member"])
        hw, bad = [], False
        for md in MODES:
            t = stc[md][i].split()
            if t[0] != "OK":
                bad = True
                break
            hw.append(int(t[2], 16))
        if not bad:
            ds = [d for d in range(-3, 4) if hw == refs[d]]
            cls = set(1 if R + d - EU == 1 else 0 for d in ds)
            if len(cls) == 1:
                fc_fire[pid] = cls.pop()
            else:
                amb_fc += 1
        hw, bad = [], False
        for md in MODES:
            t = sts[md][i].split()
            if t[0] != "OK":
                bad = True
                break
            hw.append(int(t[4], 16))
        if not bad:
            ds = [d for d in range(-3, 4) if hw == refs[d]]
            cls = set(1 if d >= 1 else 0 for d in ds)
            if ds and len(cls) == 1:
                sc_fire[pid] = cls.pop()
            else:
                amb_sc += 1
    print(f"fc class-ambiguous: {amb_fc}, sc class-ambiguous: "
          f"{amb_sc}, of {len(sel)} members")
    npairs = max(rec["pair"] for rec in sel) + 1
    tab = defaultdict(int)
    memdir = [0, 0]
    for pid in range(npairs):
        a = fc_fire.get((pid, "a"))
        b = fc_fire.get((pid, "b"))
        sa = sc_fire.get((pid, "a"))
        sb = sc_fire.get((pid, "b"))
        if None in (a, b, sa, sb):
            continue
        fd = a != b
        sd = sa != sb
        tab[(fd, sd)] += 1
        if fd and sd:
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
        print(f"double-discordant: aligned {memdir[0]} / "
              f"opposed {memdir[1]}  z={z:+.2f}")


if __name__ == "__main__":
    main()
