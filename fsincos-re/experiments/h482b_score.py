#!/usr/bin/env python3
"""h482b: score the residual-input hunt.

Per-variable McNemar (v0 vs v1 within (cell, f4_g, f4_b2) strata),
controls check, and the key diagnostic: among captured inputs, group
by the FULL measured feature vector (cell + all 7 feature bits) and
count groups containing both outcomes — each is direct evidence of a
still-unmeasured input.  Writes h482_outcomes.tsv.
Run from /tmp/stageA.
"""
import json
from collections import Counter, defaultdict
from math import sqrt

MODES = ("rn", "rd", "ru")
locked = json.load(open("h482_locked.json"))
inputs = locked["inputs"]
n = len(inputs)
status = {m: open(f"cos_{m}_status.txt").read().splitlines()
          for m in MODES}
for mode in MODES:
    assert len(status[mode]) == n, (mode, len(status[mode]), n)

outcome = {}
for i, e in enumerate(inputs):
    hw = []
    ok = True
    for mode in MODES:
        t = status[mode][i].split()
        if t[0] != "OK":
            ok = False
            break
        hw.append(f"{int(t[2], 16):016x}")
    if not ok:
        outcome[e["m"]] = "BADSTATUS"
    elif hw == e["clean"]:
        outcome[e["m"]] = "CLEAN"
    elif hw == e["fired"]:
        outcome[e["m"]] = "FIRE"
    else:
        outcome[e["m"]] = "OTHER"
print(f"inputs: {n}, outcomes: {dict(Counter(outcome.values()))}")
print(f"controls (locked 0 fires): "
      f"{Counter(outcome[m] for m in locked['controls'])}")

print("\n=== per-variable McNemar (strata: cell, f4_g, f4_b2) ===")
for v in locked["vars"]:
    pairs = locked["var_pairs"][v]
    tab = Counter()
    for p in pairs:
        tab[(outcome[p["v0"]], outcome[p["v1"]])] += 1
    d01 = tab[("CLEAN", "FIRE")]
    d10 = tab[("FIRE", "CLEAN")]
    nd = d01 + d10
    z = (d01 - d10) / sqrt(nd) if nd else 0.0
    print(f"  {v:10s} pairs={len(pairs):3d} both={tab[('FIRE','FIRE')]:3d} "
          f"neither={tab[('CLEAN','CLEAN')]:3d} 1-only={d01:3d} "
          f"0-only={d10:3d} z={z:+.2f}")

print("\n=== fully-matched discordance (evidence of hidden inputs) ===")
FEATS = ("f4_g", "f4_b2", "f4_b3", "rdisc_b14", "ldisc_top", "t2_g",
         "rf_b0")
groups = defaultdict(Counter)
for e in inputs:
    if e["payload"] in (0, 8):
        continue
    key = (tuple(e["cell"]), tuple(e["feats"][f] for f in FEATS))
    groups[key][outcome[e["m"]]] += 1
mixed = {k: c for k, c in groups.items()
         if c["CLEAN"] and c["FIRE"]}
tot_rows = sum(sum(c.values()) for c in groups.values())
mixed_rows = sum(sum(c.values()) for c in mixed.values())
print(f"  full-vector groups: {len(groups)}, mixed: {len(mixed)}, "
      f"rows in mixed: {mixed_rows}/{tot_rows}")
for k, c in sorted(mixed.items())[:12]:
    print(f"    cell={k[0]} feats={k[1]}: {dict(c)}")

names = sorted(inputs[0]["feats"])
with open("h482_outcomes.tsv", "w") as fh:
    fh.write("m\tdist\tlow3\tk\trud\tpayload\toutcome\t"
             + "\t".join(names) + "\n")
    for e in inputs:
        fh.write(e["m"] + "\t"
                 + "\t".join(str(x) for x in e["cell"])
                 + f"\t{e['payload']}\t{outcome[e['m']]}\t"
                 + "\t".join(str(e["feats"][nm]) for nm in names)
                 + "\n")
print("wrote h482_outcomes.tsv")
