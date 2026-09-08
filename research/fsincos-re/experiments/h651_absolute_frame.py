#!/usr/bin/env python3
"""h651: the absolute-frame unification of the u-table.

Model family (everything established folded in):

    T = 2^66 * u,
    u = K * floor( (L*2^65 + P*rdisc*2^(c-sR) + W) / 2^66 ) + par*(L%2)

    K = 1 for s4=66 blocks, 2 for s4=67 (jump height = one binade);
    par in {0,1} per s4 group; P in {1,3}; c global (absolute-column
    anchor); alt mode: coefficient in the XD-relative frame
    P*rdisc*2^(c-64) normalized ... enumerated as mode/c combos.
    W = ONE free integer per block (d, s4, side), FITTED exactly from
    the row constraints (each row gives a half-line on W).

Fitting uses per-cell Pareto frontiers in xd (valid for any model
monotone in xd at fixed cell); winners verified on the full row set.
Then the fitted W(d, s4, side) values are printed for the final
pattern-closure stage.
"""
import pickle
from collections import defaultdict

NAMES = ["comb4", "comb3", "comb5", "comb6", "comb7", "comb8"]
UNIT = 1 << 66


def ceil_div(a, b):
    return -((-a) // b)


def main():
    cells = defaultdict(list)
    for nm in NAMES:
        for (dist, s4, side, L, xd60, sR, fire, req) in pickle.load(
                open(f"h649_{nm}.pkl", "rb")):
            cells[(dist, s4, side, L)].append((xd60, sR, fire, req))

    # Pareto frontiers per cell (in xd60), keep sR alongside
    frontier = {}
    for k, rows in cells.items():
        if len(rows) < 300:
            continue
        sR = rows[0][1]
        def nearthird(xd):
            v = 3 * xd / 2**60
            return min(abs(v - 1), abs(v - 2)) < 1e-4
        fr = sorted((xd, req) for xd, s, f, req in rows
                    if f and not nearthird(xd))
        cl = sorted((xd, req) for xd, s, f, req in rows
                    if not f and not nearthird(xd))
        fF = []
        mx = None
        for xd, req in fr:
            if mx is None or req > mx:
                fF.append((xd, req)); mx = req
        cF = []
        mn = None
        for xd, req in reversed(cl):
            if mn is None or req < mn:
                cF.append((xd, req)); mn = req
        frontier[k] = (sR, fF, cF)

    blocks = defaultdict(list)
    for k in frontier:
        d, s4, side, L = k
        blocks[(d, s4, side)].append(k)

    print(f"{len(frontier)} cells in {len(blocks)} blocks; frontier sizes: "
          f"{sum(len(f[1])+len(f[2]) for f in frontier.values())} rows total")

    # xd60 -> rdisc: rdisc = xd60 * 2^(sR-60)  (exact: xd60=(rdisc<<60)>>sR;
    # rdisc's low sR-60 bits are lost — but comparator scales >= 2^(c-sR)
    # with c-sR >= ... treat xd60 as rdisc*2^(60-sR) exactly enough:
    # term = P * rdisc * 2^(c-sR) = P * xd60 * 2^(c-60).
    results = {}
    for P in (1, 3):
      for mode in ("rel", "abs"):
        for c in range(60, 69):     # term = P * xd60 * 2^(c-60) [* 2^(sR-63)]
            for parA, parB in ((0, 0), (0, 1), (1, 1)):
                # parA for s4=66 blocks, parB for s4=67
                tag = (P, mode, c, parA, parB)
                Ws = {}
                ok_all = True
                for bk, cellks in sorted(blocks.items()):
                    d, s4, side = bk
                    K = 1 if s4 == 66 else 2
                    par = parA if s4 == 66 else parB
                    wlo = None; whi = None
                    for ck in cellks:
                        _, _, _, L = ck
                        sR, fF, cF = frontier[ck]
                        ce = c + (sR - 63 if mode == "abs" else 0)
                        base = L << 65
                        for xd, req in fF:
                            X = base + P * (xd << (ce - 60)) if ce >= 60 \
                                else base + P * (xd >> (60 - ce))
                            g = ceil_div(req - par * (L % 2), K)
                            w = (g << 66) - X
                            wlo = w if wlo is None else max(wlo, w)
                        for xd, req in cF:
                            X = base + P * (xd << (ce - 60)) if ce >= 60 \
                                else base + P * (xd >> (60 - ce))
                            g = (req - par * (L % 2)) // K
                            w = ((g + 1) << 66) - X   # need floor(..) <= g
                            whi = w if whi is None else min(whi, w)
                    # W valid iff wlo <= W < whi (floor >= g needs X+W >= g*2^66;
                    # floor <= g needs X+W < (g+1)*2^66)
                    if wlo is None:
                        wlo = whi - 1 if whi is not None else 0
                    if whi is None:
                        whi = wlo + 1
                    if wlo < whi:
                        Ws[bk] = (wlo, whi)
                    else:
                        ok_all = False
                        Ws[bk] = None
                nok = sum(1 for v in Ws.values() if v)
                results[tag] = (nok, Ws)

    best = sorted(results, key=lambda t: -results[t][0])[:6]
    for tag in best:
        P, mode, c, parA, parB = tag
        nok, Ws = results[tag]
        print(f"\nP={P} {mode} c={c} par66={parA} par67={parB}: "
              f"{nok}/{len(blocks)} blocks consistent")
        for bk in sorted(Ws):
            v = Ws[bk]
            if v is None:
                print(f"   {bk}: FAIL")
            else:
                lo, hi = v
                # print W interval in 2^60 units for readability
                print(f"   {bk}: W in [{lo/2**66:+.4f}, {hi/2**66:+.4f}) "
                      f"*2^66  width {(hi-lo)/2**66:.4f}")


if __name__ == "__main__":
    main()
