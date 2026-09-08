#!/usr/bin/env python3
"""h590c: are the fc and sc residuals (beyond the shared
word-state models) correlated row-wise?

Unambiguous-sc rows only, all pooled (no split).  Per
(key, st3, mb) cell: p_fc, p_sc = cell means of fc_fire,
sc_fire (d>=1).  Pooled covariance test over rows:
z = sum (fc - p_fc)(sc - p_sc) / sqrt(sum p_fc(1-p_fc)
p_sc(1-p_sc)) restricted to cells where BOTH rates are
non-degenerate.  Shared arrangement state => z != 0;
schedule-generated => z ~ 0 (the h526 independence claim,
now conditional on the word state).
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
        sts = pool.map(st3_row,
                       [(cache[m][3], cache[m][4], cache[m][5])
                        for m, R, ce, hw in jobs],
                       chunksize=2000)
    cells = defaultdict(list)
    for (mhex, R, ce, hw), ds, st3 in zip(jobs, labs, sts):
        if len(ds) != 1:
            continue
        key, mb, fc = cache[mhex][0], cache[mhex][1], \
            cache[mhex][2]
        scf = 1 if ds[0] >= 1 else 0
        cells[(key, st3, mb)].append((fc, scf))
    num = 0.0
    den = 0.0
    nrows = ncells = 0
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
    z = num / den ** 0.5 if den > 0 else 0.0
    print(f"informative cells: {ncells}, rows: {nrows}")
    print(f"pooled residual covariance: sum={num:.1f} "
          f"z={z:+.2f}")
    # split by theta-proxy mb sign for texture
    for name, cond in (("mb<0", lambda mb: mb < 0),
                       ("mb>=0", lambda mb: mb >= 0)):
        num = den = 0.0
        nr = 0
        for (key, st3, mb), pts in cells.items():
            if not cond(mb):
                continue
            n = len(pts)
            if n < 3:
                continue
            pf = sum(p[0] for p in pts) / n
            ps = sum(p[1] for p in pts) / n
            if pf in (0.0, 1.0) or ps in (0.0, 1.0):
                continue
            nr += n
            for fc, scf in pts:
                num += (fc - pf) * (scf - ps)
                den += pf * (1 - pf) * ps * (1 - ps)
        z = num / den ** 0.5 if den > 0 else 0.0
        print(f"  {name}: rows={nr} z={z:+.2f}")


if __name__ == "__main__":
    main()
