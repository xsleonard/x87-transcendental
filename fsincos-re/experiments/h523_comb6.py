#!/usr/bin/env python3
"""h523: comb-6 processing.
Primary W2 teeth ([0xF0,0x100), bit53=0): census + XD-twelfth fits
-> the W2 laws.  Shifted teeth (bit53=1): blind validation of the
locked W1 laws ([0x80,0xA8) rows, h520 amendment / fcos_tie_rule) —
scored WITHOUT refitting.  W2's shifted rows are held out here; they
are scored by h523b after the W2 laws are locked."""
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h500_plane_m import build
from h510_xd_steps import fit_free
from fcos_tie_rule import classify


def load_comb6():
    rows = []
    seen = set()
    for line in open("ties_comb6.txt"):
        f = line.split()
        if f[0] in seen:
            continue
        seen.add(f[0])
        rows.append(f)
    inputs = sorted(f[0] for f in rows)
    order = {m: i for i, m in enumerate(inputs)}
    st = {md: open(f"comb6_{md}_status.txt").read().splitlines()
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
    print(f"comb-6: {len(out)} labeled, {other} OTHER")
    return out


def one_stratum(args):
    (dist, low3), pts = args
    cells = defaultdict(list)
    for p in pts:
        cells[min(11, int(p[1] * 12))].append(p)
    out = [f"\n=== W2 d{dist} low3={low3}  n={len(pts)} "
           f"fires={sum(p[3] for p in pts)}"]
    for k in sorted(cells):
        sub = cells[k]
        n, n1 = len(sub), sum(p[3] for p in sub)
        lo, hi = k / 12, (k + 1) / 12
        if n < 300 or min(n1, n - n1) < 20:
            tag = ("always" if n1 == n and n else
                   "never" if n1 == 0 else f"sparse({n1}/{n})")
            out.append(f"  XD[{lo:.3f},{hi:.3f}) n={n:6d} {tag}")
            continue
        emin, s, c, blo, bhi = fit_free(sub)
        if s is None:
            out.append(f"  XD[{lo:.3f},{hi:.3f}) n={n:6d} "
                       f"fires={n1:5d} never-fire-opt errs={emin}")
            continue
        out.append(f"  XD[{lo:.3f},{hi:.3f}) n={n:6d} fires={n1:5d} "
                   f"errs={emin:5d} ({emin/n:.4f}) s={s:.6f} "
                   f"1/s={1/s:7.3f} c={c:.6f} "
                   f"band=[{blo:.5f},{bhi:.5f}]")
    return "\n".join(out)


def main():
    rows = load_comb6()
    with Pool(8) as pool:
        data = pool.map(build, rows, chunksize=1000)
    shifted_w1, primary_w2, shifted_w2 = [], [], []
    for (mh, fire), rec in zip(rows, data):
        m = int(mh, 16)
        sh = (m >> 53) & 1
        if m < 0xA800000000000000:
            (shifted_w1 if sh else primary_w2).append(rec)  # W1 all shifted
        else:
            (shifted_w2 if sh else primary_w2).append(rec)
    # sanity: W1 primary teeth shouldn't exist in comb-6
    print(f"rows: shifted-W1 {len(shifted_w1)}, primary-W2 "
          f"{len(primary_w2)}, shifted-W2 {len(shifted_w2)}")

    # 1) blind-validate locked W1 laws on shifted-W1
    tab = defaultdict(lambda: defaultdict(int))
    for cell, XT, XD, mf, fire in shifted_w1:
        kind, pred = classify(cell[0], cell[1], XT, XD, mf)
        t = tab[(cell[0], cell[1])]
        t["n"] += 1
        t["fires"] += fire
        if kind in ("line", "never", "always"):
            t["ok" if pred == fire else "WRONG"] += 1
        else:
            t[kind] += 1
    print("\nW1 BLIND VALIDATION (shifted rows vs locked laws):")
    print(f"{'cell':10s} {'n':>7s} {'fires':>7s} {'ok':>7s} "
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
    pn = tot["ok"] + tot["WRONG"]
    print(f"W1 VERDICT: predicted {pn}, wrong {tot['WRONG']} "
          f"({tot['WRONG']/max(1,pn):.4%}), band {tot['band']}, "
          f"declared {tot['declared']}, uncovered {tot['uncovered']}")

    # 2) fit W2 laws on primary-W2
    strata = defaultdict(list)
    for cell, XT, XD, mf, fire in primary_w2:
        strata[(cell[0], cell[1])].append((XT, XD, mf, fire))
    print("\nW2 census:",
          {k: len(v) for k, v in sorted(strata.items())})
    jobs = sorted(strata.items())
    with Pool(8) as pool:
        for block in pool.imap(one_stratum, jobs, chunksize=1):
            print(block, flush=True)
    # store shifted-W2 for h523b
    with open("comb6_shifted_w2.tsv", "w") as f:
        for cell, XT, XD, mf, fire in shifted_w2:
            f.write(f"{cell[0]} {cell[1]} {cell[2]} {XT!r} {XD!r} "
                    f"{mf!r} {fire}\n")
    print(f"\nwrote comb6_shifted_w2.tsv "
          f"({len(shifted_w2)} rows, held out)")


if __name__ == "__main__":
    main()
