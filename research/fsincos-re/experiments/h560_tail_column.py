#!/usr/bin/env python3
"""h560: pin the tail's column — selector smooth term = raw tail
value at absolute column c: D_tail = t4 * 2^(c - s4), i.e. in
rf/4-ladder units x = t4 * 2^(c-s4+2) / rfv (exact per row).
j = round(x + a*mf + b) per (stratum, XD12) zone, split-half.
Grid c in {61..66}; a, b per zone by stabbing.  q=3 in h559
corresponds to c=63 iff rf ~ 2/3 — a jump in held-out coverage at
one specific c identifies the physical column.
"""
import sys
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h539_D_library import qrow

AS = list(range(-40, 9, 2))
CS = [61, 62, 63, 64, 65, 66]


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
        # x(c) in ladder units; store x at c=63, scale by 2^(c-63)
        x63 = t4 * 2.0**(63 - s4 + 2) / rfv
        XD12 = min(11, (rdisc * 12) >> rsh)
        mf = m / 2**64
        half = (m * 2654435761) & 1
        out.append(((dist, low3, ce, XD12), half, x63, mf,
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
        for key, half, x63, mf, jlo, jhi in part:
            (zones_train if half == 0 else
             zones_test)[key].append((x63, mf, jlo, jhi))
    for c in CS:
        sc = 2.0**(c - 63)
        fitted = {}
        tr_ok = tr_n = 0
        for key, pts in zones_train.items():
            best = (0, None, None)
            for a in AS:
                iv = [(jlo - 0.5 - x63 * sc - a * mf,
                       jhi + 0.5 - x63 * sc - a * mf)
                      for x63, mf, jlo, jhi in pts]
                cnt, b = stab(iv)
                if cnt > best[0]:
                    best = (cnt, a, b)
            fitted[key] = best
            tr_ok += best[0]
            tr_n += len(pts)
        te_ok = te_n = 0
        for key, pts in zones_test.items():
            f2 = fitted.get(key)
            if f2 is None or f2[1] is None:
                continue
            _, a, b = f2
            for x63, mf, jlo, jhi in pts:
                jp = round(x63 * sc + a * mf + b)
                te_n += 1
                if jlo <= jp <= jhi:
                    te_ok += 1
        print(f"c={c}: train {tr_ok/tr_n:.4f}  "
              f"HELD-OUT {te_ok/te_n:.4f}")


if __name__ == "__main__":
    main()
