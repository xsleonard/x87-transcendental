#!/usr/bin/env python3
"""h589c: composition-corrected straddle-pair analysis.

For each captured pair, expected discordance under member-
exchangeability = 2p(1-p) with p = comb-7 empirical fire rate of
the pair's (key, mb, st3) cell.  Per family: observed vs
expected discordance (Poisson-binomial z).  obs>exp => flipped
feature is a causal hidden-state carrier; obs<exp => the MATCHED
features carry variance (pinning them aligns outcomes); CTRL
(all matched) obs<exp quantifies how much of the hidden state
the four features jointly carry.
"""
import json
import math
from collections import defaultdict
from multiprocessing import Pool
from h588_select import TARGETS, fit_thr, m3_state


def _m3row(args):
    return m3_state(*args)


def main():
    rows = []
    for line in open("h587d_band.tsv"):
        f = line.split()
        key = ((int(f[1]), int(f[2]), int(f[3])), f[4])
        if key not in dict.fromkeys(TARGETS):
            continue
        rows.append((key, int(f[5]), int(f[6]), int(f[7], 16),
                     int(f[8], 16), int(f[9])))
    with Pool(15) as pool:
        sts = pool.map(_m3row, [(f4v, rfv, rsh)
                                for key, mb, fire, f4v, rfv, rsh
                                in rows], chunksize=2000)
    cellrate = defaultdict(lambda: [0, 0])
    for (key, mb, fire, f4v, rfv, rsh), st3 in zip(rows, sts):
        c = cellrate[(str(key), mb, st3)]
        c[fire] += 1
    sel = json.load(open("h589_locked.json"))
    from h437_gate_extraction import ROUNDING_MODES, \
        final_cosine_result
    from h577_three_term import qrow3
    st = {md: open(f"h589_{md}_status.txt").read().splitlines()
          for md in ROUNDING_MODES}
    from h589b_score import feat
    with Pool(15) as pool:
        feats = pool.map(feat, [rec["m"] for rec in sel],
                         chunksize=20)
    fires = {}
    for i, (rec, (R, EU, refs)) in enumerate(zip(sel, feats)):
        hw = []
        ok = True
        for md in ROUNDING_MODES:
            t = st[md][i].split()
            if t[0] != "OK":
                ok = False
                break
            hw.append(int(t[2], 16))
        if not ok:
            continue
        lab = None
        for name in ("clean", "down", "up"):
            if hw == refs[name]:
                lab = name
                break
        if lab is None:
            continue
        res_hw = R + {"clean": 0, "down": -1, "up": 1}[lab]
        fire = 1 if res_hw - EU == 1 else 0
        fires[(rec["fam"], rec["pair"], rec["member"])] = fire
    bym = {}
    for rec in sel:
        bym[(rec["fam"], rec["pair"], rec["member"])] = rec
    print(f"{'family':6s} {'pairs':>6s} {'obs':>5s} "
          f"{'exp':>7s} {'z':>6s}   (obs>exp: flipped feature "
          f"causal; obs<exp: matched features carry state)")
    for fam in ("CTRL", "F1", "F2", "F3", "F4"):
        pairs = defaultdict(dict)
        for (f, pid, mem), fire in fires.items():
            if f == fam:
                pairs[pid][mem] = fire
        obs = 0
        exp = var = 0.0
        n = 0
        for pid, p in pairs.items():
            if len(p) != 2:
                continue
            rec = bym[(fam, pid, "a")]
            ck = (str(tuple([tuple(rec["key"][0]),
                             rec["key"][1]])), rec["mb"],
                  rec["st3"])
            c = cellrate.get(ck)
            if c is None or sum(c) < 4:
                continue
            pr = c[1] / sum(c)
            e = 2 * pr * (1 - pr)
            exp += e
            var += e * (1 - e)
            obs += 1 if p["a"] != p["b"] else 0
            n += 1
        z = (obs - exp) / math.sqrt(var) if var > 0 else 0.0
        print(f"{fam:6s} {n:6d} {obs:5d} {exp:7.1f} {z:+6.2f}")


if __name__ == "__main__":
    main()
