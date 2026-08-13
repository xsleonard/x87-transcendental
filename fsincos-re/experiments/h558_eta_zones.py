#!/usr/bin/env python3
"""h558: zoned affine selector — j = round(4*tau*4)/... precisely:
j = round(4*tau + a*mf + b) with (a, b) fit PER (stratum,
XD-twelfth) zone (the h493/h510 digit-zone coordinates), split-half
held-out.

Train half: for each zone, grid a, stab b (max coverage of the
per-row b-intervals).  Test half: membership of round(4tau + a*mf
+ b) in J(row).  Reports train/held-out coverage globally, per
stratum, and the fitted (a, b) tables (dumped to
h558_zoned_selector.json for blind use on other combs).
"""
import json
import sys
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h539_D_library import qrow

AS = list(range(-80, 9, 2))


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
        tau4 = (t4 * 4) / 2**s4
        XD12 = min(11, (rdisc * 12) >> rsh)
        mf = m / 2**64
        half = (m * 2654435761) & 1
        out.append(((dist, low3, ce, XD12), half, tau4, mf,
                    jlo, jhi))
    return out


def main():
    rows = []
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
    zones_train = defaultdict(list)
    zones_test = defaultdict(list)
    for part in parts:
        for key, half, tau4, mf, jlo, jhi in part:
            (zones_train if half == 0 else
             zones_test)[key].append((tau4, mf, jlo, jhi))
    fitted = {}
    for key, pts in zones_train.items():
        best = (0, None, None)
        for a in AS:
            iv = [(jlo - 0.5 - t4a - a * mf,
                   jhi + 0.5 - t4a - a * mf)
                  for t4a, mf, jlo, jhi in pts]
            c, b = stab(iv)
            if c > best[0]:
                best = (c, a, b)
        fitted[key] = best
    tr_ok = tr_n = te_ok = te_n = 0
    per_strat = defaultdict(lambda: [0, 0])
    for key, pts in zones_train.items():
        c, a, b = fitted[key]
        tr_ok += c
        tr_n += len(pts)
    for key, pts in zones_test.items():
        f2 = fitted.get(key)
        if f2 is None:
            continue
        _, a, b = f2
        if a is None:
            continue
        for tau4, mf, jlo, jhi in pts:
            jp = round(tau4 + a * mf + b)
            te_n += 1
            ok = jlo <= jp <= jhi
            if ok:
                te_ok += 1
            ps = per_strat[key[:3]]
            ps[1] += 1
            if ok:
                ps[0] += 1
    print(f"train coverage {tr_ok}/{tr_n} ({tr_ok/tr_n:.4f})")
    print(f"HELD-OUT coverage {te_ok}/{te_n} ({te_ok/te_n:.4f})")
    print("\nper-stratum held-out:")
    for s2 in sorted(per_strat):
        ok, n = per_strat[s2]
        print(f"  {s2}: {ok}/{n} ({ok/n:.4f})")
    dump = {str(kk): (a, b) for kk, (c, a, b) in fitted.items()
            if a is not None}
    with open("h558_zoned_selector.json", "w") as fh:
        json.dump(dump, fh)
    print("fitted tables -> h558_zoned_selector.json "
          f"({len(dump)} zones)")


if __name__ == "__main__":
    main()
