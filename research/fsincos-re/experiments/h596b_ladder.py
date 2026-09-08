#!/usr/bin/env python3
"""h596b: per-stratum machinery rerun on CLEAN labels (hard
list).  For each (stratum, side):
  1. margin frame: grid over three-term configs
     T = (rdisc<<cr>>rsh) + sl*(ldisc<<cl>>lsh)
         + st4*(t4<<ct>>s4)   (cq absorbed by threshold fits);
     HARD_T configs included as candidates; selected on train
     half A by best-single-threshold accuracy.
  2. word state: resolved-sum windows w in {4..7}, off in
     {-8..-2} (shift = rsh - 54 + off); read selected on an
     internal split A1->A2 with per-(theta, state) thresholds.
  3. FINAL (test half B): base, M1 (margin only), M3-default
     (w6 off-5), M3-best-read, table (theta, mb, state)
     majority, in-sample ceiling of the table key on B.
"""
import sys
from collections import defaultdict
from multiprocessing import Pool
from h578_margin_chunks import HARD_T
from h588_select import split_words

CRS = (61, 62, 63, 64, 65)
CLS = (60, 62, 63, 64, 67)
CTS = (61, 63, 65)


def build_configs(key):
    cfgs = []
    for cr in CRS:
        for sl, cl in [(0, 0)] + [(s, c) for s in (1, -1)
                                  for c in CLS]:
            for st4, ct in [(0, 0)] + [(s, c) for s in (1, -1)
                                       for c in CTS]:
                cfgs.append((1, cr, sl, cl, st4, ct, 0))
    ht = HARD_T.get(key)
    if ht and ht not in cfgs:
        cfgs.append(ht)
    return cfgs


ROWS = None


def init_rows(r):
    global ROWS
    ROWS = r


def margin_bins(cfg):
    sr, cr, sl, cl, st4, ct, cq = cfg
    out = []
    for r in ROWS:
        (half, theta, fire, rsh, lsh, kf, Vlow, rdisc, ldisc,
         t4, s4, side, st_all) = r
        T = cq * (1 << kf) >> 10
        if sr:
            T += sr * (rdisc << cr >> rsh)
        if sl:
            T += sl * (ldisc << cl >> lsh)
        if st4:
            T += st4 * (t4 << ct >> s4)
        marg = (Vlow - ((1 << kf) - T)) if side == "up" \
            else (T - 1 - Vlow)
        mb = marg * 4096 >> kf
        mb = max(-4096, min(4095, mb))
        out.append(mb)
    return out


def fit_thr_hist(hist):
    if not hist:
        return 0
    cands = sorted(hist)
    cands.append(cands[-1] + 1)
    best = (-1, 0)
    for t in cands:
        acc = sum((n1 if mb >= t else n0)
                  for mb, (n0, n1) in hist.items())
        if acc > best[0]:
            best = (acc, t)
    return best[1]


def eval_cfg_m1(cfg):
    mbs = margin_bins(cfg)
    hist = defaultdict(lambda: [0, 0])
    n = ok = 0
    for r, mb in zip(ROWS, mbs):
        if r[0] == 0:  # train half only
            hist[mb][r[2]] += 1
    t = fit_thr_hist(hist)
    for r, mb in zip(ROWS, mbs):
        if r[0] != 0:
            continue
        ok += (1 if mb >= t else 0) == r[2]
        n += 1
    return cfg, ok / max(n, 1)


