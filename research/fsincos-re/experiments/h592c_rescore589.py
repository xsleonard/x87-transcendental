#!/usr/bin/env python3
"""h592c: alias-robust rescore of the h589 straddle pairs.
fire = (hw == refs(EU+1)); blind members dropped; per-family
observed vs expected discordance with expectations from the
CLEAN corpus cell rates (h592_band.tsv)."""
import json
import math
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h577_three_term import qrow3
from h588_select import m3_state, TARGETS


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


def _m3(args):
    return m3_state(*args)


def main():
    # clean cell rates
    rows = []
    for line in open("h592_band.tsv"):
        f = line.split()
        key = ((int(f[1]), int(f[2]), int(f[3])), f[4])
        if key not in dict.fromkeys(TARGETS):
            continue
        rows.append((key, int(f[5]), int(f[6]), int(f[7], 16),
                     int(f[8], 16), int(f[9])))
    with Pool(15) as pool:
        sts = pool.map(_m3, [(f4v, rfv, rsh)
                             for key, mb, fire, f4v, rfv, rsh
                             in rows], chunksize=2000)
        cellrate = defaultdict(lambda: [0, 0])
        for (key, mb, fire, f4v, rfv, rsh), st3 in \
                zip(rows, sts):
            cellrate[(key, mb, st3)][fire] += 1
        sel = json.load(open("h589_locked.json"))
        st = {md: open(f"h589_{md}_status.txt").read()
              .splitlines() for md in ROUNDING_MODES}
        feats = pool.map(feat, [rec["m"] for rec in sel],
                         chunksize=20)
    fires = {}
    blind = other = 0
    for i, (rec, (r0, r1)) in enumerate(zip(sel, feats)):
        hw, bad = [], False
        for md in ROUNDING_MODES:
            t = st[md][i].split()
            if t[0] != "OK":
                bad = True
                break
            hw.append(int(t[2], 16))
        if bad:
            continue
        if r0 == r1:
            blind += 1
            continue
        if hw == r1:
            fire = 1
        elif hw == r0:
            fire = 0
        else:
            other += 1
            continue
        fires[(rec["fam"], rec["pair"], rec["member"])] = fire
    print(f"blind members: {blind}, OTHER: {other}, labeled: "
          f"{len(fires)}")
    bym = {}
    for rec in sel:
        bym[(rec["fam"], rec["pair"], rec["member"])] = rec
    print(f"{'family':6s} {'pairs':>6s} {'obs':>5s} "
          f"{'exp':>7s} {'z':>6s}")
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
            ck = ((tuple(rec["key"][0]), rec["key"][1]),
                  rec["mb"], rec["st3"])
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
