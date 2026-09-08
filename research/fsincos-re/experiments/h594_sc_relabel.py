#!/usr/bin/env python3
"""h594: EU-ANCHORED RELABEL OF THE PAIRED LANE + clean-label
redo of the lead (b) analyses.

Labels: Z = {z in [-2, 3] : hw_sc == refs(EU+z)} (3-mode
vectors).  exact-z rows: |Z| = 1.  Class-level (up-dev vs not):
all z in Z agree on [z >= 1].  fc labels from the clean cache
(h592_band.tsv).

  A. sc observability census; req2_sc (= z) census by
     (stratum, theta) — the two-sidedness question in clean
     coordinates (standalone up side never has z = -1).
  B. Word-state predictability of sc_fire (z >= 1, class-level
     observable rows): margin-only vs (key, SUM6) threshold
     models, split-half held-out.  [Redo of h590's 0.745.]
  C. sc window census (key, S_w, C_w) at w in {8, 10, 12}:
     ceiling + held-out for sc_fire.
  D. fc x sc within-(key, mb, SUM6)-cell association, BOTH
     lanes clean-labeled — the shared-vs-schedule-generated
     residual test with real power.
"""
import math
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h577_three_term import qrow3
from h588_select import fit_thr, split_words, m3_state, TARGETS

MODES = ROUNDING_MODES


def row_work(args):
    mhex, f4v, rfv, rsh, hw_sc = args
    (m, R, A, P, B_full, rsh2, rd, lsh, ld, s4, t4, bsh, k,
     dist, low3) = qrow3(mhex)
    F = rsh2 - bsh
    kf = k + F
    APf = (A + P) << F
    EU = (APf - B_full) >> kf
    Z = []
    for z in range(-2, 4):
        refs = [final_cosine_result(-(EU + z), -72, md)
                for md in MODES]
        if hw_sc == refs:
            Z.append(z)
    S, C = split_words(f4v, rfv)
    sh = rsh - 59
    st3 = ((S + C) >> sh) & 63
    fb = kf - 54
    wins = tuple(((S >> (fb - w)) & ((1 << w) - 1),
                  (C >> (fb - w)) & ((1 << w) - 1))
                 for w in (8, 10, 12))
    return tuple(Z), st3, wins


def held_out_thr(rows, keyf):
    tr = defaultdict(list)
    gl = defaultdict(int)
    for r in rows:
        if r[0] == 0:
            tr[keyf(r)].append((r[1], r[2]))
            gl[r[2]] += 1
    ths = {k: fit_thr(p) for k, p in tr.items()}
    gmaj = 1 if gl[1] >= gl[0] else 0
    ok = n = 0
    for r in rows:
        if r[0] != 1:
            continue
        t = ths.get(keyf(r))
        pred = gmaj if t is None else (1 if r[1] >= t else 0)
        ok += pred == r[2]
        n += 1
    return ok / max(n, 1), n


