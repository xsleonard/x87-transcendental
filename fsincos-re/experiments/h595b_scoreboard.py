#!/usr/bin/env python3
"""h595b: THE CLEAN SCOREBOARD — per (stratum, side), held-out
predictability of the EU-anchored fire bit on observable rows,
frame-free (no fitted threshold laws):
  A: (theta, V12)              V12 = Vlow >> (kf-12)  [value]
  B: (theta, V12, SUM6)        + resolved-sum word state
  C: ceiling of B's key (in-sample majority)
Split-half by m-hash; unseen key -> train majority class.
"""
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h577_three_term import qrow3
from h588_select import split_words

MODES = ROUNDING_MODES


def work(rows):
    out = []
    for mhex, hw, R, ce, theta in rows:
        (m, R2, A, P, B_full, rsh, rdisc, lsh, ldisc, s4, t4,
         bshift, k, dist, low3) = qrow3(mhex)
        F = rsh - bshift
        if F < 0:
            continue
        kf = k + F
        APf = (A + P) << F
        EU = (APf - B_full) >> kf
        side = "up" if theta <= 0 else "dn"
        za, zb = (0, 1) if side == "up" else (-1, 0)
        ra = [final_cosine_result(-(EU + za), ce, md)
              for md in MODES]
        rb = [final_cosine_result(-(EU + zb), ce, md)
              for md in MODES]
        if ra == rb:
            continue  # blind
        if side == "up":
            fire = 1 if hw == rb else (0 if hw == ra else -1)
        else:
            fire = 1 if hw == ra else (0 if hw == rb else -1)
        if fire < 0:
            continue
        Vlow = (APf - B_full) - (EU << kf)
        v12 = Vlow >> (kf - 12)
        qsq = None
        # word state: B tree resolved-sum 6-bit window
        f4v = None
        out.append((mhex, dist, low3, ce, side, theta, fire,
                    v12, rsh))
    return out


def word_state(args):
    mhex, rsh = args
    import h539_D_library as DL
    qr = DL.qrow(mhex)
    f4v, rfv = qr[2], qr[3]
    S, C = split_words(f4v, rfv)
    sh = rsh - 59
    return ((S + C) >> max(sh, 0)) & 63


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
          for md in MODES}
    jobs = []
    for f in raw:
        R, ce, theta = int(f[7], 16), int(f[8]), int(f[9])
        i = order[f[0]]
        hw, bad = [], False
        for md in MODES:
            t = st[md][i].split()
            if t[0] != "OK":
                bad = True
                break
            hw.append(int(t[2], 16))
        if bad:
            continue
        jobs.append((f[0], hw, R, ce, theta))
    print(f"rows: {len(jobs)}", flush=True)
    nw = 14
    chunks = [jobs[i::nw * 4] for i in range(nw * 4)]
    recs = []
    with Pool(nw) as pool:
        for part in pool.imap_unordered(work, chunks):
            recs.extend(part)
        print(f"observable rows: {len(recs)}", flush=True)
        sts = pool.map(word_state,
                       [(r[0], r[8]) for r in recs],
                       chunksize=1000)
    by = defaultdict(list)
    for (mhex, dist, low3, ce, side, theta, fire, v12,
         rsh), st3 in zip(recs, sts):
        half = (int(mhex, 16) * 2654435761) & 1
        by[(dist, low3, ce, side)].append(
            (half, theta, fire, v12, st3))
    print(f"\n{'stratum/side':22s} {'n_obs':>7s} {'base':>6s} "
          f"{'A:th+V12':>9s} {'B:+SUM6':>8s} {'ceilB':>7s}")
    tots = defaultdict(float)
    totn = 0
    for key in sorted(by):
        rows = by[key]
        n = len(rows)
        base = sum(r[2] for r in rows) / n
        accs = []
        for keyf in (lambda r: (r[1], r[3]),
                     lambda r: (r[1], r[3], r[4])):
            tab = defaultdict(lambda: [0, 0])
            gl = [0, 0]
            for r in rows:
                if r[0] == 0:
                    tab[keyf(r)][r[2]] += 1
                    gl[r[2]] += 1
            gmaj = 1 if gl[1] >= gl[0] else 0
            ok = nn = 0
            for r in rows:
                if r[0] != 1:
                    continue
                c = tab.get(keyf(r))
                pred = gmaj if c is None else \
                    (0 if c[0] >= c[1] else 1)
                ok += pred == r[2]
                nn += 1
            accs.append(ok / max(nn, 1))
        # ceiling of B key (in-sample, train half)
        tab = defaultdict(lambda: [0, 0])
        for r in rows:
            if r[0] == 0:
                tab[(r[1], r[3], r[4])][r[2]] += 1
        co = sum(max(c) for c in tab.values())
        cn = sum(sum(c) for c in tab.values())
        ceil = co / max(cn, 1)
        print(f"{str(key):22s} {n:7d} {base:6.3f} "
              f"{accs[0]:9.4f} {accs[1]:8.4f} {ceil:7.4f}")
        tots["A"] += accs[0] * n
        tots["B"] += accs[1] * n
        totn += n
    print(f"\nWEIGHTED TOTALS: A {tots['A'] / totn:.4f}  "
          f"B {tots['B'] / totn:.4f}  over {totn} observable "
          f"rows")


if __name__ == "__main__":
    main()
