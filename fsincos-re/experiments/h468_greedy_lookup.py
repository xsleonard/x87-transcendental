#!/usr/bin/env python3
"""h468: held-out greedy lookup over the discovered gate inputs.

h466/h467 established the first replicated gate-input signals: the
right product's discarded top byte (direction-antisymmetric, z=+21/-16)
and, weaker, the left product's near-zero discarded band and p4_g.
The response is soft, so instead of hard rules this builds a
probability-lookup classifier by greedy forward selection: starting
from (theta), repeatedly add the feature whose bucketed conditioning
most improves HELD-OUT balanced log-loss; stop when no feature helps.
The end state answers: how much of the borrow bit do the discovered
inputs carry, and does the residual per-cell fire rate approach 0/1
(deterministic basis nearly found) or plateau strictly inside (0,1)
(inputs still missing)?

Features offered (all discrete/bucketed):
  theta, dist, low3, payload, ud, u5d, rud, lane>>4,
  rdisc_hi8>>4, ldisc_hi8>>4, rs_low16 low nibbles, ls_low8>>4

Train/test split by input hash (same convention as h458/h467).
Run from /tmp/stageA (expects h464_package/labels.tsv).
"""
import math
from collections import defaultdict

PKG = "h464_package"

FEATURES = {
    "theta": lambda r: r["theta"],
    "dist": lambda r: r["dist"],
    "low3": lambda r: r["low3"],
    "payload": lambda r: r["payload"],
    "ud": lambda r: r["ud"],
    "u5d": lambda r: r["u5d"] >> 2,
    "rud": lambda r: r["rud"],
    "lane_hi4": lambda r: r["lane"] >> 4,
    "rdisc_hi4": lambda r: r["rdisc_hi8"] >> 4,
    "ldisc_hi4": lambda r: r["ldisc_hi8"] >> 4,
    "rs_nib0": lambda r: r["rs_low16"] & 0xF,
    "rs_nib1": lambda r: (r["rs_low16"] >> 4) & 0xF,
    "ls_hi4": lambda r: r["ls_low8"] >> 4,
}


def logloss(train, test, feats):
    table = defaultdict(lambda: [0, 0])
    for r in train:
        key = tuple(FEATURES[f](r) for f in feats)
        table[key][r["fire_pre"]] += 1
    total_f = sum(r["fire_pre"] for r in train)
    prior = total_f / len(train)
    loss = 0.0
    for r in test:
        key = tuple(FEATURES[f](r) for f in feats)
        n0, n1 = table.get(key, [0, 0])
        # Laplace-smoothed toward the prior
        p = (n1 + 5 * prior) / (n0 + n1 + 5)
        p = min(max(p, 1e-6), 1 - 1e-6)
        loss -= (math.log(p) if r["fire_pre"] else math.log(1 - p))
    return loss / len(test)


def main():
    rows = []
    with open(f"{PKG}/labels.tsv") as fh:
        header = fh.readline().rstrip("\n").split("\t")
        for line in fh:
            r = dict(zip(header, line.rstrip("\n").split("\t")))
            for k in ("theta", "fire_pre", "dist", "low3", "payload",
                      "ud", "u5d", "rud", "lane", "rs_low16", "ls_low8",
                      "ldisc_hi8", "rdisc_hi8"):
                r[k] = int(r[k])
            rows.append(r)
    train = [r for r in rows if hash((r["se"], r["sig"])) & 1 == 0]
    test = [r for r in rows if hash((r["se"], r["sig"])) & 1 == 1]
    prior = sum(r["fire_pre"] for r in test) / len(test)
    base = -(prior * math.log(prior) + (1 - prior) * math.log(1 - prior))
    print(f"train {len(train)}, test {len(test)}, "
          f"test prior {prior:.4f}, entropy {base:.4f}")

    chosen = []
    current = logloss(train, test, chosen) if chosen else base
    while True:
        best = None
        for f in FEATURES:
            if f in chosen:
                continue
            ll = logloss(train, test, chosen + [f])
            if best is None or ll < best[0]:
                best = (ll, f)
        if best is None or best[0] >= current - 1e-4:
            break
        current, f = best
        chosen.append(f)
        print(f"  + {f:10s} -> held-out logloss {current:.4f}")
    print(f"selected: {chosen}")

    # residual determinism check: held-out fire rate in the most
    # confident predicted buckets
    table = defaultdict(lambda: [0, 0])
    for r in train:
        key = tuple(FEATURES[f](r) for f in chosen)
        table[key][r["fire_pre"]] += 1
    buckets = defaultdict(lambda: [0, 0])
    for r in test:
        key = tuple(FEATURES[f](r) for f in chosen)
        n0, n1 = table.get(key, [0, 0])
        p = (n1 + 1) / (n0 + n1 + 2)
        band = min(int(p * 10), 9)
        buckets[band][r["fire_pre"]] += 1
    print("\npredicted-p band -> held-out actual fire rate")
    for band in sorted(buckets):
        n0, n1 = buckets[band]
        print(f"  p~{band / 10:.1f}-{band / 10 + 0.1:.1f}: "
              f"{n1:5d}/{n0 + n1:6d} ({n1 / (n0 + n1):.3f})")


if __name__ == "__main__":
    main()
