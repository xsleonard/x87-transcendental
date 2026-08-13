#!/usr/bin/env python3
"""h573: EXACT-D vs ROUNDED-SELECTOR — the first mechanism-level
discriminator after the side-split reframe.

Hypothesis family (addend-wiring): the terminal's deviation from
unchopped-exact is EXACT VALUE ARITHMETIC
    D = s1 * t4 * 2^(c4 - s4)  [+ s2 * rdisc * 2^(cd - rsh)]
        + offset(zone)
(raw tails consumed as addend rows at fixed absolute columns),
versus the h559 selector where D = round(...) * rfv/4 (quantized
digit-selection).  Same per-(stratum, XD12) zone offsets, same
split-half protocol; both scored against the model-free D-brackets
(h538): row consistent iff dlo < D_model <= dhi, brackets in
rfv/4 ladder units.
Filters reported per config: EASY-side held-out (must approach
1.0), HARD-side held-out, and for the best configs the
per-stratum table + integer-snapped (quantized) offset comparison.
Easy side per h567: dn for (8,1),(9,1..4); up for the rest.
"""
import math
import sys
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h539_D_library import qrow

HIDDEN_UP = {(8, 1), (9, 1), (9, 2), (9, 3), (9, 4)}


def easy_side(dist, low3):
    return "dn" if (dist, low3) in HIDDEN_UP else "up"


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
        u = 4.0 / rfv
        dlo = (Vlow - ((req2 + 1) << kf)) * u
        dhi = (Vlow - (req2 << kf)) * u
        f4_full = sqv * sqv
        s4 = f4_full.bit_length() - 67
        t4f = t4 * u / 2.0**s4
        rdf = rdisc * u / 2.0**rsh
        XD12 = min(11, (rdisc * 12) >> rsh)
        mf = m / 2**64
        half = (m * 2654435761) & 1
        side = "up" if theta <= 0 else "dn"
        out.append(((dist, low3, ce), XD12, half, side,
                    t4f, rdf, mf, dlo, dhi))
    return out


CONFIGS = []
for s1 in (1, -1):
    for c4 in (61, 62, 63, 64, 65, 66):
        CONFIGS.append((s1, c4, 0, 0))
        for s2 in (1, -1):
            for cd in (61, 62, 63, 64, 65, 66):
                CONFIGS.append((s1, c4, s2, cd))
CONFIGS.append((0, 0, 0, 0))  # offset-only control


TR = TE = None


def init_data(tr, te):
    global TR, TE
    TR, TE = tr, te


def eval_config(cfg):
    tr, te = TR, TE
    s1, c4, s2, cd = cfg
    f4s = s1 * 2.0**c4
    rds = s2 * 2.0**cd
    fitted = {}
    for key, pts in tr.items():
        iv = []
        for t4f, rdf, mf, dlo, dhi in pts:
            base = f4s * t4f + rds * rdf
            iv.append((dlo - base, dhi - base))
        c, b = stab(iv)
        fitted[key] = b
    res = defaultdict(lambda: [0, 0, 0, 0])  # eok en hok hn
    resr = defaultdict(lambda: [0, 0, 0, 0])  # rounded variant
    for key, pts in te.items():
        b = fitted.get(key)
        if b is None:
            continue
        strat, XD12 = key
        es = easy_side(strat[0], strat[1])
        for side, plist in pts.items():
            for t4f, rdf, mf, dlo, dhi in plist:
                base = f4s * t4f + rds * rdf
                D = base + b
                okx = dlo < D <= dhi
                Dr = round(D)
                okr = dlo < Dr <= dhi
                idx = 0 if side == es else 2
                r = res[strat]
                rr = resr[strat]
                r[idx + 1] += 1
                rr[idx + 1] += 1
                if okx:
                    r[idx] += 1
                if okr:
                    rr[idx] += 1
    return cfg, dict(res), dict(resr)


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
    stride = int(sys.argv[1]) if len(sys.argv) > 1 else 8
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
    te = defaultdict(lambda: defaultdict(list))
    for part in parts:
        for strat, XD12, half, side, t4f, rdf, mf, dlo, dhi \
                in part:
            key = (strat, XD12)
            pt = (t4f, rdf, mf, dlo, dhi)
            if half == 0:
                tr[key].append(pt)
            else:
                te[key][side].append(pt)
    tr = dict(tr)
    te = {k: dict(v) for k, v in te.items()}
    with Pool(8, initializer=init_data,
              initargs=(tr, te)) as pool:
        results = pool.map(eval_config, CONFIGS)
    scored = []
    for cfg, res, resr in results:
        e_ok = sum(v[0] for v in res.values())
        e_n = sum(v[1] for v in res.values())
        h_ok = sum(v[2] for v in res.values())
        h_n = sum(v[3] for v in res.values())
        er_ok = sum(v[0] for v in resr.values())
        hr_ok = sum(v[2] for v in resr.values())
        if e_n and h_n:
            scored.append((e_ok / e_n, h_ok / h_n,
                           er_ok / e_n, hr_ok / h_n, cfg, res))
    scored.sort(reverse=True)
    print(f"\n{'config':22s} {'easyX':>7s} {'hardX':>7s} "
          f"{'easyR':>7s} {'hardR':>7s}")
    for ex, hx, er, hr, cfg, _ in scored[:20]:
        print(f"{str(cfg):22s} {ex:7.4f} {hx:7.4f} "
              f"{er:7.4f} {hr:7.4f}")
    print("\nper-stratum for best config", scored[0][4])
    for strat in sorted(scored[0][5]):
        eok, en, hok, hn = scored[0][5][strat]
        print(f"  {strat}: easy {eok}/{en} "
              f"({eok/max(en,1):.4f})  hard {hok}/{hn} "
              f"({hok/max(hn,1):.4f})")


if __name__ == "__main__":
    main()
