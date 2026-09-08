#!/usr/bin/env python3
"""h594b: class-level sc_fire by (stratum, theta) + per-theta
predictability + theta-0-only association."""
from collections import defaultdict
from multiprocessing import Pool
from h594_sc_relabel import row_work, held_out_thr
from h588_select import TARGETS
from h437_gate_extraction import ROUNDING_MODES

MODES = ROUNDING_MODES


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
    with Pool(15) as pool:
        res = pool.map(row_work, jobs, chunksize=300)
    rows = []
    for (mhex, f4v, rfv, rsh, hw), (Z, st3, wins) in \
            zip(jobs, res):
        key, mb, fire, theta = meta[mhex]
        half = (int(mhex, 16) * 2654435761) & 1
        cls = set(1 if z >= 1 else 0 for z in Z)
        if len(cls) != 1:
            continue
        rows.append((half, mb, cls.pop(), key, st3, fire,
                     theta, len(Z) == 1))
    print("sc_fire rate by (stratum, theta), class-level:")
    tab = defaultdict(lambda: [0, 0])
    for half, mb, scf, key, st3, fire, theta, ex in rows:
        tab[(key[0], theta)][scf] += 1
    for k in sorted(tab):
        c = tab[k]
        n = c[0] + c[1]
        print(f"  {k}: n={n} rate={c[1] / n:.4f}")
    print("\nheld-out with theta in the key:")
    for name, keyf in (
            ("key+theta", lambda r: (r[3], r[6])),
            ("key+theta+SUM6", lambda r: (r[3], r[6], r[4]))):
        acc, n = held_out_thr(rows, keyf)
        print(f"  {name:18s}: {acc:.4f} (n={n})")
    for th in (0, -1, -2):
        sub = [r for r in rows if r[6] == th]
        if not sub:
            continue
        base = sum(r[2] for r in sub) / len(sub)
        acc, n = held_out_thr(sub, lambda r: (r[3], r[4]))
        print(f"  theta={th}: n={len(sub)} base={base:.4f} "
              f"key+SUM6={acc:.4f}")
    print("\nfc x sc association, theta=0 rows only:")
    cells = defaultdict(list)
    for half, mb, scf, key, st3, fire, theta, ex in rows:
        if theta == 0:
            cells[(key, mb, st3)].append((fire, scf))
    num = den = 0.0
    ncells = nrows = 0
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
    print(f"  cells={ncells} rows={nrows} z={z:+.2f}")
    for th in (-1, -2):
        cells = defaultdict(list)
        for half, mb, scf, key, st3, fire, theta, ex in rows:
            if theta == th:
                cells[(key, mb, st3)].append((fire, scf))
        num = den = 0.0
        ncells = nrows = 0
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
        print(f"  theta={th}: cells={ncells} rows={nrows} "
              f"z={z:+.2f}")


if __name__ == "__main__":
    main()
