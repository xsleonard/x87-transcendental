#!/usr/bin/env python3
"""h565: side-split selector — the down/borrow threshold is not the
up/carry threshold.

h564 autopsy: in (8,4/5/6)@-73 EVERY held-out miss is a theta>=+1
row, 98 percent clean rows the joint line predicts to down-fire.
So fit the sides separately per (stratum, XD12) zone:
  up-line  : stab fit on theta<=0 rows only
  dn variants, fit on theta>=+1 rows:
    D0: score dn rows with the up-line (joint baseline)
    D1: up-line minus per-zone constant delta (delta 0..10 grid)
    D2: independent line (a_dn, b_dn)
Split-half held-out, per-stratum up/dn accuracy; also report
delta and (a_dn - a_up) distributions.  All dist 8/9 strata.
"""
import sys
from collections import Counter, defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h539_D_library import qrow

AG = list(range(-80, 9, 2))
DG = list(range(0, 11))


def stab(intervals):
    ev = []
    for lo, hi in intervals:
        ev.append((lo, 1))
        ev.append((hi, -1))
    ev.sort()
    best = (0, None)
    cur = 0
    for x, d in ev:
        cur += d
        if cur > best[0]:
            best = (cur, x)
    return best


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
        base = Vlow << 2
        top = 1 << (kf + 2)
        jlo = jhi = None
        for j in range(-16, 17):
            T = base - j * rfv
            pred = 1 if T >= top else (-1 if T < 0 else 0)
            if pred == req2:
                if jlo is None:
                    jlo = j
                jhi = j
        if jlo is None:
            continue
        f4_full = sqv * sqv
        s4 = f4_full.bit_length() - 67
        x4 = t4 * 2.0**(65 - s4) / rfv
        XD12 = min(11, (rdisc * 12) >> rsh)
        mf = m / 2**64
        half = (m * 2654435761) & 1
        out.append(((dist, low3, ce, XD12), half, x4, mf,
                    jlo, jhi, theta))
    return out


def fit_line(pts):
    best = (0, None, None)
    for a in AG:
        iv = [(jlo - 0.5 - x4 - a * mf, jhi + 0.5 - x4 - a * mf)
              for x4, mf, jlo, jhi in pts]
        c, b = stab(iv)
        if c > best[0]:
            best = (c, a, b)
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
    stride = int(sys.argv[1]) if len(sys.argv) > 1 else 2
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
    tr_up = defaultdict(list)
    tr_dn = defaultdict(list)
    te_up = defaultdict(list)
    te_dn = defaultdict(list)
    for part in parts:
        for key, half, x4, mf, jlo, jhi, theta in part:
            pt = (x4, mf, jlo, jhi)
            if theta <= 0:
                (tr_up if half == 0 else te_up)[key].append(pt)
            else:
                (tr_dn if half == 0 else te_dn)[key].append(pt)
    fit_up = {}
    fit_dn = {}
    fit_delta = {}
    for key in tr_up:
        cu, au, bu = fit_line(tr_up[key])
        fit_up[key] = (au, bu)
        dn = tr_dn.get(key, [])
        if dn and au is not None:
            best = (0, None)
            for d in DG:
                ok = sum(1 for x4, mf, jlo, jhi in dn
                         if jlo <= round(x4 + au * mf + bu - d)
                         <= jhi)
                if ok > best[0]:
                    best = (ok, d)
            fit_delta[key] = best[1]
            cd, ad, bd = fit_line(dn)
            fit_dn[key] = (ad, bd)
    S = defaultdict(lambda: defaultdict(int))
    for key, pts in te_up.items():
        f2 = fit_up.get(key)
        if not f2 or f2[0] is None:
            continue
        a, b = f2
        s2 = S[key[:3]]
        for x4, mf, jlo, jhi in pts:
            s2["un"] += 1
            if jlo <= round(x4 + a * mf + b) <= jhi:
                s2["uok"] += 1
    for key, pts in te_dn.items():
        f2 = fit_up.get(key)
        if not f2 or f2[0] is None:
            continue
        a, b = f2
        d = fit_delta.get(key)
        f3 = fit_dn.get(key)
        s2 = S[key[:3]]
        for x4, mf, jlo, jhi in pts:
            s2["dn"] += 1
            jp = round(x4 + a * mf + b)
            if jlo <= jp <= jhi:
                s2["d0ok"] += 1
            if d is not None and jlo <= jp - d <= jhi:
                s2["d1ok"] += 1
            if f3 and f3[0] is not None:
                if jlo <= round(x4 + f3[0] * mf + f3[1]) <= jhi:
                    s2["d2ok"] += 1
    print(f"\n{'stratum':14s} {'n_up':>7s} {'up':>7s} "
          f"{'n_dn':>7s} {'D0':>7s} {'D1':>7s} {'D2':>7s}")
    for strat in sorted(S):
        s2 = S[strat]
        un, dn = s2["un"], s2["dn"]
        if not un or not dn:
            continue
        print(f"{str(strat):14s} {un:7d} {s2['uok']/un:7.4f} "
              f"{dn:7d} {s2['d0ok']/dn:7.4f} "
              f"{s2['d1ok']/dn:7.4f} {s2['d2ok']/dn:7.4f}")
    dd = Counter(fit_delta.values())
    print("\ndelta distribution:", dd.most_common(12))
    da = Counter()
    for key in fit_dn:
        au = fit_up[key][0]
        ad = fit_dn[key][0]
        if au is not None and ad is not None:
            da[ad - au] += 1
    print("a_dn - a_up distribution:", da.most_common(12))


if __name__ == "__main__":
    main()
