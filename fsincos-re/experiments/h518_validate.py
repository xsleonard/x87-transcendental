#!/usr/bin/env python3
"""h518: PHASE C1 — score the locked h515 rule (with amendments) on
the shifted comb-4, hardware-blind: predictions were registered before
any comb-4 outcome was read.

Reports per (dist, low3, zone): n, fires, predicted-correct, WRONG,
in-band, declared, uncovered; V1 purity of NEVER/ALWAYS regions; V4
pivot corridors; OTHER count (V5).  Then E2 first pass: the paired
(sincos) lane on the d9-window subset — per-stratum fire rates and a
free-line fit (does the paired gate have its own m-law?).
"""
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h500_plane_m import build
from h510_xd_steps import fit_free

TW73_81 = {0: (0.33717, 0.63957), 1: (0.31898, 0.65565),
           2: (0.31898, 0.65565), 3: (0.39510, 0.58911),
           4: (0.36809, 0.61250), 5: (0.36055, 0.61987),
           6: (0.36055, 0.61987), 7: (0.34966, 0.62838)}
TW73_83 = {4: (0.12465, 0.85699), 5: (0.15678, 0.83706),
           6: (0.14644, 0.84353), 7: (0.16063, 0.83509),
           8: (0.15385, 0.83886), 9: (0.16972, 0.82932),
           10: (0.16704, 0.83082), 11: (0.15932, 0.83565)}
TW73_85 = {8: (0.09648, 0.89892), 9: (0.09978, 0.89790),
           10: (0.08949, 0.90163), 11: (0.09871, 0.89831)}
TW73_D8L1 = {0: (0.364029, 0.343320), 1: (0.362411, 0.344806),
             2: (0.353500, 0.352698), 3: (0.357498, 0.349299),
             4: (0.354904, 0.352109), 5: (0.361984, 0.345132),
             6: (0.364609, 0.342681), 7: (0.362320, 0.344699)}


def line(s, c, w, XT, mf):
    r = mf - s * XT - c
    if abs(r) < w:
        return "band", None
    return "line", (1 if r < 0 else 0)


def classify(dist, low3, XT, XD, mf):
    tw = min(11, int(XD * 12))
    if dist == 9 and 0.656 <= mf < 0.938:
        if low3 == 1:
            return "never", 0
        if low3 == 2:
            if XD >= 1/3 and mf - 0.25 * XT < 0.475:
                return "declared", None
            return "never", 0
        if low3 == 3:
            return line(0.125, 0.58325, 0.003, XT, mf)
        if low3 == 4:
            if XD < 1/3:
                return line(0.0833, 0.6186, 0.006, XT, mf)
            return line(0.084106, 0.707687, 0.003, XT, mf)
        if low3 == 5:
            return line(0.067505, 0.707687, 0.003, XT, mf)
        if low3 == 6:
            if XD < 1/3:
                return line(0.056366, 0.707687, 0.003, XT, mf)
            return line(0.053818, 0.763793, 0.003, XT, mf)
        if low3 == 7:
            return line(0.046380, 0.756040, 0.003, XT, mf)
    if dist == 8 and 0.656 <= mf < 0.781:          # le2=-73 window
        if low3 == 1:
            if XD >= 2/3:
                return "always", 1
            s, c = TW73_D8L1[tw]
            return line(s, c, 0.004, XT, mf)
        if low3 == 2:
            if XD < 1/3:
                return line(0.1805, 0.5265, 0.004, XT, mf)
            return "always", 1
        return "always", 1
    if dist == 8 and 0.781 <= mf < 0.938:
        if low3 == 1:
            return "declared", None
        if low3 == 2:
            if XD < 1/3:
                return "never", 0
            return "declared", None
        if low3 == 3:
            if XD < 2/3:
                return line(0.10332, 0.71321, 0.003, XT, mf)
            return line(0.1950, 0.8155, 0.006, XT, mf)
        if low3 == 4:
            if XD < 1/3:
                return line(0.0755, 0.7148, 0.008, XT, mf)
            return line(0.0714, 0.79190, 0.004, XT, mf)
        if low3 == 5:
            if XD < 2/3:
                k, p = line(0.0619, 0.7750, 0.003, XT, mf)
                if k == "line" and p == 0:
                    r = mf - 0.0619 * XT - 0.7750
                    if 0.004 <= r <= 0.05:
                        return "declared", None
                return k, p
            return line(0.0510, 0.8285, 0.012, XT, mf)
        if low3 == 6:
            if XD < 1/3:
                return line(0.05141, 0.76507, 0.003, XT, mf)
            return line(0.0977, 0.8163, 0.005, XT, mf)
        if low3 == 7:
            if XD < 2/3:
                return line(0.04320, 0.80194, 0.003, XT, mf)
            return line(0.08009, 0.84601, 0.003, XT, mf)
    if dist == 7 and 0.781 <= mf < 0.938:
        if low3 == 1:
            if XD >= 2/3:
                return "always", 1
            s, c = TW73_81[tw]
            return line(s, c, 0.004, XT, mf)
        if low3 == 3:
            if XD < 1/3:
                return "never", 0
            s, c = TW73_83[tw]
            return line(s, c, 0.004, XT, mf)
        if low3 == 5:
            if XD < 2/3:
                return "never", 0
            s, c = TW73_85[tw]
            return line(s, c, 0.004, XT, mf)
        if low3 == 7:
            return "never", 0
    return "uncovered", None


