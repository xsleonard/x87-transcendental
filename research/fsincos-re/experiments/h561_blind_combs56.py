#!/usr/bin/env python3
"""h561: BLIND validation of the comb-7-fitted zoned selector
(h558_zoned_selector.json, j = round(4*tau + a*mf + b) per
(stratum, XD12) zone) on combs 5 and 6 — disjoint m-windows
(W1 = [0x80,0xA8) and W2 = [0xF0,0x100) vs comb-7's [0xA8,0xC8)).
Ties only (theta=0).  Zones absent from the tables (new strata /
windows) are counted uncovered.  This measures whether the affine
zone terms extrapolate across windows or are window-local.
"""
import json
import sys
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h539_D_library import qrow

TABLES = {}


def init_tables():
    global TABLES
    raw = json.load(open("h558_zoned_selector.json"))
    TABLES = {}
    for kk, (a, b) in raw.items():
        key = eval(kk)
        TABLES[key] = (a, b)


def work(rows):
    init_tables()
    cen = defaultdict(int)
    for mhex, lab, ce in rows:
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
            cen[("viol",)] += 1
            continue
        f4_full = sqv * sqv
        s4 = f4_full.bit_length() - 67
        tau4 = (t4 * 4) / 2**s4
        XD12 = min(11, (rdisc * 12) >> rsh)
        mf = m / 2**64
        key = (dist, low3, ce, XD12)
        tab = TABLES.get(key)
        strat = (dist, low3, ce)
        if tab is None:
            cen[("nozone", strat)] += 1
            continue
        a, b = tab
        jp = round(tau4 + a * mf + b)
        ok = jlo <= jp <= jhi
        cen[("s", strat, ok)] += 1
    return dict(cen)


def load_comb(name, statpre, stride):
    rows = []
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
    for cname, spre, stride in (("ties_comb5.txt", "comb5", 1),
                                ("ties_comb6.txt", "comb6", 4)):
        labeled = load_comb(cname, spre, stride)
        print(f"\n===== {cname}: labeled {len(labeled)} =====",
              flush=True)
        chunks = [labeled[i::8] for i in range(8)]
        with Pool(8) as pool:
            parts = pool.map(work, chunks)
        cen = defaultdict(int)
        for part in parts:
            for kk, v in part.items():
                cen[kk] += v
        okt = badt = 0
        strata = sorted(set(kk[1] for kk in cen
                            if kk[0] == "s"))
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
              f"({okt/max(okt+badt,1):.4f}); no-zone rows {noz}; "
              f"ladder violations {cen.get(('viol',), 0)}")


if __name__ == "__main__":
    main()
