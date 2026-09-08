#!/usr/bin/env python3
"""h590b: the paired cos lane in the borrow-census frame.

1. Borrow-frame recode (unambiguous rows): req2_sc = R + d_sc
   - EU; bp_sc = b - req2_sc; count single-borrow violations
   (bp outside {0,1}).
2. Window-function census for the sc lane: key = (strat, S_w,
   C_w) at w in {6,8,10,12} (APf constant per stratum): ceiling
   + held-out for the sc 3-class d in {-1,0,+1} — the analog of
   h587c for the paired schedule.
3. Alias-aware 3-class model on ALL rows: per (key, st3, mb)
   majority-d fit on unambiguous train; scored exact on
   unambiguous test, consistency (pred in D_sc set) on
   ambiguous rows; baseline = best constant-per-key d.
"""
import sys
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h577_three_term import qrow3
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


def words_borrow(args):
    mhex, f4v, rfv, rsh_c, kf_c, Vlow = args
    (m, R, A, P, B_full, rsh, rdisc, lsh, ldisc, s4, t4,
     bshift, k, dist, low3) = qrow3(mhex)
    F = rsh - bshift
    kf = k + F
    APf = (A + P) << F
    EU = (APf - B_full) >> kf
    B_low = B_full & ((1 << kf) - 1)
    APf_low = (Vlow + B_low) & ((1 << kf) - 1)
    b = 1 if APf_low < B_low else 0
    S, C = split_words(f4v, rfv)
    return R, EU, b, S, C


def main():
    stride = int(sys.argv[1]) if len(sys.argv) > 1 else 1
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
                       int(f[7], 16), int(f[8], 16),
                       int(f[9]), int(f[10]), int(f[11], 16))
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
    print(f"rows: {len(jobs)}", flush=True)
    with Pool(15) as pool:
        labs = pool.map(sc_label, jobs, chunksize=500)
        wb = pool.map(words_borrow,
                      [(mhex, cache[mhex][3], cache[mhex][4],
                        cache[mhex][5], cache[mhex][6],
                        cache[mhex][7])
                       for mhex, R, ce, hw in jobs],
                      chunksize=500)
    # 1. borrow-frame recode on unambiguous
    viol = ok1 = 0
    bpcnt = defaultdict(int)
    recs = []
    for (mhex, R, ce, hw), ds, (R2, EU, b, S, C) in \
            zip(jobs, labs, wb):
        key, mb, fc, f4v, rfv, rsh, kf, Vlow = cache[mhex]
        half = (int(mhex, 16) * 2654435761) & 1
        sh = rsh - 59
        st3 = ((S + C) >> sh) & 63
        recs.append((key, half, mb, st3, ds, R, EU, b, S, C,
                     rsh, kf))
        if len(ds) != 1:
            continue
        req2 = R + ds[0] - EU
        bp = b - req2
        bpcnt[bp] += 1
        if bp in (0, 1):
            ok1 += 1
        else:
            viol += 1
    print(f"1. borrow frame (unambiguous): bp census "
          f"{dict(sorted(bpcnt.items()))}  single-borrow ok "
          f"{ok1}, violations {viol}", flush=True)

    # 2. window census for sc 3-class d (unambiguous)
    print("\n2. sc window census (unambiguous, 3-class d):")
    print(f"{'w':>3s} {'groups':>7s} {'ceil':>7s} "
          f"{'heldout':>8s} {'unseen':>7s}")
    una = [r for r in recs if len(r[4]) == 1]
    for w in (6, 8, 10, 12):
        gtr = defaultdict(lambda: defaultdict(int))
        te = []
        for (key, half, mb, st3, ds, R, EU, b, S, C, rsh,
             kf) in una:
            fb = kf - 54
            gk = (key, (S >> (fb - w)) & ((1 << w) - 1),
                  (C >> (fb - w)) & ((1 << w) - 1))
            d = ds[0]
            if half == 0:
                gtr[gk][d] += 1
            else:
                te.append((gk, d))
        ceil_ok = sum(max(c.values()) for c in gtr.values())
        ceil_n = sum(sum(c.values()) for c in gtr.values())
        ho = unseen = 0
        for gk, d in te:
            c = gtr.get(gk)
            if c is None:
                unseen += 1
                pred = 1
            else:
                pred = max(c, key=c.get)
            ho += pred == d
        print(f"{w:3d} {len(gtr):7d} "
              f"{ceil_ok / max(ceil_n, 1):7.4f} "
              f"{ho / max(len(te), 1):8.4f} {unseen:7d}",
              flush=True)

    # 3. alias-aware 3-class model on ALL rows
    print("\n3. alias-aware (key, SUM6, mb) majority-d model:")
    gtr = defaultdict(lambda: defaultdict(int))
    kcst = defaultdict(lambda: defaultdict(int))
    for (key, half, mb, st3, ds, R, EU, b, S, C, rsh,
         kf) in recs:
        if half == 0 and len(ds) == 1:
            gtr[(key, st3, mb)][ds[0]] += 1
            kcst[key][ds[0]] += 1
    kconst = {k: max(c, key=c.get) for k, c in kcst.items()}
    ex_ok = ex_n = 0
    cons_ok = cons_n = 0
    bcons_ok = 0
    for (key, half, mb, st3, ds, R, EU, b, S, C, rsh,
         kf) in recs:
        if half != 1:
            continue
        c = gtr.get((key, st3, mb))
        pred = max(c, key=c.get) if c else kconst[key]
        if len(ds) == 1:
            ex_n += 1
            ex_ok += pred == ds[0]
        else:
            cons_n += 1
            cons_ok += pred in ds
            bcons_ok += kconst[key] in ds
    print(f"  unambiguous test: exact {ex_ok}/{ex_n} = "
          f"{ex_ok / max(ex_n, 1):.4f}")
    print(f"  ambiguous test: consistent {cons_ok}/{cons_n} = "
          f"{cons_ok / max(cons_n, 1):.4f}  (const-baseline "
          f"{bcons_ok / max(cons_n, 1):.4f})")
    amb_sizes = defaultdict(int)
    for r in recs:
        amb_sizes[len(r[4])] += 1
    print(f"  D_sc set-size census: {dict(sorted(amb_sizes.items()))}")


if __name__ == "__main__":
    main()
