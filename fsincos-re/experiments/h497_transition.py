#!/usr/bin/env python3
"""h497: per-stratum m-transition characterization + crossing census.

Per (dist, low3, rud) stratum (le2 deliberately NOT in the key — it
becomes an integer candidate):
  1. fine-binned fire rate vs m; interpolated m10/m50/m90;
  2. RANGE GATE (the rf lesson, institutionalized): every candidate's
     corpus-wide 5-95 percentile range is measured FIRST; fractional
     candidates with range < 0.05 of a binade and integer candidates
     with < 2 distinct values are DISQUALIFIED before alignment is
     assessed;
  3. fractional census: qualified candidates' median value in a
     window around m50, per stratum; alignment score =
     cross-stratum dispersion / corpus range (small = aligned);
  4. integer census: does the integer step at m50?  distance from
     the candidate's step location to m50, normalized by the
     transition width (m90-m10), per stratum.

Candidates: fractions m,R,ls,rs,sq,f4,lf,rf,lprod,rprod (binade
fractions); integers le2,re2,corr_e,k,sL,sR,s4,s2,Mbits,shift_final.
Run from /tmp/stageA.
"""
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h453_chain_variants import (C6_1, C6_2, C6_3, C6_4, C6_5, C6_6,
                                 build_chain, mul_round)
E2M = -66
FRACS = ("m", "R", "ls", "rs", "sq", "f4", "lf", "rf", "lprod",
         "rprod")
INTS = ("le2", "re2", "corr_e", "k", "sL", "sR", "s4", "s2",
        "Mbits", "shift_final")

def frac(x):
    return x / (1 << x.bit_length())        # in [0.5, 1)

def build(args):
    mhex, fire = args
    m = int(mhex, 16)
    mag = (0, E2M, m)
    square = mul_round(mag, mag, 67, "chop")
    fourth = mul_round(square, square, 67, "chop")
    negative = build_chain(fourth, C6_5, C6_3, C6_1, 67, 64, "rn",
                           False, False, False)
    positive = build_chain(fourth, C6_6, C6_4, C6_2, 67, 64, "rn",
                           False, False, False)
    left = mul_round(square, negative, 67, "chop")
    right = mul_round(fourth, positive, 67, "chop")
    low3 = square[2] & 7
    dist = abs(left[1] - right[1])
    payload = low3 + 8 - dist
    scale = min(left[1], right[1])
    if payload and left[1] - 8 < scale:
        scale = left[1] - 8
    M = (left[2] << (left[1]-scale)) + (payload << (left[1]-8-scale)) \
        - (right[2] << (right[1]-scale))
    k = M.bit_length() - 67
    R = M >> k
    corr_e = scale + k
    lprod = square[2] * negative[2]
    rprod = fourth[2] * positive[2]
    sL = lprod.bit_length() - 67
    sR = rprod.bit_length() - 67
    s4 = (square[2] * square[2]).bit_length() - 67
    s2 = (m * m).bit_length() - 67
    rud = (rprod & ((1 << sR) - 1)) >> (sR - 1)
    numerator = (1 << -corr_e) - R
    shift_final = numerator.bit_length() - 64
    fr = {"m": frac(m), "R": frac(R), "ls": frac(left[2]),
          "rs": frac(right[2]), "sq": frac(square[2]),
          "f4": frac(fourth[2]), "lf": frac(negative[2]),
          "rf": frac(positive[2]), "lprod": frac(lprod),
          "rprod": frac(rprod)}
    iv = {"le2": left[1], "re2": right[1], "corr_e": corr_e, "k": k,
          "sL": sL, "sR": sR, "s4": s4, "s2": s2,
          "Mbits": M.bit_length(), "shift_final": shift_final}
    return ((dist, low3, rud), m, fr, iv, int(fire))

def load_rows():
    rows = []
    with open("h491_mapdata.tsv") as fh:
        fh.readline()
        for line in fh:
            f = line.rstrip("\n").split("\t")
            if f[7] in ("CLEAN", "FIRE"):
                rows.append((f[0], f[7] == "FIRE"))
    fresh = []
    seen = set()
    for line in open("ties_fresh.txt"):
        f = line.split()
        if f[0] not in seen:
            seen.add(f[0])
            fresh.append(f)
    inputs = sorted(f[0] for f in fresh)
    order = {mm: i for i, mm in enumerate(inputs)}
    st = {md: open(f"fcos2_{md}_status.txt").read().splitlines()
          for md in ROUNDING_MODES}
    for f in fresh:
        Rv = int(f[7], 16)
        ce = int(f[8])
        i = order[f[0]]
        hw = []
        bad = False
        for md in ROUNDING_MODES:
            t = st[md][i].split()
            if t[0] != "OK":
                bad = True
                break
            hw.append(int(t[2], 16))
        if bad:
            continue
        clean = [final_cosine_result(-Rv, ce, md)
                 for md in ROUNDING_MODES]
        fired = [final_cosine_result(-(Rv-1), ce, md)
                 for md in ROUNDING_MODES]
        if hw == clean:
            rows.append((f[0], False))
        elif hw == fired:
            rows.append((f[0], True))
    dedup = {}
    for mhex, fire in rows:
        dedup[mhex] = fire
    return sorted(dedup.items())

