#!/usr/bin/env python3
"""h653: integer-bits family fit — comparator taps summed inside a floor.

    u = K*floor((a*L + G1*[3XD>=1] + G2*[3XD>=2] + p*(L%2) + W)/Q)
        + par*(L%2)

The thirds comparator contributes INTEGER taps into a floored sum (the
h642 dist-8 form generalized) — this reproduces parity-selective jump
appearance/suppression naturally.  Per block (d, s4, side): enumerate
(a, G1, G2, p, Q, K, par), fit W exactly; print passing configs.
Boundary-sliver rows excluded (comparator constant pinned separately).
"""
import pickle
from collections import defaultdict

NAMES = ["comb4", "comb3", "comb5", "comb6", "comb7", "comb8"]
T60 = 1 << 60


def ceil_div(a, b):
    return -((-a) // b)


def main():
    cells = defaultdict(list)
    for nm in NAMES:
        for (dist, s4, side, L, xd60, sR, fire, req) in pickle.load(
                open(f"h649_{nm}.pkl", "rb")):
            cells[(dist, s4, side, L)].append((xd60, sR, fire, req))

    # constraints per (cell, tapclass): tapclass tt = [3XD>=1]+[3XD>=2]
    # (0,1,2); within a tapclass u is CONSTANT under this family, so the
    # binding info per (cell, tt) is just (max fire req, min clean req).
    cons = {}
    for k, rows in cells.items():
        if len(rows) < 300:
            continue
        d, s4, side, L = k
        agg = {}
        for xd, sR, fire, req in rows:
            v3 = 3 * xd
            if xd == 0 or min(abs(v3 - T60), abs(v3 - 2 * T60)) < (T60 >> 16):
                continue    # degenerate XD=0 / comparator-boundary sliver
            tt = (1 if v3 >= T60 else 0) + (1 if v3 >= 2 * T60 else 0)
            key = (k, tt)
            d_ = agg.setdefault(key, {})
            side_ = "ge" if fire else "le"
            d_.setdefault(side_, []).append(req)
        for key, d_ in agg.items():
            def ext(vals, top):
                if not vals:
                    return (None, 0, None)
                vs = sorted(set(vals), reverse=top)
                e = vs[0]
                cnt = vals.count(e)
                e2 = vs[1] if len(vs) > 1 else e
                return (e, cnt, e2)
            cons[key] = (ext(d_.get("ge", []), True),
                         ext(d_.get("le", []), False))

    blocks = defaultdict(list)
    for (k, tt), v in cons.items():
        blocks[k[:3]].append((k[3], tt, v))

    allpass = {}
    for bk in sorted(blocks):
      for LEN1 in (False, True):
        items = blocks[bk]
        passing = []
        for a in range(1, 9):
            for G1 in range(0, 6):
                for G2 in range(0, 6):
                    for p in range(-4, 5):
                        for Q in (2, 3, 4, 6, 8, 12, 16):
                            for K in (1, 2):
                                for par in (0, 1):
                                    wlo = None; whi = None
                                    ok = True
                                    for L, tt, (GE, LE) in items:
                                        ge = GE[0] if not LEN1 or GE[1] is None \
                                            else (GE[2] if GE[1] <= 3 else GE[0])
                                        le = LE[0] if not LEN1 or LE[1] is None \
                                            else (LE[2] if LE[1] <= 3 else LE[0])
                                        b1 = 1 if tt >= 1 else 0
                                        b2 = 1 if tt >= 2 else 0
                                        X = (a * L + G1 * b1 + G2 * b2
                                             + p * (L % 2))
                                        pv = par * (L % 2)
                                        if ge is not None:
                                            g = ceil_div(ge - pv, K)
                                            w = g * Q - X
                                            wlo = w if wlo is None \
                                                else max(wlo, w)
                                        if le is not None:
                                            g = (le - pv) // K
                                            w = (g + 1) * Q - X
                                            whi = w if whi is None \
                                                else min(whi, w)
                                        if (wlo is not None and whi is not None
                                                and wlo >= whi):
                                            ok = False
                                            break
                                    if ok and wlo is not None \
                                            and whi is not None \
                                            and wlo < whi:
                                        passing.append(
                                            (a, G1, G2, p, Q, K, par,
                                             wlo, whi))
        if LEN1 and allpass.get(bk):
            continue
        allpass[bk] = passing
        print(f"block {bk}{' LENIENT' if LEN1 else ''}: "
              f"{len(passing)} configs pass")
        shown = 0
        for cfg in sorted(passing, key=lambda c: (c[5], c[4], c[0], c[1],
                                                  c[2], abs(c[3]), c[6])):
            a, G1, G2, p, Q, K, par, wlo, whi = cfg
            print(f"   a={a} G1={G1} G2={G2} p={p:+d} Q={Q} K={K} "
                  f"par={par}  W in [{wlo}, {whi})")
            shown += 1
            if shown >= 10:
                break
    pickle.dump(allpass, open("h653_pass.pkl", "wb"))


if __name__ == "__main__":
    main()
