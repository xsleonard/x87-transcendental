#!/usr/bin/env python3
"""h523b: score the held-out shifted-W2 rows (comb6_shifted_w2.tsv)
against the W2 laws just locked into fcos_tie_rule (fitted on primary
teeth only — held-out discipline)."""
from collections import defaultdict
from fcos_tie_rule import classify


def main():
    tab = defaultdict(lambda: defaultdict(int))
    for line in open("comb6_shifted_w2.tsv"):
        d, l3, ru, xt, xd, mf, fi = line.split()
        dist, low3, fire = int(d), int(l3), int(fi)
        kind, pred = classify(dist, low3, float(xt), float(xd),
                              float(mf))
        t = tab[(dist, low3)]
        t["n"] += 1
        t["fires"] += fire
        if kind in ("line", "never", "always"):
            t["ok" if pred == fire else "WRONG"] += 1
        else:
            t[kind] += 1
    print("W2 HELD-OUT VALIDATION (shifted rows):")
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
    print(f"VERDICT: predicted {pn}, wrong {tot['WRONG']} "
          f"({tot['WRONG']/max(1,pn):.4%}), band {tot['band']}, "
          f"uncovered {tot['uncovered']}")


if __name__ == "__main__":
    main()