def main():
    rows = load_rows()
    print(f"rows: {len(rows)}")
    with Pool(8) as pool:
        data = pool.map(build, rows, chunksize=500)

    # ---- range gate --------------------------------------------------
    fvals = defaultdict(list)
    ivals = defaultdict(set)
    for s, m, fr, iv, fire in data:
        for kq, v in fr.items():
            fvals[kq].append(v)
        for kq, v in iv.items():
            ivals[kq].add(v)
    qual_f, qual_i = [], []
    print("\n=== range gate ===")
    for kq in FRACS:
        vs = sorted(fvals[kq])
        r = vs[int(len(vs)*0.95)] - vs[int(len(vs)*0.05)]
        ok = r >= 0.05
        print(f"  frac {kq:6s} 5-95 range {r:.5f} "
              f"{'OK' if ok else 'DISQUALIFIED (near-constant)'}")
        if ok:
            qual_f.append(kq)
    for kq in INTS:
        nv = len(ivals[kq])
        ok = nv >= 2
        print(f"  int  {kq:11s} distinct values {nv} "
              f"{'OK' if ok else 'DISQUALIFIED'}")
        if ok:
            qual_i.append(kq)

    # ---- per-stratum transitions -------------------------------------
    strata = defaultdict(list)
    for s, m, fr, iv, fire in data:
        strata[s].append((m, fr, iv, fire))
    print("\n=== transitions (m10/m50/m90 as binade fractions) ===")
    crossings = {}
    for s in sorted(strata):
        pts = sorted(strata[s])
        n = len(pts)
        if n < 2000:
            continue
        # fine bins: equal-count bins of ~400 rows
        B = max(20, n // 400)
        prof = []
        for b in range(B):
            seg = pts[b*n//B:(b+1)*n//B]
            if not seg:
                continue
            rate = sum(p[3] for p in seg) / len(seg)
            mid = seg[len(seg)//2][0]
            prof.append((mid, rate))
        def crossing(level):
            for i in range(len(prof)-1):
                a, b2 = prof[i], prof[i+1]
                if (a[1] - level) * (b2[1] - level) <= 0 \
                        and a[1] != b2[1]:
                    t = (a[1] - level) / (a[1] - b2[1])
                    return a[0] + t * (b2[0] - a[0])
            return None
        m50 = crossing(0.5)
        m10 = crossing(0.9)     # rate decreasing: 90 percent first
        m90 = crossing(0.1)
        if m50 is None:
            print(f"  {s}: no 50-percent crossing in sampled range")
            continue
        width = (m90 - m10) / 2**64 if (m10 and m90) else None
        crossings[s] = (m50, m10, m90)
        print(f"  {s}: m50={m50/2**64:.6f} "
              f"width={'%.6f' % width if width else 'n/a'}")

    # ---- fractional census at m50 ------------------------------------
    print("\n=== fractional candidates at m50 (qualified only) ===")
    print(f"{'stratum':16s} " + " ".join(f"{k:>9s}" for k in qual_f))
    table = defaultdict(dict)
    for s, (m50, _, _) in sorted(crossings.items()):
        pts = strata[s]
        near = sorted(pts, key=lambda p: abs(p[0] - m50))[:400]
        line = []
        for kq in qual_f:
            vs = sorted(p[1][kq] for p in near)
            med = vs[len(vs)//2]
            table[kq][s] = med
            line.append(f"{med:9.5f}")
        print(f"{str(s):16s} " + " ".join(line))
    print("\nalignment score (cross-stratum stddev / corpus range):")
    import statistics
    for kq in qual_f:
        vals = list(table[kq].values())
        if len(vals) < 4:
            continue
        sd = statistics.pstdev(vals)
        vs = sorted(fvals[kq])
        rng = vs[int(len(vs)*0.95)] - vs[int(len(vs)*0.05)]
        print(f"  {kq:6s} sd={sd:.5f} range={rng:.5f} "
              f"score={sd/rng:.3f}")

    # ---- integer census ----------------------------------------------
    print("\n=== integer candidates: step at m50? ===")
    for kq in qual_i:
        report = []
        for s, (m50, m10, m90) in sorted(crossings.items()):
            pts = sorted(strata[s])
            below = [p[2][kq] for p in pts if p[0] < m50][-300:]
            above = [p[2][kq] for p in pts if p[0] > m50][:300]
            if not below or not above:
                continue
            vb = max(set(below), key=below.count)
            va = max(set(above), key=above.count)
            report.append((s, vb, va, vb != va))
        steps = sum(1 for _, _, _, st_ in report if st_)
        print(f"  {kq:11s}: steps at m50 in {steps}/{len(report)} "
              f"strata " + " ".join(
                  f"{s}:{vb}->{va}" for s, vb, va, st_ in report
                  if st_)[:120])

if __name__ == "__main__":
    main()
