#!/usr/bin/env python3
"""h590: cross-schedule differencing in the validated tree-word
frame (lead (b) after h589).

Joins the h587d band cache (targets (9,1)/(9,2)@-72 up side,
213k rows) with the comb-7 PAIRED-lane captures (comb7_sc_*,
cos lane = tokens 3-4; alias-aware labeling per the h572
caution: keep the full matching-d SET, d in [-3,3]).

  A. Joint census (fc_fire, d_sc) per stratum + ambiguity rate.
  B. Paired-lane predictability: held-out accuracy of
     margin-only vs margin+SUM6 (the h588-validated state) vs
     margin+SUM6+sw6 for sc_fire.  h491 ruled out VALUE coords
     for the paired lane; the WORD state was never tested.
  C. Within-cell (key, mb, st3) association fc_fire vs sc_fire:
     pooled z over cells (shared arrangement state would show
     conditional correlation; independence = schedule-generated
     state).
  D. The d=+2 branch: rate by theta/stratum, predictability
     from (mb, st3).
Usage: h590_xsched.py [STRIDE]
"""
import sys
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h588_select import split_words, fit_thr, TARGETS
import h539_D_library as DL

MODES = ROUNDING_MODES


def sc_label(args):
    """Return (mhex, D_sc frozenset) from the paired cos lane."""
    mhex, R, ce, hw_sc = args
    ds = []
    for d in range(-3, 4):
        refs = [final_cosine_result(-(R + d), ce, md)
                for md in MODES]
        if hw_sc == refs:
            ds.append(d)
    return mhex, tuple(ds)


def st3_row(args):
    f4v, rfv, rsh = args
    S, C = split_words(f4v, rfv)
    sh = rsh - 59
    return ((S + C) >> sh) & 63, (S >> sh) & 63


def held_out_acc(rows, keyf):
    """rows: (half, mb, fire, ...features); model: per-key
    threshold on mb, fit on half 0, scored on half 1; unseen key
    -> majority-class of train."""
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
        if t is None:
            pred = gmaj
        else:
            pred = 1 if r[1] >= t else 0
        ok += pred == r[2]
        n += 1
    return ok / max(n, 1), n


