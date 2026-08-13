#!/usr/bin/env python3
"""h574b: THE INJECTION + INTEGER-QUARTER REFRAME.

h574a's offset dump: on (9,1..4)@-72 dn the fitted per-zone D =
-(2^kf)*u + (24 - XD12)/4 ladder units EXACTLY (u = 4/rfv;
bracket width 3*2^(kf-63) = 1536 there) — i.e. hardware = EU + 1
injected, minus an integer count of rf/4 quarters that steps -1
per XD-twelfth.  Generalize: for EVERY (stratum, side):
  1. verify kf is constant per stratum (print distribution);
  2. per row find injection inj in {-1, 0, +1} minimizing the
     bracket magnitude; express brackets in QUARTERS q:
     bracket_q = (bracket + inj*2^kf*u) * 4;
  3. per (zone=XD12) fit the best INTEGER quarter-count q(zone)
     (stab over integers) with the t4 term optionally added in
     exact quarters (t4-term from h573: tau*2^(c-64)... use the
     h573b-winning per-stratum c4 grid 61..66 scaled correctly);
  4. print per-zone integer q tables + held-out rates + the
     zero-parameter test q = 24 - XD12 on the four strata.
"""
import sys
from collections import Counter, defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h539_D_library import qrow


def work(rows):
    out = []
    for mhex, theta, lab, ce in rows:
        (m, sqv, f4v, rfv, t4, rdisc, A, P, M, k, R, B_full,
         rsh, bshift, dist, low3) = qrow(mhex)
        F = rsh - bshift
        if F < 0:
            continue
        kf = k + F
        APf = (A + P) << F
        res_hw = R + {"clean": 0, "down": -1, "up": 1}[lab]
        EU = (APf - B_full) >> kf
        req2 = res_hw - EU
        Vlow = (APf - B_full) - (EU << kf)
        u = 4.0 / rfv
        dlo = (Vlow - ((req2 + 1) << kf)) * u
        dhi = (Vlow - (req2 << kf)) * u
        wq = (1 << kf) * u          # bracket width, ladder units
        f4_full = sqv * sqv
        s4 = f4_full.bit_length() - 67
        t4f = t4 * u / 2.0**s4      # h573 code-unit tail base
        XD12 = min(11, (rdisc * 12) >> rsh)
        half = (m * 2654435761) & 1
        side = "up" if theta <= 0 else "dn"
        out.append(((dist, low3, ce), side, XD12, half, kf,
                    wq, t4f, dlo, dhi))
    return out


def stab_int_q(ivs, lim=1024):
    # best integer q in [-lim, lim] maximizing containment;
    # ivs are (lo, hi) OPEN-CLOSED in quarters
    ev = []
    for lo, hi in ivs:
        ev.append((lo, 1))
        ev.append((hi, -1))
    ev.sort()
    # sweep, but snap to integer: count for floor(x)+1 after each
    # open; simpler: candidate integers near interval edges
    cands = set()
    for lo, hi in ivs[:400]:
        cands.add(int(lo) + 1)
        cands.add(int(hi))
    best = (-1, None)
    for q in cands:
        c = sum(1 for lo, hi in ivs if lo < q <= hi)
        if c > best[0]:
            best = (c, q)
    return best


def main():
    seen = set()
    raw = []
    for line in open("ties_comb7.txt"):
        f = line.split()
        if f[0] in seen:
            continue
        seen.add(f[0])
        raw.append(f)
    inputs = sorted(f[0] for f in raw)
    order = {m2: i for i, m2 in enumerate(inputs)}
    st = {md: open(f"comb7_{md}_status.txt").read().splitlines()
          for md in ROUNDING_MODES}
    stride = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    labeled = []
    for j, f in enumerate(raw):
        if j % stride:
            continue
        R, ce, theta = int(f[7], 16), int(f[8]), int(f[9])
        i = order[f[0]]
        hw, bad = [], False
        for md in ROUNDING_MODES:
            t = st[md][i].split()
            if t[0] != "OK":
                bad = True
                break
            hw.append(int(t[2], 16))
        if bad:
            continue
        refs = {name: [final_cosine_result(-(R + d), ce, md)
                       for md in ROUNDING_MODES]
                for name, d in (("clean", 0), ("down", -1),
                                ("up", 1))}
        for name in ("clean", "down", "up"):
            if hw == refs[name]:
                labeled.append((f[0], theta, name, ce))
                break
    print(f"labeled sample: {len(labeled)}", flush=True)
    chunks = [labeled[i::8] for i in range(8)]
    with Pool(8) as pool:
        parts = pool.map(work, chunks)
    kfc = defaultdict(Counter)
    groups = defaultdict(lambda: ([], []))
    for part in parts:
        for strat, side, XD12, half, kf, wq, t4f, dlo, dhi \
                in part:
            kfc[strat][kf] += 1
            pt = (XD12, wq, t4f, dlo, dhi)
            groups[(strat, side)][0 if half == 0 else 1].append(pt)
    print("\nkf distribution per stratum:")
    for strat in sorted(kfc):
        print(f"  {strat}: {dict(kfc[strat])}")
    print("\nPer (stratum, side): best injection frame + integer"
          "-quarter zone table (train half), held-out rate:")
    Z4 = {(9, 1, -72), (9, 2, -72), (9, 3, -72), (9, 4, -72)}
    for (strat, side) in sorted(groups):
        tr, te = groups[(strat, side)]
        if len(tr) < 400:
            continue
        # choose injection per side: the one minimizing median |mid|
        best_inj = None
        best_med = None
        for inj in (-1, 0, 1):
            mids = []
            for XD12, wq, t4f, dlo, dhi in tr[:2000]:
                mid = (dlo + dhi) / 2 + inj * wq
                mids.append(abs(mid))
            mids.sort()
            med = mids[len(mids) // 2]
            if best_med is None or med < best_med:
                best_med, best_inj = med, inj
        inj = best_inj
        zones_tr = defaultdict(list)
        for XD12, wq, t4f, dlo, dhi in tr:
            zones_tr[XD12].append(((dlo + inj * wq) * 4,
                                   (dhi + inj * wq) * 4))
        qtab = {}
        for z, ivs in zones_tr.items():
            c, q = stab_int_q(ivs)
            qtab[z] = (q, c, len(ivs))
        ok = n = 0
        okz = n0 = 0
        for XD12, wq, t4f, dlo, dhi in te:
            qq = qtab.get(XD12)
            if qq is None or qq[0] is None:
                continue
            lo = (dlo + inj * wq) * 4
            hi = (dhi + inj * wq) * 4
            n += 1
            if lo < qq[0] <= hi:
                ok += 1
            if strat in Z4 and side == "dn":
                n0 += 1
                if lo < (24 - XD12) <= hi:
                    okz += 1
        tabs = " ".join(f"{z}:{qtab[z][0]}"
                        for z in sorted(qtab))
        print(f"{strat} {side} inj={inj:+d} held-out "
              f"{ok/max(n,1):.4f} ({n})")
        print(f"    q(zone): {tabs}")
        if n0:
            print(f"    ZERO-PARAM q=24-XD12: {okz/n0:.4f} ({n0})")


if __name__ == "__main__":
    main()
