#!/usr/bin/env python3
"""h488b: score FSINCOS cos-lane vs known FCOS outcomes."""
import json
from collections import Counter
MODES = ("rn", "rd", "ru")
locked = json.load(open("h488_locked.json"))["inputs"]
st = {m: open(f"sincos_{m}_status.txt").read().splitlines()
      for m in MODES}
tab = Counter()
flips = []
for i, e in enumerate(locked):
    cos = []
    bad = False
    for m in MODES:
        t = st[m][i].split()
        if t[0] != "OK":
            bad = True
            break
        cos.append(f"{int(t[4],16):016x}")
    if bad:
        tab[("BAD", e["fcos"])] += 1
        continue
    if cos == e["clean"]:
        sc = 0
    elif cos == e["fired"]:
        sc = 1
    else:
        sc = 2
    tab[(sc, e["fcos"])] += 1
    if sc != e["fcos"] and sc != 2:
        flips.append((e["m"], e["fcos"], sc))
print("rows (sincos_outcome, fcos_outcome):")
for k in sorted(tab, key=str):
    print(f"  {k}: {tab[k]}")
n_match = tab[(0, 0)] + tab[(1, 1)]
print(f"\nidentical fire-ness: {n_match}; flips clean->fire: "
      f"{tab[(1, 0)]}, fire->clean: {tab[(0, 1)]}; OTHER: "
      f"{tab[(2, 0)] + tab[(2, 1)]}")
for m, a, b in flips[:12]:
    print(f"  flip {m}: fcos={a} sincos={b}")
