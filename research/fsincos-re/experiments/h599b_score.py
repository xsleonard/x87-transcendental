#!/usr/bin/env python3
"""h599b: score the locked J1 predictions against the fresh
captures.  Alias-robust: fire from the side-appropriate EU
refs.  Per stratum: n, correct, misses, OTHER, blind."""
import json
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h577_three_term import qrow3

MODES = ROUNDING_MODES


def feat(args):
    mhex, ce, side = args
    (m, R, A, P, B_full, rsh, rd, lsh, ld, s4, t4, bsh, k,
     dist, low3) = qrow3(mhex)
    F = rsh - bsh
    kf = k + F
    APf = (A + P) << F
    EU = (APf - B_full) >> kf
    za, zb = (0, 1) if side == "up" else (-1, 0)
    ra = [final_cosine_result(-(EU + za), ce, md)
          for md in MODES]
    rb = [final_cosine_result(-(EU + zb), ce, md)
          for md in MODES]
    return ra, rb


def main():
    sel = json.load(open("h599_locked.json"))
    st = {md: open(f"h599_{md}_status.txt").read().splitlines()
          for md in MODES}
    with Pool(15) as pool:
        feats = pool.map(
            feat, [(r["m"], r["strat"][2], r["side"])
                   for r in sel], chunksize=50)
    res = defaultdict(lambda: defaultdict(int))
    for i, (rec, (ra, rb)) in enumerate(zip(sel, feats)):
        key = tuple(rec["strat"]) + (rec["side"],)
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
        if ra == rb:
            r["blind"] += 1
            continue
        side = rec["side"]
        if side == "up":
            fire = 1 if hw == rb else (0 if hw == ra else -1)
        else:
            fire = 1 if hw == ra else (0 if hw == rb else -1)
        if fire < 0:
            r["OTHER"] += 1
            continue
        r["n"] += 1
        if rec["pred"] == fire:
            r["ok"] += 1
    print(f"{'stratum/side':22s} {'n':>5s} {'ok':>5s} "
          f"{'acc':>8s} {'OTHER':>6s} {'blind':>6s}")
    tot = defaultdict(int)
    for key in sorted(res):
        r = res[key]
        print(f"{str(key):22s} {r['n']:5d} {r['ok']:5d} "
              f"{r['ok'] / max(r['n'], 1):8.4f} "
              f"{r['OTHER']:6d} {r['blind']:6d}")
        for kk in ("n", "ok", "OTHER", "blind"):
            tot[kk] += r[kk]
    print(f"{'TOTAL':22s} {tot['n']:5d} {tot['ok']:5d} "
          f"{tot['ok'] / max(tot['n'], 1):8.4f} "
          f"{tot['OTHER']:6d} {tot['blind']:6d}")


if __name__ == "__main__":
    main()
