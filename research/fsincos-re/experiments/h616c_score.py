#!/usr/bin/env python3
"""h616c: score the h616 FSIN captures against the locked
off/on predictions.  THE cross-schedule verdict: on
disagreement rows, does FSIN hardware follow the FCOS rule
(on) or the chop model (off)?  Controls must match both."""
import json
from collections import defaultdict
from h437_gate_extraction import ROUNDING_MODES

locked = json.load(open("h616_locked.json"))
st = {md: open(f"h616_{md}_status.txt").read().splitlines()
      for md in ROUNDING_MODES}
tot = defaultdict(lambda: [0, 0, 0, 0])  # dis: [on, off, other, n]
per_key = defaultdict(lambda: [0, 0, 0, 0])
badstat = 0
for i, rec in enumerate(locked):
    hw = []
    ok = True
    for md in ROUNDING_MODES:
        t = st[md][i].split()
        if t[0] != "OK":
            ok = False
            break
        hw.append(f"{int(t[2], 16):x}")
    if not ok:
        badstat += 1
        continue
    dis = rec["dis"]
    row = tot[dis]
    row[3] += 1
    if hw == rec["on"]:
        row[0] += 1
        cat = 0
    elif hw == rec["off"]:
        row[1] += 1
        cat = 1
    else:
        row[2] += 1
        cat = 2
    if dis:
        pk = per_key[tuple(rec["key"])]
        pk[3] += 1
        pk[cat] += 1
print(f"badstat {badstat}")
for dis in (1, 0):
    on, off, oth, n = tot[dis]
    name = "DISAGREEMENT" if dis else "CONTROL (on==off pred?)"
    print(f"{name}: n={n} hw==rule(on) {on} hw==chop(off) "
          f"{off} OTHER {oth}")
print("\nper stratum-side (disagreement rows): "
      "rule / chop / other / n")
for k in sorted(per_key, key=str):
    on, off, oth, n = per_key[k]
    print(f"  {k}: {on:5d} {off:5d} {oth:4d} {n:5d} "
          f"rule-rate {on / max(n, 1):.4f}")
