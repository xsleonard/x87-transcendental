#!/usr/bin/env python3
"""h625b: tie-correct AUC + FLIP-RULE mining on the band.

Baseline = round() (pred = frac >= 0.5).  Mine per-stratum-
side rules of the form 'flip the baseline when feature f is in
threshold region R' — the baseline is always expressible
(flip nowhere), so held-out can only be beaten by real signal.
Features: singles and pairs from the h625 battery (correct
tie-handling AUC first).
"""
import bisect
import json
import pickle
from collections import defaultdict
from itertools import combinations
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES
from h625_band_direction import prep, initp

FEATS = ("st", "stA6", "theta", "xd48", "t4d16", "rd_d16",
         "ld8", "sq8", "m8", "kf", "pay", "t4g", "frac")


def auc_of(vals, labels):
    pos = sorted(v for v, l in zip(vals, labels) if l)
    neg = sorted(v for v, l in zip(vals, labels) if not l)
    if not pos or not neg:
        return 0.5
    s = 0.0
    for v in pos:
        lo = bisect.bisect_left(neg, v)
        hi = bisect.bisect_right(neg, v)
        s += (lo + hi) / 2
    a = s / (len(pos) * len(neg))
    return max(a, 1 - a)


def main():
    try:
        ps = pickle.load(open("h625_rows.pkl", "rb"))
        print(f"cached band rows: {len(ps)}")
    except FileNotFoundError:
        rows = []
        locked = json.load(open("h616_locked.json"))
        st6 = {md: open(f"h616_{md}_status.txt").read()
               .splitlines() for md in ROUNDING_MODES}
        for i, rec in enumerate(locked):
            hw = [int(st6[md][i].split()[2], 16)
                  for md in ROUNDING_MODES]
            rows.append((int(rec["m"], 16), hw))
        recs = json.load(open("h619_rows.json"))
        st9 = {md: open(f"h619_{md}_status.txt").read()
               .splitlines() for md in ROUNDING_MODES}
        for i, rec in enumerate(recs):
            t = [st9[md][i].split() for md in ROUNDING_MODES]
            if any(x[0] != "OK" for x in t):
                continue
            rows.append((int(rec["m"], 16),
                         [int(x[2], 16) for x in t]))
        with Pool(14, initializer=initp) as pool:
            ps = pool.map(prep, rows, chunksize=200)
        ps = [p for p in ps if p is not None]
        pickle.dump(ps, open("h625_rows.pkl", "wb"))
        print(f"band rows: {len(ps)}")
    # error indicator vs baseline
    data = []
    for key, half, lab, f in ps:
        base = 1 if f["frac"] >= 0.5 else 0
        data.append((key, half, lab, base, base != lab, f))
    nerr = sum(d[4] for d in data)
    print(f"baseline errors: {nerr}/{len(data)}")
    print("\ntie-correct AUC of features vs ERROR indicator:")
    for nm in FEATS:
        a = auc_of([d[5][nm] for d in data],
                   [d[4] for d in data])
        print(f"  {nm:7s}: {a:.3f}")
    # flip mining: per (stratum-side-group, feature) single
    # threshold region on train; accept only if train
    # improvement is significant; score held-out
    tr = [d for d in data if d[1] == 0]
    te = [d for d in data if d[1] == 1]
    base_te = sum(1 for d in te if not d[4]) / len(te)
    print(f"\nheld-out baseline: {base_te:.4f} (n={len(te)})")
    results = []
    for nm in FEATS:
        if nm == "frac":
            continue
        # per stratum-side: flip when feature >= t (or < t)
        rules = {}
        bykey = defaultdict(list)
        for key, half, lab, base, err, f in tr:
            bykey[key].append((f[nm], err))
        for key, pts in bykey.items():
            vals = sorted(set(v for v, e in pts))
            if len(vals) < 2:
                continue
            best = (0, None)
            for t0 in vals:
                for sense in (0, 1):
                    # flip region: v >= t0 (sense 0) / v < t0
                    gain = 0
                    for v, e in pts:
                        inr = v >= t0 if sense == 0 else v < t0
                        if inr:
                            gain += 1 if e else -1
                    if gain > best[0]:
                        best = (gain, (t0, sense))
            if best[0] >= 8:  # significance floor on train
                rules[key] = best[1]
        ok = 0
        for key, half, lab, base, err, f in te:
            r = rules.get(key)
            pred = base
            if r is not None:
                t0, sense = r
                inr = f[nm] >= t0 if sense == 0 else f[nm] < t0
                if inr:
                    pred = 1 - base
            ok += pred == lab
        results.append((ok / len(te), nm, len(rules)))
    results.sort(reverse=True)
    print("\nflip-rule held-out (per-stratum single "
          "threshold):")
    for acc, nm, nr in results:
        print(f"  {nm:7s}: {acc:.4f} ({nr} strata rules)  "
              f"{'+' if acc > base_te else '-'}")


if __name__ == "__main__":
    main()
