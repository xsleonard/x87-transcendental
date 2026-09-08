#!/usr/bin/env python3
"""h590d: powered fc-sc residual correlation.

fc side: p_fc per (key, st3, mb) cell estimated from the FULL
213k-row band corpus (fc labels exist for every row).
sc side: p_sc per (key, st3, mb) cell from unambiguous-sc rows,
leave-one-out (cells are small; LOO kills self-correlation).
Test rows: unambiguous-sc rows in cells with 0<p_fc<1 and
sc-cell n>=2.  z = sum (fc-p_fc)(sc-p_sc) /
sqrt(sum p_fc(1-p_fc)*p_sc_loo_var).
"""
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h588_select import split_words, TARGETS

MODES = ROUNDING_MODES


def sc_label(args):
    mhex, R, ce, hw_sc = args
    ds = []
    for d in range(-3, 4):
        refs = [final_cosine_result(-(R + d), ce, md)
                for md in MODES]
        if hw_sc == refs:
            ds.append(d)
    return ds


def st3_row(args):
    f4v, rfv, rsh = args
    S, C = split_words(f4v, rfv)
    return ((S + C) >> (rsh - 59)) & 63


def main():
    cache = {}
    for line in open("h587d_band.tsv"):
        f = line.split()
        key = ((int(f[1]), int(f[2]), int(f[3])), f[4])
        if key not in dict.fromkeys(TARGETS):
            continue
        cache[f[0]] = (key, int(f[5]), int(f[6]),
                       int(f[7], 16), int(f[8], 16), int(f[9]))
    order_jobs = list(cache.items())
    with Pool(15) as pool:
        sts_all = pool.map(st3_row,
                           [(v[3], v[4], v[5])
                            for m, v in order_jobs],
                           chunksize=2000)
    st3_of = {m: s for (m, v), s in zip(order_jobs, sts_all)}
    # fc rates from FULL corpus
    fc_cell = defaultdict(lambda: [0, 0])
    for m, (key, mb, fc, f4v, rfv, rsh) in cache.items():
        fc_cell[(key, st3_of[m], mb)][fc] += 1
    # sc labels
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
    for f in raw:
        mhex = f[0]
        if mhex not in cache:
            continue
        R, ce = int(f[7], 16), int(f[8])
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
        jobs.append((mhex, R, ce, hw))
    with Pool(15) as pool:
        labs = pool.map(sc_label, jobs, chunksize=500)
    sc_cell = defaultdict(list)
    for (mhex, R, ce, hw), ds in zip(jobs, labs):
        if len(ds) != 1:
            continue
        key, mb = cache[mhex][0], cache[mhex][1]
        scf = 1 if ds[0] >= 1 else 0
        sc_cell[(key, st3_of[mhex], mb)].append((mhex, scf))
    num = den = 0.0
    nrows = ncells = 0
    for ck, pts in sc_cell.items():
        n = len(pts)
        if n < 2:
            continue
        c = fc_cell[ck]
        nf = c[0] + c[1]
        pf = c[1] / nf
        if pf in (0.0, 1.0):
            continue
        stot = sum(s for m, s in pts)
        used = False
        for m, s in pts:
            ps = (stot - s) / (n - 1)
            if ps in (0.0, 1.0):
                # LOO rate degenerate is fine; variance term
                # still 0 -> contributes nothing
                continue
            fc = cache[m][2]
            num += (fc - pf) * (s - ps)
            den += pf * (1 - pf) * ps * (1 - ps)
            nrows += 1
            used = True
        if used:
            ncells += 1
    z = num / den ** 0.5 if den > 0 else 0.0
    print(f"informative cells: {ncells}, rows: {nrows}")
    print(f"pooled residual covariance: sum={num:.2f} "
          f"z={z:+.2f}")


if __name__ == "__main__":
    main()