def load(prefix, ties_file, subset=None):
    rows = []
    seen = set()
    for lineS in open(ties_file):
        f = lineS.split()
        if f[0] in seen:
            continue
        seen.add(f[0])
        if subset and not subset(f[0]):
            continue
        rows.append(f)
    inputs = sorted(f[0] for f in rows)
    order = {m: i for i, m in enumerate(inputs)}
    st = {md: open(f"{prefix}_{md}_status.txt").read().splitlines()
          for md in ROUNDING_MODES}
    out, other = [], 0
    for f in rows:
        R, ce, i = int(f[7], 16), int(f[8]), order[f[0]]
        hw, bad = [], False
        for md in ROUNDING_MODES:
            t = st[md][i].split()
            if t[0] != "OK":
                bad = True
                break
            hw.append(int(t[2], 16))
        if bad:
            continue
        clean = [final_cosine_result(-R, ce, md)
                 for md in ROUNDING_MODES]
        fired = [final_cosine_result(-(R - 1), ce, md)
                 for md in ROUNDING_MODES]
        if hw == clean:
            out.append((f[0], False))
        elif hw == fired:
            out.append((f[0], True))
        else:
            other += 1
    return out, other


def main():
    rows, other = load("comb4", "ties_comb4.txt")
    print(f"comb-4 cos: {len(rows)} labeled, {other} OTHER (V5)")
    with Pool(8) as pool:
        data = pool.map(build, rows, chunksize=1000)
    tab = defaultdict(lambda: defaultdict(int))
    for cell, XT, XD, mf, fire in data:
        dist, low3, _ = cell
        kind, pred = classify(dist, low3, XT, XD, mf)
        key = (dist, low3)
        t = tab[key]
        t["n"] += 1
        t["fires"] += fire
        if kind in ("line", "never", "always"):
            t["ok" if pred == fire else "WRONG"] += 1
            if pred != fire:
                t[f"wrong_{kind}"] += 1
        else:
            t[kind] += 1
            if fire:
                t[f"{kind}_fire"] += 1
    print(f"\n{'cell':10s} {'n':>7s} {'fires':>7s} {'ok':>7s} "
          f"{'WRONG':>6s} {'band':>6s} {'decl':>6s} {'uncov':>6s}")
    tot = defaultdict(int)
    for key in sorted(tab):
        t = tab[key]
        for k in ("n", "fires", "ok", "WRONG", "band", "declared",
                  "uncovered"):
            tot[k] += t[k]
        print(f"{str(key):10s} {t['n']:7d} {t['fires']:7d} "
              f"{t['ok']:7d} {t['WRONG']:6d} {t['band']:6d} "
              f"{t['declared']:6d} {t['uncovered']:6d}")
    print(f"{'TOTAL':10s} {tot['n']:7d} {tot['fires']:7d} "
          f"{tot['ok']:7d} {tot['WRONG']:6d} {tot['band']:6d} "
          f"{tot['declared']:6d} {tot['uncovered']:6d}")
    pred_n = tot["ok"] + tot["WRONG"]
    print(f"\nVERDICT: predicted {pred_n}, wrong {tot['WRONG']} "
          f"({tot['WRONG']/max(1,pred_n):.4%}); "
          f"band {tot['band']/max(1,tot['n']):.3%}, declared "
          f"{tot['declared']/max(1,tot['n']):.3%}, uncovered "
          f"{tot['uncovered']/max(1,tot['n']):.3%}")

    # E2: paired lane on the d9-window subset
    sc_rows, sc_other = load("comb4_sc", "ties_comb4.txt",
                             subset=lambda mh: mh < "c8")
    print(f"\nE2 sincos (d9 window): {len(sc_rows)} labeled, "
          f"{sc_other} OTHER (paired-window rows)")
    with Pool(8) as pool:
        sdata = pool.map(build, sc_rows, chunksize=1000)
    strata = defaultdict(list)
    for cell, XT, XD, mf, fire in sdata:
        strata[(cell[0], cell[1])].append((XT, XD, mf, fire))
    print(f"{'stratum':10s} {'n':>7s} {'fires':>7s} {'rate':>6s} "
          f"{'line errs':>9s} {'s':>9s} {'c':>9s}")
    for key in sorted(strata):
        pts = strata[key]
        n, n1 = len(pts), sum(p[3] for p in pts)
        if n < 2000 or min(n1, n - n1) < 50:
            print(f"{str(key):10s} {n:7d} {n1:7d} "
                  f"{n1/max(1,n):6.3f}   (sparse/pure)")
            continue
        emin, s, c, blo, bhi = fit_free(pts)
        if s is None:
            print(f"{str(key):10s} {n:7d} {n1:7d} {n1/n:6.3f} "
                  f"  no-line ({emin} errs)")
            continue
        print(f"{str(key):10s} {n:7d} {n1:7d} {n1/n:6.3f} "
              f"{emin:9d} {s:9.5f} {c:9.5f}  "
              f"rel_err={emin/n:.4f}")


if __name__ == "__main__":
    main()
