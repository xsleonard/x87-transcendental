#!/usr/bin/env python3
"""h584: ARCHITECTURE-CONSTRAINED tree search for the
participation bits.

Word-level CSA is input-symmetric -> the (S,C) split depends only
on the GROUPING TREE.  Enumerate the Tan/Lemonds/Schulte-shaped
space instead of free permutations:
  roles: (mcand, mplier) = (f4, rf) | (rf, f4)
  chunk width w in {27, 32} (3 passes 27/27/13 | 2 passes 32/32)
  chunk order: low-first (Fig 6)
  hot-ones: sep-row | next-row-merged | dropped-below-seam
  level-1 grouping of [pp0..pp13, fbS, fbC]:
    Gnat  = {0-3}{4-7}{8-11}{12,13,fb,fb}   (natural)
    Gfb1  = {fb,fb,0,1}{2-5}{6-9}{10-13}    (feedback first)
    Gspl  = {0-3}{4-7}{8-11,fbS}{12,13,fbC} (split feedback)
  level-2 pairing: (12)(34) | (13)(24) | (14)(23)
  4:2 = csa(csa(a,b,c), d) at word level.
Per pass the low w columns retire (exact value recorded); final
split bits read at product column rsh (absolute) from the last
pass's (S, C) window.  Objective: 4-threshold margin model
(h582), split-half held-out, targets (9,1/2,-72)up +
(8,5/6,-73)dn.
"""
import sys
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h577_three_term import qrow3
from h534_bitlevel_seam import csa, WIDTH, MASK
from h578_margin_chunks import HARD_T
import h539_D_library as DL

TARGETS = [((9, 1, -72), "up"), ((9, 2, -72), "up"),
           ((8, 5, -73), "dn"), ((8, 6, -73), "dn")]


def booth_rows(x, y, w0, hot):
    """radix-4 Booth rows of x*y (y width w0 bits + overlap 0),
    hardware encoding; returns list of rows (ints); hot
    conventions: 'sep' separate rows, 'next' merged into next
    row, 'drop' hot-ones below column 27 dropped."""
    rows = []
    pend_hot = 0
    y2 = y << 1
    nb = y2.bit_length()
    for i in range(0, max(nb, 1), 2):
        trip = (y2 >> i) & 7
        d = {0: 0, 1: 1, 2: 1, 3: 2, 4: -2, 5: -1, 6: -1,
             7: 0}[trip]
        row = 0
        if d > 0:
            row = (d * x << i) & MASK
        elif d < 0:
            row = ((((~((-d) * x)) & MASK) << i) & MASK)
        if hot == "next":
            row |= pend_hot
            pend_hot = (1 << i) if d < 0 else 0
        elif d < 0:
            if hot == "sep":
                rows.append(1 << i)
            elif hot == "drop" and i >= 27:
                rows.append(1 << i)
            # hot == 'drop' and i < 27: lost
        rows.append(row)
    if hot == "next" and pend_hot:
        rows.append(pend_hot)
    while len(rows) < 14:
        rows.append(0)
    return rows[:16]


def c42(a, b, c, d):
    s1, c1 = csa(a, b, c, MASK)
    return csa(s1, c1, d, MASK)


def reduce_tree(items, grouping, pairing):
    it = items + [0] * (16 - len(items))
    gs = []
    for grp in grouping:
        vals = [it[i] for i in grp]
        while len(vals) < 4:
            vals.append(0)
        gs.append(c42(*vals[:4]))
    (i1, i2), (i3, i4) = pairing
    l2a = c42(gs[i1][0], gs[i1][1], gs[i2][0], gs[i2][1])
    l2b = c42(gs[i3][0], gs[i3][1], gs[i4][0], gs[i4][1])
    S, C = c42(l2a[0], l2a[1], l2b[0], l2b[1])
    return S, C


GROUPINGS = {
    "nat": [[0, 1, 2, 3], [4, 5, 6, 7], [8, 9, 10, 11],
            [12, 13, 14, 15]],
    "fb1": [[14, 15, 0, 1], [2, 3, 4, 5], [6, 7, 8, 9],
            [10, 11, 12, 13]],
    "spl": [[0, 1, 2, 3], [4, 5, 6, 7], [8, 9, 10, 14],
            [11, 12, 13, 15]],
}
PAIRINGS = {"12_34": ((0, 1), (2, 3)),
            "13_24": ((0, 2), (1, 3)),
            "14_23": ((0, 3), (1, 2))}


def split_state(f4v, rfv, rsh, cfg):
    role, w, hot, gname, pname = cfg
    mcand, mplier = (f4v, rfv) if role == "fr" else (rfv, f4v)
    nb = mplier.bit_length()
    S = C = 0
    col0 = 0  # absolute column of current window base
    pos = 0
    while pos < nb:
        chunk = (mplier >> pos) & ((1 << w) - 1)
        rows = booth_rows(mcand, chunk, w, hot)
        items = rows[:14] + [S, C]
        S, C = reduce_tree(items, GROUPINGS[gname],
                           PAIRINGS[pname])
        pos += w
        if pos < nb:
            # retire low w columns; feedback shifts down
            S >>= w
            C >>= w
            col0 += w
    cs = rsh - col0
    if cs < 0:
        cs = 0
    return ((S >> cs) & 1, (C >> (cs + 1)) & 1)


ROWS = None


def init_rows(r):
    global ROWS
    ROWS = r


def eval_cfg(args):
    key, cfg = args
    tr, te = ROWS[key]
    def classify(rows):
        by = defaultdict(list)
        for mb, fire, f4v, rfv, rsh in rows:
            st = split_state(f4v, rfv, rsh, cfg)
            by[st].append((mb, fire))
        return by
    bytr = classify(tr)
    ths = {}
    for st2, pts in bytr.items():
        pts.sort()
        cands = sorted(set(mb for mb, _ in pts))
        cands.append(cands[-1] + 1)
        best = (-1, 0)
        for t in cands:
            acc = sum(1 for mb, f in pts
                      if (1 if mb >= t else 0) == f)
            if acc > best[0]:
                best = (acc, t)
        ths[st2] = best[1]
    okte = 0
    byte = classify(te)
    for st2, pts in byte.items():
        t = ths.get(st2, 0)
        okte += sum(1 for mb, f in pts
                    if (1 if mb >= t else 0) == f)
    return key, cfg, okte, len(te)


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
        if side == "up":
            marg = Vlow - ((1 << kf) - T)
            fire = 1 if req2 == 1 else 0
        else:
            marg = T - 1 - Vlow
            fire = 1 if req2 == -1 else 0
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
    cfgs = []
    for role in ("fr", "rf"):
        for w in (27, 32):
            for hot in ("sep", "next", "drop"):
                for g in GROUPINGS:
                    for p in PAIRINGS:
                        cfgs.append((role, w, hot, g, p))
    jobs = [(key, cfg) for key in rowsd for cfg in cfgs]
    print(f"configs: {len(cfgs)}, jobs: {len(jobs)}", flush=True)
    with Pool(8, initializer=init_rows,
              initargs=(rowsd,)) as pool:
        results = pool.map(eval_cfg, jobs)
    best_by = defaultdict(list)
    for key, cfg, okte, nte in results:
        best_by[key].append((okte / max(nte, 1), cfg))
    for key in sorted(best_by):
        rr = sorted(best_by[key], reverse=True)
        print(f"\n{key}:")
        for acc, cfg in rr[:5]:
            print(f"  {acc:.4f}  {cfg}")


if __name__ == "__main__":
    main()
