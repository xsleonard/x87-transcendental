#!/usr/bin/env python3
"""h563: is the zone-varying a*mf term a linearized SECOND TAIL?

h559's per-zone mf slopes swing -22..-80 — the signature of a
locally-linearized wrapped quantity, not a genuine m-dependence.
Candidate: the square's below-chop tail t2 (value-read at a fixed
absolute column, like t4 at ~63 per h560).  Models, zones
(stratum, XD12), split-half held-out, J-interval scoring:
  M0 baseline : j = round(x4 + a*mf + b)          (h558 form, q=4->x4)
  MA          : j = round(x4 + s*x2 + b)          s per zone
  MB          : j = round(x4 + s*x2 + a*mf + b)   does mf survive x2?
x4 = t4 * 2^(65-s4) / rfv  (ladder units, column 63)
x2 = t2 * 2^(c2-s2+2) / rfv, c2 gridded via scale s = +-2^k.
If MA >= M0 with s stable across zones, the mf term was t2 all
along and the selector is two raw tail addends.
"""
import sys
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h539_D_library import qrow


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
        sq_full = m * m
        s2 = sq_full.bit_length() - 67
        t2 = sq_full & ((1 << s2) - 1)
        x2 = t2 * 2.0**(65 - s2) / rfv
        XD12 = min(11, (rdisc * 12) >> rsh)
        mf = m / 2**64
        half = (m * 2654435761) & 1
        out.append(((dist, low3, ce, XD12), half, x4, x2, mf,
                    jlo, jhi, theta))
    return out


SG = [s * 2.0**k for k in range(-4, 4) for s in (1, -1)]
AG = list(range(-80, 9, 4))


def fit_eval(tr, te, argf, grid, tag):
    fitted = {}
    for key, pts in tr.items():
        best = (0, None, None)
        for p in grid:
            iv = []
            for r in pts:
                x = argf(r, p)
                iv.append((r[4] - 0.5 - x, r[5] + 0.5 - x))
            c, b = stab(iv)
            if c > best[0]:
                best = (c, p, b)
        fitted[key] = best
    ok = n = 0
    per_strat = defaultdict(lambda: [0, 0])
    for key, pts in te.items():
        f2 = fitted.get(key)
        if f2 is None or f2[1] is None:
            continue
        _, p, b = f2
        for r in pts:
            jp = round(argf(r, p) + b)
            good = r[4] <= jp <= r[5]
            n += 1
            ps = per_strat[key[:3]]
            ps[1] += 1
            if good:
                ok += 1
                ps[0] += 1
    print(f"\n{tag}: HELD-OUT {ok}/{n} ({ok/n:.4f})", flush=True)
    for s2 in sorted(per_strat):
        o2, n2 = per_strat[s2]
        print(f"  {s2}: {o2/n2:.4f} ({n2})")
    return fitted


def main():
    rows_l = []
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
    tr = defaultdict(list)
    te = defaultdict(list)
    for part in parts:
        for key, half, x4, x2, mf, jlo, jhi, theta in part:
            r = (key, x4, x2, mf, jlo, jhi, theta)
            # r indices: 1=x4 2=x2 3=mf 4=jlo 5=jhi
            (tr if half == 0 else te)[key].append(
                (key, x4, x2, mf, jlo, jhi))
    fit_eval(tr, te, lambda r, p: r[1] + p * r[3], AG, "M0_mf")
    fa = fit_eval(tr, te, lambda r, p: r[1] + p * r[2], SG, "MA_t2")
    from collections import Counter
    cnt = Counter(v[1] for v in fa.values() if v[1] is not None)
    print("  MA s-coefficient distribution:",
          cnt.most_common(10))
    fit_eval(tr, te,
             lambda r, p: r[1] + p[0] * r[2] + p[1] * r[3],
             [(s, a) for s in SG for a in range(-60, 9, 10)],
             "MB_t2_mf")


if __name__ == "__main__":
    main()
