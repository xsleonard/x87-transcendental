#!/usr/bin/env python3
"""h570: blind validation of SIDE-SPLIT up-lines on the tie combs.

h565: fitting the up/carry threshold on theta<=0 rows alone is
near-exact (0.9985-0.9996) in every dist=8@-73 stratum — the joint
fit was dragged by down-side rows.  Ties are up-side rows, so the
tie combs 3/4/5/6 (disjoint inputs; 5/6 disjoint m-windows) are a
blind test: PREDICTION (locked): up-line tables fit on comb-7
theta<=0 rows push dist=8@-73 tie coverage to ~0.999, vs ~0.93 for
the h561 joint tables.  dist=9-low up side is the HARD side —
expect no improvement there (ceiling ~0.93-0.99).
Fit: j = round(x4 + a*mf + b) per (stratum, XD12) zone on ALL
comb-7 theta<=0 rows; score every labeled tie in combs 3-6.
"""
import sys
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h539_D_library import qrow

AG = list(range(-80, 9, 2))
FITTED = {}


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


def prep(mhex, lab, ce):
    (m, sqv, f4v, rfv, t4, rdisc, A, P, M, k, R, B_full,
     rsh, bshift, dist, low3) = qrow(mhex)
    F = rsh - bshift
    if F < 0:
        return None
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
        return None
    f4_full = sqv * sqv
    s4 = f4_full.bit_length() - 67
    x4 = t4 * 2.0**(65 - s4) / rfv
    XD12 = min(11, (rdisc * 12) >> rsh)
    mf = m / 2**64
    return ((dist, low3, ce), XD12, x4, mf, jlo, jhi)


def work_fit(rows):
    zones = defaultdict(list)
    for mhex, theta, lab, ce in rows:
        if theta > 0:
            continue
        r = prep(mhex, lab, ce)
        if r is None:
            continue
        strat, XD12, x4, mf, jlo, jhi = r
        zones[(strat, XD12)].append((x4, mf, jlo, jhi))
    return {k: v for k, v in zones.items()}


def work_score(rows):
    cen = defaultdict(int)
    for mhex, lab, ce in rows:
        r = prep(mhex, lab, ce)
        if r is None:
            cen[("viol",)] += 1
            continue
        strat, XD12, x4, mf, jlo, jhi = r
        tab = FITTED.get((strat, XD12))
        if tab is None:
            cen[("nozone", strat)] += 1
            continue
        a, b = tab
        jp = round(x4 + a * mf + b)
        cen[("s", strat, jlo <= jp <= jhi)] += 1
    return dict(cen)


def init_pool(fitted):
    global FITTED
    FITTED = fitted


def load_comb7(stride):
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
    return labeled


def load_comb(name, statpre, stride):
    seen = set()
    raw = []
    for line in open(name):
        f = line.split()
        if f[0] in seen:
            continue
        seen.add(f[0])
        raw.append(f)
    inputs = sorted(f[0] for f in raw)
    order = {m2: i for i, m2 in enumerate(inputs)}
    st = {md: open(f"{statpre}_{md}_status.txt").read()
          .splitlines() for md in ROUNDING_MODES}
    out = []
    for j, f in enumerate(raw):
        if j % stride:
            continue
        R, ce = int(f[7], 16), int(f[8])
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
        refs = {nm: [final_cosine_result(-(R + d), ce, md)
                     for md in ROUNDING_MODES]
                for nm, d in (("clean", 0), ("down", -1),
                              ("up", 1))}
        for nm in ("clean", "down", "up"):
            if hw == refs[nm]:
                out.append((f[0], nm, ce))
                break
    return out


def main():
    labeled = load_comb7(1)
    print(f"comb-7 labeled: {len(labeled)}", flush=True)
    chunks = [labeled[i::8] for i in range(8)]
    with Pool(8) as pool:
        parts = pool.map(work_fit, chunks)
    zones = defaultdict(list)
    for part in parts:
        for k, v in part.items():
            zones[k].extend(v)
    fitted = {}
    for key, pts in zones.items():
        best = (0, None, None)
        for a in AG:
            iv = [(jlo - 0.5 - x4 - a * mf,
                   jhi + 0.5 - x4 - a * mf)
                  for x4, mf, jlo, jhi in pts]
            c, b = stab(iv)
            if c > best[0]:
                best = (c, a, b)
        if best[1] is not None:
            fitted[key] = (best[1], best[2])
    print(f"zones fitted: {len(fitted)}", flush=True)
    for cname, spre, stride in (("ties_comb3.txt", "comb3", 4),
                                ("ties_comb4.txt", "comb4", 4),
                                ("ties_comb5.txt", "comb5", 1),
                                ("ties_comb6.txt", "comb6", 4)):
        rows = load_comb(cname, spre, stride)
        print(f"\n===== {cname}: labeled {len(rows)} =====",
              flush=True)
        chunks = [rows[i::8] for i in range(8)]
        with Pool(8, initializer=init_pool,
                  initargs=(fitted,)) as pool:
            parts = pool.map(work_score, chunks)
        cen = defaultdict(int)
        for part in parts:
            for kk, v in part.items():
                cen[kk] += v
        okt = badt = 0
        strata = sorted(set(kk[1] for kk in cen if kk[0] == "s"))
        for strat in strata:
            ok = cen.get(("s", strat, True), 0)
            bad = cen.get(("s", strat, False), 0)
            okt += ok
            badt += bad
            if ok + bad >= 200:
                print(f"  {strat}: {ok}/{ok+bad} "
                      f"({ok/(ok+bad):.4f})")
        noz = sum(v for kk, v in cen.items() if kk[0] == "nozone")
        print(f"  BLIND covered: {okt}/{okt+badt} "
              f"({okt/max(okt+badt,1):.4f}); no-zone {noz}; "
              f"ladder viol {cen.get(('viol',), 0)}")


if __name__ == "__main__":
    main()
