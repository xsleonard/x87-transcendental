#!/usr/bin/env python3
"""h579: do CS-SPLIT BITS explain the hard-side threshold dither?

Hard sides = exact value-threshold + bounded few-quarter offset
with ~2-bit statistics (h578 margin sigmoids, 0.75 plateaus).
Candidates for the offset bits, tested on mixing-band rows
(|margin| < 24 units of 2^(kf-12)):
  cheap:  R&1, left-retained&1, right-retained&1, payload&1,
          rsh&1, lsh&1, s4&1, kf parity of F, (rsh-lsh)&1
  tree:   h534 simulate_pair C-word bits at columns rsh-1, rsh,
          rsh+1 and pb boundary bits, for (pb, mult) in
          {(27, 'rf'), (27, 'f4'), (54, 'rf')}
Per (stratum-side, bit): fit TWO margin thresholds (bit=0/1) on
half A, score held-out half B; report accuracy gain over the
single-threshold baseline.  A real split-bit shows a stable
horizontal sigmoid shift and a positive held-out gain.
"""
import sys
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h577_three_term import qrow3
from h534_bitlevel_seam import simulate_pair
from h578_margin_chunks import HARD_T

TARGETS = [((8, 4, -73), "dn"), ((8, 5, -73), "dn"),
           ((8, 6, -73), "dn"), ((9, 1, -72), "up"),
           ((9, 2, -72), "up"), ((9, 4, -72), "up"),
           ((9, 5, -72), "up")]


def work(rows):
    out = []
    for mhex, theta, lab, ce in rows:
        (m, R, A, P, B_full, rsh, rdisc, lsh, ldisc, s4, t4,
         bshift, k, dist, low3) = qrow3(mhex)
        F = rsh - bshift
        if F < 0:
            continue
        kf = k + F
        APf = (A + P) << F
        res_hw = R + {"clean": 0, "down": -1, "up": 1}[lab]
        EU = (APf - B_full) >> kf
        req2 = res_hw - EU
        Vlow = (APf - B_full) - (EU << kf)
        strat = (dist, low3, ce)
        side = "up" if theta <= 0 else "dn"
        key = (strat, side)
        if key not in HARD_T or key not in dict.fromkeys(TARGETS):
            continue
        cfg = HARD_T[key]
        sr, cr, sl, cl, st, ct, cq = cfg
        T = cq * (1 << kf) >> 10
        if sr:
            T += sr * (rdisc << cr >> rsh)
        if sl:
            T += sl * (ldisc << cl >> lsh)
        if st:
            T += st * (t4 << ct >> s4)
        if side == "up":
            marg = Vlow - ((1 << kf) - T)
            fire = 1 if req2 == 1 else 0
        else:
            marg = T - 1 - Vlow
            fire = 1 if req2 == -1 else 0
        mb = marg * 4096 >> kf
        if not (-24 <= mb < 24):
            continue
        # cheap bits
        f4s = (m * m >> 64) * (m * m >> 64)  # unused; placeholder
        bits = {
            "R&1": R & 1,
            "A&1": (A >> (A.bit_length() - 67) & 1)
            if A.bit_length() >= 67 else 0,
            "pay&1": (low3 + 8 - dist) & 1,
            "rsh&1": rsh & 1,
            "lsh&1": lsh & 1,
            "s4&1": s4 & 1,
            "F&1": F & 1,
            "rl&1": (rsh - lsh) & 1,
        }
        # tree bits from simulate_pair (exact conventions)
        import h539_D_library as DL
        qr = DL.qrow(mhex)
        f4v, rfv = qr[2], qr[3]
        for pb, mult in ((27, "rf"), (27, "f4"), (54, "rf")):
            S, C, ret = simulate_pair(f4v, rfv, (pb, mult))
            for dc in (-1, 0, 1):
                col = rsh + dc
                if col >= 0:
                    bits[f"C{pb}{mult}@{dc}"] = (C >> col) & 1
            bits[f"S{pb}{mult}@0"] = (S >> rsh) & 1
        half = (m * 2654435761) & 1
        out.append((key, half, mb, fire, bits))
    return out


def best_thr(pts):
    if len(pts) < 50:
        return None
    # pts: (mb, fire); best single threshold on mb
    pts = sorted(pts)
    total_f = sum(f for _, f in pts)
    best = (total_f, -1000)  # predict all clean
    cur = 0  # fires below threshold if we predict fire above t
    n = len(pts)
    fires_below = 0
    cleans_below = 0
    i = 0
    prev = None
    accs = []
    fb = 0
    cb = 0
    for mb, f in pts:
        pass
    # simpler: candidate thresholds = unique mb
    ub = sorted(set(mb for mb, _ in pts))
    ub.append(ub[-1] + 1)
    from bisect import bisect_left
    arr = pts
    pre_f = [0]
    pre_n = [0]
    for mb, f in arr:
        pre_f.append(pre_f[-1] + f)
        pre_n.append(pre_n[-1] + 1)
    bestacc = -1
    bestt = None
    for t in ub:
        idx = bisect_left(arr, (t, -1))
        below_f = pre_f[idx]
        below_n = idx
        above_f = pre_f[-1] - below_f
        above_n = len(arr) - below_n
        acc = (below_n - below_f) + above_f
        if acc > bestacc:
            bestacc = acc
            bestt = t
    return bestt


def acc_thr(pts, t):
    ok = 0
    for mb, f in pts:
        pred = 1 if mb >= t else 0
        if pred == f:
            ok += 1
    return ok


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
    groups = defaultdict(lambda: ([], []))
    for part in parts:
        for key, half, mb, fire, bits in part:
            groups[key][0 if half == 0 else 1].append(
                (mb, fire, bits))
    for key in sorted(groups):
        tr, te = groups[key]
        if len(tr) < 1500:
            continue
        base_t = best_thr([(mb, f) for mb, f, _ in tr])
        base_ok = acc_thr([(mb, f) for mb, f, _ in te], base_t)
        n_te = len(te)
        print(f"\n{key}: band rows tr={len(tr)} te={n_te}  "
              f"baseline {base_ok/n_te:.4f} (t={base_t})")
        names = sorted(tr[0][2])
        gains = []
        for name in names:
            t0 = best_thr([(mb, f) for mb, f, b in tr
                           if b[name] == 0])
            t1 = best_thr([(mb, f) for mb, f, b in tr
                           if b[name] == 1])
            if t0 is None or t1 is None:
                continue
            ok = 0
            for mb, f, b in te:
                t = t1 if b[name] else t0
                pred = 1 if mb >= t else 0
                if pred == f:
                    ok += 1
            gains.append((ok - base_ok, name, t0, t1))
        gains.sort(reverse=True)
        for g, name, t0, t1 in gains[:6]:
            print(f"    {name:14s} gain {g:+5d} "
                  f"({g/n_te:+.4f})  t0={t0} t1={t1}")


if __name__ == "__main__":
    main()
