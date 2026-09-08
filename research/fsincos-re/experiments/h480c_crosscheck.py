#!/usr/bin/env python3
"""h480c: cross-run consistency of repeated inputs (h479 vs h480)."""
import json
MODES = ("rn", "rd", "ru")
l479 = json.load(open("h479_locked.json"))
l480 = json.load(open("h480_locked.json"))
order479 = []
for p in l479["pairs"]:
    order479.append(p["g0"]); order479.append(p["g1"])
order479.extend(l479["controls"])
s479 = {m: open(f"h479_cos_{m}_status.txt").read().splitlines() for m in MODES}
s480 = {m: open(f"cos_{m}_status.txt").read().splitlines() for m in MODES}
def sig(tokline):
    t = tokline.split(); return f"{int(t[2],16):016x}" if t[0]=="OK" else "BAD"
res479 = {}
for i, e in enumerate(order479):
    res479[e["m"]] = tuple(sig(s479[m][i]) for m in MODES)
res480 = {}
for i, e in enumerate(l480["inputs"]):
    res480[e["m"]] = tuple(sig(s480[m][i]) for m in MODES)
common = set(res479) & set(res480)
diff = [m for m in common if res479[m] != res480[m]]
print(f"h479 inputs: {len(res479)}, h480 inputs: {len(res480)}, "
      f"common: {len(common)}, DIFFERING: {len(diff)}")
for m in diff[:10]:
    print(f"  {m}: h479={res479[m]} h480={res480[m]}")
# cell (8,4,8,1) population comparison
by480 = {e["m"]: e for e in l480["inputs"]}
cellms_480 = [e["m"] for e in l480["inputs"] if e["cell"] == [8,4,8,1]]
cellms_479 = [e["m"] for p in l479["pairs"] if p["cell"] == [8,4,8,1]
              for e in (p["g0"], p["g1"])]
overlap = set(cellms_479) & set(cellms_480)
print(f"cell (8,4,8,1): h479 inputs {len(cellms_479)}, "
      f"h480 inputs {len(cellms_480)}, overlap {len(overlap)}")
