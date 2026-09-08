#!/usr/bin/env python3
"""h658: close the theta-ladder edge table — h653-style tap fit.

h657i: a single constant tap -g*theta inside the u-floor gives ZERO
edge violations but is too conservative at |theta|=2 (region rates
0.10-0.15 vs the 3/4 ceiling) — the tap must interact with the
existing taps.  This script does the h653 exercise on the edges:

1. Per cell (sign, |theta|, quadrant, dist, L, b1, b2): empirical
   lattice edge from the labeled rows, with (a) censoring detection
   (edge bin must be populated by >= MINBIN rows to count as two-sided;
   fires reaching the corpus rim give one-sided constraints), and
   (b) h653's lenient handling of <=3-row isolated anomalies (dropped
   and reported, gap >= 2 lattice levels).
2. Convert each edge to the feasible integer interval of the tap T in
     dn: fire possible <=> M <  u_T*2^66,
         u_T = K*floor((base - T)/Q) + par*(L%2) + o
     up: fire possible <=> M >= u_T*2^66,
         u_T = K*floor((base + T)/Q) + par*(L%2) + o
   (base = a*L + G1*b1 + G2*b2 + p*(L%2) + W(d); o in {0,1} group-wide.)
3. Enumerate integer forms T = c0 + c1*b1 + c2*b2 + c3*(L%2) + c4*(d-7)
   satisfying every interval; c0 solved analytically per (c1..c4).
4. m-parity split-half stability: edges from even-m rows only must not
   be violated by odd-m fires.

Data: h657m caches (exact rdisc -> exact b1/b2 taps).
"""
import pickle
from collections import defaultdict

UNIT = 2**66
MINROWS = 30     # skip thinner cells
MINBIN = 10      # rows needed in the first outside bin to pin an edge

QUAD = {
    (66, 1): (2, 2, 1,  0, 4, 1, 0, lambda d: -5 * (d - 7)),
    (66, 0): (4, 1, 0,  0, 2, 1, 0, lambda d: -9 - 5 * (d - 9)),
    (67, 0): (4, 2, 1, -2, 4, 2, 1, lambda d: -5 * (d - 7)),
    (67, 1): (2, 2, 3, -3, 8, 2, 1, lambda d: -4 - 2 * (d - 7)),
}


def load():
    groups = defaultdict(lambda: defaultdict(list))
    for name in ("comb7", "comb8"):
        rows = pickle.load(open(f"h657m_{name}.pkl", "rb"))
        for mhex, theta, dist, s4, side, L, rdisc, sR, label, M, sqlow in rows:
            b1 = 1 if 3 * rdisc >= (1 << sR) else 0
            b2 = 1 if 3 * rdisc >= (1 << (sR + 1)) else 0
            q = M // UNIT
            mpar = int(mhex, 16) & 1
            if theta > 0:
                sign, fire = "dn", int(label == 1)
            else:
                sign, fire = "up", int(label == 2)
            groups[(sign, abs(theta), (s4, side))][
                (dist, L, b1, b2)].append((q, fire, mpar))
        print(f"{name} loaded", flush=True)
    return groups


def edge_of(rows, sign):
    """rows: [(q, fire)] -> (kind, u_emp, anomalies, rate_in)
    kind: 'two' (exact edge), 'one' (censored, bound only), 'nofire'."""
    fq = defaultdict(int)
    allq = defaultdict(int)
    for q, f in rows:
        allq[q] += 1
        if f:
            fq[q] += 1
    nfire = sum(fq.values())
    if nfire < 5:
        # too few fires to pin an edge (the <=3-row anomaly families
        # would poison it) — constrain nothing, but report the count
        return ("nofire", min(allq) if sign == "dn" else max(allq),
                nfire, 0.0) if nfire == 0 else ("skip", None, nfire, 0.0)
    lv = sorted(fq)
    anom = 0
    if sign == "dn":
        if len(lv) > 1 and fq[lv[-1]] <= 3 and lv[-1] - lv[-2] >= 2:
            anom = fq[lv[-1]]
            lv = lv[:-1]
        top = lv[-1]
        u = top + 1
        outside = allq.get(u, 0)
        kind = "two" if outside >= MINBIN else "one"
        nin = sum(c for q, c in allq.items() if q < u)
        nf = sum(c for q, c in fq.items() if q < u)
    else:
        if len(lv) > 1 and fq[lv[0]] <= 3 and lv[1] - lv[0] >= 2:
            anom = fq[lv[0]]
            lv = lv[1:]
        bot = lv[0]
        u = bot
        outside = allq.get(u - 1, 0)
        kind = "two" if outside >= MINBIN else "one"
        nin = sum(c for q, c in allq.items() if q >= u)
        nf = sum(c for q, c in fq.items() if q >= u)
    return (kind, u, anom, nf / nin if nin else 0.0)