def run_stratum(key, rows):
    global ROWS
    ROWS = rows
    cfgs = build_configs(key)
    with Pool(15, initializer=init_rows,
              initargs=(rows,)) as pool:
        res = pool.map(eval_cfg_m1, cfgs,
                       chunksize=max(1, len(cfgs) // 60))
    res.sort(key=lambda r: -r[1])
    best_cfg = res[0][0]
    mbs = margin_bins(best_cfg)

    def model_eval(read, fit_sel, score_sel):
        w, off = read
        hist = defaultdict(lambda: defaultdict(lambda: [0, 0]))
        ghist = defaultdict(lambda: [0, 0])
        for r, mb in zip(rows, mbs):
            if not fit_sel(r):
                continue
            (half, theta, fire, rsh, lsh, kf, Vlow, rdisc,
             ldisc, t4, s4, side, st_all) = r
            sh = rsh - 59 + (off + 5)
            st = (st_all >> max(sh, 0)) & ((1 << w) - 1)
            hist[(theta, st)][mb][fire] += 1
            ghist[mb][fire] += 1
        ths = {k: fit_thr_hist(h) for k, h in hist.items()}
        gthr = fit_thr_hist(ghist)
        ok = n = 0
        for r, mb in zip(rows, mbs):
            if not score_sel(r):
                continue
            (half, theta, fire, rsh, lsh, kf, Vlow, rdisc,
             ldisc, t4, s4, side, st_all) = r
            sh = rsh - 59 + (off + 5)
            st = (st_all >> max(sh, 0)) & ((1 << w) - 1)
            t = ths.get((theta, st), gthr)
            ok += (1 if mb >= t else 0) == fire
            n += 1
        return ok / max(n, 1)

    # read selection on internal split of train half
    reads = [(w, off) for w in (4, 5, 6, 7)
             for off in (-8, -7, -6, -5, -4, -3, -2)]
    rsel = []
    for read in reads:
        acc = model_eval(read,
                         lambda r: r[0] == 0 and r[6] & 1 == 0,
                         lambda r: r[0] == 0 and r[6] & 1 == 1)
        rsel.append((acc, read))
    rsel.sort(reverse=True)
    best_read = rsel[0][1]

    is_tr = lambda r: r[0] == 0
    is_te = lambda r: r[0] == 1
    m1 = model_eval((1, 50), is_tr, is_te)  # state reads
    # above the word top -> constant 0 -> margin-only
    m3d = model_eval((6, -5), is_tr, is_te)
    m3b = model_eval(best_read, is_tr, is_te)
    # table + ceiling
    tab = defaultdict(lambda: [0, 0])
    for r, mb in zip(rows, mbs):
        if r[0] != 0:
            continue
        (half, theta, fire, rsh, lsh, kf, Vlow, rdisc, ldisc,
         t4, s4, side, st_all) = r
        st = (st_all >> max(rsh - 59, 0)) & 63
        tab[(theta, mb, st)][fire] += 1
    ok = n = 0
    ctab = defaultdict(lambda: [0, 0])
    gmaj_c = [0, 0]
    for r, mb in zip(rows, mbs):
        if r[0] != 1:
            continue
        (half, theta, fire, rsh, lsh, kf, Vlow, rdisc, ldisc,
         t4, s4, side, st_all) = r
        st = (st_all >> max(rsh - 59, 0)) & 63
        c = tab.get((theta, mb, st))
        gmaj_c[fire] += 1
        ctab[(theta, mb, st)][fire] += 1
        if c is None:
            pred = 1 if sum(x[1] for x in tab.values()) >= \
                sum(x[0] for x in tab.values()) else 0
        else:
            pred = 0 if c[0] >= c[1] else 1
        ok += pred == fire
        n += 1
    table_acc = ok / max(n, 1)
    ceil = sum(max(c) for c in ctab.values()) / \
        max(sum(sum(c) for c in ctab.values()), 1)
    base = max(gmaj_c) / max(sum(gmaj_c), 1)
    return (best_cfg, res[0][1], best_read, base, m1, m3d,
            m3b, table_acc, ceil)


def main():
    by = defaultdict(list)
    for line in open("h596_hard.tsv"):
        f = line.split()
        key = ((int(f[1]), int(f[2]), int(f[3])), f[4])
        m = int(f[0], 16)
        half = (m * 2654435761) & 1
        by[key].append(
            [half, int(f[5]), int(f[6]), int(f[9]),
             int(f[10]), int(f[11]), int(f[12], 16),
             int(f[13], 16), int(f[14], 16), int(f[15], 16),
             int(f[16]), f[4], int(f[7], 16), int(f[8], 16)])
    print("computing word states...", flush=True)
    with Pool(15) as pool:
        for key, rows in by.items():
            sts = pool.map(_ws, [(r[12], r[13]) for r in rows],
                           chunksize=1000)
            for r, s in zip(rows, sts):
                r[12] = s  # replace f4v slot with S+C word
                del r[13:]
    print(f"{'stratum/side':20s} {'n':>6s} {'base':>6s} "
          f"{'M1':>7s} {'M3d':>7s} {'M3best':>7s} "
          f"{'table':>7s} {'ceil':>7s}  cfg/read")
    for key in sorted(by):
        rows = [tuple(r) for r in by[key]]
        (cfg, m1tr, read, base, m1, m3d, m3b, tacc,
         ceil) = run_stratum(key, rows)
        n = len(rows)
        print(f"{str(key):20s} {n:6d} {base:6.3f} {m1:7.4f} "
              f"{m3d:7.4f} {m3b:7.4f} {tacc:7.4f} {ceil:7.4f}"
              f"  {cfg}/{read}", flush=True)


def _ws(args):
    f4v, rfv = args
    S, C = split_words(f4v, rfv)
    return S + C


if __name__ == "__main__":
    main()
