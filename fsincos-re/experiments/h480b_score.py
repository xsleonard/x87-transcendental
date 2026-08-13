#!/usr/bin/env python3
"""h480b: score the second-variable readout against locked predictions.

Reads h480_locked.json + cos_{mode}_status.txt (i7).  Per input:
CLEAN (matches R tuple), FIRE (matches R-1), OTHER (must be 0).
Reports:
  - controls (payload 0/8): fire count, locked prediction 0;
  - f4_g replication McNemar on the density pairs;
  - per-variable McNemar within (cell, f4_g) strata (v=1 side minus
    v=0 side over discordant pairs);
  - per-cell f4_g table merged with h479's (fresh pairs only here);
  - h480_outcomes.tsv (m, cell, payload, outcome, all features) for
    post-hoc conditional analysis.
Run from /tmp/stageA.
"""
import json
from collections import Counter, defaultdict
from math import sqrt

ROUNDING_MODES = ("rn", "rd", "ru")

locked = json.load(open("h480_locked.json"))
inputs = locked["inputs"]
n = len(inputs)
status = {m: open(f"cos_{m}_status.txt").read().splitlines()
          for m in ROUNDING_MODES}
for mode in ROUNDING_MODES:
    assert len(status[mode]) == n, (mode, len(status[mode]), n)

outcome = {}
for i, e in enumerate(inputs):
    hw = []
    bad = False
    for mode in ROUNDING_MODES:
        tok = status[mode][i].split()
        if tok[0] != "OK":
            bad = True
            break
        hw.append(f"{int(tok[2], 16):016x}")
    if bad:
        outcome[e["m"]] = "BADSTATUS"
    elif hw == e["clean"]:
        outcome[e["m"]] = "CLEAN"
    elif hw == e["fired"]:
        outcome[e["m"]] = "FIRE"
    else:
        outcome[e["m"]] = "OTHER"

print(f"inputs: {n}, outcomes: {dict(Counter(outcome.values()))}")
ctrl = [outcome[m] for m in locked["controls"]]
print(f"controls (locked: 0 fires): {Counter(ctrl)}")

def mcnemar(pairs, k0, k1, label):
    tab = Counter()
    for p in pairs:
        tab[(outcome[p[k0]], outcome[p[k1]])] += 1
    d01 = tab[("CLEAN", "FIRE")]
    d10 = tab[("FIRE", "CLEAN")]
    both = tab[("FIRE", "FIRE")]
    neither = tab[("CLEAN", "CLEAN")]
    nd = d01 + d10
    z = (d01 - d10) / sqrt(nd) if nd else 0.0
    print(f"  {label:12s} pairs={len(pairs):3d}  both={both:3d} "
          f"neither={neither:3d}  1-only={d01:3d} 0-only={d10:3d}  "
          f"z={z:+.2f}")
    return z

print("\n=== f4_g replication (density pairs) ===")
mcnemar(locked["f4g_pairs"], "g0", "g1", "f4_g")

print("\n=== per-variable McNemar within (cell, f4_g) strata ===")
for v in locked["vars"]:
    mcnemar(locked["var_pairs"][v], "v0", "v1", v)

print("\n=== per-variable, split by f4_g stratum ===")
for v in locked["vars"]:
    for g in (0, 1):
        sub = [p for p in locked["var_pairs"][v]
               if p["stratum"][1] == g]
        if sub:
            mcnemar(sub, "v0", "v1", f"{v}|f4_g={g}")

print("\n=== f4_g density pairs per cell ===")
percell = defaultdict(Counter)
for p in locked["f4g_pairs"]:
    percell[tuple(p["cell"])][(outcome[p["g0"]],
                               outcome[p["g1"]])] += 1
for cell in sorted(percell):
    c = percell[cell]
    print(f"  {cell}: " + " ".join(f"{k}:{v}" for k, v in
                                   sorted(c.items())))

names = sorted(inputs[0]["feats"])
with open("h480_outcomes.tsv", "w") as fh:
    fh.write("m\tdist\tlow3\tk\trud\tpayload\toutcome\t"
             + "\t".join(names) + "\n")
    for e in inputs:
        fh.write(e["m"] + "\t"
                 + "\t".join(str(x) for x in e["cell"])
                 + f"\t{e['payload']}\t{outcome[e['m']]}\t"
                 + "\t".join(str(e["feats"][nm]) for nm in names)
                 + "\n")
print("\nwrote h480_outcomes.tsv")