def main():
    cache = {}
    for line in open("h592_band.tsv"):
        f = line.split()
        key = ((int(f[1]), int(f[2]), int(f[3])), f[4])
        if key not in dict.fromkeys(TARGETS):
            continue
        cache[f[0]] = (key, int(f[5]), int(f[6]),
                       int(f[7], 16), int(f[8], 16), int(f[9]))
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
    sc = {md: open(f"comb7_sc_{md}_status.txt").read()
          .splitlines() for md in MODES}
    jobs = []
    meta = {}
    for f in raw:
        mhex = f[0]
        if mhex not in cache:
            continue
        i = order[mhex]
        hw, bad = [], False
        for md in MODES:
            t = sc[md][i].split()
            if t[0] != "OK":
                bad = True
                break
            hw.append(int(t[4], 16))
        if bad:
            continue
        key, mb, fire, f4v, rfv, rsh = cache[mhex]
        jobs.append((mhex, f4v, rfv, rsh, hw))
        meta[mhex] = (key, mb, fire, int(f[9]))
    print(f"clean-fc rows with sc capture: {len(jobs)}",
          flush=True)
    with Pool(15) as pool:
        res = pool.map(row_work, jobs, chunksize=300)
    rows = []
    zcen = defaultdict(int)
    obs_exact = obs_class = 0
    for (mhex, f4v, rfv, rsh, hw), (Z, st3, wins) in \
            zip(jobs, res):
        key, mb, fire, theta = meta[mhex]
        half = (int(mhex, 16) * 2654435761) & 1
        if len(Z) == 0:
            zcen["nomatch"] += 1
            continue
        exact = len(Z) == 1
        cls = set(1 if z >= 1 else 0 for z in Z)
        clsok = len(cls) == 1
        if exact:
            obs_exact += 1
            zcen[(key[0], theta, Z[0])] += 1
        if clsok:
            obs_class += 1
            rows.append((half, mb, cls.pop(), key, st3, wins,
                         fire, theta, Z[0] if exact else None))
    print(f"exact-z rows: {obs_exact}, class-observable: "
          f"{obs_class}, nomatch: {zcen.pop('nomatch', 0)}")

    print("\nA. req2_sc (z) census by (stratum, theta) "
          "[exact-z rows]:")
    strata = sorted(set(k[0] for k in zcen))
    for st in strata:
        for th in (0, -1, -2):
            zs = {z: zcen.get((st, th, z), 0)
                  for z in range(-2, 4)}
            n = sum(zs.values())
            if not n:
                continue
            print(f"  {st} theta={th}: n={n} " +
                  " ".join(f"z{z:+d}:{c}" for z, c in
                           sorted(zs.items()) if c))

    print("\nB. sc_fire (z>=1) held-out "
          "[class-observable rows]:")
    base = sum(r[2] for r in rows) / len(rows)
    print(f"  base rate {base:.4f}")
    for name, keyf in (
            ("margin-only (key)", lambda r: r[3]),
            ("key+SUM6", lambda r: (r[3], r[4]))):
        acc, n = held_out_thr(rows, keyf)
        print(f"  {name:20s}: {acc:.4f} (n={n})")

    print("\nC. sc window census (class-observable rows):")
    print(f"{'w':>4s} {'groups':>7s} {'ceil':>7s} "
          f"{'heldout':>8s} {'unseen':>7s}")
    for wi, w in enumerate((8, 10, 12)):
        gtr = defaultdict(lambda: [0, 0])
        te = []
        for half, mb, scf, key, st3, wins, fire, theta, z \
                in rows:
            gk = (key,) + wins[wi]
            if half == 0:
                gtr[gk][scf] += 1
            else:
                te.append((gk, scf))
        ceil_ok = sum(max(c) for c in gtr.values())
        ceil_n = sum(sum(c) for c in gtr.values())
        gmaj = 1 if sum(c[1] for c in gtr.values()) >= \
            sum(c[0] for c in gtr.values()) else 0
        ho = unseen = 0
        for gk, scf in te:
            c = gtr.get(gk)
            if c is None:
                pred = gmaj
                unseen += 1
            else:
                pred = 0 if c[0] >= c[1] else 1
            ho += pred == scf
        print(f"{w:4d} {len(gtr):7d} "
              f"{ceil_ok / max(ceil_n, 1):7.4f} "
              f"{ho / max(len(te), 1):8.4f} {unseen:7d}",
              flush=True)

    print("\nD. fc x sc within-(key, mb, SUM6) association "
          "(both lanes clean):")
    cells = defaultdict(list)
    for half, mb, scf, key, st3, wins, fire, theta, z in rows:
        cells[(key, mb, st3)].append((fire, scf))
    num = den = 0.0
    nrows = ncells = 0
    tot11 = exp11 = 0.0
    for cell, pts in cells.items():
        n = len(pts)
        if n < 3:
            continue
        pf = sum(p[0] for p in pts) / n
        ps = sum(p[1] for p in pts) / n
        if pf in (0.0, 1.0) or ps in (0.0, 1.0):
            continue
        ncells += 1
        nrows += n
        for fc, scf in pts:
            num += (fc - pf) * (scf - ps)
            den += pf * (1 - pf) * ps * (1 - ps)
            if fc and scf:
                tot11 += 1
            exp11 += pf * ps
    z = num / den ** 0.5 if den > 0 else 0.0
    print(f"  informative cells: {ncells}, rows: {nrows}")
    print(f"  pooled residual covariance z = {z:+.2f}")


if __name__ == "__main__":
    main()
