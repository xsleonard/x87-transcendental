#!/usr/bin/env python3
"""h472: rebuild the frame around the subtractor difference and push
the mid band down.

h471 found the cleaner variable: diff = (rs - payload) mod 16 (fires
live at diff in {0,+1}, echoing the lane-collision zone at nibble
granularity), and rdisc's top bits as the first refinements.  This
pass: FRAME2 = (theta, diff4, rud, dist), greedy over a wider pool
(all rdisc/ldisc top bits, payload, low3, lane bits, u5d/ud bits, rs
bits 4..15, ls low bits, and the byte-level diff (rs-pay) mod 256 in
buckets), recursive-backoff smoothing, held-out throughout.  Then a
drill-down: the largest remaining mid-band keys, printed with counts
and rates, to name what still separates them.

Run from /tmp/stageA (expects h464_package/combined_labels.tsv).
"""
import math
from collections import defaultdict

from h471_frame_refine import load, build_tables, predict

FRAME2 = [
    ("theta", lambda r: r["theta"]),
    ("diff4", lambda r: (r["rs_low16"] - r["payload"]) & 0xF),
    ("rud", lambda r: r["rud"]),
    ("dist", lambda r: r["dist"]),
]
POOL = (
    [(f"rd_b{b}", (lambda b: lambda r: (r["rdisc_hi8"] >> b) & 1)(b))
     for b in range(8)]
    + [(f"ld_b{b}", (lambda b: lambda r: (r["ldisc_hi8"] >> b) & 1)(b))
       for b in range(8)]
    + [("payload", lambda r: r["payload"]),
       ("low3", lambda r: r["low3"]),
       ("diff8_hi", lambda r: ((r["rs_low16"] - r["payload"]) & 0xFF) >> 4)]
    + [(f"lane_b{b}", (lambda b: lambda r: (r["lane"] >> b) & 1)(b))
       for b in range(8)]
    + [(f"u5d_b{b}", (lambda b: lambda r: (r["u5d"] >> b) & 1)(b))
       for b in range(5)]
    + [(f"ud_b{b}", (lambda b: lambda r: (r["ud"] >> b) & 1)(b))
       for b in range(3)]
    + [(f"rs_b{b}", (lambda b: lambda r: (r["rs_low16"] >> b) & 1)(b))
       for b in range(4, 16)]
    + [(f"ls_b{b}", (lambda b: lambda r: (r["ls_low8"] >> b) & 1)(b))
       for b in range(6)]
)


def logloss(tables, feats, rows):
    return sum(-math.log(predict(tables, feats, r)) if r["fire_pre"]
               else -math.log(1 - predict(tables, feats, r))
               for r in rows) / len(rows)


def main():
    rows = load()
    train = [r for r in rows if hash((r["se"], r["sig"])) & 1 == 0]
    test = [r for r in rows if hash((r["se"], r["sig"])) & 1 == 1]
    print(f"train {len(train)}, test {len(test)}")

    feats = list(FRAME2)
    tables = build_tables(train, feats)
    current = logloss(tables, feats, test)
    print(f"FRAME2 baseline held-out logloss: {current:.4f}")
    remaining = list(POOL)
    while True:
        best = None
        for cand in remaining:
            trial = feats + [cand]
            tt = build_tables(train, trial)
            ll = logloss(tt, trial, test)
            if best is None or ll < best[0]:
                best = (ll, cand)
        if best is None or best[0] >= current - 5e-4:
            break
        current, cand = best
        feats.append(cand)
        remaining.remove(cand)
        print(f"  + {cand[0]:9s} -> held-out logloss {current:.4f}")

    tables = build_tables(train, feats)
    bands = defaultdict(lambda: [0, 0])
    mid_keys = defaultdict(lambda: [0, 0])
    for r in test:
        p = predict(tables, feats, r)
        band = ("<0.02" if p < 0.02 else (">0.9" if p > 0.9 else "mid"))
        bands[band][r["fire_pre"]] += 1
        if band == "mid":
            key = tuple(f(r) for _, f in feats[:6])
            mid_keys[key][r["fire_pre"]] += 1
    print("determinism profile (held-out):")
    for band in ("<0.02", "mid", ">0.9"):
        n0, n1 = bands[band]
        n = n0 + n1
        print(f"  {band:5s}: {n:6d} rows ({n / len(test):.2%}), "
              f"actual fire rate {n1 / max(n, 1):.4f}")
    names = [n for n, _ in feats[:6]]
    print(f"\nlargest mid-band keys ({names}):")
    ranked = sorted(mid_keys.items(), key=lambda kv: -sum(kv[1]))
    for key, (n0, n1) in ranked[:12]:
        print(f"  {key}: {n1}/{n0 + n1} ({n1 / (n0 + n1):.3f})")


if __name__ == "__main__":
    main()
