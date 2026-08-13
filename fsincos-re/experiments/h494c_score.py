#!/usr/bin/env python3
"""h494c: score fresh captures against locked predictions."""
import json
from collections import defaultdict, Counter
MODES = ("rn", "rd", "ru")
preds = json.load(open("h494_pred.json"))
st = {m: open(f"vcos_{m}_status.txt").read().splitlines()
      for m in MODES}
per = defaultdict(lambda: [0, 0, 0])   # n, exceptions, other
for i, e in enumerate(preds):
    hw = []
    bad = False
    for m in MODES:
        t = st[m][i].split()
        if t[0] != "OK":
            bad = True
            break
        hw.append(f"{int(t[2],16):016x}")
    s = per[e["s"]]
    s[0] += 1
    if bad or (hw != e["clean"] and hw != e["fired"]):
        s[2] += 1
        continue
    actual = 1 if hw == e["fired"] else 0
    if actual != e["pred"]:
        s[1] += 1
tot = exc = oth = 0
exact = near = broken = 0
print(f"{'stratum':18s} {'n':>6s} {'exceptions':>10s} {'other':>6s}")
for k in sorted(per):
    n, e, o = per[k]
    tot += n
    exc += e
    oth += o
    verdict = "EXACT" if e == 0 else \
        ("near" if e <= max(1, n // 100) else "BROKEN")
    if e == 0:
        exact += 1
    elif e <= max(1, n // 100):
        near += 1
    else:
        broken += 1
    print(f"{k:18s} {n:6d} {e:10d} {o:6d}  {verdict}")
print(f"\nTOTAL {tot} fresh rows in claimed strata: "
      f"{exc} exceptions, {oth} other")
print(f"strata verdicts: EXACT {exact}, near {near}, broken {broken}")
