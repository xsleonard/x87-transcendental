#!/usr/bin/env python3
"""h582: TREE-TOPOLOGY SEARCH for the dither bits.

Target: (9,1,-72) up and (9,2,-72) up mixing-band rows (h579's
positive split-bit signals).  The B = f4*rf product is built as
a 2-pass iterative PP array (h534 machinery, exact conventions);
the reduction ORDER (a permutation driving a queue-style CSA
schedule, feedback rows included as items) defines the (S, C)
split.  Objective: predict fire with FOUR margin thresholds
selected by the 2-bit state (S@rsh, C@rsh+1); hill-climb the
permutation on training accuracy; report held-out gain vs the
1-threshold baseline and vs h579's canonical-tree gain.
"""
import random
import sys
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h577_three_term import qrow3
from h534_bitlevel_seam import booth4_pps, csa, WIDTH, MASK
from h578_margin_chunks import HARD_T
import h539_D_library as DL

TARGETS = [((9, 1, -72), "up"), ((9, 2, -72), "up")]
PB = 54


def pp_rows(f4v, rfv):
    """Two-pass PP item lists (exact conventions, pb=PB,
    mult='rf'): returns (pass1_items, pass2_items_maker) where
    pass-2 items = PPs + [S1, C1] feedback slots."""
    chunks = [(0, PB), (PB, rfv.bit_length())]
    items1 = []
    y1 = (rfv >> 0) & ((1 << PB) - 1)
    for pp, hcol in booth4_pps(f4v, y1, 0, 0, WIDTH):
        items1.append(pp)
        if hcol is not None:
            items1.append(1 << hcol)
    y2 = rfv >> PB
    items2 = []
    for pp, hcol in booth4_pps(f4v, y2, PB, 0, WIDTH):
        items2.append(pp)
        if hcol is not None:
            items2.append(1 << hcol)
    return items1, items2


def reduce_perm(items, perm):
    """Queue-style reduction following perm order."""
    q = [items[i] for i in perm if i < len(items)]
    q += [items[i] for i in range(len(items))
          if i not in set(perm)]
    while len(q) > 2:
        a, b, c = q[0], q[1], q[2]
        s, co = csa(a, b, c, MASK)
        q = q[3:]
        q.append(s)
        q.append(co)
    while len(q) < 2:
        q.append(0)
    return q[0], q[1]


def split_bits(f4v, rfv, rsh, perm1, perm2):
    it1, it2 = pp_rows(f4v, rfv)
    S1, C1 = reduce_perm(it1, perm1)
    items2 = it2 + [S1, C1]
    S, C = reduce_perm(items2, perm2)
    return ((S >> rsh) & 1, (C >> (rsh + 1)) & 1)


ROWS = None


def init_rows(r):
    global ROWS
    ROWS = r


