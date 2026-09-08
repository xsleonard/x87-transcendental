#!/usr/bin/env python3
"""h664b: derive the (66,0)-quadrant theta-band tap vectors — the
h658 edge-table exercise on the comb11 (W1 window) corpus.

h658 could not constrain quadrant (s4=66, side=0): every theta-labeled
corpus lived in [0xA8,0xF0) where side=0 forces s4=67.  comb11 is the
W1 window [0x80,0xA8) captured with the theta scanner.  This script:

1. Per cell (sign, |theta|, dist, L, b1, b2) inside (66,0): empirical
   lattice edge with censoring detection (h658 edge_of verbatim).
2. Tap intervals through the h656 (66,0) u-floor
   (a,G1,G2,p,Q,K,par,W) = (4,1,0,0,2,1,0, -9-5*(d-9)), o in {0,1}.
3. Enumerate T = c0 + c1*b1 + c2*b2 + c3*(L%2) + c4*(d-7); verify every
   candidate row-by-row, including the h662b/h662k interior law check
   (fires inside the region must obey the block-start law; that part
   needs the terminal frame, done in h664c on region rows only).
4. m-parity split-half stability.

Data: h664_comb11.pkl (h657m-schema rows, theta=0 included).
"""
import pickle, sys
from collections import defaultdict

UNIT = 2**66
MINROWS = 30
MINBIN = 10

# h656 (66,0) u-floor tuple
QA, QG1, QG2, QP, QQ, QK, QPAR = 4, 1, 0, 0, 2, 1, 0
W = lambda d: -9 - 5 * (d - 9)


def load():
    groups = defaultdict(lambda: defaultdict(list))
    other = defaultdict(lambda: [0, 0])
    for name in sys.argv[1:] or ("comb11",):
        rows = pickle.load(open(f"h664_{name}.pkl", "rb"))
        for mhex, theta, dist, s4, side, L, rdisc, sR, label, M, sqlow in rows:
            if theta == 0 or label < 0:
                continue
            sign = "dn" if theta > 0 else "up"
            fire = int(label == (1 if theta > 0 else 2))
            if (s4, side) != (66, 0):
                other[(s4, side, sign, abs(theta))][0] += 1
                other[(s4, side, sign, abs(theta))][1] += fire
                continue
            b1 = 1 if 3 * rdisc >= (1 << sR) else 0
            b2 = 1 if 3 * rdisc >= (1 << (sR + 1)) else 0
            q = M // UNIT
            groups[(sign, abs(theta))][(dist, L, b1, b2)].append(
                (q, fire, int(mhex, 16) & 1))
    print("non-(66,0) theta!=0 strata (rows/fires):")
    for k in sorted(other):
        print(f"  {k}: {other[k][0]:,} / {other[k][1]:,}")
    return groups


def edge_of(rows, sign):
    fq = defaultdict(int)
    allq = defaultdict(int)
    for q, f in rows:
        allq[q] += 1
        if f:
            fq[q] += 1
    nfire = sum(fq.values())
    if nfire < 5:
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


def tap_interval(sign, dist, L, b1, b2, o, kind, u_emp):
    base = QA * L + QG1 * b1 + QG2 * b2 + QP * (L % 2) + W(dist)
    lp = QPAR * (L % 2) + o
    K, Q = QK, QQ
    if sign == "dn":
        if kind == "two":
            if (u_emp - lp) % K:
                return None
            f = (u_emp - lp) // K
            return (base - Q * (f + 1) + 1, base - Q * f)
        if kind == "one":
            f = -((-(u_emp - lp)) // K)
            return (None, base - Q * f)
        f = (u_emp - lp) // K
        return (base - Q * (f + 1) + 1, None)
    else:
        if kind == "two":
            if (u_emp - lp) % K:
                return None
            f = (u_emp - lp) // K
            return (Q * f - base, Q * (f + 1) - 1 - base)
        if kind == "one":
            f = (u_emp - lp) // K
            return (None, Q * (f + 1) - 1 - base)
        f = -((-(u_emp + 1 - lp)) // K)
        return (Q * f - base, None)


def fit_group(sign, cells, o):
    ivs, infeas = [], []
    for (dist, L, b1, b2), (kind, u_emp) in cells.items():
        if kind == "skip":
            continue
        iv = tap_interval(sign, dist, L, b1, b2, o, kind, u_emp)
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


def verify(sign, th, groups, tap, o):
    """row-by-row: no fire outside the tap region; report in-rates."""
    c0, c1, c2, c3, c4 = tap
    viol = nin = nfin = tot = 0
    for (dist, L, b1, b2), rr in groups[(sign, th)].items():
        base = QA * L + QG1 * b1 + QG2 * b2 + QP * (L % 2) + W(dist)
        T = c0 + c1 * b1 + c2 * b2 + c3 * (L % 2) + c4 * (dist - 7)
        lp = QPAR * (L % 2) + o
        if sign == "dn":
            u = QK * ((base - T) // QQ) + lp
        else:
            u = QK * ((base + T) // QQ) + lp
        for q, f, mp in rr:
            tot += 1
            inr = q < u if sign == "dn" else q >= u
            if inr:
                nin += 1
                nfin += f
            elif f:
                viol += 1
    rate = nfin / nin if nin else 0.0
    return viol, nin, nfin, rate, tot


def main():
    groups = load()
    print()
    best = {}
    for (sign, th) in sorted(groups):
        cellrows = groups[(sign, th)]
        cells = {}
        anomtot = 0
        rates = []
        nrows = sum(len(v) for v in cellrows.values())
        nfires = sum(f for v in cellrows.values() for _, f, _ in v)
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
        print(f"===== {sign} |theta|={th} (66,0): rows={nrows:,} "
              f"fires={nfires:,}; cells two/one/nofire/skip = "
              f"{n2}/{n1}/{n0}/{ns}, anomalies dropped {anomtot}, "
              f"mean in-rate {sum(rates)/len(rates) if rates else 0:.3f}",
              flush=True)
        if nfires == 0:
            print("  NO FIRES — stratum is clean, no tap needed")
            continue
        for o in (0, 1):
            sols, infeas, ivs = fit_group(sign, cells, o)
            if sols is None:
                print(f"  o={o}: INFEASIBLE cells: {sorted(infeas)[:8]}")
                continue
            if not sols:
                print(f"  o={o}: NO solution; intervals:")
                for v, iv, kind in sorted(ivs, key=lambda t: t[0]):
                    print(f"      feat{v} {kind}: T in {iv}")
                continue
            seen = set()
            show = []
            for w, c in sols:
                if c not in seen:
                    seen.add(c)
                    show.append((w, c))
                if len(show) >= 5:
                    break
            print(f"  o={o}: {len(seen)} candidate tap forms; simplest "
                  f"(c0,b1,b2,Lpar,d-7): "
                  + "  ".join(f"{c} (w={w})" for w, c in show))
            for w, c in show[:3]:
                viol, nin, nfin, rate, tot = verify(sign, th, groups, c, o)
                print(f"      verify {c} o={o}: viol={viol} "
                      f"in-region={nin:,} fires-in={nfin:,} "
                      f"rate={rate:.3f} (of {tot:,} rows)")
                if viol == 0 and (sign, th) not in best:
                    best[(sign, th)] = (c, o, rate)

    print("\n===== m-parity split-half stability =====")
    for (sign, th) in sorted(groups):
        cellrows = groups[(sign, th)]
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
        print(f"  {sign} |theta|={th}: odd-m fires {tot}, "
              f"violations of even-m edges {viol}")

    print("\nSELECTED:", best)


if __name__ == "__main__":
    main()
