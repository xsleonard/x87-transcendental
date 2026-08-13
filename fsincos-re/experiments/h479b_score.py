#!/usr/bin/env python3
"""h479b: score the constructed-pair captures against the locked
predictions.

Reads h479_locked.json (written BEFORE capture) and the three
cos_{mode}_status.txt files fetched from the i7.  Per input, hardware
is classified as CLEAN (matches the model's R tuple), FIRE (matches
R-1), or OTHER (anything else -- must be ~0 or the construction is
broken).  Then:
  - controls (payload 0/8): fire count (locked prediction: 0);
  - per-pair contingency: (g0 outcome, g1 outcome);
  - McNemar on discordant pairs: H-causal predicts one-sided
    (g1 fires, g0 clean); H-proxy predicts ~even split;
  - per-cell breakdown.
Run from /tmp/stageA with the status files alongside.
"""
import json
from collections import Counter, defaultdict

ROUNDING_MODES = ("rn", "rd", "ru")

locked = json.load(open("h479_locked.json"))
status = {}
for mode in ROUNDING_MODES:
    lines = open(f"cos_{mode}_status.txt").read().splitlines()
    status[mode] = lines

order = []
for p in locked["pairs"]:
    order.append(p["g0"])
    order.append(p["g1"])
order.extend(locked["controls"])
n = len(order)
for mode in ROUNDING_MODES:
    assert len(status[mode]) == n, (mode, len(status[mode]), n)


def classify(i, entry):
    hw = []
    for mode in ROUNDING_MODES:
        tok = status[mode][i].split()
        if tok[0] != "OK":
            return "BADSTATUS"
        hw.append(f"{int(tok[2], 16):016x}")
    if hw == entry["clean"]:
        return "CLEAN"
    if hw == entry["fired"]:
        return "FIRE"
    return "OTHER"


out = [classify(i, e) for i, e in enumerate(order)]
counts = Counter(out)
print(f"inputs: {n}, outcomes: {dict(counts)}")

nc = len(locked["controls"])
ctrl = out[2 * len(locked["pairs"]):]
print(f"controls (payload 0/8, locked prediction 0 fires): "
      f"{Counter(ctrl)}")

table = Counter()
percell = defaultdict(Counter)
for pi, p in enumerate(locked["pairs"]):
    o0, o1 = out[2 * pi], out[2 * pi + 1]
    table[(o0, o1)] += 1
    percell[tuple(p["cell"])][(o0, o1)] += 1

print("\n=== pair contingency (g0 outcome, g1 outcome) ===")
for key in sorted(table):
    print(f"  {key}: {table[key]}")

d01 = table[("CLEAN", "FIRE")]           # g1 fired, g0 not (H-causal)
d10 = table[("FIRE", "CLEAN")]           # reverse
both = table[("FIRE", "FIRE")]
neither = table[("CLEAN", "CLEAN")]
nd = d01 + d10
print(f"\nconcordant: both-fire {both}, neither {neither}")
print(f"discordant: g1-only {d01}, g0-only {d10}")
if nd:
    from math import sqrt
    z = (d01 - d10) / sqrt(nd)
    print(f"McNemar z = {z:+.2f}  "
          f"(H-causal: strongly positive; H-proxy: |z| small)")
    print(f"strict rule check (fire <=> f4_g): violations = "
          f"{d10 + both + neither - neither} ... "
          f"non-conforming pairs = {d10 + both} + missed {neither}")

print("\n=== per-cell (dist, low3, k, rud) ===")
for cell in sorted(percell):
    c = percell[cell]
    print(f"  {cell}: " + " ".join(f"{k}:{v}" for k, v in
                                   sorted(c.items())))