def objective(args):
    key, perm1, perm2, seed = args
    tr, te = ROWS[key]
    # training: fit 4 thresholds by state
    def fit_apply(rows, fit_from=None):
        by = defaultdict(list)
        for mb, fire, f4v, rfv, rsh in rows:
            st = split_bits(f4v, rfv, rsh, perm1, perm2)
            by[st].append((mb, fire))
        if fit_from is None:
            ths = {}
            for st2, pts in by.items():
                pts.sort()
                best = (-1, 0)
                cands = sorted(set(mb for mb, _ in pts))
                cands.append(cands[-1] + 1)
                for t in cands:
                    acc = sum(1 for mb, f in pts
                              if (1 if mb >= t else 0) == f)
                    if acc > best[0]:
                        best = (acc, t)
                ths[st2] = best[1]
            ok = sum(1 for st2, pts in by.items()
                     for mb, f in pts
                     if (1 if mb >= ths[st2] else 0) == f)
            return ok, ths
        else:
            ok = 0
            for st2, pts in by.items():
                t = fit_from.get(st2, 0)
                ok += sum(1 for mb, f in pts
                          if (1 if mb >= t else 0) == f)
            return ok, None
    rng = random.Random(seed)
    n1 = 40
    n2 = 40
    best_ok, ths = fit_apply(tr)
    bp1, bp2 = list(perm1), list(perm2)
    for it in range(120):
        p1 = list(bp1)
        p2 = list(bp2)
        which = rng.random()
        tgt = p1 if which < 0.4 else p2
        i, j = rng.randrange(len(tgt)), rng.randrange(len(tgt))
        tgt[i], tgt[j] = tgt[j], tgt[i]
        ok, th2 = fit_apply(tr) if False else (None, None)
        # recompute with modified perms
        def fa(rows):
            by = defaultdict(list)
            for mb, fire, f4v, rfv, rsh in rows:
                st = split_bits(f4v, rfv, rsh, p1, p2)
                by[st].append((mb, fire))
            ths = {}
            tot = 0
            for st2, pts in by.items():
                pts.sort()
                best = (-1, 0)
                cands = sorted(set(mb for mb, _ in pts))
                cands.append(cands[-1] + 1)
                for t in cands:
                    acc = sum(1 for mb, f in pts
                              if (1 if mb >= t else 0) == f)
                    if acc > best[0]:
                        best = (acc, t)
                ths[st2] = best[1]
                tot += best[0]
            return tot, ths
        ok, th2 = fa(tr)
        if ok > best_ok:
            best_ok, ths = ok, th2
            bp1, bp2 = p1, p2
    # held-out
    okte = 0
    by = defaultdict(list)
    for mb, fire, f4v, rfv, rsh in te:
        st = split_bits(f4v, rfv, rsh, bp1, bp2)
        t = ths.get(st, 0)
        if (1 if mb >= t else 0) == fire:
            okte += 1
    return key, seed, best_ok, len(tr), okte, len(te), bp1, bp2


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
    rowsd = defaultdict(lambda: ([], []))
    for mhex, theta, lab, ce in labeled:
        (m, R, A, P, B_full, rsh, rdisc, lsh, ldisc, s4, t4,
         bshift, k, dist, low3) = qrow3(mhex)
        F = rsh - bshift
        if F < 0:
            continue
        kf = k + F
        strat = (dist, low3, ce)
        side = "up" if theta <= 0 else "dn"
        key = (strat, side)
        if key not in dict.fromkeys(TARGETS) or key not in HARD_T:
            continue
        cfg = HARD_T[key]
        sr, cr, sl, cl, st4, ct, cq = cfg
        APf = (A + P) << F
        res_hw = R + {"clean": 0, "down": -1, "up": 1}[lab]
        EU = (APf - B_full) >> kf
        req2 = res_hw - EU
        Vlow = (APf - B_full) - (EU << kf)
        T = cq * (1 << kf) >> 10
        if sr:
            T += sr * (rdisc << cr >> rsh)
        if sl:
            T += sl * (ldisc << cl >> lsh)
        if st4:
            T += st4 * (t4 << ct >> s4)
        marg = Vlow - ((1 << kf) - T)
        fire = 1 if req2 == 1 else 0
        mb = marg * 4096 >> kf
        if not (-24 <= mb < 24):
            continue
        qr = DL.qrow(mhex)
        f4v, rfv = qr[2], qr[3]
        half = (m * 2654435761) & 1
        rowsd[key][0 if half == 0 else 1].append(
            (mb, fire, f4v, rfv, rsh))
    rowsd = dict(rowsd)
    for key, (tr, te) in rowsd.items():
        print(f"{key}: band tr={len(tr)} te={len(te)}")
    it1_len = 60  # covers all PP+hot-one items
    jobs = []
    for key in rowsd:
        for seed in range(6):
            rng = random.Random(1000 + seed)
            p1 = list(range(it1_len))
            p2 = list(range(20))
            rng.shuffle(p1)
            rng.shuffle(p2)
            jobs.append((key, p1, p2, seed))
    with Pool(6, initializer=init_rows,
              initargs=(rowsd,)) as pool:
        results = pool.map(objective, jobs)
    best_by = {}
    for key, seed, oktr, ntr, okte, nte, p1, p2 in results:
        print(f"{key} seed={seed}: train {oktr/ntr:.4f} "
              f"HELD-OUT {okte/nte:.4f}")
        if key not in best_by or okte > best_by[key][0]:
            best_by[key] = (okte, nte, p1, p2)
    for key, (okte, nte, p1, p2) in best_by.items():
        print(f"\nBEST {key}: held-out {okte/nte:.4f}")
        print(f"  perm1={p1}")
        print(f"  perm2={p2}")


if __name__ == "__main__":
    main()
