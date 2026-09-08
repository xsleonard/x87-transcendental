#!/usr/bin/env python3
"""h552: held-out validation of g = g(XT, mf, stratum) + residual
structure of the forced j against the base map round(4*tau)-4.

Split rows by parity of a hash; learn per-cell j (any member of the
train intersection, take its midpoint) on train; score held-out
membership j* in J(row).  Also: for cells whose TRAIN intersection
is a single j, record delta = j - (round(4*XT*4)/4...) base and
cross-tab delta vs mf per stratum.
"""
import sys
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h539_D_library import qrow


def work(rows):
    train = {}
    test = []
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
        for j in range(-8, 9):
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
        xtb = (t4 << 8) >> s4
        mfb = m >> 53
        key = (xtb, mfb, dist, low3, ce)
        qr = ((t4 << 2) + (1 << (s4 - 1))) >> s4    # round(4 tau)
        half = (m * 2654435761) & 1
        if half == 0:
            cell = train.get(key)
            if cell is None:
                train[key] = [jlo, jhi]
            else:
                if jlo > cell[0]:
                    cell[0] = jlo
                if jhi < cell[1]:
                    cell[1] = jhi
        else:
            test.append((key, jlo, jhi, qr, dist, low3, ce,
                         xtb, mfb))
    return train, test


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
    train = {}
    test = []
    for tr, te in parts:
        for key, (lo, hi) in tr.items():
            cell = train.get(key)
            if cell is None:
                train[key] = [lo, hi]
            else:
                if lo > cell[0]:
                    cell[0] = lo
                if hi < cell[1]:
                    cell[1] = hi
        test.extend(te)
    # learned j* per feasible train cell = midpoint of interval
    jstar = {}
    for key, (lo, hi) in train.items():
        if lo <= hi:
            jstar[key] = (lo + hi) // 2
    nh = nmiss = nnocell = 0
    delta_tab = defaultdict(int)
    for key, jlo, jhi, qr, dist, low3, ce, xtb, mfb in test:
        js = jstar.get(key)
        if js is None:
            nnocell += 1
            continue
        nh += 1
        if not (jlo <= js <= jhi):
            nmiss += 1
        # residual structure where train pinned tightly
        lo, hi = train[key]
        if lo == hi:
            delta_tab[(dist, low3, ce, lo - (qr - 4))] += 1
    print(f"held-out rows with a trained cell: {nh}, member "
          f"{(nh-nmiss)}/{nh} ({(nh-nmiss)/nh:.4f}), "
          f"no-cell {nnocell}")
    print("\ndelta = j_forced - (round(4tau)-4) census by stratum:")
    strata = sorted(set(kk[:3] for kk in delta_tab))
    for s2 in strata:
        ds = {kk[3]: v for kk, v in delta_tab.items()
              if kk[:3] == s2}
        tot = sum(ds.values())
        if tot < 50:
            continue
        line = " ".join(f"{d}:{ds[d]}" for d in sorted(ds))
        print(f"  {s2} (n={tot}): {line}")


if __name__ == "__main__":
    main()