def main():
    stride = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    # band cache join keys
    cache = {}
    cnt = defaultdict(int)
    for line in open("h587d_band.tsv"):
        f = line.split()
        key = ((int(f[1]), int(f[2]), int(f[3])), f[4])
        if key not in dict.fromkeys(TARGETS):
            continue
        cnt[key] += 1
        if (cnt[key] - 1) % stride:
            continue
        cache[f[0]] = (key, int(f[5]), int(f[6]),
                       int(f[7], 16), int(f[8], 16), int(f[9]))
    print(f"cache rows: {len(cache)}", flush=True)
    # comb-7 order + R/ce/theta + sc capture join
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
        R, ce, theta = int(f[7], 16), int(f[8]), int(f[9])
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
        meta[mhex] = theta
    print(f"joined rows with sc capture: {len(jobs)}",
          flush=True)
    with Pool(15) as pool:
        labs = pool.map(sc_label, jobs, chunksize=500)
        sts = pool.map(st3_row,
                       [(cache[mhex][3], cache[mhex][4],
                         cache[mhex][5])
                        for mhex, ds in labs],
                       chunksize=2000)
    # assemble
    rows = []
    amb = noamb = nolabel = 0
    census = defaultdict(int)
    for (mhex, ds), (st3, sw6) in zip(labs, sts):
        key, mb, fc_fire, f4v, rfv, rsh = cache[mhex]
        theta = meta[mhex]
        if not ds:
            nolabel += 1
            continue
        if len(ds) > 1:
            amb += 1
            continue
        noamb += 1
        d_sc = ds[0]
        census[(key[0], theta, fc_fire, d_sc)] += 1
        half = (int(mhex, 16) * 2654435761) & 1
        rows.append((half, mb, d_sc, fc_fire, key, st3, sw6,
                     theta))
    print(f"sc labels: unambiguous {noamb}, ambiguous {amb}, "
          f"unlabeled {nolabel}", flush=True)
    print("\nA. joint census (stratum, theta, fc_fire, d_sc) "
          "[top 25]:")
    for k in sorted(census, key=lambda k: -census[k])[:25]:
        print(f"  {k}: {census[k]}")
    dcnt = defaultdict(int)
    for half, mb, d_sc, fc, key, st3, sw6, theta in rows:
        dcnt[d_sc] += 1
    print(f"d_sc marginal: {dict(sorted(dcnt.items()))}")

    # B. paired-lane predictability
    print("\nB. sc_fire (d_sc >= 1) held-out accuracy:")
    sc_rows = [(half, mb, 1 if d_sc >= 1 else 0, key, st3, sw6)
               for half, mb, d_sc, fc, key, st3, sw6, theta
               in rows]
    base1 = sum(r[2] for r in sc_rows) / len(sc_rows)
    print(f"  base sc fire rate: {base1:.4f}")
    for name, keyf in (
            ("margin-only (key)", lambda r: r[3]),
            ("key+SUM6", lambda r: (r[3], r[4])),
            ("key+SUM6+sw6", lambda r: (r[3], r[4], r[5]))):
        acc, n = held_out_acc(sc_rows, keyf)
        print(f"  {name:22s}: {acc:.4f}  (n={n})")
    print("  [fc_fire same models, for reference]:")
    fc_rows = [(half, mb, fc, key, st3, sw6)
               for half, mb, d_sc, fc, key, st3, sw6, theta
               in rows]
    for name, keyf in (
            ("margin-only (key)", lambda r: r[3]),
            ("key+SUM6", lambda r: (r[3], r[4]))):
        acc, n = held_out_acc(fc_rows, keyf)
        print(f"  {name:22s}: {acc:.4f}  (n={n})")

    # C. within-cell association fc vs sc
    print("\nC. within-(key, mb, SUM6)-cell association "
          "fc_fire x sc_fire:")
    cells = defaultdict(lambda: [0, 0, 0, 0])
    for half, mb, d_sc, fc, key, st3, sw6, theta in rows:
        scf = 1 if d_sc >= 1 else 0
        cells[(key, mb, st3)][2 * fc + scf] += 1
    num = den = 0.0
    tot11 = exp11 = 0.0
    ncells = 0
    for c in cells.values():
        n00, n01, n10, n11 = c
        n = n00 + n01 + n10 + n11
        r1 = n10 + n11
        c1 = n01 + n11
        if n < 4 or r1 == 0 or r1 == n or c1 == 0 or c1 == n:
            continue
        ncells += 1
        e = r1 * c1 / n
        v = r1 * (n - r1) * c1 * (n - c1) / (n * n * (n - 1))
        tot11 += n11
        exp11 += e
        den += v
    z = (tot11 - exp11) / (den ** 0.5) if den > 0 else 0.0
    print(f"  informative cells: {ncells}; obs11={tot11:.0f} "
          f"exp11={exp11:.1f} z={z:+.2f}")

    # D. d=+2 branch
    print("\nD. d_sc=+2 branch:")
    for th in (0, -1, -2):
        sub = [r for r in rows if r[7] == th]
        if not sub:
            continue
        r2 = sum(1 for r in sub if r[2] == 2) / len(sub)
        print(f"  theta={th}: n={len(sub)} d2_rate={r2:.4f}")
    d2_rows = [(half, mb, 1 if d_sc == 2 else 0, key, st3, sw6)
               for half, mb, d_sc, fc, key, st3, sw6, theta
               in rows]
    for name, keyf in (
            ("margin-only (key)", lambda r: r[3]),
            ("key+SUM6", lambda r: (r[3], r[4]))):
        acc, n = held_out_acc(d2_rows, keyf)
        print(f"  {name:22s}: {acc:.4f}")
    b2 = sum(r[2] for r in d2_rows) / len(d2_rows)
    print(f"  base d2 rate: {b2:.4f} (majority-class acc "
          f"{max(b2, 1 - b2):.4f})")


if __name__ == "__main__":
    main()
