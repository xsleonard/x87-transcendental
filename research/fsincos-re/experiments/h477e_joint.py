#!/usr/bin/env python3
"""h477e: joint contingency + proper holdout on the tie-stratum signals.

h477d found (paired, replicated): f4_g z~+100, R_low8 z~-75 with a
clean necessary condition R mod 8 in {0,1}, rdisc16 z~+36, p1_g z~-22.
This script reads h477d_ties_features.tsv and:
  1. prints the direct joint contingency of fire against small
     conjunctions of the flagged features;
  2. tests candidate exact rules (necessary/sufficient sides
     separately) with a RANDOM-within-cell holdout split;
  3. prints the best conjunction's confusion on both halves.

Run from /tmp/stageA.
"""
import random
from collections import defaultdict

rows = []
with open("h477d_ties_features.tsv") as fh:
    header = fh.readline().rstrip("\n").split("\t")
    for line in fh:
        vals = line.rstrip("\n").split("\t")
        rows.append({h: int(v) for h, v in zip(header, vals)})
print(f"rows: {len(rows)}, fires: {sum(r['fire'] for r in rows)}")

rnd = random.Random(477)
for r in rows:
    r["half"] = rnd.random() < 0.5


def rate_table(name, fn):
    buckets = defaultdict(lambda: [0, 0])
    for r in rows:
        v = fn(r)
        if v is None:
            continue
        b = buckets[v]
        b[0] += 1
        b[1] += r["fire"]
    print(f"\n--- fire rate by {name} ---")
    for v in sorted(buckets):
        tot, f = buckets[v]
        if tot >= 8:
            print(f"  {v}: n={tot:5d} fires={f:5d} rate={f/tot:.3f}")


rate_table("f4_g", lambda r: r["f4_g"] if r["f4_g"] >= 0 else None)
rate_table("(f4_g, R_low3<2)",
           lambda r: (r["f4_g"], 1 if r["R_low8"] & 6 == 0 else 0)
           if r["f4_g"] >= 0 else None)
rate_table("(f4_g, R_low3<2, p1_g)",
           lambda r: (r["f4_g"], 1 if r["R_low8"] & 6 == 0 else 0,
                      r["p1_g"]) if r["f4_g"] >= 0 else None)
rate_table("(f4_g, R_low3<2, rud)",
           lambda r: (r["f4_g"], 1 if r["R_low8"] & 6 == 0 else 0,
                      r["rud"]) if r["f4_g"] >= 0 else None)
rate_table("(f4_g, R_low3<2, prepay0or8)",
           lambda r: (r["f4_g"], 1 if r["R_low8"] & 6 == 0 else 0,
                      1 if (r["low3"] + 8 - r["dist"]) in (0, 8) else 0)
           if r["f4_g"] >= 0 else None)

# rdisc16 banding within the promising cell
sub = [r for r in rows if r["f4_g"] == 1 and r["R_low8"] & 6 == 0]
print(f"\nsubset f4_g=1 & R_low3<2: n={len(sub)}, "
      f"fires={sum(r['fire'] for r in sub)} "
      f"rate={sum(r['fire'] for r in sub)/len(sub):.3f}")
buckets = defaultdict(lambda: [0, 0])
for r in sub:
    b = buckets[r["rdisc16"] >> 12]
    b[0] += 1
    b[1] += r["fire"]
print("--- subset fire rate by rdisc16 top nibble ---")
for v in sorted(buckets):
    tot, f = buckets[v]
    print(f"  {v:2d}: n={tot:5d} fires={f:5d} rate={f/tot:.3f}")

# necessary-condition audit: which single conditions hold for ALL fires
fires = [r for r in rows if r["fire"]]
cools = [r for r in rows if not r["fire"]]
print(f"\n=== necessary-condition audit (all {len(fires)} fires) ===")
conds = {
    "f4_g==1": lambda r: r["f4_g"] == 1,
    "p1_g==0": lambda r: r["p1_g"] == 0,
    "R_low3 in {0,1}": lambda r: r["R_low8"] & 6 == 0,
    "R_trail1<2": lambda r: r["R_trail1"] < 2,
    "rud==1": lambda r: r["rud"] == 1,
    "rdisc16>=0x8000": lambda r: r["rdisc16"] >= 0x8000,
    "prepay not in {0,8}": lambda r: (r["low3"] + 8 - r["dist"])
    not in (0, 8),
}
for name, fn in conds.items():
    nf = sum(1 for r in fires if fn(r))
    nc = sum(1 for r in cools if fn(r))
    print(f"  {name:22s} holds for {nf}/{len(fires)} fires, "
          f"{nc}/{len(cools)} cools")

# best conjunction of necessary conditions -> confusion by half
print("\n=== conjunction confusion (random halves) ===")


def conj(r):
    return (r["f4_g"] == 1 and r["p1_g"] == 0 and r["R_low8"] & 6 == 0
            and (r["low3"] + 8 - r["dist"]) not in (0, 8))


for half in (False, True):
    tp = fp = fn_ = tn = 0
    for r in rows:
        if r["half"] != half:
            continue
        pred = conj(r)
        if pred and r["fire"]:
            tp += 1
        elif pred:
            fp += 1
        elif r["fire"]:
            fn_ += 1
        else:
            tn += 1
    print(f"  half{int(half)}: pred-fire correct {tp}, spurious {fp}, "
          f"missed {fn_}, clean {tn}")