def tap_interval(sign, quad, dist, L, b1, b2, o, kind, u_emp):
    """Feasible integer interval [lo, hi] (inclusive; None = unbounded)
    for the tap T given the edge constraint."""
    a, G1, G2, p, Q, K, par, W = QUAD[quad]
    base = a * L + G1 * b1 + G2 * b2 + p * (L % 2) + W(dist)
    lp = par * (L % 2) + o
    if sign == "dn":
        # u_T = K*floor((base-T)/Q) + lp ; region q < u_T
        if kind == "two":                     # u_T == u_emp
            if (u_emp - lp) % K:
                return None
            f = (u_emp - lp) // K
            return (base - Q * (f + 1) + 1, base - Q * f)
        if kind == "one":                     # u_T >= u_emp
            f = -((-(u_emp - lp)) // K)       # ceil
            return (None, base - Q * f)
        # nofire: u_T <= qmin  (u_emp carries qmin)
        f = (u_emp - lp) // K                 # floor
        return (base - Q * (f + 1) + 1, None)
    else:
        # u_T = K*floor((base+T)/Q) + lp ; region q >= u_T
        if kind == "two":
            if (u_emp - lp) % K:
                return None
            f = (u_emp - lp) // K
            return (Q * f - base, Q * (f + 1) - 1 - base)
        if kind == "one":                     # u_T <= u_emp
            f = (u_emp - lp) // K
            return (None, Q * (f + 1) - 1 - base)
        # nofire: u_T >= qmax+1 (u_emp carries qmax)
        f = -((-(u_emp + 1 - lp)) // K)       # ceil
        return (Q * f - base, None)


def fit_group(sign, th, quad, cells, o):
    """cells: {(dist,L,b1,b2): (kind, u_emp)} -> solutions of
    T = c0 + c1*b1 + c2*b2 + c3*(L%2) + c4*(d-7)."""
    ivs = []
    infeas = []
    for (dist, L, b1, b2), (kind, u_emp) in cells.items():
        if kind == "skip":
            continue
        iv = tap_interval(sign, quad, dist, L, b1, b2, o, kind, u_emp)
        if iv is None:
            infeas.append((dist, L, b1, b2))
            continue
        ivs.append(((b1, b2, L % 2, dist - 7), iv, kind))
    if infeas:
        return None, infeas, ivs
    sols = []
    R = range(-8, 9)
    for c1 in R:
        for c2 in R:
            for c3 in R:
                for c4 in range(-6, 7):
                    lo0, hi0 = -10**9, 10**9
                    ok = True
                    for (b1, b2, lp, dd), (lo, hi), kind in ivs:
                        r = c1 * b1 + c2 * b2 + c3 * lp + c4 * dd
                        if lo is not None:
                            lo0 = max(lo0, lo - r)
                        if hi is not None:
                            hi0 = min(hi0, hi - r)
                        if lo0 > hi0:
                            ok = False
                            break
                    if ok:
                        for c0 in range(lo0, min(hi0, lo0 + 200) + 1):
                            sols.append((abs(c0) + abs(c1) + abs(c2)
                                         + abs(c3) + abs(c4),
                                         (c0, c1, c2, c3, c4)))
    sols.sort()
    return sols, infeas, ivs


def main():
    groups = load()
    for (sign, th, quad) in sorted(groups, key=str):
        cellrows = groups[(sign, th, quad)]
        cells = {}
        anomtot = 0
        rates = []
        for ck, rr in cellrows.items():
            if len(rr) < MINROWS:
                continue
            kind, u_emp, anom, rate = edge_of([(q, f) for q, f, _ in rr], sign)
            cells[ck] = (kind, u_emp)
            anomtot += anom
            if kind == "two" and rate:
                rates.append(rate)
        n2 = sum(1 for v in cells.values() if v[0] == "two")
        n1 = sum(1 for v in cells.values() if v[0] == "one")
        n0 = sum(1 for v in cells.values() if v[0] == "nofire")
        ns = sum(1 for v in cells.values() if v[0] == "skip")
        print(f"\n===== {sign} |theta|={th} {quad}: cells two/one/nofire/skip"
              f" = {n2}/{n1}/{n0}/{ns}, anomalies dropped {anomtot}, "
              f"mean in-rate {sum(rates)/len(rates) if rates else 0:.3f}",
              flush=True)
        got = False
        for o in (0, 1):
            sols, infeas, ivs = fit_group(sign, th, quad, cells, o)
            if sols is None:
                print(f"  o={o}: INFEASIBLE cells (parity clash): "
                      f"{sorted(infeas)[:8]}{'...' if len(infeas) > 8 else ''}")
                continue
            if sols:
                got = True
                seen = set()
                show = []
                for w, c in sols:
                    if c not in seen:
                        seen.add(c)
                        show.append((w, c))
                    if len(show) >= 3:
                        break
                print(f"  o={o}: {len(seen) if len(sols) < 4000 else '4000+'}"
                      f" solutions; simplest "
                      f"(c0,b1,b2,Lpar,d-7): "
                      + "  ".join(f"{c} (w={w})" for w, c in show))
            else:
                print(f"  o={o}: NO solution in coefficient range")
                # print the intervals for inspection
                for v, iv, kind in sorted(ivs, key=lambda t: t[0]):
                    print(f"      feat{v} {kind}: T in {iv}")
        if not got:
            print("  >>> group needs a richer form (record intervals above)")

    # ---- split-half stability: edges from even-m, violations on odd-m ----
    print("\n===== m-parity split-half stability =====")
    for (sign, th, quad) in sorted(groups, key=str):
        cellrows = groups[(sign, th, quad)]
        viol = tot = 0
        for ck, rr in cellrows.items():
            ev = [(q, f) for q, f, mp in rr if mp == 0]
            od = [(q, f) for q, f, mp in rr if mp == 1]
            if len(ev) < MINROWS or not od:
                continue
            kind, u_emp, _, _ = edge_of(ev, sign)
            if kind in ("nofire", "skip"):
                continue
            for q, f in od:
                if not f:
                    continue
                tot += 1
                if sign == "dn" and q >= u_emp:
                    viol += 1
                if sign == "up" and q < u_emp:
                    viol += 1
        print(f"  {sign} |theta|={th} {quad}: odd-m fires {tot}, "
              f"violations of even-m edges {viol}")


if __name__ == "__main__":
    main()
