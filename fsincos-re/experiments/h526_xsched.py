#!/usr/bin/env python3
"""h526: cross-schedule differencing at scale.

comb-4's d9 window has BOTH captures: standalone FCOS and paired
FSINCOS cos-lane, 390,898 rows labeled under both schedules.  h488
(1,310 rows) showed near-independence; here:
  1. joint contingency per stratum;
  2. the DISAGREEMENT indicator delta = (cos_fire != sc_fire) as a
     label: does IT have (XT, XD, m) structure?  (If the schedule
     changes a deterministic internal arrangement, delta may be
     lawful even though sc alone looks flat.)
  3. sc_fire conditioned on the cos-rule's residual r: is the paired
     gate's rate modulated by distance from the standalone boundary?
"""
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h500_plane_m import build
from h510_xd_steps import fit_free
import fcos_tie_rule


def load_pairs():
    rows = []
    seen = set()
    for line in open("ties_comb4.txt"):
        f = line.split()
        if f[0] in seen or f[0] >= "c8":
            continue
        seen.add(f[0])
        rows.append(f)
    inputs = sorted(f[0] for f in rows)
    order = {m: i for i, m in enumerate(inputs)}
    stc = {md: open(f"comb4_{md}_status.txt").read().splitlines()
           for md in ROUNDING_MODES}
    sts = {md: open(f"comb4_sc_{md}_status.txt").read().splitlines()
           for md in ROUNDING_MODES}
    # cos status is over ALL comb4 inputs; sc over the d9 subset only
    all_inputs = sorted(set(line.split()[0]
                            for line in open("ties_comb4.txt")))
    order_all = {m: i for i, m in enumerate(all_inputs)}
    out = []
    both, sc_other, cos_other = 0, 0, 0
    for f in rows:
        R, ce = int(f[7], 16), int(f[8])
        ia, i9 = order_all[f[0]], order[f[0]]
        lab = []
        for st, idx, tok in ((stc, ia, 2), (sts, i9, 4)):
            hw, bad = [], False
            for md in ROUNDING_MODES:
                t = st[md][idx].split()
                if t[0] != "OK":
                    bad = True
                    break
                hw.append(int(t[tok], 16))
            if bad:
                lab.append(None)
                continue
            clean = [final_cosine_result(-R, ce, md)
                     for md in ROUNDING_MODES]
            fired = [final_cosine_result(-(R - 1), ce, md)
                     for md in ROUNDING_MODES]
            lab.append(False if hw == clean else
                       True if hw == fired else None)
        cf, sf = lab
        if cf is None:
            cos_other += 1
            continue
        if sf is None:
            sc_other += 1
            continue
        both += 1
        out.append((f[0], cf, sf))
    print(f"paired-labeled {both}, sc OTHER/paired-window {sc_other}, "
          f"cos OTHER {cos_other}")
    return out


def main():
    pairs = load_pairs()
    with Pool(8) as pool:
        data = pool.map(build, [(mh, cf) for mh, cf, _ in pairs],
                        chunksize=1000)
    scf = {mh: sf for mh, _, sf in pairs}
    strata = defaultdict(lambda: defaultdict(int))
    delta_pts = defaultdict(list)
    sc_by_r = defaultdict(lambda: [0, 0])
    for (mh, cf, sf), (cell, XT, XD, mf, _) in zip(pairs, data):
        key = (cell[0], cell[1])
        strata[key][(cf, sf)] += 1
        delta_pts[key].append((XT, XD, mf, int(cf != sf)))
        ln = fcos_tie_rule.boundary(cell[0], cell[1], XT, XD, mf)
        if ln:
            r = mf - ln[0] * XT - ln[1]
            rb = max(-8, min(8, int(r / 0.01)))
            b = sc_by_r[rb]
            b[0] += 1
            b[1] += sf
    print("\njoint contingency per stratum "
          "(clean/clean, clean/fire, fire/clean, fire/fire):")
    for key in sorted(strata):
        t = strata[key]
        n = sum(t.values())
        cc, cf_, fc, ff = (t[(False, False)], t[(False, True)],
                           t[(True, False)], t[(True, True)])
        pc = (cc + cf_) / n
        ps = (cc + fc) / n
        agree = (cc + ff) / n
        exp = pc * ps + (1 - pc) * (1 - ps)
        print(f"  {key}: n={n} cc={cc} cs={cf_} fc={fc} ff={ff} "
              f"agree={agree:.3f} chance={exp:.3f}")
    print("\ndisagreement-label line fits per stratum:")
    for key in sorted(delta_pts):
        pts = delta_pts[key]
        n = len(pts)
        n1 = sum(p[3] for p in pts)
        if n < 3000 or min(n1, n - n1) < 100:
            print(f"  {key}: n={n} deltas={n1} (thin)")
            continue
        emin, s, c, blo, bhi = fit_free(pts)
        if s is None:
            print(f"  {key}: n={n} deltas={n1} rate={n1/n:.3f} "
                  f"NO structure (never-beat)")
        else:
            print(f"  {key}: n={n} deltas={n1} rate={n1/n:.3f} "
                  f"line errs={emin} ({emin/n:.4f}) s={s:.5f} "
                  f"c={c:.5f}")
    print("\nsc fire rate vs standalone-boundary residual bin "
          "(0.01 bins):")
    for rb in sorted(sc_by_r):
        n, n1 = sc_by_r[rb]
        if n >= 200:
            print(f"  r~{rb * 0.01:+.2f}: n={n:7d} "
                  f"sc_rate={n1/n:.3f}")


if __name__ == "__main__":
    main()
